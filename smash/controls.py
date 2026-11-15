"""Keyboard / gamepad -> raw input lists (see sim.py for the format)."""
import math
import time

import pygame

from .config import WIDTH, HEIGHT, TOUCH_UI
from .sim import BUTTONS, BUTTON_BITS

K = pygame
# Keyboard 1 = keyboard + mouse (Brawlhalla-style): W is up AND jump (tap-jump), mouse does the attacking.
KEYBOARD_1 = {
    "name": "Keyboard + Mouse",
    "left": [K.K_a], "right": [K.K_d], "up": [K.K_w], "down": [K.K_s],
    "jump": [K.K_w], "atk": [K.K_j], "spc": [K.K_k], "shd": [K.K_LSHIFT, K.K_l],
    "grb": [K.K_SPACE, K.K_u], "sms": [K.K_e, K.K_i],
    "mouse": {1: "atk", 3: "spc", 2: "sms"},          # 1 = left button, 2 = middle, 3 = right
    "menu_ok": ["atk", "grb"], "menu_back": ["spc"],
}
KEYBOARD_2 = {
    "name": "Keyboard 2",
    "left": [K.K_LEFT], "right": [K.K_RIGHT], "up": [K.K_UP], "down": [K.K_DOWN],
    "jump": [K.K_KP0, K.K_RSHIFT], "atk": [K.K_KP1, K.K_PERIOD], "spc": [K.K_KP2, K.K_SLASH],
    "shd": [K.K_KP3, K.K_RCTRL], "grb": [K.K_KP4, K.K_SEMICOLON], "sms": [K.K_KP5, K.K_QUOTE],
    "menu_ok": ["atk", "jump"], "menu_back": ["spc"],
}

CONTROLS_HELP = [
    ("", "Keyboard + Mouse", "Keyboard 2", "Gamepad"),
    ("Move", "A / D  (S = down)", "Arrow keys", "Left stick / D-pad"),
    ("Jump", "W  (hold = full hop)", "Num0 / R-Shift", "X / Y"),
    ("Attack", "Left click  (or J)", "Num1 / .", "A"),
    ("Special", "Right click  (or K)", "Num2 / /", "B"),
    ("Shield / dodge", "Left Shift  (or L)", "Num3 / R-Ctrl", "RB / RT / LT"),
    ("Grab", "Space  (or U)", "Num4 / ;", "LB"),
    ("Smash attack", "E / middle click / dir+click", "Num5 / '", "Right stick"),
]


class Device:
    """Base class: keeps press counters so taps survive packet loss on the network."""
    kind = "?"

    def __init__(self):
        self.counts = {b: 0 for b in BUTTONS}
        self.menu_presses = []      # menu events: "up","down","left","right","ok","back","start"

    def press(self, b):
        self.counts[b] += 1

    def raw(self):
        x, y, held, sx, sy = self.read()
        bits = sum(bit for b, bit in zip(BUTTONS, BUTTON_BITS) if b in held)
        return [round(x, 3), round(y, 3), bits] + [self.counts[b] for b in BUTTONS] + [round(sx, 3), round(sy, 3)]

    def take_menu(self):
        m = self.menu_presses
        self.menu_presses = []
        return m


TOUCH_SEEN = [0.0]     # time of the last real finger event (phones send fake mouse clicks for every tap)


