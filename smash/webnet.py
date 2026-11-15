"""
Online play for the browser/phone version: same host-authoritative game as net.py (LAN), but the packets
travel over WebRTC using PeerJS (free public matchmaking server, then phone <-> phone directly).

The host gets a 4-digit room code; friends type it in. The JavaScript half lives in web/smashnet.js and is
added to the web page by the GitHub build. Python talks to it through `platform.window.SmashNet`, passing
plain strings only.

On a PC (no browser) a LoopBridge stands in so the code can be tested with host + client in one process.
"""
import base64
import json
import random
import sys
import time
import zlib

from . import net

ROOM_DIGITS = 4


def encode(msg):
    msg["g"] = net.GAME_ID
    return base64.b64encode(zlib.compress(json.dumps(msg, separators=(",", ":")).encode("utf-8"), 3)).decode("ascii")


def decode(text):
    try:
        if text.startswith("{"):                 # bridge-made events like {"t":"_open"} are plain JSON
            msg = json.loads(text)
            msg["g"] = net.GAME_ID
            return msg
        return json.loads(zlib.decompress(base64.b64decode(text)).decode("utf-8"))
    except Exception:
        return None


# ------------------------------------------------------------------ bridges
class LoopBridge:
    """In-process stand-in for SmashNet (tests on a PC). All instances share one fake 'internet'."""
    rooms = {}          # code -> host bridge
    _n = 0

    def __init__(self):
        LoopBridge._n += 1
        self.id = "peer%d" % LoopBridge._n
        self.inbox = []
        self.state = "idle"
        self.links = {}     # peer id -> bridge
        self.code = None

    def host(self, code):
        if code in LoopBridge.rooms:
            self.state = "taken"
            return
        LoopBridge.rooms[code] = self
        self.code = code
        self.state = "ready"

    def join(self, code):
        h = LoopBridge.rooms.get(code)
        if h is None:
            self.state = "nohost"
            return
        self.links[h.id] = h
        h.links[self.id] = self
        h.inbox.append([self.id, '{"t":"_open"}'])
        self.state = "ready"

    def send(self, to, text):
        if not to:
            for b in self.links.values():
                b.inbox.append([self.id, text])
        elif to in self.links:
            self.links[to].inbox.append([self.id, text])

    def broadcast(self, text):
        for b in self.links.values():
            b.inbox.append([self.id, text])

    def poll(self):
        out = json.dumps(self.inbox)
        self.inbox = []
        return out

    def status(self):
        return self.state

    def error(self):
        return ""

    def close(self):
        for b in self.links.values():
            b.inbox.append([self.id, '{"t":"_close"}'])
            b.links.pop(self.id, None)
        self.links = {}
        if self.code and LoopBridge.rooms.get(self.code) is self:
            del LoopBridge.rooms[self.code]
        self.state = "idle"


def bridge():
    if sys.platform == "emscripten":
        import platform as _pf          # pygbag's platform module exposes the browser's window
        sn = getattr(_pf.window, "SmashNet", None)
        if sn is None:
            raise RuntimeError("online code missing from the page")
        return sn
    return LoopBridge()


def _inbox(b):
    try:
        items = json.loads(str(b.poll()))
    except Exception:
        return
    for frm, text in items:
        msg = decode(str(text))
        if isinstance(msg, dict):
            yield msg, str(frm)


# ------------------------------------------------------------------ host / client
class WebHost(net.Host):
    def __init__(self, name="Host"):
        self.name = name
        self.port = 0
        self.clients = {}
        self.events = []
        self.b = bridge()
        self.code = ""
        self.started = 0.0
        self._open_room()

    def _open_room(self):
        self.code = "".join(random.choice("0123456789") for _ in range(ROOM_DIGITS))
        self.started = time.time()
        self.b.host(self.code)

    @property
    def ip(self):          # the lobby screen shows host.ip -> show the room code instead
        return self.code

    @property
    def state(self):
        return str(self.b.status())

    def _recv(self):
        yield from _inbox(self.b)

    def _beacon(self, now):
        if self.state == "taken":          # someone else has this code: pick another
            self.b.close()
            self._open_room()

    def send(self, addr, msg):
        self.b.send(addr, encode(msg))

    def broadcast(self, msg):
        if self.clients:
            self.b.broadcast(encode(msg))

    def close(self):
        try:
            self.broadcast({"t": "closed"})
            self.b.close()
        except Exception:
            pass


class WebClient(net.Client):
    def __init__(self, code, name="Guest"):
        super().__init__("room " + code, name)
        self.b = bridge()
        self.code = code
        self.started = time.time()
        self.b.join(code)

    def _make_socket(self):
        return None

    def _recv(self):
        st = str(self.b.status())
        if st == "nohost":
            self.status = "nohost"
        elif st == "error" and self.status == "connecting":
            self.status = "lost"
        if st != "ready" and time.time() - self.started < 15:
            self.last_heard = time.time()           # still finding the room: don't time out yet
        yield from (m for m, _ in _inbox(self.b))

    def send(self, msg):
        self.b.send("", encode(msg))

    def close(self):
        try:
            self.send({"t": "bye"})
            self.b.close()
        except Exception:
            pass
