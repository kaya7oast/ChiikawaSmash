"""Window, scenes (title / character select / join / match / results) and the main loop."""
import asyncio
import json
import math
import sys
import time

import pygame

from . import characters
from .bot import Bot
from .config import (IS_WEB, TOUCH_UI)
from .config import (WIDTH, HEIGHT, FPS, TITLE, SAVE_FILE, SLOT_COLORS, CPU_COLOR, WHITE, BLACK, INK,
                     MAX_PLAYERS, DEFAULT_STOCKS, NET_PORT)
from .controls import DeviceManager, CONTROLS_HELP


def _net():
    """LAN code is only loaded when you actually host/join (browsers can't do UDP)."""
    from . import net
    return net


def make_host(name):
    if IS_WEB:
        from . import webnet
        return webnet.WebHost(name)
    return _net().Host(name)


def make_client(addr, name):
    if IS_WEB:
        from . import webnet
        return webnet.WebClient(addr, name)
    return _net().Client(addr, name)


def touch_overlay(app, devices):
    """Draw the on-screen controller if one of these devices is (or contains) the touch controls."""
    t = app.devices.touch
    for d in devices:
        if d is t or t in getattr(d, "subs", ()):
            t.draw(app.screen)
            return
from .render import Renderer, Background, Camera, text, font, damage_color
from .sim import Game, GAME_END_FRAMES
from .stages import STAGES, STAGE_ORDER

ROSTER = characters.ROSTER


def load_settings():
    d = {"name": "", "last_ip": "192.168.1.", "stocks": DEFAULT_STOCKS, "stage": 0, "cpu_level": 2}
    try:
        with open(SAVE_FILE) as fh:
            d.update(json.load(fh))
    except Exception:
        pass
    if not d["name"]:
        try:
            import platform
            d["name"] = (platform.node() or "Player")[:10] if not IS_WEB else "Player"
        except Exception:
            d["name"] = "Player"
    return d


def save_settings(d):
    try:
        with open(SAVE_FILE, "w") as fh:
            json.dump(d, fh, indent=1)
    except Exception:
        pass


def button(surf, rect, label, col=(255, 245, 250), size=22, txt=INK):
    """A big tappable button (touch UI)."""
    panel(surf, rect, col=col, alpha=235, radius=16, border=INK)
    text(surf, label, size, txt, rect.center)
    return rect


def tapped(app, rect):
    """Was this rect tapped this frame? (taps are consumed by take_taps in each scene's update)."""
    return any(rect.collidepoint(x, y) for x, y in getattr(app, "_frame_taps", []))


def panel(surf, rect, col=(255, 255, 255), alpha=215, radius=18, border=None):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, col + (alpha,), s.get_rect(), border_radius=radius)
    surf.blit(s, rect.topleft)
    if border:
        pygame.draw.rect(surf, border, rect, 4, border_radius=radius)


# ====================================================================== base scene
class Scene:
    def __init__(self, app):
        self.app = app
        self.t = 0

    def event(self, e):
        pass

    def update(self):
        self.t += 1

    def draw(self, surf):
        pass

    def menu_presses(self):
        """(device, press) pairs from every device this frame."""
        out = []
        for d in self.app.devices.all:
            for m in d.take_menu():
                out.append((d, m))
        return out

    def leave(self):
        pass


class MenuBackdrop:
    def __init__(self, theme="day"):
        self.bg = Background(theme)
        self.cam = Camera()
        self.cam.x, self.cam.y, self.cam.z = 0, -150, 0.7

    def draw(self, surf):
        self.cam.x += 0.6
        self.bg.draw(surf, self.cam)