class KeyboardDevice(Device):
    kind = "keyboard"

    def __init__(self, layout):
        super().__init__()
        self.layout = layout
        self.name = layout["name"]
        self.keymap = {}
        for b in BUTTONS:
            for k in layout[b]:
                self.keymap[k] = b
        self.menu_keys = {}
        for d in ("up", "down", "left", "right"):
            for k in layout[d]:
                self.menu_keys[k] = d
        for b in layout.get("menu_ok", ["atk"]):
            for k in layout[b]:
                self.menu_keys[k] = "ok"
        for b in layout.get("menu_back", ["spc"]):
            for k in layout[b]:
                self.menu_keys[k] = "back"
        self.mouse = layout.get("mouse", {})

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and self.mouse:
            if TOUCH_UI and (getattr(e, "touch", False) or TOUCH_SEEN[0] > 0):
                return False          # a finger, not a real mouse
            b = self.mouse.get(e.button)
            if b:
                self.press(b)
                if not TOUCH_UI:      # in the touch UI, clicks on menus are 'taps' instead
                    if e.button == 1:
                        self.menu_presses.append("ok")
                    elif e.button == 3:
                        self.menu_presses.append("back")
                return True
            return False
        if e.type == pygame.KEYDOWN:
            b = self.keymap.get(e.key)
            if b:
                self.press(b)
            m = self.menu_keys.get(e.key)
            if m:
                self.menu_presses.append(m)
            return bool(b or m)
        return False

    def owns_key(self, key):
        return key in self.keymap or key in self.menu_keys

    def read(self):
        keys = pygame.key.get_pressed()

        def down(name):
            return any(keys[k] for k in self.layout[name])
        x = (1.0 if down("right") else 0.0) - (1.0 if down("left") else 0.0)
        y = (1.0 if down("down") else 0.0) - (1.0 if down("up") else 0.0)
        held = {b for b in BUTTONS if down(b)}
        if self.mouse and not TOUCH_SEEN[0]:
            try:
                mb = pygame.mouse.get_pressed()
                for btn, name in self.mouse.items():
                    if btn - 1 < len(mb) and mb[btn - 1]:
                        held.add(name)
            except pygame.error:
                pass
        return x, y, held, 0.0, 0.0


class GamepadDevice(Device):
    """Xbox-style layout (works for most pads through SDL)."""
    kind = "gamepad"
    BTN = {0: "atk", 1: "spc", 2: "jump", 3: "jump", 4: "grb", 5: "shd"}

    def __init__(self, joystick):
        super().__init__()
        self.js = joystick
        self.instance_id = joystick.get_instance_id() if hasattr(joystick, "get_instance_id") else joystick.get_id()
        self.name = "Gamepad %d" % (joystick.get_id() + 1)
        self.trig = [False, False]
        self.last_menu_axis = (0, 0)

    def matches(self, e):
        iid = getattr(e, "instance_id", getattr(e, "joy", None))
        return iid == self.instance_id

    def handle_event(self, e):
        if e.type == pygame.JOYBUTTONDOWN and self.matches(e):
            b = self.BTN.get(e.button)
            if b:
                self.press(b)
            if e.button == 0:
                self.menu_presses.append("ok")
            elif e.button == 1:
                self.menu_presses.append("back")
            elif e.button == 7:
                self.menu_presses.append("start")
            elif e.button == 3:
                self.menu_presses.append("cpu")
            return True
        if e.type == pygame.JOYHATMOTION and self.matches(e):
            hx, hy = e.value
            if hx:
                self.menu_presses.append("right" if hx > 0 else "left")
            if hy:
                self.menu_presses.append("up" if hy > 0 else "down")
            return True
        if e.type == pygame.JOYAXISMOTION and self.matches(e):
            if e.axis in (4, 5):   # triggers = shield
                pressed = e.value > 0.3
                i = e.axis - 4
                if pressed and not self.trig[i]:
                    self.press("shd")
                self.trig[i] = pressed
            elif e.axis in (0, 1):
                ax = self._axis(0)
                ay = self._axis(1)
                mx = 1 if ax > 0.7 else -1 if ax < -0.7 else 0
                my = 1 if ay > 0.7 else -1 if ay < -0.7 else 0
                if (mx, my) != self.last_menu_axis:
                    if mx and mx != self.last_menu_axis[0]:
                        self.menu_presses.append("right" if mx > 0 else "left")
                    if my and my != self.last_menu_axis[1]:
                        self.menu_presses.append("down" if my > 0 else "up")
                    self.last_menu_axis = (mx, my)
            return True
        return False

    def _axis(self, i):
        try:
            return self.js.get_axis(i) if self.js.get_numaxes() > i else 0.0
        except pygame.error:
            return 0.0

    def read(self):
        x, y = self._axis(0), self._axis(1)
        try:
            if self.js.get_numhats() > 0:
                hx, hy = self.js.get_hat(0)
                if hx:
                    x = float(hx)
                if hy:
                    y = float(-hy)
        except pygame.error:
            pass
        held = set()
        try:
            for i, b in self.BTN.items():
                if self.js.get_numbuttons() > i and self.js.get_button(i):
                    held.add(b)
        except pygame.error:
            pass
        if self.trig[0] or self.trig[1]:
            held.add("shd")
        sx, sy = self._axis(2), self._axis(3)
        if abs(sx) < 0.3:
            sx = 0.0
        if abs(sy) < 0.3:
            sy = 0.0
        return x, y, held, sx, sy


