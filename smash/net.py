"""
LAN networking (UDP, host-authoritative). No pygame in here.

Host  : runs the real game. Receives each client's controller input every frame and sends back a snapshot
        of the whole game every frame. Also shouts a "beacon" on the LAN once a second so joiners can find it.
Client: sends its input, draws whatever snapshot arrives last.
On the same Wi-Fi the round trip is a few ms, so no prediction/rollback is needed.
"""
import json
import socket
import time
import zlib

from .config import NET_PORT, MAX_PLAYERS

BEACON_PORT_OFFSET = 1
CLIENT_TIMEOUT = 6.0
HOST_TIMEOUT = 8.0
GAME_ID = "chiikawa-smash-1"


def pack(msg):
    return zlib.compress(json.dumps(msg, separators=(",", ":")).encode("utf-8"), 3)


def unpack(data):
    try:
        return json.loads(zlib.decompress(data).decode("utf-8"))
    except Exception:
        return None


def local_ip():
    """Best guess of this PC's LAN address (what friends should type in)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is actually sent
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class Host:
    def __init__(self, name="Host", port=NET_PORT):
        self.name = name
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.setblocking(False)
        self.beacon = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.beacon.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.beacon.setblocking(False)
        self.last_beacon = 0.0
        self.clients = {}        # addr -> dict(slot, name, char, ready, seen, raw, seq)
        self.ip = local_ip()
        self.events = []         # ("join"/"leave", slot, name) for the UI

    def free_slot(self, taken):
        for s in range(MAX_PLAYERS):
            if s not in taken:
                return s
        return None

    # ---- transport (UDP here; the browser version swaps these out, see webnet.py)
    def _recv(self):
        """Yields (message dict, sender address) for everything waiting."""
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
            except (BlockingIOError, InterruptedError):
                break
            except ConnectionResetError:     # Windows reports ICMP 'port unreachable' this way
                continue
            except OSError:
                break
            msg = unpack(data)
            if isinstance(msg, dict) and msg.get("g") == GAME_ID:
                yield msg, addr

    def _beacon(self, now):
        if now - self.last_beacon > 1.0:
            self.last_beacon = now
            info = pack({"g": GAME_ID, "t": "beacon", "name": self.name, "port": self.port,
                         "players": len(self.clients)})
            for target in ("255.255.255.255", "<broadcast>"):
                try:
                    self.beacon.sendto(info, (target, self.port + BEACON_PORT_OFFSET))
                    break
                except OSError:
                    continue

    def poll(self, taken_slots):
        """Read everything waiting. taken_slots: slots used by local/CPU players."""
        now = time.time()
        for msg, addr in self._recv():
            t = msg.get("t")
            c = self.clients.get(addr)
            if t == "hello":
                if c is None:
                    used = set(taken_slots) | {cl["slot"] for cl in self.clients.values()}
                    slot = self.free_slot(used)
                    if slot is None:
                        self.send(addr, {"t": "full"})
                        continue
                    c = {"slot": slot, "name": str(msg.get("name", "Guest"))[:12], "char": msg.get("char", "chiikawa"),
                         "ready": False, "seen": now, "raw": None, "seq": -1}
                    self.clients[addr] = c
                    self.events.append(("join", slot, c["name"]))
                c["seen"] = now
                self.send(addr, {"t": "welcome", "slot": c["slot"], "host": self.name})
            elif c is None:
                continue
            elif t == "pick":
                c["seen"] = now
                c["char"] = msg.get("char", c["char"])
                c["ready"] = bool(msg.get("ready"))
            elif t == "in":
                c["seen"] = now
                seq = msg.get("q", 0)
                if seq > c["seq"]:
                    c["seq"] = seq
                    c["raw"] = msg.get("i")
            elif t == "ping":
                c["seen"] = now
            elif t in ("bye", "_close"):
                self.events.append(("leave", c["slot"], c["name"]))
                del self.clients[addr]
        for addr in list(self.clients):
            if now - self.clients[addr]["seen"] > CLIENT_TIMEOUT:
                c = self.clients.pop(addr)
                self.events.append(("leave", c["slot"], c["name"]))
        self._beacon(now)

    def inputs(self):
        return {c["slot"]: c["raw"] for c in self.clients.values() if c["raw"] is not None}

    def send(self, addr, msg):
        msg["g"] = GAME_ID
        try:
            self.sock.sendto(pack(msg), addr)
        except OSError:
            pass

    def broadcast(self, msg):
        msg["g"] = GAME_ID
        data = pack(msg)
        for addr in list(self.clients):
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass

    def close(self):
        self.broadcast({"t": "closed"})
        for s in (self.sock, self.beacon):
            try:
                s.close()
            except OSError:
                pass


class Client:
    def __init__(self, host_ip, name="Guest", port=NET_PORT):
        self.addr = (host_ip, port)
        self.name = name
        self.sock = self._make_socket()
        self.slot = None
        self.host_name = ""
        self.lobby = None        # latest lobby state from the host
        self.snap = None         # latest game snapshot
        self.snap_frame = -1
        self.last_heard = time.time()
        self.last_hello = 0.0
        self.last_pick = 0.0
        self.seq = 0
        self.status = "connecting"   # connecting / lobby / match / full / lost / closed
        self.char = "chiikawa"
        self.ready = False

    def send(self, msg):
        msg["g"] = GAME_ID
        try:
            self.sock.sendto(pack(msg), self.addr)
        except OSError:
            pass

    def _make_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        return sock

    def _recv(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(65536)
            except (BlockingIOError, InterruptedError):
                break
            except ConnectionResetError:
                continue
            except OSError:
                break
            msg = unpack(data)
            if isinstance(msg, dict) and msg.get("g") == GAME_ID:
                yield msg

    def poll(self):
        now = time.time()
        for msg in self._recv():
            self.last_heard = now
            t = msg.get("t")
            if t == "welcome":
                self.slot = msg["slot"]
                self.host_name = msg.get("host", "")
                if self.status == "connecting":
                    self.status = "lobby"
            elif t == "full":
                self.status = "full"
            elif t == "lobby":
                if self.lobby is None or msg.get("mid") != self.lobby.get("mid"):
                    self.snap, self.snap_frame = None, -1      # new match: forget the old one
                self.lobby = msg
                if self.slot is not None:
                    self.status = "match" if msg.get("phase") == "match" else "lobby"
            elif t == "snap":
                s = msg.get("s") or {}
                # only accept snapshots of the match the host says is current, and never older frames
                if self.lobby and s.get("mid") == self.lobby.get("mid") and s.get("fr", -1) >= self.snap_frame:
                    self.snap = s
                    self.snap_frame = s["fr"]
            elif t in ("closed", "_close"):
                self.status = "closed"
        if self.slot is None and now - self.last_hello > 0.5 and self.status == "connecting":
            self.last_hello = now
            self.send({"t": "hello", "name": self.name, "char": self.char})
        elif self.slot is not None and self.status == "lobby" and now - self.last_pick > 0.5:
            self.send_pick()
        if now - self.last_heard > HOST_TIMEOUT and self.status not in ("full", "closed", "nohost", "noroute"):
            self.status = "lost"

    def send_pick(self):
        self.last_pick = time.time()
        self.send({"t": "pick", "char": self.char, "ready": self.ready})

    def send_input(self, raw):
        self.seq += 1
        self.send({"t": "in", "q": self.seq, "i": raw})

    def close(self):
        self.send({"t": "bye"})
        try:
            self.sock.close()
        except OSError:
            pass


class Finder:
    """Listens for host beacons on the LAN (for the Join screen)."""
    def __init__(self, port=NET_PORT):
        self.hosts = {}   # ip -> (name, players, last_seen)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", port + BEACON_PORT_OFFSET))
            self.ok = True
        except OSError:
            self.ok = False
        self.sock.setblocking(False)

    def poll(self):
        now = time.time()
        while self.ok:
            try:
                data, addr = self.sock.recvfrom(4096)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            msg = unpack(data)
            if isinstance(msg, dict) and msg.get("g") == GAME_ID and msg.get("t") == "beacon":
                self.hosts[addr[0]] = (msg.get("name", "?"), msg.get("players", 0), now)
        for ip in list(self.hosts):
            if now - self.hosts[ip][2] > 4:
                del self.hosts[ip]
        return sorted(self.hosts.items())

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