# ====================================================================== title
class TitleScene(Scene):
    ITEMS = (["Battle vs CPU", "Host Room", "Join Room", "Controls"] if IS_WEB else
             ["Local Battle", "Host LAN Game", "Join LAN Game", "Controls", "Name", "Quit"])

    def __init__(self, app, message=""):
        super().__init__(app)
        self.sel = 0
        self.back = MenuBackdrop("day")
        self.typing = False
        self.message = message
        self.message_t = 300 if message else 0
        self.show_controls = False

    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if self.typing:
            s = self.app.settings
            if e.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_KP_ENTER):
                self.typing = False
                s["name"] = s["name"].strip() or "Player"
                save_settings(s)
            elif e.key == pygame.K_BACKSPACE:
                s["name"] = s["name"][:-1]
            elif e.unicode and e.unicode.isprintable() and len(s["name"]) < 12:
                s["name"] += e.unicode
            self.app.devices.clear_menu()
            return
        if self.show_controls:
            if e.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_KP_ENTER):
                self.show_controls = False
            return
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.choose()
        elif e.key == pygame.K_ESCAPE:
            self.app.running = False

    def choose(self):
        item = self.ITEMS[self.sel]
        if item in ("Local Battle", "Battle vs CPU"):
            self.app.go(CharSelectScene(self.app, hosting=False))
        elif item == "Host Room":
            try:
                self.app.go(CharSelectScene(self.app, hosting=True))
            except Exception as ex:
                self.message, self.message_t = "Couldn't open a room: %s" % ex, 300
        elif item == "Join Room":
            self.app.go(RoomJoinScene(self.app))
        elif item == "Host LAN Game":
            try:
                self.app.go(CharSelectScene(self.app, hosting=True))
            except OSError as ex:
                self.message, self.message_t = "Could not host (port %d busy?): %s" % (NET_PORT, ex), 300
        elif item == "Join LAN Game":
            self.app.go(JoinScene(self.app))
        elif item == "Controls":
            self.show_controls = True
        elif item == "Name":
            self.typing = True
        elif item == "Quit":
            self.app.running = False

    def update(self):
        super().update()
        if self.message_t > 0:
            self.message_t -= 1
        if self.app._frame_taps:
            if self.show_controls:
                self.show_controls = False
            else:
                for i, rc in enumerate(getattr(self, "item_rects", [])):
                    if tapped(self.app, rc):
                        self.sel = i
                        self.choose()
                        return
        for d, m in self.menu_presses():
            if self.typing:
                continue
            if self.show_controls:
                if m in ("ok", "back", "start"):
                    self.show_controls = False
                continue
            if m == "up":
                self.sel = (self.sel - 1) % len(self.ITEMS)
            elif m == "down":
                self.sel = (self.sel + 1) % len(self.ITEMS)
            elif m in ("ok", "start"):
                self.choose()

    def draw(self, surf):
        self.back.draw(surf)
        r = self.app.renderer
        # bouncing cast
        n = len(ROSTER)
        for i, k in enumerate(ROSTER):
            x = WIDTH / 2 + (i - (n - 1) / 2) * 150
            y = 330 - abs(math.sin(self.t * 0.06 + i * 0.9)) * 26
            spr = r.images.sprite(k, 120)
            surf.blit(spr, spr.get_rect(midbottom=(int(x), int(y))))
        text(surf, "Chiikawa Smash!", 84, (255, 150, 170), (WIDTH / 2, 110), outline=INK, ow=5)
        text(surf, "a tiny platform fighter", 22, INK, (WIDTH / 2, 170))
        box = pygame.Rect(WIDTH / 2 - 230, 370, 460, 300)
        panel(surf, box, alpha=200, border=INK)
        self.item_rects = []
        for i, it in enumerate(self.ITEMS):
            self.item_rects.append(pygame.Rect(box.x + 20, box.y + 30 + i * 46 - 20, box.w - 40, 40))
            label = it
            if it == "Name":
                label = "Name: " + self.app.settings["name"] + ("_" if self.typing and (self.t // 20) % 2 == 0 else "")
            y = box.y + 30 + i * 46
            col = (230, 80, 110) if i == self.sel else INK
            if i == self.sel:
                pygame.draw.rect(surf, (255, 225, 235), pygame.Rect(box.x + 20, y - 20, box.w - 40, 40), border_radius=12)
            text(surf, label, 28, col, (box.centerx, y))
        hint = ("tap to choose  -  turn your phone sideways" if TOUCH_UI else
                "W/S or arrows to move, click / Space / Enter to pick, Esc to quit, F11 fullscreen")
        text(surf, hint, 16, INK, (WIDTH / 2, HEIGHT - 24))
        if self.message_t > 0:
            text(surf, self.message, 20, (200, 40, 40), (WIDTH / 2, 352), outline=WHITE)
        if self.show_controls:
            draw_controls(surf)


def draw_controls(surf):
    box = pygame.Rect(60, 70, WIDTH - 120, HEIGHT - 140)
    panel(surf, box, alpha=240, border=INK)
    if TOUCH_UI:
        text(surf, "Touch controls", 40, INK, (WIDTH / 2, box.y + 40))
        lines = ["Left side: drag anywhere for the stick (up = aim up, down = crouch / drop / fast-fall)",
                 "ATK = attack (stick + ATK = tilts & aerials, flick + ATK = smash)   SMASH = smash attack",
                 "SPC = special (stick direction picks which)   JUMP = jump (hold for a full hop)",
                 "SHLD = shield / dodge (with the stick)   GRAB = grab, then push the stick to throw",
                 "|| (top left) = pause",
                 "Play in landscape. Tip: 'Add to Home Screen' makes it open full screen like an app."]
        for i, ln in enumerate(lines):
            text(surf, ln, 19, INK, (WIDTH / 2, box.y + 110 + i * 52))
        text(surf, "tap to close", 16, (150, 120, 120), (WIDTH / 2, box.bottom - 18))
        return
    text(surf, "Controls", 40, INK, (WIDTH / 2, box.y + 36))
    cols = [box.x + 30, box.x + 260, box.x + 600, box.x + 880]
    for r_, row in enumerate(CONTROLS_HELP):
        y = box.y + 90 + r_ * 44
        for c_, cell in enumerate(row):
            text(surf, cell, 19 if r_ else 22, (230, 80, 110) if r_ == 0 or c_ == 0 else INK, (cols[c_], y), anchor="midleft")
    tips = ["W jumps. W + click at the same time = up-tilt (or up-B with right-click) instead of jumping.",
            "Shift + A/D = roll, Shift + S = spot dodge, Shift in the air = air dodge (aim with a direction).",
            "Hold click on jab for a rapid jab. Hold right-click to charge some specials. Hold E to charge smashes.",
            "Tap S on a platform to drop through / while falling to fast-fall. Ledges grab automatically. F2 = show hitboxes."]
    for i, tip in enumerate(tips):
        text(surf, tip, 16, INK, (WIDTH / 2, box.bottom - 120 + i * 26))
    text(surf, "click / Enter to close", 16, (150, 120, 120), (WIDTH / 2, box.bottom - 14))


# ====================================================================== character select (local + host)
class CharSelectScene(Scene):
    def __init__(self, app, hosting=False, host=None, keep_slots=None):
        super().__init__(app)
        self.hosting = hosting
        self.host = host
        if hosting and host is None:
            self.host = make_host(app.settings["name"])
        self.slots = keep_slots or [None] * MAX_PLAYERS   # dicts: kind local/cpu, device, char, ok, level
        self.back = MenuBackdrop("sunset" if hosting else "day")
        s = app.settings
        self.stage_i = s.get("stage", 0) % len(STAGE_ORDER)
        self.stocks = s.get("stocks", DEFAULT_STOCKS)
        self.last_lobby = 0.0
        self.msg = ""
        self.msg_t = 0
        self.esc_t = 0
        self.match_id = int(time.time()) % 100000
        self.portrait_rects = []
        self.card_rects = []
        self.touch_buttons = {}
        if TOUCH_UI and keep_slots is None:
            # phone/browser: you're P1 (touch + keyboard + mouse together); vs-CPU starts with one CPU
            self.slots[0] = {"kind": "local", "device": app.devices.you, "char": 0, "ok": False}
            if not hosting:
                self.add_cpu()

    # ---------- helpers
    def remote(self):
        if not self.host:
            return {}
        return {c["slot"]: c for c in self.host.clients.values()}

    def taken(self):
        return {i for i, s in enumerate(self.slots) if s is not None}

    def free_slot(self):
        used = self.taken() | set(self.remote().keys())
        for i in range(MAX_PLAYERS):
            if i not in used:
                return i
        return None

    def slot_of(self, dev):
        for i, s in enumerate(self.slots):
            if s and s["kind"] == "local" and (s["device"] is dev or dev in getattr(s["device"], "subs", ())):
                return i
        return None

    def players(self):
        out = []
        rem = self.remote()
        for i in range(MAX_PLAYERS):
            s = self.slots[i]
            if s:
                name = self.app.settings["name"] if s["kind"] == "local" and i == self.first_local() else (
                    "CPU Lv%d" % s["level"] if s["kind"] == "cpu" else "P%d" % (i + 1))
                out.append({"slot": i, "kind": s["kind"], "char": ROSTER[s["char"]], "ok": s["ok"] or s["kind"] == "cpu",
                            "name": name, "level": s.get("level", 0)})
            elif i in rem:
                c = rem[i]
                ch = c["char"] if c["char"] in ROSTER else ROSTER[0]
                out.append({"slot": i, "kind": "remote", "char": ch, "ok": c["ready"], "name": c["name"], "level": 0})
        return out

    def first_local(self):
        for i, s in enumerate(self.slots):
            if s and s["kind"] == "local":
                return i
        return -1

    def add_cpu(self):
        i = self.free_slot()
        if i is None:
            return
        self.slots[i] = {"kind": "cpu", "device": None, "char": (i * 2 + 1) % len(ROSTER), "ok": True,
                         "level": self.app.settings.get("cpu_level", 2)}

    def remove_cpu(self):
        for i in range(MAX_PLAYERS - 1, -1, -1):
            if self.slots[i] and self.slots[i]["kind"] == "cpu":
                self.slots[i] = None
                return

    # ---------- input
    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.try_start()
        elif k == pygame.K_ESCAPE:
            if self.esc_t > 0:
                self.leave()
                self.app.go(TitleScene(self.app))
            else:
                self.esc_t = 60
        elif k == pygame.K_c:
            self.add_cpu()
        elif k == pygame.K_x:
            self.remove_cpu()
        elif k == pygame.K_v:
            lv = self.app.settings.get("cpu_level", 2) % 3 + 1
            self.app.settings["cpu_level"] = lv
            for s in self.slots:
                if s and s["kind"] == "cpu":
                    s["level"] = lv
        elif k == pygame.K_TAB:
            self.stage_i = (self.stage_i + 1) % len(STAGE_ORDER)
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.stocks = max(1, self.stocks - 1)
        elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.stocks = min(9, self.stocks + 1)
        elif k == pygame.K_n:
            # CPU character cycle
            for s in self.slots:
                if s and s["kind"] == "cpu":
                    s["char"] = (s["char"] + 1) % len(ROSTER)

    def update(self):
        super().update()
        if self.esc_t > 0:
            self.esc_t -= 1
        if self.msg_t > 0:
            self.msg_t -= 1
        if self.host:
            self.host.poll(self.taken())
            for ev, slot, name in self.host.events:
                self.msg, self.msg_t = ("%s joined!" % name) if ev == "join" else ("%s left" % name), 180
            self.host.events.clear()
            if time.time() - self.last_lobby > 0.1:
                self.last_lobby = time.time()
                self.host.broadcast(self.lobby_msg("lobby"))
        self.handle_taps()
        for d, m in self.menu_presses():
            i = self.slot_of(d)
            if i is None:
                if m in ("ok",):
                    j = self.free_slot()
                    if j is not None:
                        self.slots[j] = {"kind": "local", "device": d, "char": j % len(ROSTER), "ok": False}
                elif m == "start":
                    self.try_start()
                elif m == "cpu":
                    self.add_cpu()
                continue
            s = self.slots[i]
            if m == "left" and not s["ok"]:
                s["char"] = (s["char"] - 1) % len(ROSTER)
            elif m == "right" and not s["ok"]:
                s["char"] = (s["char"] + 1) % len(ROSTER)
            elif m == "up" and not s["ok"]:
                s["char"] = (s["char"] - 3) % len(ROSTER)
            elif m == "down" and not s["ok"]:
                s["char"] = (s["char"] + 3) % len(ROSTER)
            elif m == "ok":
                if s["ok"]:
                    pass
                else:
                    s["ok"] = True
            elif m == "back":
                if s["ok"]:
                    s["ok"] = False
                else:
                    self.slots[i] = None
            elif m == "start":
                self.try_start()
            elif m == "cpu":
                self.add_cpu()

    def handle_taps(self):
        app = self.app
        if not app._frame_taps:
            return
        touch = app.devices.touch
        i = self.slot_of(touch)
        for k, rc in enumerate(self.portrait_rects):
            if tapped(app, rc):
                if i is None:
                    j = self.free_slot()
                    if j is None:
                        return
                    self.slots[j] = {"kind": "local", "device": app.devices.you, "char": k, "ok": True}
                else:
                    self.slots[i]["char"] = k
                    self.slots[i]["ok"] = True
                return
        for slot, rc in self.card_rects:
            s_ = self.slots[slot]
            if s_ and s_["kind"] == "cpu" and tapped(app, rc):       # tap a CPU card to change its character
                s_["char"] = (s_["char"] + 1) % len(ROSTER)
                return
        tb = self.touch_buttons
        if "cpu+" in tb and tapped(app, tb["cpu+"]):
            self.add_cpu()
        elif "cpu-" in tb and tapped(app, tb["cpu-"]):
            self.remove_cpu()
        elif "lv" in tb and tapped(app, tb["lv"]):
            lv = app.settings.get("cpu_level", 2) % 3 + 1
            app.settings["cpu_level"] = lv
            for s_ in self.slots:
                if s_ and s_["kind"] == "cpu":
                    s_["level"] = lv
        elif "stage" in tb and tapped(app, tb["stage"]):
            self.stage_i = (self.stage_i + 1) % len(STAGE_ORDER)
        elif "stock-" in tb and tapped(app, tb["stock-"]):
            self.stocks = max(1, self.stocks - 1)
        elif "stock+" in tb and tapped(app, tb["stock+"]):
            self.stocks = min(9, self.stocks + 1)
        elif "back" in tb and tapped(app, tb["back"]):
            self.leave()
            app.go(TitleScene(app))
        elif "fight" in tb and tapped(app, tb["fight"]):
            self.try_start()

    def lobby_msg(self, phase):
        return {"t": "lobby", "phase": phase, "mid": self.match_id, "players": self.players(), "stage": STAGE_ORDER[self.stage_i],
                "stocks": self.stocks, "ip": self.host.ip if self.host else ""}

    def try_start(self):
        ps = self.players()
        if len(ps) < 2:
            self.msg, self.msg_t = "Need at least 2 players (press C to add a CPU)", 150
            return
        not_ready = [p for p in ps if not p["ok"]]
        if not_ready:
            self.msg, self.msg_t = "Waiting for %s to pick" % ", ".join(p["name"] for p in not_ready), 150
            return
        s = self.app.settings
        s["stage"], s["stocks"] = self.stage_i, self.stocks
        save_settings(s)
        players, devices, bots = [], {}, []
        for p in ps:
            col = SLOT_COLORS[p["slot"]]
            players.append({"slot": p["slot"], "char": p["char"], "name": p["name"], "color": col, "cpu": p["kind"] == "cpu"})
            if p["kind"] == "local":
                devices[p["slot"]] = self.slots[p["slot"]]["device"]
            elif p["kind"] == "cpu":
                bots.append(Bot(p["slot"], p["level"]))
        game = Game(players, STAGE_ORDER[self.stage_i], self.stocks)
        self.match_id += 1
        game.match_id = self.match_id
        if self.host:
            self.host.broadcast(self.lobby_msg("match"))
        self.app.go(MatchScene(self.app, game, devices, bots, self.host, lobby=self))

    def leave(self):
        if self.host:
            self.host.close()
            self.host = None

    # ---------- drawing
    def draw(self, surf):
        self.back.draw(surf)
        r = self.app.renderer
        title = ("Host Room" if IS_WEB else "Host LAN Game") if self.hosting else (
            "Battle vs CPU" if IS_WEB else "Local Battle")
        text(surf, title, 44, WHITE, (WIDTH / 2, 40), outline=INK, ow=4)
        if self.host and IS_WEB:
            st = self.host.state
            line = {"ready": "Room code:  %s   -  friends tap Join Room and type it" % self.host.ip,
                    "connecting": "Opening room %s ..." % self.host.ip,
                    "error": "Couldn't reach the matchmaking server - check your internet"}.get(st, "Room %s (%s)" % (self.host.ip, st))
            text(surf, line, 24, (255, 245, 180), (WIDTH / 2, 82), outline=INK, ow=2)
        elif self.host:
            text(surf, "Friends: Join LAN Game and type  %s  (port %d)" % (self.host.ip, NET_PORT), 22, (255, 245, 180),
                 (WIDTH / 2, 82), outline=INK, ow=2)
        # roster grid: just the character and their name
        ps = self.players()
        n = len(ROSTER)
        gap = 12 if n > 6 else 14
        cw, ch = min(170, int((WIDTH - 40 - (n - 1) * gap) / n)), 196      # one row, shrinks to fit the roster
        gx = WIDTH / 2 - (n * cw + (n - 1) * gap) / 2
        gy = 106
        self.portrait_rects = []
        for i, k in enumerate(ROSTER):
            rect = pygame.Rect(int(gx + i * (cw + gap)), gy, cw, ch)
            self.portrait_rects.append(rect)
            chosen = [p for p in ps if p["char"] == k and p["kind"] != "cpu"]
            border = SLOT_COLORS[chosen[0]["slot"]] if chosen else INK
            panel(surf, rect, alpha=225, border=border, radius=18)
            c = characters.CHARACTERS[k]
            spr = r.images.sprite(k, 128)
            if spr.get_width() > cw - 12:                     # wide sprites (Siren, Rakko) still fit the card
                spr = r.images.sprite(k, int(128 * (cw - 12) / spr.get_width()))
            bob = math.sin(self.t * 0.08 + i) * 3 if chosen else 0
            surf.blit(spr, spr.get_rect(midbottom=(rect.centerx, rect.bottom - 42 + bob)))
            text(surf, c["name"], 22 if cw >= 150 else 17, c["color"], (rect.centerx, rect.bottom - 22), outline=INK, ow=2)
            # little P1/P2 badges for whoever is hovering this character
            for j, p in enumerate(chosen):
                cx = rect.right - 20 - 30 * j
                pygame.draw.circle(surf, SLOT_COLORS[p["slot"]], (cx, rect.y + 20), 14)
                text(surf, "P%d" % (p["slot"] + 1), 12, WHITE, (cx, rect.y + 20))
        # player cards
        cw2 = 280
        y0 = 322
        self.card_rects = []
        for i in range(MAX_PLAYERS):
            rect = pygame.Rect(int(WIDTH / 2 - 2 * (cw2 + 14) + i * (cw2 + 14) + 7), y0, cw2, 300)
            self.card_rects.append((i, rect))
            p = next((q for q in ps if q["slot"] == i), None)
            col = SLOT_COLORS[i] if (p and p["kind"] != "cpu") else CPU_COLOR if p else (200, 200, 205)
            panel(surf, rect, col=(255, 255, 255), alpha=200 if p else 110, border=col)
            text(surf, "P%d" % (i + 1), 22, col, (rect.x + 16, rect.y + 18), anchor="midleft", outline=WHITE)
            if not p:
                text(surf, "tap + CPU to add a CPU" if TOUCH_UI else "click / A to join", 16, (120, 120, 130), rect.center)
                continue
            spr = r.images.sprite(p["char"], 170)
            bob = 0 if p["ok"] else math.sin(self.t * 0.1 + i) * 4
            surf.blit(spr, spr.get_rect(midbottom=(rect.centerx, rect.bottom - 44 + bob)))
            text(surf, characters.CHARACTERS[p["char"]]["name"], 22, INK, (rect.centerx, rect.bottom - 30))
            kind = {"local": "", "cpu": "", "remote": " (LAN)"}[p["kind"]]
            text(surf, p["name"] + kind, 16, INK, (rect.right - 14, rect.y + 18), anchor="midright")
            if p["ok"]:
                text(surf, "READY" if p["kind"] != "cpu" else "CPU", 26, (60, 170, 80) if p["kind"] != "cpu" else (110, 110, 120),
                     (rect.centerx, rect.y + 52), outline=WHITE, ow=2)
            elif p["kind"] == "local":
                text(surf, "< pick >", 18, col, (rect.centerx, rect.y + 52))
            else:
                text(surf, "choosing...", 18, col, (rect.centerx, rect.y + 52))
        # rules bar
        st = STAGES[STAGE_ORDER[self.stage_i]]
        if TOUCH_UI:
            # big tap buttons instead of keyboard hints
            y = HEIGHT - 80
            spec = [("back", "BACK", 110), ("cpu+", "+ CPU", 120), ("cpu-", "- CPU", 120),
                    ("lv", "CPU Lv %d" % self.app.settings.get("cpu_level", 2), 140),
                    ("stage", st["name"], 210), ("stock-", "-", 60), ("stock+", "+", 60), ("fight", "FIGHT!", 200)]
            x = 30
            self.touch_buttons = {}
            for key, label, w in spec:
                if key == "stock-":
                    text(surf, "Stocks: %d" % self.stocks, 22, INK, (x + 70, y + 32))
                    x += 140
                col = (255, 120, 140) if key == "fight" else (255, 245, 250)
                self.touch_buttons[key] = button(surf, pygame.Rect(x, y, w, 64), label, col=col,
                                                 txt=WHITE if key == "fight" else INK, size=26 if key == "fight" else 20)
                x += w + 12
            if self.msg_t > 0:
                text(surf, self.msg, 22, (230, 70, 70), (WIDTH / 2, 312), outline=WHITE, ow=2)
            return
        bar = pygame.Rect(40, HEIGHT - 82, WIDTH - 80, 64)
        panel(surf, bar, alpha=210, border=INK)
        text(surf, "Stage: %s  [Tab]     Stocks: %d  [-/+]     CPU: [C] add  [X] remove  [V] level %d  [N] change char"
             % (st["name"], self.stocks, self.app.settings.get("cpu_level", 2)), 18, INK, (bar.centerx, bar.y + 20))
        text(surf, "Click/A join + ready, right-click/B back, A/D pick.   Enter / Start = FIGHT!   Esc twice = leave", 16, (150, 90, 100),
             (bar.centerx, bar.y + 46))
        if self.msg_t > 0:
            text(surf, self.msg, 22, (230, 70, 70), (WIDTH / 2, 312), outline=WHITE, ow=2)
        if self.esc_t > 0:
            text(surf, "press Esc again to leave", 20, (230, 70, 70), (WIDTH / 2, 312), outline=WHITE, ow=2)


def _wrap(s, n):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


# ====================================================================== match (local / host)
class MatchScene(Scene):
    def __init__(self, app, game, devices, bots, host, lobby):
        super().__init__(app)
        self.game = game
        self.devices = devices       # slot -> Device
        self.bots = bots
        self.host = host
        self.lobby = lobby
        self.acc = 0.0
        self.esc_t = 0
        self.paused = False
        self.pause_rects = {}
        self.snap = game.snapshot()
        self.last_lobby = 0.0
        app.devices.touch.pause_req = False
        app.renderer.stage_key = None

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.esc_t > 0:
                self.back_to_lobby()
            else:
                self.esc_t = 90

    def back_to_lobby(self):
        for s in self.lobby.slots:
            if s and s["kind"] == "local":
                s["ok"] = False
        if self.host:
            for c in self.host.clients.values():
                c["ready"] = False
            self.host.broadcast(self.lobby.lobby_msg("lobby"))
        self.app.go(self.lobby)

    def update(self):
        super().update()
        touch = self.app.devices.touch
        if touch.pause_req:
            touch.pause_req = False
            if not self.host:          # never pause an online match: || twice ends it instead
                self.paused = not self.paused
            elif self.esc_t > 0:
                self.back_to_lobby()
                return
            else:
                self.esc_t = 120
        if self.paused:
            if tapped(self.app, self.pause_rects.get("resume", pygame.Rect(0, 0, 0, 0))):
                self.paused = False
            elif tapped(self.app, self.pause_rects.get("quit", pygame.Rect(0, 0, 0, 0))):
                self.paused = False
                self.back_to_lobby()
            self.app.devices.clear_menu()
            self.acc = 0.0
            return
        self.app.devices.clear_menu()
        if self.esc_t > 0:
            self.esc_t -= 1
        if self.host:
            self.host.poll(set(self.devices.keys()) | {b.slot for b in self.bots})
            self.host.events.clear()
            if time.time() - self.last_lobby > 1.0:
                self.last_lobby = time.time()
                self.host.broadcast(self.lobby.lobby_msg("match"))
        # run the simulation at a fixed 60 steps/second, catching up (max 3 steps) if frames are slow
        self.acc += min(100.0, getattr(self.app, "dt_ms", 1000.0 / 60)) / (1000.0 / 60)
        steps = 0
        while self.acc >= 1.0 and steps < 3:
            self.acc -= 1.0
            steps += 1
            inputs = {slot: d.raw() for slot, d in self.devices.items()}
            if self.host:
                inputs.update(self.host.inputs())
            for b in self.bots:
                inputs[b.slot] = b.update(self.game)
            self.game.step(inputs)
        if self.acc > 3.0:
            self.acc = 0.0
        self.snap = self.game.snapshot()
        if self.host:
            self.host.broadcast({"t": "snap", "s": self.snap})
        if self.game.finished:
            self.app.go(ResultsScene(self.app, self.snap, on_done=self.back_to_lobby, host=self.host, lobby=self.lobby))

    def draw(self, surf):
        self.app.renderer.draw(surf, self.snap, local_slots=tuple(self.devices.keys()))
        touch_overlay(self.app, self.devices.values())
        if self.esc_t > 0:
            text(surf, "tap || again to end the match" if TOUCH_UI else "press Esc again to end the match", 22, WHITE,
                 (WIDTH / 2, 130 if TOUCH_UI else 30), outline=INK)
        if self.paused:
            dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dim.fill((30, 20, 25, 140))
            surf.blit(dim, (0, 0))
            text(surf, "Paused", 72, WHITE, (WIDTH / 2, 240), outline=INK, ow=5)
            self.pause_rects = {
                "resume": button(surf, pygame.Rect(WIDTH / 2 - 160, 320, 320, 76), "Resume", size=30),
                "quit": button(surf, pygame.Rect(WIDTH / 2 - 160, 420, 320, 76), "End match", size=30),
            }


# ====================================================================== results
class ResultsScene(Scene):
    def __init__(self, app, snap, on_done=None, host=None, lobby=None, client=None):
        super().__init__(app)
        self.snap = snap
        self.on_done = on_done
        self.host = host
        self.lobby = lobby
        self.client = client
        self.back = MenuBackdrop("night")
        self.last_send = 0.0

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.done()

    def done(self):
        if self.client:
            return       # clients wait for the host
        if self.on_done:
            self.on_done()

    def update(self):
        super().update()
        if self.host:
            self.host.poll(set())
            self.host.events.clear()
            if time.time() - self.last_send > 0.25:
                self.last_send = time.time()
                self.host.broadcast({"t": "snap", "s": self.snap})
        if self.client:
            self.client.poll()
            st = self.client.status
            if st in ("lost", "closed"):
                self.app.go(TitleScene(self.app, "Host closed the game" if st == "closed" else "Lost connection to host"))
                return
            if self.client.lobby and self.client.lobby.get("phase") == "lobby":
                self.app.go(ClientLobbyScene(self.app, self.client))
                return
        if self.app._frame_taps and self.t > 60:
            self.done()
            return
        for d, m in self.menu_presses():
            if m in ("ok", "start") and self.t > 60:
                self.done()

    def draw(self, surf):
        self.back.draw(surf)
        r = self.app.renderer
        fs = sorted(self.snap["f"], key=lambda f: f["pl"] or 9)
        win = fs[0] if fs and fs[0]["pl"] == 1 else None
        if win:
            text(surf, "%s wins!" % (win["n"] if not win["cpu"] else "CPU " + characters.CHARACTERS[win["c"]]["name"]), 56,
                 tuple(win["col"]), (WIDTH / 2, 60), outline=WHITE, ow=4)
            spr = r.images.sprite(win["c"], 230)
            bob = abs(math.sin(self.t * 0.08)) * 18
            surf.blit(spr, spr.get_rect(midbottom=(WIDTH / 2, 340 - bob)))
        else:
            text(surf, "No contest!", 56, WHITE, (WIDTH / 2, 60), outline=INK, ow=4)
        cw = 270
        n = len(fs)
        for i, f in enumerate(fs):
            rect = pygame.Rect(int(WIDTH / 2 - n * (cw + 12) / 2 + i * (cw + 12)), 380, cw, 250)
            panel(surf, rect, alpha=225, border=tuple(f["col"]))
            text(surf, "#%d" % (f["pl"] or n), 40, tuple(f["col"]), (rect.x + 20, rect.y + 30), anchor="midleft", outline=INK, ow=2)
            spr = r.images.sprite(f["c"], 70)
            surf.blit(spr, spr.get_rect(topright=(rect.right - 16, rect.y + 10)))
            text(surf, f["n"] if not f["cpu"] else "CPU", 20, INK, (rect.x + 20, rect.y + 72), anchor="midleft")
            s = f["st8"]
            rows = [("KOs", s["kos"]), ("Falls", s["falls"]), ("Self-destructs", s["sd"]),
                    ("Damage dealt", "%d%%" % s["dealt"]), ("Damage taken", "%d%%" % s["taken"])]
            for j, (k, v) in enumerate(rows):
                y = rect.y + 108 + j * 27
                text(surf, k, 17, (110, 90, 90), (rect.x + 20, y), anchor="midleft")
                text(surf, str(v), 19, INK, (rect.right - 20, y), anchor="midright")
        msg = "waiting for the host..." if self.client else "click / A / Enter to continue"
        text(surf, msg, 20, WHITE, (WIDTH / 2, HEIGHT - 40), outline=INK)


# ====================================================================== join (client)
class JoinScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.finder = _net().Finder()
        self.found = []
        self.sel = 0              # 0 = manual IP field, 1.. = found hosts
        self.ip = app.settings.get("last_ip", "")
        self.back = MenuBackdrop("night")

    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.leave()
            self.app.go(TitleScene(self.app))
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.connect()
        elif e.key == pygame.K_BACKSPACE and self.sel == 0:
            self.ip = self.ip[:-1]
        elif e.key in (pygame.K_UP,):
            self.sel = max(0, self.sel - 1)
        elif e.key in (pygame.K_DOWN,):
            self.sel = min(len(self.found), self.sel + 1)
        elif self.sel == 0 and e.unicode and (e.unicode.isalnum() or e.unicode in ".-:") and len(self.ip) < 40:
            self.ip += e.unicode
        self.app.devices.clear_menu()

    def connect(self):
        ip = self.ip.strip() if self.sel == 0 else self.found[self.sel - 1][0]
        if not ip:
            return
        self.app.settings["last_ip"] = ip
        save_settings(self.app.settings)
        self.leave()
        client = make_client(ip, self.app.settings["name"])
        self.app.go(ClientLobbyScene(self.app, client))

    def leave(self):
        self.finder.close()

    def update(self):
        super().update()
        if self.t % 10 == 0:
            self.found = self.finder.poll()
        for d, m in self.menu_presses():   # gamepads can pick found hosts
            if d.kind != "gamepad":
                continue
            if m == "up":
                self.sel = max(0, self.sel - 1)
            elif m == "down":
                self.sel = min(len(self.found), self.sel + 1)
            elif m in ("ok", "start"):
                self.connect()
            elif m == "back":
                self.leave()
                self.app.go(TitleScene(self.app))

    def draw(self, surf):
        self.back.draw(surf)
        text(surf, "Join LAN Game", 48, WHITE, (WIDTH / 2, 60), outline=INK, ow=4)
        box = pygame.Rect(WIDTH / 2 - 320, 120, 640, 470)
        panel(surf, box, alpha=225, border=INK)
        text(surf, "Type the host's IP address (shown on their screen):", 20, INK, (box.centerx, box.y + 36))
        field = pygame.Rect(box.x + 70, box.y + 64, box.w - 140, 56)
        pygame.draw.rect(surf, (255, 235, 240) if self.sel == 0 else (240, 240, 245), field, border_radius=12)
        pygame.draw.rect(surf, (230, 80, 110) if self.sel == 0 else INK, field, 3, border_radius=12)
        cur = "_" if self.sel == 0 and (self.t // 20) % 2 == 0 else ""
        text(surf, self.ip + cur, 32, INK, field.center)
        text(surf, "Games found on your Wi-Fi:", 20, INK, (box.centerx, box.y + 160))
        if not self.found:
            text(surf, "(searching... if nothing shows up, just type the IP)", 16, (130, 120, 130), (box.centerx, box.y + 196))
        for i, (ip, (name, players, _)) in enumerate(self.found[:6]):
            y = box.y + 200 + i * 44
            rr = pygame.Rect(box.x + 70, y - 18, box.w - 140, 38)
            if self.sel == i + 1:
                pygame.draw.rect(surf, (255, 225, 235), rr, border_radius=10)
            text(surf, "%s's game   %s   (%d joined)" % (name, ip, players), 20, INK, rr.center)
        text(surf, "Up/Down to choose, Enter to join, Esc to go back", 16, (150, 90, 100), (box.centerx, box.bottom - 22))


class RoomJoinScene(Scene):
    """Browser version: type the host's 4-digit room code on a big number pad."""
    KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "<", "0", "OK"]

    def __init__(self, app, message=""):
        super().__init__(app)
        self.code = ""
        self.back = MenuBackdrop("night")
        self.rects = {}
        self.message = message

    def event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.app.go(TitleScene(self.app))
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.connect()
        elif e.key == pygame.K_BACKSPACE:
            self.code = self.code[:-1]
        elif e.unicode and e.unicode.isdigit() and len(self.code) < 4:
            self.code += e.unicode
        self.app.devices.clear_menu()

    def connect(self):
        if len(self.code) != 4:
            self.message = "Room codes have 4 numbers"
            return
        self.app.go(ClientLobbyScene(self.app, make_client(self.code, self.app.settings["name"])))

    def update(self):
        super().update()
        self.app.devices.clear_menu()
        for k, rc in self.rects.items():
            if tapped(self.app, rc):
                if k == "back":
                    self.app.go(TitleScene(self.app))
                elif k == "OK":
                    self.connect()
                elif k == "<":
                    self.code = self.code[:-1]
                elif len(self.code) < 4:
                    self.code += k
                return

    def draw(self, surf):
        self.back.draw(surf)
        text(surf, "Join Room", 48, WHITE, (WIDTH / 2, 50), outline=INK, ow=4)
        field = pygame.Rect(WIDTH / 2 - 170, 96, 340, 78)
        panel(surf, field, alpha=240, border=INK)
        shown = " ".join(self.code[i] if i < len(self.code) else "_" for i in range(4))
        text(surf, shown, 50, INK, field.center)
        if self.message:
            text(surf, self.message, 20, (255, 210, 210), (WIDTH / 2, 196), outline=INK, ow=2)
        self.rects = {}
        bw, bh, gap = 130, 96, 14
        x0 = WIDTH / 2 - (3 * bw + 2 * gap) / 2
        for i, k in enumerate(self.KEYS):
            r = pygame.Rect(int(x0 + (i % 3) * (bw + gap)), int(216 + (i // 3) * (bh + gap)), bw, bh)
            col = (255, 120, 140) if k == "OK" else (255, 245, 250)
            self.rects[k] = button(surf, r, "JOIN" if k == "OK" else k, col=col, size=40 if k.isdigit() else 30,
                                   txt=WHITE if k == "OK" else INK)
        self.rects["back"] = button(surf, pygame.Rect(30, 30, 130, 64), "BACK", size=24)
        text(surf, "Ask the host for the code on their screen", 18, WHITE, (WIDTH / 2, HEIGHT - 20), outline=INK)


class ClientLobbyScene(Scene):
    def __init__(self, app, client):
        super().__init__(app)
        self.client = client
        self.device = app.devices.you if TOUCH_UI else None
        self.back = MenuBackdrop("sunset")
        self.char_i = ROSTER.index(client.char) if client.char in ROSTER else 0
        self.btns = {}

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.client.close()
            self.app.go(TitleScene(self.app))

    def update(self):
        super().update()
        c = self.client
        c.poll()
        if c.status in ("lost", "closed", "full", "nohost", "noroute"):
            msg = {"lost": "Couldn't reach the host" + (" (try both on the same Wi-Fi)" if IS_WEB else
                                                           " (check the IP / firewall / same Wi-Fi)"),
                   "closed": "The host closed the game", "full": "That game is full",
                   "nohost": "No room with code %s" % getattr(c, "code", ""),
                   "noroute": "Found the room but couldn't connect - try the same Wi-Fi"}[c.status]
            c.close()
            self.app.go(RoomJoinScene(self.app, msg) if IS_WEB and c.status in ("nohost", "noroute")
                        else TitleScene(self.app, msg))
            return
        # taps: < > to pick, READY, LEAVE
        for k, rc in self.btns.items():
            if tapped(self.app, rc):
                if k == "leave":
                    c.close()
                    self.app.go(TitleScene(self.app))
                    return
                if k == "prev" and not c.ready:
                    self.char_i = (self.char_i - 1) % len(ROSTER)
                elif k == "next" and not c.ready:
                    self.char_i = (self.char_i + 1) % len(ROSTER)
                elif k == "ready":
                    c.ready = not c.ready
                c.char = ROSTER[self.char_i]
                c.send_pick()
                break
        if c.status == "match" and c.snap is not None and c.lobby and c.lobby.get("phase") == "match":
            dev = self.device or self.app.devices.kb1
            self.app.devices.touch.pause_req = False
            self.app.go(ClientMatchScene(self.app, c, dev))
            return
        for d, m in self.menu_presses():
            if self.device is None:
                self.device = d
            if d is not self.device and d not in getattr(self.device, "subs", ()):
                continue
            if m in ("left", "up") and not c.ready:
                self.char_i = (self.char_i - 1) % len(ROSTER)
            elif m in ("right", "down") and not c.ready:
                self.char_i = (self.char_i + 1) % len(ROSTER)
            elif m == "ok":
                c.ready = True
            elif m == "back":
                c.ready = False
            else:
                continue
            c.char = ROSTER[self.char_i]
            c.send_pick()

    def draw(self, surf):
        self.back.draw(surf)
        c = self.client
        r = self.app.renderer
        if c.status == "connecting":
            text(surf, "Connecting to %s ..." % c.addr[0], 36, WHITE, (WIDTH / 2, HEIGHT / 2), outline=INK, ow=3)
            if TOUCH_UI:
                self.btns = {"leave": button(surf, pygame.Rect(WIDTH / 2 - 90, HEIGHT / 2 + 50, 180, 64), "CANCEL", size=24)}
            else:
                text(surf, "Esc to cancel", 18, WHITE, (WIDTH / 2, HEIGHT / 2 + 50), outline=INK)
            return
        text(surf, "Joined %s's game" % c.host_name, 40, WHITE, (WIDTH / 2, 44), outline=INK, ow=3)
        # my pick
        k = ROSTER[self.char_i]
        box = pygame.Rect(60, 110, 420, 470)
        panel(surf, box, alpha=225, border=SLOT_COLORS[c.slot or 0])
        text(surf, "You are P%d" % ((c.slot or 0) + 1), 28, SLOT_COLORS[c.slot or 0], (box.centerx, box.y + 30), outline=INK, ow=1)
        spr = r.images.sprite(k, 220)
        bob = 0 if c.ready else math.sin(self.t * 0.1) * 5
        surf.blit(spr, spr.get_rect(midbottom=(box.centerx, box.y + 330 + bob)))
        ch = characters.CHARACTERS[k]
        text(surf, "< %s >" % ch["name"] if not c.ready else ch["name"], 32, ch["color"], (box.centerx, box.y + 360), outline=INK, ow=2)
        if TOUCH_UI:
            self.btns = {
                "prev": button(surf, pygame.Rect(box.x + 16, box.y + 170, 70, 90), "<", size=40),
                "next": button(surf, pygame.Rect(box.right - 86, box.y + 170, 70, 90), ">", size=40),
                "ready": button(surf, pygame.Rect(box.x + 60, box.bottom - 86, box.w - 120, 66),
                                "CHANGE" if c.ready else "READY!", col=(140, 210, 150) if c.ready else (255, 120, 140),
                                size=28, txt=WHITE),
                "leave": button(surf, pygame.Rect(30, 26, 120, 56), "LEAVE", size=20),
            }
        else:
            text(surf, "READY! (right-click / B to change)" if c.ready else "A/D to pick, click / A = ready", 18,
                 (60, 160, 80) if c.ready else (150, 90, 100), (box.centerx, box.bottom - 24))
        # lobby list
        lob = c.lobby or {}
        box2 = pygame.Rect(520, 110, 700, 470)
        panel(surf, box2, alpha=210, border=INK)
        st = STAGES.get(lob.get("stage", "battlefield"), STAGES["battlefield"])
        text(surf, "Stage: %s     Stocks: %s" % (st["name"], lob.get("stocks", "?")), 22, INK, (box2.centerx, box2.y + 30))
        for i, p in enumerate(lob.get("players", [])):
            y = box2.y + 80 + i * 92
            col = SLOT_COLORS[p["slot"]] if p["kind"] != "cpu" else CPU_COLOR
            row = pygame.Rect(box2.x + 24, y, box2.w - 48, 80)
            pygame.draw.rect(surf, (250, 248, 245), row, border_radius=14)
            pygame.draw.rect(surf, col, row, 3, border_radius=14)
            spr = r.images.sprite(p["char"] if p["char"] in ROSTER else ROSTER[0], 66)
            surf.blit(spr, spr.get_rect(midleft=(row.x + 12, row.centery)))
            me = " (you)" if p["slot"] == c.slot else ""
            text(surf, "P%d  %s%s" % (p["slot"] + 1, p["name"], me), 22, col, (row.x + 100, row.centery - 12), anchor="midleft")
            text(surf, characters.CHARACTERS.get(p["char"], ch)["name"], 17, INK, (row.x + 100, row.centery + 16), anchor="midleft")
            text(surf, "READY" if p["ok"] else "choosing", 20, (60, 160, 80) if p["ok"] else (170, 140, 140),
                 (row.right - 20, row.centery), anchor="midright")
        text(surf, "The host starts the match." + ("" if TOUCH_UI else " Esc = leave"), 18, WHITE, (WIDTH / 2, HEIGHT - 40), outline=INK)


class ClientMatchScene(Scene):
    def __init__(self, app, client, device):
        super().__init__(app)
        self.client = client
        self.device = device
        app.renderer.stage_key = None
        self.esc_t = 0

    def event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.esc_t > 0:
                self.client.close()
                self.app.go(TitleScene(self.app, "You left the match"))
            else:
                self.esc_t = 90

    def update(self):
        super().update()
        self.app.devices.clear_menu()
        if self.esc_t > 0:
            self.esc_t -= 1
        c = self.client
        touch = self.app.devices.touch
        if touch.pause_req:
            touch.pause_req = False
            if self.esc_t > 0:
                self.client.close()
                self.app.go(TitleScene(self.app, "You left the match"))
                return
            self.esc_t = 120
        c.poll()
        c.send_input(self.device.raw())
        if c.status in ("lost", "closed"):
            c.close()
            self.app.go(TitleScene(self.app, "Host closed the game" if c.status == "closed" else "Lost connection to host"))
            return
        if c.lobby and c.lobby.get("phase") == "lobby":
            c.ready = False
            c.snap = None
            self.app.go(ClientLobbyScene(self.app, c))
            return
        s = c.snap
        if s and s["over"] and s["et"] >= GAME_END_FRAMES:
            c.ready = False
            self.app.go(ResultsScene(self.app, s, client=c))

    def draw(self, surf):
        if self.client.snap:
            self.app.renderer.draw(surf, self.client.snap, local_slots=(self.client.slot,))
        else:
            surf.fill((30, 30, 40))
            text(surf, "waiting for the host...", 30, WHITE, (WIDTH / 2, HEIGHT / 2))
        touch_overlay(self.app, [self.device])
        if self.esc_t > 0:
            text(surf, "tap || again to leave" if TOUCH_UI else "press Esc again to leave", 22, WHITE,
                 (WIDTH / 2, 130 if TOUCH_UI else 30), outline=INK)


# ====================================================================== app
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        try:
            if IS_WEB:
                # browser: a plain fixed 1280x720 canvas; the page's CSS scales it to the screen.
                # (SCALED|RESIZABLE made SDL re-scale on phone rotation -> zoomed-in, cropped picture)
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
            else:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.settings = load_settings()
        self.devices = DeviceManager()
        self.renderer = Renderer()
        self.running = True
        self._frame_taps = []
        self.dt_ms = 1000.0 / FPS
        self.scene = TitleScene(self)
        self.show_fps = False

    def go(self, scene):
        self.devices.clear_menu()
        self.scene = scene

    def run(self):
        asyncio.run(self.run_async())

    async def run_async(self):
        self.dt_ms = 1000.0 / FPS
        while self.running:
            self.dt_ms = self.clock.tick(FPS)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11 and not IS_WEB:
                    pygame.display.toggle_fullscreen()
                    continue
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F2:
                    self.renderer.debug = not self.renderer.debug
                self.devices.handle_event(e)
                self.scene.event(e)
            self._frame_taps = self.devices.take_taps()
            self.scene.update()
            self.scene.draw(self.screen)
            if self.show_fps:
                text(self.screen, "%d fps" % self.clock.get_fps(), 16, WHITE, (8, 8), anchor="topleft", outline=BLACK)
            pygame.display.flip()
            await asyncio.sleep(0)      # lets the browser breathe (required for the web build)
        try:
            self.scene.leave()
        except Exception:
            pass
        save_settings(self.settings)
        pygame.quit()


def run():
    App().run()


async def main():
    """Entry point for the web build (pygbag)."""
    await App().run_async()