# ---------------------------------------------------------------- touch screen
# Right-hand button cluster (screen coordinates, 1280x720 logical): name -> (x, y, radius, label)
TOUCH_BUTTONS = {
    "atk":  (1062, 646, 60, "ATK"),
    "jump": (1196, 610, 58, "JUMP"),
    "spc":  (1112, 512, 52, "SPC"),
    "shd":  (1228, 470, 42, "SHLD"),
    "grb":  (952, 664, 40, "GRAB"),
    "sms":  (990, 548, 40, "SMASH"),
}
TOUCH_COLORS = {"atk": (235, 90, 90), "jump": (90, 170, 235), "spc": (245, 190, 60), "shd": (150, 120, 220),
                "grb": (90, 190, 120), "sms": (240, 130, 60)}
PAUSE_BUTTON = (44, 44, 30)
import os as _os
MOUSE_IS_TOUCH = _os.environ.get("SDL_MOUSE_TOUCH_EVENTS") == "1"   # PC testing: the mouse pretends to be a finger
STICK_RADIUS = 90


class TouchDevice(Device):
    """On-screen controller: a floating stick on the left half, buttons on the right."""
    kind = "touch"

    def __init__(self):
        super().__init__()
        self.name = "Touch"
        self.fingers = {}          # finger id -> "stick" / button name / "pause"
        self.stick_origin = None
        self.stick_pos = None
        self.active = False        # becomes True the first time the screen is touched (laptops never see the buttons)
        self.pause_req = False
        self.visible = MOUSE_IS_TOUCH

    @staticmethod
    def to_screen(e):
        return e.x * WIDTH, e.y * HEIGHT

    def button_at(self, x, y):
        best, bd = None, 1e9
        for name, (bx, by, r, _) in TOUCH_BUTTONS.items():
            d = math.hypot(x - bx, y - by)
            if d <= r * 1.18 and d < bd:
                best, bd = name, d
        return best

    def handle_event(self, e):
        if e.type not in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            return False
        self.active = True
        self.visible = True
        TOUCH_SEEN[0] = time.time()
        x, y = self.to_screen(e)
        fid = e.finger_id
        if e.type == pygame.FINGERDOWN:
            if math.hypot(x - PAUSE_BUTTON[0], y - PAUSE_BUTTON[1]) <= PAUSE_BUTTON[2] * 1.3:
                self.fingers[fid] = "pause"
                self.pause_req = True
                return True
            b = self.button_at(x, y)
            if b:
                self.fingers[fid] = b
                self.press(b)
                return True
            if x < WIDTH * 0.5 and "stick" not in self.fingers.values():
                self.fingers[fid] = "stick"
                self.stick_origin = (x, y)
                self.stick_pos = (x, y)
            return True
        if e.type == pygame.FINGERMOTION:
            if self.fingers.get(fid) == "stick":
                self.stick_pos = (x, y)
            return True
        # finger lifted
        what = self.fingers.pop(fid, None)
        if what == "stick":
            self.stick_origin = self.stick_pos = None
        return True

    def stick(self):
        if not self.stick_origin:
            return 0.0, 0.0
        dx = (self.stick_pos[0] - self.stick_origin[0]) / STICK_RADIUS
        dy = (self.stick_pos[1] - self.stick_origin[1]) / STICK_RADIUS
        n = math.hypot(dx, dy)
        if n > 1.0:
            dx, dy = dx / n, dy / n
        return dx, dy

    def read(self):
        x, y = self.stick()
        held = {v for v in self.fingers.values() if v in BUTTONS}
        return x, y, held, 0.0, 0.0

    def draw(self, surf):
        """Semi-transparent controller overlay."""
        if not self.visible:
            return
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # stick
        if self.stick_origin:
            ox, oy = self.stick_origin
            px, py = self.stick_pos
        else:
            ox, oy = 170, 570
            px, py = ox, oy
        pygame.draw.circle(layer, (255, 255, 255, 60), (int(ox), int(oy)), STICK_RADIUS)
        pygame.draw.circle(layer, (255, 255, 255, 150), (int(ox), int(oy)), STICK_RADIUS, 3)
        dx, dy = px - ox, py - oy
        n = math.hypot(dx, dy)
        if n > STICK_RADIUS:
            px, py = ox + dx / n * STICK_RADIUS, oy + dy / n * STICK_RADIUS
        pygame.draw.circle(layer, (255, 255, 255, 170), (int(px), int(py)), 38)
        pygame.draw.circle(layer, (60, 40, 35, 200), (int(px), int(py)), 38, 3)
        # buttons
        held = set(self.fingers.values())
        for name, (bx, by, r, label) in TOUCH_BUTTONS.items():
            col = TOUCH_COLORS[name]
            on = name in held
            pygame.draw.circle(layer, col + ((220 if on else 120),), (bx, by), r)
            pygame.draw.circle(layer, (255, 255, 255, 220), (bx, by), r, 3)
        # pause
        pygame.draw.circle(layer, (255, 255, 255, 140), PAUSE_BUTTON[:2], PAUSE_BUTTON[2])
        surf.blit(layer, (0, 0))
        from .render import text   # (late import to avoid a cycle)
        for name, (bx, by, r, label) in TOUCH_BUTTONS.items():
            text(surf, label, 16 if r > 45 else 13, (255, 255, 255), (bx, by), outline=(60, 40, 35), ow=2)
        x, y = PAUSE_BUTTON[:2]
        pygame.draw.rect(surf, (60, 40, 35), pygame.Rect(x - 9, y - 11, 6, 22))
        pygame.draw.rect(surf, (60, 40, 35), pygame.Rect(x + 3, y - 11, 6, 22))


class MergedDevice(Device):
    """'You' in the touch UI: the touch controls AND keyboard/mouse together, so a phone or a laptop
    (or a laptop with a touchscreen) all drive the same player."""
    kind = "merged"

    def __init__(self, subs):
        super().__init__()
        self.subs = subs
        self.name = "You"

    def handle_event(self, e):
        return False

    def read(self):
        x = y = sx = sy = 0.0
        held = set()
        for d in self.subs:
            dx, dy, h, ax, ay = d.read()
            if abs(dx) > abs(x):
                x = dx
            if abs(dy) > abs(y):
                y = dy
            if ax or ay:
                sx, sy = ax, ay
            held |= h
        return x, y, held, sx, sy

    def raw(self):
        r = Device.raw(self)
        for i, b in enumerate(BUTTONS):
            r[3 + i] = sum(d.counts[b] for d in self.subs)
        return r

    def take_menu(self):
        out = []
        for d in self.subs:
            out += d.take_menu()
        return out


class DeviceManager:
    def __init__(self):
        self.kb1 = KeyboardDevice(KEYBOARD_1)
        self.kb2 = KeyboardDevice(KEYBOARD_2)
        self.touch = TouchDevice()
        self.you = MergedDevice([self.touch, self.kb1])
        self.taps = []            # screen positions tapped this frame (for menus)
        self.last_finger = 0.0
        self.pads = {}
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            self.add_pad(i)

    def add_pad(self, index):
        try:
            js = pygame.joystick.Joystick(index)
            js.init()
            d = GamepadDevice(js)
            self.pads[d.instance_id] = d
        except pygame.error:
            pass

    @property
    def all(self):
        return [self.kb1, self.kb2, self.touch] + list(self.pads.values())

    def take_taps(self):
        t = self.taps
        self.taps = []
        return t

    def handle_event(self, e):
        # taps for menus: real fingers, or mouse clicks when testing the touch UI on a PC
        if e.type == pygame.FINGERDOWN:
            self.taps.append((e.x * WIDTH, e.y * HEIGHT))
            self.last_finger = time.time()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and TOUCH_UI and not MOUSE_IS_TOUCH:
            if not getattr(e, "touch", False) and time.time() - self.last_finger > 0.5:
                self.taps.append(e.pos)
        if e.type == getattr(pygame, "JOYDEVICEADDED", -1):
            self.add_pad(e.device_index)
            return
        if e.type == getattr(pygame, "JOYDEVICEREMOVED", -1):
            self.pads.pop(e.instance_id, None)
            return
        for d in self.all:
            d.handle_event(e)

    def clear_menu(self):
        for d in self.all:
            d.menu_presses = []
        self.taps = []
