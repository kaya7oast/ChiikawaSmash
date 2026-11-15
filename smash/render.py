"""Draws a game snapshot with pygame. Everything is procedural apart from the character pictures."""
import json
import math
import os
import random

import pygame

from . import characters
from .characters import hb_pos
from .sim import ARTS
from .config import WIDTH, HEIGHT, ASSET_DIR, WHITE, BLACK, INK, CREAM, TOUCH_UI
from .stages import STAGES, main_poly, ISLAND_EXTRA

# Hit sparks: True = animated sprite sheets in assets/fx (Sinestesia "Hit Animation 2", CC0),
# False = the old shapes drawn in code.
FX_SPRITES = True
HUD_H = 108
HUD_TOP = TOUCH_UI          # touch controls live at the bottom, so the damage cards go to the top
VIEW_CY = (HUD_H + (HEIGHT - HUD_H) / 2) if HUD_TOP else (HEIGHT - HUD_H) / 2   # screen y the camera centres on
_FONT_CACHE = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = pygame.font.SysFont("arialroundedmtbold,arialblack,verdana,arial", size, bold=bold)
        except Exception:
            _FONT_CACHE[key] = pygame.font.Font(None, int(size * 1.3))
    return _FONT_CACHE[key]


def text(surf, s, size, col, pos, anchor="center", outline=None, ow=2):
    f = font(size)
    img = f.render(str(s), True, col)
    r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if outline:
        o = f.render(str(s), True, outline)
        for dx in range(-ow, ow + 1, ow):
            for dy in range(-ow, ow + 1, ow):
                if dx or dy:
                    surf.blit(o, r.move(dx, dy))
    surf.blit(img, r)
    return r


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def damage_color(d):
    stops = [(0, (255, 255, 255)), (40, (255, 236, 150)), (80, (255, 170, 80)), (120, (240, 80, 60)), (170, (160, 20, 30))]
    for (d0, c0), (d1, c1) in zip(stops, stops[1:]):
        if d <= d1:
            return mix(c0, c1, (d - d0) / (d1 - d0))
    return stops[-1][1]


# ------------------------------------------------------------------ images
class Images:
    def __init__(self):
        self.base = {}
        self.cache = {}
        for key, c in characters.CHARACTERS.items():
            self.base[key] = self._load(c["image"])
        self.claw = self._load("Kani_crabclaw")
        self.dekatsuyo = self._load("dekatsuyo")
        # hands / feet cropped from each character's own art (assets/parts)
        self.parts, self.meta = {}, {}
        try:
            with open(os.path.join(ASSET_DIR, "parts", "meta.json")) as fh:
                self.meta = json.load(fh)
        except Exception:
            self.meta = {}
        for key in characters.CHARACTERS:
            for kind in ("hand", "foot"):
                img = self._load(os.path.join("parts", "%s_%s" % (kind, key)))
                if img is not None:
                    self.parts[(key, kind)] = img
        self.part_cache = {}
        # hit-spark sheets: 4x4 grid of 192px frames (loaded raw, not trimmed, so the grid stays intact)
        self.fx_sheets = {}
        for name in ("white", "yellow"):
            path = os.path.join(ASSET_DIR, "fx", "hit_%s.png" % name)
            try:
                sheet = pygame.image.load(path).convert_alpha()
                fw = sheet.get_width() // 4
                self.fx_sheets[name] = [sheet.subsurface(pygame.Rect((i % 4) * fw, (i // 4) * fw, fw, fw)).copy()
                                        for i in range(16)]
            except (pygame.error, FileNotFoundError, OSError):
                pass
        self.fx_cache = {}
        self.poses = {}
        pdir = os.path.join(ASSET_DIR, "poses")
        if os.path.isdir(pdir):
            for fn in os.listdir(pdir):
                if fn.endswith(".png"):
                    img = self._load(os.path.join("poses", fn[:-4]))
                    if img is not None:
                        self.poses[fn[:-4]] = img

    def fx_frame(self, sheet, frame, size, rot):
        frames = self.fx_sheets.get(sheet)
        if not frames:
            return None
        size = max(8, int(size) // 8 * 8)
        rot = int(rot) // 15 * 15
        ck = (sheet, frame, size, rot)
        s = self.fx_cache.get(ck)
        if s is None:
            s = pygame.transform.smoothscale(frames[frame], (size, size))
            if rot:
                s = pygame.transform.rotate(s, rot)
            if len(self.fx_cache) > 500:
                self.fx_cache.clear()
            self.fx_cache[ck] = s
        return s

    def pose(self, name, height, flip=False):
        base = self.poses.get(name)
        if base is None:
            return None
        height = max(6, int(height) // 2 * 2)
        ck = ("pose", name, height, flip)
        s = self.cache.get(ck)
        if s is None:
            w = max(4, int(base.get_width() * height / base.get_height()))
            s = pygame.transform.smoothscale(base, (w, height))
            if flip:
                s = pygame.transform.flip(s, True, False)
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[ck] = s
        return s

    def part(self, key, kind, char_h_px, angle):
        """A hand/foot sprite scaled to the character's on-screen size and rotated to point along `angle`
        (screen degrees, y down). Returns None if this character has no cropped part."""
        img = self.parts.get((key, kind))
        if img is None:
            return None
        m = self.meta.get(key, {})
        src_h = m.get("src_h", 280)
        base_dir = m.get(kind + "_dir", 40) if kind == "hand" else 90.0
        scale = char_h_px / float(src_h) * (1.45 if kind == "hand" else 1.3)
        size = max(4, int(img.get_height() * scale))
        rot = int(round((base_dir - angle) / 6.0)) * 6
        ck = (key, kind, size, rot)
        s = self.part_cache.get(ck)
        if s is None:
            w = max(3, int(img.get_width() * scale))
            s = pygame.transform.rotate(pygame.transform.smoothscale(img, (w, size)), rot)
            if len(self.part_cache) > 600:
                self.part_cache.clear()
            self.part_cache[ck] = s
        return s

    def _load(self, name):
        for ext in (".png", ".webp", ".jpg"):
            p = os.path.join(ASSET_DIR, name + ext)
            if os.path.exists(p):
                try:
                    img = pygame.image.load(p).convert_alpha()
                    r = img.get_bounding_rect(min_alpha=8)
                    if r.width > 4 and r.height > 4:
                        img = img.subsurface(r).copy()
                    return img
                except pygame.error:
                    pass
        return None

    def sprite(self, key, height, flip=False):
        """Character picture scaled to a height (cached, height rounded to 2px)."""
        height = max(6, int(height) // 2 * 2)
        ck = (key, height, flip)
        s = self.cache.get(ck)
        if s is None:
            base = self.base.get(key)
            if base is None:
                c = characters.CHARACTERS.get(key, {"color": (200, 200, 200)})
                base = pygame.Surface((80, 80), pygame.SRCALPHA)
                pygame.draw.circle(base, c["color"], (40, 40), 38)
                pygame.draw.circle(base, INK, (40, 40), 38, 4)
                self.base[key] = base
            w = max(4, int(base.get_width() * height / base.get_height()))
            s = pygame.transform.smoothscale(base, (w, height))
            if flip:
                s = pygame.transform.flip(s, True, False)
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[ck] = s
        return s

    def scaled(self, img, w, h):
        ck = (id(img), int(w), int(h))
        s = self.cache.get(ck)
        if s is None:
            s = pygame.transform.smoothscale(img, (max(2, int(w)), max(2, int(h))))
            self.cache[ck] = s
        return s


# ------------------------------------------------------------------ camera
class Camera:
    def __init__(self):
        self.x, self.y, self.z = 0.0, -150.0, 0.7
        self.shake_x = self.shake_y = 0.0

    def update(self, snap, instant=False):
        """Frame the fighters (not the whole stage) so characters stay big; zoom out as they spread apart."""
        st = STAGES[snap["stage"]]
        sx, sy, sw, sh = st["main"]
        l, t, r, b = st["blast"]
        xs, ys = [], []
        for f in snap["f"]:
            if f["al"] and not f["dd"]:
                h = characters.CHARACTERS[f["c"]]["h"]
                xs += [f["x"] - 140, f["x"] + 140]
                ys += [f["y"] - h - 120, f["y"] + 60]
        if not xs:
            xs, ys = [sx, sx + sw], [-300, 100]
        ys.append(sy + 150)                      # always show a bit of the ground
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        MIN_W, MIN_H = 860, 420                  # never zoom in further than this
        if maxx - minx < MIN_W:
            c = (minx + maxx) / 2
            minx, maxx = c - MIN_W / 2, c + MIN_W / 2
        if maxy - miny < MIN_H:
            c = (miny + maxy) / 2
            miny, maxy = c - MIN_H / 2, c + MIN_H / 2
        minx, maxx = max(minx, l + 40), min(maxx, r - 40)
        miny, maxy = max(miny, t + 40), min(maxy, b)
        view_h = HEIGHT - HUD_H
        z = min(WIDTH / max(1.0, maxx - minx), view_h / max(1.0, maxy - miny))
        z = max(0.3, min(1.5, z))
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        k = 1.0 if instant else 0.08
        self.x = lerp(self.x, cx, k)
        self.y = lerp(self.y, cy, k)
        self.z = lerp(self.z, z, k * 0.7)
        sh_ = snap.get("shake", 0)
        self.shake_x = random.uniform(-sh_, sh_) * 0.7
        self.shake_y = random.uniform(-sh_, sh_) * 0.7

    def pt(self, x, y):
        return ((x - self.x) * self.z + WIDTH / 2 + self.shake_x,
                (y - self.y) * self.z + VIEW_CY + self.shake_y)

    def s(self, v):
        return v * self.z


# ------------------------------------------------------------------ backgrounds
THEMES = {
    "day": {"sky": ((128, 196, 255), (232, 244, 255)), "hill1": (170, 220, 160), "hill2": (130, 195, 130),
            "grass": (126, 196, 96), "grass_hi": (170, 226, 130), "dirt": (196, 150, 110), "dirt_dk": (160, 115, 82),
            "plat": (255, 236, 205), "plat_dk": (214, 178, 140)},
    "night": {"sky": ((22, 26, 64), (78, 70, 130)), "hill1": (52, 60, 110), "hill2": (38, 44, 88),
              "grass": (90, 150, 120), "grass_hi": (140, 200, 165), "dirt": (110, 100, 130), "dirt_dk": (80, 72, 100),
              "plat": (200, 205, 235), "plat_dk": (140, 145, 185)},
    "sunset": {"sky": ((255, 150, 120), (255, 226, 170)), "hill1": (230, 150, 140), "hill2": (190, 110, 120),
               "grass": (150, 185, 90), "grass_hi": (200, 220, 120), "dirt": (205, 140, 95), "dirt_dk": (165, 105, 72),
               "plat": (255, 230, 200), "plat_dk": (215, 160, 125)},
}


class Background:
    def __init__(self, theme):
        self.theme = theme
        self.th = THEMES[theme]
        top, bot = self.th["sky"]
        self.sky = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            pygame.draw.line(self.sky, mix(top, bot, y / HEIGHT), (0, y), (WIDTH, y))
        rng = random.Random(3)
        self.stars = [(rng.randint(0, WIDTH), rng.randint(0, HEIGHT // 2), rng.random()) for _ in range(90)]
        self.clouds = [(rng.uniform(0, 3000), rng.uniform(40, 260), rng.uniform(0.6, 1.4)) for _ in range(7)]
        self.t = 0

    def draw(self, surf, cam):
        self.t += 1
        surf.blit(self.sky, (0, 0))
        th = self.th
        if self.theme == "night":
            for x, y, b in self.stars:
                tw = 0.5 + 0.5 * math.sin(self.t * 0.05 + b * 20)
                c = int(150 + 100 * tw)
                surf.set_at((x, y), (c, c, c))
                if b > 0.85:
                    pygame.draw.circle(surf, (c, c, 255), (x, y), 2)
            pygame.draw.circle(surf, (255, 248, 220), (WIDTH - 200, 120), 54)
            pygame.draw.circle(surf, mix(th["sky"][0], (255, 248, 220), 0.15), (WIDTH - 178, 104), 50)
        elif self.theme == "sunset":
            pygame.draw.circle(surf, (255, 240, 200), (WIDTH // 2 + 220, 330), 90)
            pygame.draw.circle(surf, (255, 210, 150), (WIDTH // 2 + 220, 330), 90, 6)
        else:
            pygame.draw.circle(surf, (255, 250, 220), (180, 110), 46)
        if self.theme != "night":
            for i, (cx, cy, s) in enumerate(self.clouds):
                x = (cx + self.t * 0.25 * s - cam.x * 0.05) % (WIDTH + 400) - 200
                for dx, dy, r in ((0, 0, 34), (36, 8, 28), (-34, 10, 26), (12, 16, 30)):
                    pygame.draw.circle(surf, (255, 255, 255), (int(x + dx * s), int(cy + dy * s)), int(r * s))
        # parallax hills
        base_y = HEIGHT * 0.62 - (cam.y + 150) * 0.08
        for layer, (col, par, amp, freq) in enumerate(((th["hill1"], 0.06, 50, 0.004), (th["hill2"], 0.12, 36, 0.007))):
            pts = [(0, HEIGHT)]
            off = cam.x * par
            for x in range(0, WIDTH + 41, 40):
                y = base_y + layer * 50 + math.sin((x + off) * freq + layer) * amp + math.sin((x + off) * freq * 2.7) * amp * 0.3
                pts.append((x, y))
            pts.append((WIDTH, HEIGHT))
            pygame.draw.polygon(surf, col, pts)
        if self.theme == "sunset":   # weed silhouettes
            for i in range(0, WIDTH, 26):
                hgt = 30 + (i * 37) % 50
                x = i - (cam.x * 0.2) % 26
                y = HEIGHT * 0.78
                pygame.draw.line(surf, (150, 90, 100), (x, y), (x + 6 * math.sin(self.t * 0.02 + i), y - hgt), 3)


def draw_stage(surf, cam, stage, th):
    sx, sy, sw, sh = stage["main"]
    x0, y0 = cam.pt(sx, sy)
    x1, _ = cam.pt(sx + sw, sy)
    depth = cam.s(sh + ISLAND_EXTRA)
    body = [cam.pt(px, py) for px, py in main_poly(stage)]     # exactly the collision shape
    pygame.draw.polygon(surf, th["dirt"], body)
    for k in range(1, 4):  # stripes of darker dirt
        yy = y0 + depth * k * 0.22
        pygame.draw.line(surf, th["dirt_dk"], (x0 + cam.s(40 + k * 30), yy), (x1 - cam.s(40 + k * 30), yy), max(1, int(cam.s(5))))
    pygame.draw.polygon(surf, INK, body, max(2, int(cam.s(5))))
    gh = max(6, int(cam.s(22)))
    grass = pygame.Rect(int(x0 - cam.s(6)), int(y0 - cam.s(4)), int(x1 - x0 + cam.s(12)), gh)
    pygame.draw.rect(surf, th["grass"], grass, border_radius=max(2, gh // 2))
    pygame.draw.rect(surf, th["grass_hi"], grass.inflate(-gh, -gh * 0.6).move(0, -gh * 0.15), border_radius=max(2, gh // 3))
    pygame.draw.rect(surf, INK, grass, max(2, int(cam.s(4))), border_radius=max(2, gh // 2))
    # little flowers / tufts along the top
    step = int(max(30, sw // 14))
    for i, xx in enumerate(range(int(sx + 30), int(sx + sw - 20), step)):
        px, py = cam.pt(xx, sy - 3)
        if i % 3 == 0:
            pygame.draw.circle(surf, (255, 200, 220), (int(px), int(py - cam.s(6))), max(2, int(cam.s(5))))
            pygame.draw.circle(surf, (255, 240, 160), (int(px), int(py - cam.s(6))), max(1, int(cam.s(2))))
        else:
            pygame.draw.line(surf, INK, (px, py), (px - cam.s(4), py - cam.s(12)), max(1, int(cam.s(2))))
            pygame.draw.line(surf, INK, (px, py), (px + cam.s(4), py - cam.s(10)), max(1, int(cam.s(2))))
    for (px, py, pw) in stage["platforms"]:
        a = cam.pt(px, py)
        b = cam.pt(px + pw, py)
        th_ = max(5, int(cam.s(16)))
        r = pygame.Rect(int(a[0]), int(a[1] - cam.s(2)), int(b[0] - a[0]), th_)
        pygame.draw.rect(surf, th["plat"], r, border_radius=th_ // 2)
        pygame.draw.rect(surf, th["plat_dk"], r.inflate(0, -th_ * 0.5).move(0, th_ * 0.25), border_radius=th_ // 3)
        pygame.draw.rect(surf, INK, r, max(2, int(cam.s(3.5))), border_radius=th_ // 2)


# ------------------------------------------------------------------ fighter animation
# ---------------------------------------------------------------- pose sprites
# Whole-body pictures cut from the anime/wiki art for a few signature moves (assets/poses).
# Each rule gives (image, flip, height scale vs the normal sprite, body-centre x as a fraction of the image).
def pose_for(f):
    if f["st"] != "attack" or not f["mv"]:
        return None
    ck, mv, mf, face = f["c"], f["mv"], f["mf"], f["fa"]
    if ck == "chiikawa":
        if mv == "bair":                         # swats behind him (art swats to the left)
            return ("chii_bair", face < 0, 1.18, 0.62)
        if mv in ("sspec", "onslaught"):         # flailing barrage (art swats to the left)
            return ("chii_swat", face > 0, 1.12, 0.5)
        if mv == "nair":                         # happy wiggle, flipping left/right
            return ("chii_float", (mf // 6) % 2 == 1, 1.08, 0.5)
    elif ck == "hachiware" and mv == "sspec":    # tail spin: front, back, front (flipped), back (flipped)
        k = (mf // 4) % 4
        name = "hachi_spin_front" if k % 2 == 0 else "hachi_spin_back"
        fl = (k >= 2) != (face < 0)
        return (name, fl, 1.0, 0.36 if name == "hachi_spin_front" else 0.33)
    elif ck == "momonga":
        if mv == "nspec":
            return ("momo_counter", face < 0, 1.2, 0.5)
        if mv == "counter_hit":                  # Kani dragging Momonga out of harm's way
            return ("kani_protect", face < 0, 1.05, 0.42)
    elif ck == "kurimanju" and mv == "dspec":
        return ("kuri_drink" if mf < 32 else "kuri_ahh", face < 0, 1.0, 0.5)
    elif ck == "kani" and mv == "dspec":
        return ("kani_read", face < 0, 1.0, 0.5)
    return None


def body_pose(f, move):
    """Returns (scale_x, scale_y, rotation_deg_forward, offset_forward, offset_up). Positive rotation = lean forward."""
    st, sf = f["st"], f["sf"]
    t = sf
    sx = sy = 1.0
    rot = ox = oy = 0.0
    if st == "idle":
        sy = 1.0 + 0.025 * math.sin(t * 0.12)
        sx = 2.0 - sy
    elif st == "run":
        ph = t * 0.45
        oy = abs(math.sin(ph)) * 7
        rot = 9
        sy = 1.0 + 0.05 * math.cos(ph * 2)
        sx = 2.0 - sy
    elif st == "crouch":
        sy, sx = 0.72, 1.16
    elif st == "jumpsquat":
        sy, sx = 0.78, 1.18
    elif st in ("land",):
        k = max(0.0, 1.0 - sf / 6.0)
        sy, sx = 1.0 - 0.2 * k, 1.0 + 0.16 * k
    elif st == "air":
        vy = f["vy"]
        if vy < 0:
            sy = 1.0 + min(0.14, -vy * 0.01)
            sx = 2.0 - sy
        if f.get("dj", 0) > 0:
            rot = -360 * (1 - f["dj"] / 14.0)      # backflip on double jump
        if f["tu"]:
            rot = f["sp"]
    elif st == "hitstun":
        if f["tu"]:
            rot = f["sp"] * 1.0
        else:
            rot = -14
            ox = -4
    elif st == "knockdown":
        rot, sy, oy = -90, 1.0, -f_h(f) * 0.0
    elif st == "getup":
        rot = -90 * max(0.0, 1 - sf / 10.0)
    elif st in ("shield", "shieldstun"):
        sy, sx = 0.92, 1.05
    elif st == "roll":
        rot = -(sf / 30.0) * 360
    elif st == "spotdodge":
        sx = 1.0 - 0.25 * math.sin(min(1.0, sf / 26.0) * math.pi)
    elif st == "airdodge":
        rot = 0
    elif st in ("helpless",):
        rot = math.sin(t * 0.3) * 6
        sy = 1.05
    elif st == "glide":
        rot = 20
        sx, sy = 1.3, 0.8
    elif st == "parachute":
        rot = math.sin(t * 0.08) * 6
    elif st == "sleep":
        rot = -14
        sy, sx = 0.9 + 0.03 * math.sin(t * 0.08), 1.05
    elif st == "ledge":
        rot = 12
    elif st == "dizzy":
        rot = math.sin(t * 0.15) * 12
    elif st == "grabbed":
        rot = -10 + math.sin(t * 0.8) * 4
        sy = 0.95
    elif st == "holding":
        rot = 6
        ox = 4
    elif st == "tech":
        rot = -(sf / 20.0) * 360 if sf < 20 else 0
    elif st == "attack" and move:
        m = move
        p = f["mf"] / max(1, m["frames"])
        hits = m.get("hits", [])
        a = hits[0]["f"][0] if hits else int(m["frames"] * 0.3)
        b = hits[-1]["f"][1] if hits else a + 3
        mf = f["mf"]
        pre = min(1.0, mf / max(1, a))                     # wind-up 0..1
        act = a <= mf <= b + 2
        post = max(0.0, (mf - b) / max(1, m["frames"] - b))
        an = m.get("anim", "jab")
        if an in ("jab", "jab2", "jab3", "ftilt", "throw_fwd", "spit", "snip", "pummel", "fthrow", "grab"):
            rot = (-6 * pre if not act else 16) * (1 - post)
            ox = (10 if act else -3 * pre) * (1 - post)
            if an == "jab3" and act:
                rot, ox = 22, 14
        elif an in ("fsmash", "fair"):
            if mf < a:
                rot, ox = -18 * pre, -8 * pre
            else:
                rot, ox = 30 * (1 - post), 18 * (1 - post)
            if f.get("ch"):
                ox += random.uniform(-2, 2)
        elif an in ("utilt", "usmash", "uair", "uthrow", "rise"):
            if mf < a:
                sy, sx = 1.0 - 0.2 * pre, 1.0 + 0.15 * pre
            else:
                sy, sx = 1.0 + 0.2 * (1 - post), 1.0 - 0.12 * (1 - post)
                oy = 8 * (1 - post)
            if an == "uair" and act:
                rot = -360 * ((mf - a) / max(1, b - a + 3))
        elif an in ("dtilt", "dsmash", "dthrow", "land_slam"):
            sy, sx = 1.0 - 0.28 * (1 - post), 1.0 + 0.22 * (1 - post)
            if an == "dtilt":
                ox = 8 * (1 - post)
        elif an == "dash":
            rot, ox = 28 * (1 - post), 10 * (1 - post)
        elif an in ("nair", "copter", "crazy"):
            if act or an != "nair":
                rot = -(mf * (24 if an != "nair" else 30)) % 360
        elif an == "bair":
            rot = -26 * (1 - post) if mf >= a else 6 * pre
            ox = -12 * (1 - post) if mf >= a else 0
        elif an in ("dair", "flop", "guitar_slam"):
            if an == "flop":
                rot = 90 * min(1.0, mf / 14.0)
            sy, sx = (1.12, 0.92) if mf >= a else (1.0 - 0.1 * pre, 1.0)
        elif an == "bthrow":
            rot = -360 * min(1.0, mf / max(1, m.get("throw", (12,))[0]))
        elif an in ("cry",):
            ox = math.sin(mf * 1.7) * 3
            sy = 0.94
        elif an in ("burp", "scream", "guitar"):
            k = math.sin(min(1.0, mf / max(1, a + 4)) * math.pi)
            sx, sy = 1.0 + 0.16 * k, 1.0 + 0.1 * k
            rot = -8 * pre if mf < a else 10 * (1 - post)
        elif an in ("eat", "drink", "read", "summon"):
            oy = abs(math.sin(mf * 0.35)) * 6
            rot = math.sin(mf * 0.2) * 6
        elif an == "slide":
            rot = 70 * (1 - post) if mf >= 4 else 0
            oy = -10 * (1 - post) if mf >= 4 else 0
        elif an == "charge":
            rot, ox = 24, 6
        elif an == "rapid":
            rot = 12 + math.sin(mf * 1.8) * 8
            ox = 6 + math.sin(mf * 1.8) * 4
        elif an in ("nair_still", "uair_still"):
            k = 1.0 if act else 0.0
            sy, sx = 1.0 + 0.06 * k, 1.0 - 0.04 * k
            rot = 6 * k if an == "nair_still" else -4 * k
        elif an == "pogo":
            sy, sx = 1.15, 0.9
        elif an == "flip":
            rot = -(mf * 22) % 360 if mf < 30 else 0
        elif an == "nibble":
            oy = abs(math.sin(mf * 0.5)) * 5
            rot = math.sin(mf * 0.5) * 8
        elif an == "summon_down":
            sy, sx = (0.85, 1.12) if mf < 10 else (1.0, 1.0)
        elif an == "tether":
            rot = -12
        elif an == "tatsu":
            rot = -(mf * 26) % 360 if 6 <= mf <= 38 else 0
        elif an == "shoryu":
            rot = 22 if mf < 4 else -12 + (mf - 4) * 0.6 if mf < 30 else 0
            sy, sx = (0.86, 1.1) if mf < 4 else (1.12, 0.92)
        elif an == "trampoline":
            sy, sx = (0.7, 1.25) if mf < 4 else (1.15, 0.9)
        elif an == "flail":
            ox = math.sin(mf * 1.9) * 4
            rot = math.sin(mf * 1.3) * 14
        elif an == "art":
            k = math.sin(min(1.0, mf / 12.0) * math.pi)
            sy, sx = 1.0 + 0.1 * k, 1.0 - 0.05 * k
        elif an == "hold_out":
            rot = 8
        elif an == "teleport":
            sy, sx = (0.8, 1.15) if mf < 6 else (1.0, 1.0)
        elif an == "reflect":
            rot = -10 + math.sin(mf * 2.2) * 4
            sx = 1.08
    if f["hl"] > 0 and st == "hitstun":
        ox += random.uniform(-4, 4)
    return sx, sy, rot, ox, oy


def f_h(f):
    return characters.CHARACTERS[f["c"]]["h"]


# ------------------------------------------------------------------ limbs (fists / feet / grabbing hands)
LIMB_DEFAULT = {
    "jab1": "fist", "jab2": "fist", "jab3": "fist", "jab_rapid": "fists", "jab_fin": "fist", "ftilt": "fist",
    "fsmash": "fist", "utilt": "fist", "usmash": "fists", "dtilt": "foot", "dsmash": "feet", "dash": "body",
    "nair": "body", "fair": "fist", "bair": "foot", "uair": "foot", "dair": "feet", "grab": "grab",
    "pummel": "fist", "fthrow": "grab", "bthrow": "grab", "uthrow": "grab", "dthrow": "grab", "getup": "fist",
    "counter_hit": "fist", "crab_pinch": "grab",
}
LIMB_OVERRIDE = {
    "chiikawa": {"utilt": "head", "usmash": "head", "jab_fin": "head", "fair": "fists", "nair": "fists",
                 "dair": "feet", "sspec": "fist", "onslaught": "fists", "uspec": "body", "dspec": "body"},
    "hachiware": {"dash": "feet", "sspec": "body", "sspec_air": "body", "uspec": "fist", "dspec": "body", "nspec": "body"},
    "usagi": {"dair": "weapon", "uspec": "body"},
    "momonga": {"ftilt": "head", "fair": "foot", "jab_fin": "fist", "utilt": "foot", "dash": "body", "uair": "foot",
                "dsmash": "feet", "sspec": "grab", "nibble": "body", "dair": "body", "nspec": "body",
                "counter_hit": "body"},
    "kurimanju": {"jab1": "body", "jab2": "body", "dash": "body", "bair": "body", "uair": "head", "nair": "body",
                  "usmash": "fists", "dsmash": "fists"},
    "kani": {"uspec": "body", "dspec": "body", "tether_kick": "grab"},
}
LIMB_COLOR = {"chiikawa": (255, 255, 255), "hachiware": (255, 255, 255), "usagi": (252, 239, 202),
              "momonga": (255, 255, 255), "kurimanju": (252, 233, 203), "kani": (254, 238, 232)}


def limb_kind(char_key, move_name, move):
    if move.get("weapon"):
        return "weapon"
    k = LIMB_OVERRIDE.get(char_key, {}).get(move_name) or LIMB_DEFAULT.get(move_name)
    if k:
        return k
    # specials without an entry: punch if the hitbox is in front, nothing if it's around the body
    hits = move.get("hits", [])
    if hits and abs(hits[0]["x"]) > 20:
        return "fist" if hits[0]["y"] < 15 else "foot"
    return None


def draw_fist(surf, x, y, r, col):
    r = max(4, int(r))
    o = max(2, int(r * 0.28))
    pygame.draw.circle(surf, INK, (int(x), int(y)), r + o)
    pygame.draw.circle(surf, col, (int(x), int(y)), r)
    # knuckle lines so it reads as a fist, not a ball
    for k in (-1, 0, 1):
        kx = x + k * r * 0.38
        pygame.draw.line(surf, INK, (kx, y - r * 0.55), (kx, y - r * 0.1), max(1, int(r * 0.16)))


def draw_foot(surf, x, y, r, col, face):
    rw, rh = max(6, int(r * 1.7)), max(4, int(r * 1.1))
    rect = pygame.Rect(0, 0, rw, rh)
    rect.center = (int(x + face * r * 0.2), int(y))
    o = max(3, int(r * 0.5))
    pygame.draw.ellipse(surf, INK, rect.inflate(o, o))
    pygame.draw.ellipse(surf, col, rect)


def draw_arm(surf, a, b, w, col):
    w = max(3, int(w))
    pygame.draw.line(surf, INK, a, b, w + max(4, w // 2))
    pygame.draw.line(surf, col, a, b, w)


# ------------------------------------------------------------------ the renderer
class Renderer:
    def __init__(self):
        self.images = Images()
        self.cam = Camera()
        self.bgs = {}
        self.fx = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.prev_dmg = {}
        self.dmg_jiggle = {}
        self.stage_key = None
        self.letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
        self.flash = 0
        self.debug = False
        self.prev_move = {}
        self.callouts = []
        self.prev_art = {}

    def reset(self, snap):
        self.cam = Camera()
        self.cam.update(snap, instant=True)
        self.prev_dmg = {}
        self.dmg_jiggle = {}
        self.prev_move = {}
        self.callouts = []
        self.prev_art = {}

    def draw(self, surf, snap, local_slots=()):
        if self.stage_key != snap["stage"]:
            self.stage_key = snap["stage"]
            self.reset(snap)
        stage = STAGES[snap["stage"]]
        theme = stage["theme"]
        if theme not in self.bgs:
            self.bgs[theme] = Background(theme)
        bg = self.bgs[theme]
        self.cam.update(snap)
        cam = self.cam
        bg.draw(surf, cam)
        draw_stage(surf, cam, stage, bg.th)
        self.fx.fill((0, 0, 0, 0))

        fighters = sorted(snap["f"], key=lambda f: (f["st"] != "grabbed", f["hit"]))
        for f in fighters:
            if f["al"] and not f["dd"]:
                self.draw_shadow(surf, f, stage)
        for f in fighters:
            if f["al"] and not f["dd"]:
                self.draw_fighter(surf, f, snap)
        for p in snap["p"]:
            self.draw_projectile(surf, p, snap)
        for e in snap["e"]:
            self.draw_effect(surf, e)
        surf.blit(self.fx, (0, 0))
        if self.flash > 0:
            fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fl.fill((255, 255, 255, int(self.flash)))
            surf.blit(fl, (0, 0))
            self.flash = 0
        self.draw_callouts(surf, snap)
        if self.debug:
            self.draw_debug(surf, snap)
            text(surf, "F2: hitboxes on (yellow hurtbox, red hitbox, pink sweetspot, purple grab, cyan reflect/projectile)",
                 14, WHITE, (WIDTH / 2, 12), outline=BLACK, ow=1)
        for f in fighters:
            if f["al"] and not f["dd"]:
                self.draw_tag(surf, f)
        self.draw_offscreen(surf, snap)
        self.draw_hud(surf, snap, local_slots)
        self.draw_overlay(surf, snap)

    # ---------- fighters
    def draw_shadow(self, surf, f, stage):
        sx, sy, sw, sh = stage["main"]
        surfaces = [sy] if sx <= f["x"] <= sx + sw else []
        surfaces += [py for (px, py, pw) in stage["platforms"] if px <= f["x"] <= px + pw]
        below = [y for y in surfaces if y >= f["y"] - 2]
        if not below:
            return
        ground_y = min(below)
        dist = ground_y - f["y"]
        if dist > 500:
            return
        w = characters.CHARACTERS[f["c"]]["w"] * (1.0 - min(0.6, dist / 600))
        x, y = self.cam.pt(f["x"], ground_y)
        r = pygame.Rect(0, 0, max(4, int(self.cam.s(w))), max(2, int(self.cam.s(10))))
        r.center = (int(x), int(y))
        pygame.draw.ellipse(self.fx, (40, 30, 30, 70), r)

    def draw_fighter(self, surf, f, snap):
        cam = self.cam
        c = characters.CHARACTERS[f["c"]]
        move = c["moves"].get(f["mv"]) if f["st"] == "attack" and f["mv"] else None
        sx, sy, rot, ox, oy = body_pose(f, move)
        face = f["fa"]
        vis_h = c["h"] * 1.32
        H = cam.s(vis_h)
        pose = pose_for(f)
        pspr = self.images.pose(pose[0], H * pose[2], pose[1]) if pose else None
        self._posed = pspr is not None
        if pspr is not None:
            spr = pspr
            rot = 0.0 if pose[0] != "chii_bair" else rot * 0.5
            sx, sy = 1.0 + (sx - 1.0) * 0.5, 1.0 + (sy - 1.0) * 0.5
        else:
            spr = self.images.sprite(f["c"], H, flip=face < 0)
        w, h = spr.get_size()
        if abs(sx - 1) > 0.01 or abs(sy - 1) > 0.01:
            spr = pygame.transform.smoothscale(spr, (max(2, int(w * sx)), max(2, int(h * sy))))
        if f["hl"] > 0 and f["st"] == "hitstun":
            spr = spr.copy()
            spr.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
        if f.get("bf") and pspr is None:
            spr = spr.copy()
            spr.fill((50, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        if abs(rot) > 0.5:
            spr = pygame.transform.rotate(spr, -rot * face)
        if f["it"] and pspr is None:
            spr = spr.copy()
            spr.set_alpha(120)
        fx, fy = cam.pt(f["x"], f["y"])
        if move and move.get("teleport"):
            a_, b_, _ = move["teleport"]
            if a_ <= f["mf"] <= b_ + 1:          # vanished: just a trail of sparkles
                for i in range(4):
                    sx_ = fx + random.uniform(-1, 1) * cam.s(c["w"] * 0.6)
                    sy_ = fy - cam.s(c["h"] * 0.5) + random.uniform(-1, 1) * cam.s(c["h"] * 0.5)
                    star(self.fx, sx_, sy_, max(3, cam.s(8)), tuple(f["col"]) + (200,))
                return
        centre = (fx + cam.s(ox) * face, fy - h * sy / 2 - cam.s(oy) + cam.s(vis_h - c["h"]) * 0.12)
        # auras behind the body
        if f.get("art"):
            acol = ARTS[f["art"]]["col"]
            pulse = 0.5 + 0.5 * math.sin(snap["fr"] * 0.15)
            pygame.draw.circle(self.fx, acol + (int(50 + 40 * pulse),), (int(fx), int(fy - h * 0.45)), int(h * 0.62))
            pygame.draw.circle(self.fx, acol + (200,), (int(fx), int(fy - h * 0.45)), int(h * 0.62), max(2, int(cam.s(4))))
        if f.get("bf"):
            pygame.draw.circle(self.fx, (255, 80, 60, 70), (int(centre[0]), int(centre[1])), int(h * 0.62))
        if f.get("ch"):
            k = f["ch"] / 60.0
            pygame.draw.circle(self.fx, (255, 230, 90, int(60 + 80 * k)), (int(centre[0]), int(centre[1])),
                               int(h * (0.55 + 0.1 * math.sin(f["ch"]))), max(2, int(cam.s(4))))
        if f["iv"] and (snap["fr"] // 3) % 2 == 0:
            pygame.draw.circle(self.fx, (255, 255, 255, 90), (int(centre[0]), int(centre[1])), int(h * 0.6))
        if f["st"] == "respawn":
            r = pygame.Rect(0, 0, int(cam.s(110)), int(cam.s(22)))
            r.center = (int(fx), int(fy + cam.s(6)))
            pygame.draw.ellipse(surf, (255, 255, 255), r)
            pygame.draw.ellipse(surf, tuple(f["col"]), r, max(2, int(cam.s(4))))
        if self._posed:
            ax = 1.0 - pose[3] if pose[1] else pose[3]
            bx = centre[0] + (0.5 - ax) * spr.get_width()
            surf.blit(spr, spr.get_rect(center=(int(bx), int(centre[1]))))
            if move:
                self.draw_swooshes(f, c, move)
        else:
            self.draw_weapon(surf, f, c, move, centre, behind=True)
            surf.blit(spr, spr.get_rect(center=(int(centre[0]), int(centre[1]))))
            self.draw_weapon(surf, f, c, move, centre, behind=False)
            if move:
                self.draw_limbs(surf, f, c, move)
                self.draw_swooshes(f, c, move)
        if f["st"] == "holding" or (move and f["mv"] in ("pummel", "fthrow", "bthrow", "uthrow", "dthrow", "crab_pinch")):
            v = next((o for o in snap["f"] if o["st"] == "grabbed" and abs(o["x"] - f["x"]) < 140), None)
            if v is not None:
                vc = characters.CHARACTERS[v["c"]]
                local = ((v["x"] - f["x"]) * f["fa"], (v["y"] - vc["h"] / 2) - (f["y"] - c["h"] / 2))
                self.draw_grab_hands(surf, f, c, None, victim=local)
        if f["st"] in ("shield", "shieldstun"):
            k = max(0.15, f["sh"] / 50.0)
            rad = int(cam.s(c["h"] * 0.78) * (0.45 + 0.55 * k))
            col = tuple(f["col"])
            pygame.draw.circle(self.fx, (col[0], col[1], col[2], 95), (int(centre[0]), int(centre[1])), rad)
            pygame.draw.circle(self.fx, (255, 255, 255, 170), (int(centre[0]), int(centre[1])), rad, max(2, int(cam.s(4))))
        if f["c"] == "kani" and (f["st"] == "tether" or (move and move.get("tether"))):
            self.draw_tether(surf, f, c, move)
        self.draw_extras(surf, f, c, move, centre, h, snap)
        if f["st"] == "dizzy":
            for i in range(3):
                a = snap["fr"] * 0.12 + i * math.tau / 3
                px = centre[0] + math.cos(a) * cam.s(28)
                py = centre[1] - h * 0.55 + math.sin(a) * cam.s(8)
                star(surf, px, py, max(4, cam.s(9)), (255, 220, 60))
        if f["st"] == "glide" or f.get("gl"):
            # flying-squirrel membrane
            pts = [(centre[0] - cam.s(46), centre[1]), (centre[0], centre[1] - cam.s(10)),
                   (centre[0] + cam.s(46), centre[1]), (centre[0], centre[1] + cam.s(18))]
            pygame.draw.polygon(self.fx, (200, 230, 255, 120), pts)

    # ---------- weapons & swooshes (follow the real hitbox paths)
    def lpt(self, f, c, lx, ly):
        """Fighter-local point (x forward, y down, from the hurtbox centre) -> screen."""
        return self.cam.pt(f["x"] + lx * f["fa"], f["y"] - c["h"] / 2 + ly)

    def lead_hitbox(self, move, mf):
        hits = move.get("hits", [])
        if not hits:
            return None
        active = [h_ for h_ in hits if h_["f"][0] <= mf <= h_["f"][1]]
        pool = active or [h_ for h_ in hits if h_["f"][0] > mf][:1] or [max(hits, key=lambda h_: h_["f"][1])]
        pool = active or pool

        def reach(h_):
            if "arc" in h_:
                return h_["arc"][2] + 1000
            x, y = hb_pos(h_, h_["f"][1])
            return math.hypot(x, y)
        return max(pool, key=reach)

    def weapon_pose(self, f, c, move):
        """(pivot_local, angle_deg_forward_relative, length) of the held weapon for this frame."""
        mf = f["mf"]
        hb = self.lead_hitbox(move, mf)
        if hb is None:
            return (4, 0), -50, c["h"] * 0.7
        a, b = hb["f"]
        if "arc" in hb:
            cx, cy, rad, a0, a1 = hb["arc"]
            d = 1 if a1 >= a0 else -1
            if mf < a:
                k = mf / max(1.0, a)
                ang = a0 - d * 55 * (1 - k)
            elif mf <= b:
                ang = a0 + (a1 - a0) * (mf - a) / max(1.0, b - a)
            else:
                k = min(1.0, (mf - b) / 12.0)
                ang = a1 + (-60 - a1) * k if abs(a1 - a0) < 300 else a1
            return (cx, cy), ang, rad + hb["r"] * 0.45
        tx, ty = hb_pos(hb, min(max(mf, a), b))
        px, py = 4, -4
        ang = math.degrees(math.atan2(-(ty - py), tx - px))
        L = math.hypot(tx - px, ty - py) + hb["r"] * 0.5
        if mf < a:
            L *= 0.45 + 0.55 * mf / max(1.0, a)
        elif mf > b + 3:
            L *= max(0.5, 1.0 - (mf - b - 3) / 14.0)
        return (px, py), ang, L

    def draw_weapon(self, surf, f, c, move, centre, behind):
        cam = self.cam
        kind = (move or {}).get("weapon")
        face = f["fa"]
        if not kind:
            if behind and f["st"] in ("idle", "run", "air", "shield", "crouch", "land", "jumpsquat"):
                idle = {"usagi": "stick", "kurimanju": "stick", "hachiware": "guitar"}.get(f["c"])
                if idle:   # carried on the back
                    base = self.lpt(f, c, -c["w"] * 0.15, c["h"] * 0.1)
                    ang = math.radians(115)
                    tip = (base[0] + math.cos(ang) * face * cam.s(c["h"] * 0.75), base[1] - math.sin(ang) * cam.s(c["h"] * 0.75))
                    self._weapon_shape(surf, idle, base, tip, cam.s(c["h"] * 0.75), small=True)
            return
        if behind:
            return
        (px, py), ang, L = self.weapon_pose(f, c, move)
        base = self.lpt(f, c, px, py)
        rad = math.radians(ang)
        tip = (base[0] + math.cos(rad) * face * cam.s(L), base[1] - math.sin(rad) * cam.s(L))
        self._weapon_shape(surf, kind, base, tip, cam.s(L))
        if kind != "claw":   # their own little hand gripping the handle
            grip = (base[0] + (tip[0] - base[0]) * 0.08, base[1] + (tip[1] - base[1]) * 0.08)
            self.draw_part(surf, f, c, "hand", base, grip, 0.85)

    def _weapon_shape(self, surf, kind, base, tip, L, small=False):
        cam = self.cam
        dx, dy = tip[0] - base[0], tip[1] - base[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        if kind == "stick":
            back = (base[0] - ux * cam.s(10), base[1] - uy * cam.s(10))
            stick(surf, back, tip, cam.s(5 if small else 6))
        elif kind == "guitar":
            w = max(2, int(cam.s(4 if small else 5)))
            neck_end = (base[0] + dx * 0.5, base[1] + dy * 0.5)
            head = (base[0] - ux * cam.s(12), base[1] - uy * cam.s(12))
            pygame.draw.line(surf, INK, head, neck_end, w + 3)
            pygame.draw.line(surf, (150, 100, 60), head, neck_end, w)
            pygame.draw.circle(surf, INK, (int(head[0]), int(head[1])), max(3, int(cam.s(6))))
            for k_, rr in ((0.66, 0.2), (0.9, 0.26)):
                p_ = (base[0] + dx * k_, base[1] + dy * k_)
                r_ = max(4, int(n * rr * (0.75 if small else 1.0)))
                pygame.draw.circle(surf, INK, (int(p_[0]), int(p_[1])), r_ + 2)
                pygame.draw.circle(surf, (225, 85, 75), (int(p_[0]), int(p_[1])), r_)
            hole = (base[0] + dx * 0.8, base[1] + dy * 0.8)
            pygame.draw.circle(surf, (60, 40, 40), (int(hole[0]), int(hole[1])), max(2, int(n * 0.07)))
        elif kind == "weed":
            w = max(2, int(cam.s(4)))
            pygame.draw.line(surf, INK, base, tip, w + 3)
            pygame.draw.line(surf, (110, 170, 80), base, tip, w)
            for k_, sd in ((0.7, 1), (0.85, -1), (1.0, 1), (1.0, -1)):
                p_ = (base[0] + dx * k_, base[1] + dy * k_)
                lx, ly = p_[0] + (-uy * sd + ux) * cam.s(12), p_[1] + (ux * sd + uy) * cam.s(12)
                pygame.draw.line(surf, INK, p_, (lx, ly), w + 3)
                pygame.draw.line(surf, (130, 200, 90), p_, (lx, ly), w + 1)
        elif kind == "claw" and self.images.claw is not None:
            sz = max(8, cam.s(34))
            img = self.images.scaled(self.images.claw, sz * 1.3, sz)
            angd = math.degrees(math.atan2(-dy, dx))
            img = pygame.transform.rotate(img if dx >= 0 else pygame.transform.flip(img, False, True), angd)
            surf.blit(img, img.get_rect(center=(int(tip[0]), int(tip[1]))))

    def draw_swooshes(self, f, c, move):
        cam = self.cam
        face = f["fa"]
        mf = f["mf"]
        col = tuple(f["col"])
        for hb in move.get("hits", []):
            a, b = hb["f"]
            if not (a <= mf <= b + 4):
                continue
            fade = 1.0 if mf <= b else 1.0 - (mf - b) / 5.0
            alpha = max(0, int(200 * fade))
            kind = hb.get("fx", "swipe")
            lx, ly = hb_pos(hb, min(mf, b))
            hx, hy = self.lpt(f, c, lx, ly)
            r = cam.s(hb["r"])
            if kind == "arc" and "arc" in hb:
                cx, cy, rad, a0, a1 = hb["arc"]
                cur = a0 + (a1 - a0) * min(1.0, (mf - a) / max(1.0, b - a))
                span = cur - a0
                if abs(span) > 150:
                    span = math.copysign(150, span)
                start = cur - span
                pts_o, pts_i = [], []
                n = 12
                for i in range(n + 1):
                    t = i / n
                    ang = math.radians(start + span * t)
                    taper = t
                    ro = rad + hb["r"] * 0.55
                    ri = rad - hb["r"] * (0.2 + 0.8 * taper)
                    pts_o.append(self.lpt(f, c, cx + math.cos(ang) * ro, cy - math.sin(ang) * ro))
                    pts_i.append(self.lpt(f, c, cx + math.cos(ang) * ri, cy - math.sin(ang) * ri))
                poly = pts_o + pts_i[::-1]
                if len(poly) >= 3 and abs(span) > 4:
                    pygame.draw.polygon(self.fx, col + (int(alpha * 0.75),), poly)
                    pygame.draw.lines(self.fx, (255, 255, 255, alpha), False, pts_o, max(3, int(r * 0.3)))
            elif kind in ("swipe", "stick", "big", "kick", "dash"):
                width = 0.55 if kind != "big" else 0.75
                base = 0 if face > 0 else math.pi
                if 100 < hb["ang"] < 260:
                    base += math.pi
                crescent(self.fx, hx - face * r * 0.3, hy, r * 1.15, base - 1.2, base + 1.2, r * width,
                         col + (int(alpha * 0.75),), (255, 255, 255, alpha))
            elif kind == "poke":
                pygame.draw.ellipse(self.fx, (255, 255, 255, alpha),
                                    pygame.Rect(int(hx - r), int(hy - r * 0.45), int(r * 2), int(r * 0.9)))
                pygame.draw.ellipse(self.fx, col + (alpha,),
                                    pygame.Rect(int(hx - r), int(hy - r * 0.45), int(r * 2), int(r * 0.9)), max(2, int(r * 0.12)))
            elif kind == "flurry":
                for k_ in range(4):
                    seed = (mf * 7 + k_ * 13) % 17
                    ox = (seed / 17.0 - 0.5) * r * 1.6
                    oy = ((seed * 5) % 17 / 17.0 - 0.5) * r * 1.4
                    pygame.draw.ellipse(self.fx, (255, 255, 255, alpha),
                                        pygame.Rect(int(hx + ox - r * 0.5), int(hy + oy - r * 0.2), int(r), int(r * 0.4)))
            elif kind == "drill":
                for k_ in range(3):
                    ang = mf * 0.9 + k_ * math.tau / 3
                    pygame.draw.arc(self.fx, (255, 255, 255, alpha), pygame.Rect(int(hx - r), int(hy - r * 0.6), int(r * 2), int(r * 1.2)),
                                    ang, ang + 1.4, max(2, int(r * 0.14)))
                pygame.draw.circle(self.fx, col + (int(alpha * 0.5),), (int(hx), int(hy)), int(r * 0.5))
            elif kind == "note":
                for k_ in range(3):
                    ang = mf * 0.3 + k_ * 2.1
                    nx_, ny_ = hx + math.cos(ang) * r * 0.8, hy + math.sin(ang) * r * 0.6
                    pygame.draw.circle(self.fx, (60, 60, 110, alpha), (int(nx_), int(ny_)), max(2, int(r * 0.18)))
                    pygame.draw.line(self.fx, (60, 60, 110, alpha), (nx_ + r * 0.15, ny_), (nx_ + r * 0.15, ny_ - r * 0.5), 2)
            elif kind == "claw":
                for s_ in (-1, 1):
                    rr = pygame.Rect(int(hx - r), int(hy - r + s_ * r * 0.35), int(r * 2), int(r * 2))
                    a0_ = (0.3 if face > 0 else math.pi - 1.2)
                    pygame.draw.arc(self.fx, (255, 255, 255, alpha), rr, a0_ + (0.4 if s_ > 0 else -0.4), a0_ + 1.0 + (0.4 if s_ > 0 else -0.4),
                                    max(2, int(r * 0.2)))
            elif kind == "arc_up" or kind == "arc":
                crescent(self.fx, hx, hy + r * 0.3, r * 1.2, -math.pi / 2 - 1.3, -math.pi / 2 + 1.3, r * 0.6,
                         (255, 255, 255, alpha), col + (alpha,))
            elif kind == "spin":
                rr = int(r)
                pygame.draw.circle(self.fx, (255, 255, 255, int(alpha * 0.5)), (int(hx), int(hy)), rr, max(3, int(r * 0.25)))
                for k_ in range(3):
                    st = mf * 0.6 + k_ * math.tau / 3
                    pygame.draw.arc(self.fx, col + (alpha,), pygame.Rect(int(hx - rr), int(hy - rr), rr * 2, rr * 2),
                                    st, st + 1.0, max(2, int(r * 0.18)))
            elif kind == "stomp":
                for k_ in (-1, 0, 1):
                    x = hx + k_ * r * 0.5
                    pygame.draw.line(self.fx, (255, 255, 255, alpha), (x, hy - r), (x, hy + r * 0.8), max(2, int(r * 0.12)))
                pygame.draw.circle(self.fx, col + (int(alpha * 0.6),), (int(hx), int(hy + r * 0.4)), int(r * 0.6))
            elif kind == "ground":
                pygame.draw.ellipse(self.fx, (255, 255, 255, alpha),
                                    pygame.Rect(int(hx - r * 1.2), int(hy - r * 0.35), int(r * 2.4), int(r * 0.7)))
                pygame.draw.ellipse(self.fx, col + (alpha,),
                                    pygame.Rect(int(hx - r * 1.2), int(hy - r * 0.35), int(r * 2.4), int(r * 0.7)), max(2, int(r * 0.12)))
            elif kind in ("shout", "burp"):
                k = (mf - a) / max(1, b - a + 4)
                for i in range(3):
                    rr = int(r * (0.5 + 0.35 * i + 0.3 * k))
                    if kind == "shout":
                        base = 0 if face > 0 else math.pi
                        pygame.draw.arc(self.fx, (255, 255, 255, alpha), pygame.Rect(int(hx - rr - face * r * 0.6), int(hy - rr), rr * 2, rr * 2),
                                        base - 0.6, base + 0.6, max(3, int(r * 0.12)))
                    else:
                        pygame.draw.circle(self.fx, (255, 236, 150, alpha), (int(hx), int(hy)), rr, max(3, int(r * 0.08)))
            if hb.get("sweet") and a <= mf <= b:   # little sparkle on sweetspots
                star(self.fx, hx, hy, max(4, r * 0.45), (255, 255, 255, 230))

    def draw_debug(self, surf, snap):
        """F2: hurtboxes (yellow), hitboxes (red, sweetspots magenta), grab boxes (purple), reflectors (cyan)."""
        cam = self.cam
        for f in snap["f"]:
            if not f["al"] or f["dd"]:
                continue
            c = characters.CHARACTERS[f["c"]]
            h = c["h"] * (0.65 if f["st"] == "crouch" else 1.0)
            x0, y0 = cam.pt(f["x"] - c["w"] / 2, f["y"] - h)
            x1, y1 = cam.pt(f["x"] + c["w"] / 2, f["y"])
            colr = (90, 160, 255) if f["it"] else (255, 255, 255) if f["iv"] else (255, 220, 40)
            pygame.draw.rect(surf, colr, pygame.Rect(int(x0), int(y0), max(1, int(x1 - x0)), max(1, int(y1 - y0))), 2)
            if f["st"] != "attack" or not f["mv"]:
                continue
            m = c["moves"].get(f["mv"], {})
            for hb in m.get("hits", []):
                a, b = hb["f"]
                if a <= f["mf"] <= b:
                    lx, ly = hb_pos(hb, f["mf"])
                    px, py = self.lpt(f, c, lx, ly)
                    pygame.draw.circle(surf, (255, 60, 220) if hb.get("sweet") else (255, 40, 40), (int(px), int(py)),
                                       max(2, int(cam.s(hb["r"]))), 2)
            if m.get("grabbox"):
                (a, b), gx, gy, gr = m["grabbox"]
                if a <= f["mf"] <= b:
                    px, py = self.lpt(f, c, gx, gy)
                    pygame.draw.circle(surf, (170, 80, 255), (int(px), int(py)), max(2, int(cam.s(gr))), 2)
            if m.get("reflect") and m["reflect"][0] <= f["mf"] <= m["reflect"][1]:
                px, py = self.lpt(f, c, 0, 0)
                pygame.draw.circle(surf, (60, 230, 255), (int(px), int(py)), max(2, int(cam.s(m.get("reflect_r", 72)))), 2)
        for p in snap["p"]:
            px, py = cam.pt(p["x"], p["y"])
            pygame.draw.circle(surf, (60, 230, 255), (int(px), int(py)), max(2, int(cam.s(p["r"]))), 2)

    # ---------- limbs
    def draw_part(self, surf, f, c, kind, A, P, size_mult=1.0):
        """Draw the character's own hand/foot at P, pointing away from A (arm/leg start)."""
        ang = math.degrees(math.atan2(P[1] - A[1], P[0] - A[0])) if (P[0] - A[0] or P[1] - A[1]) else (0 if f["fa"] > 0 else 180)
        char_px = self.cam.s(c["h"] * 1.32) * size_mult
        img = self.images.part(f["c"], kind, char_px, ang)
        col = LIMB_COLOR.get(f["c"], (255, 255, 255))
        if img is None:
            if kind == "hand":
                draw_fist(surf, P[0], P[1], self.cam.s(c["h"] * 0.2), col)
            else:
                draw_foot(surf, P[0], P[1], self.cam.s(c["h"] * 0.2), col, f["fa"])
            return
        r = math.radians(ang)
        off = img.get_height() * 0.18
        surf.blit(img, img.get_rect(center=(int(P[0] + math.cos(r) * off), int(P[1] + math.sin(r) * off))))

    def limb_local(self, f, c, move, hb, mf, anchor):
        """Local position of a punching fist / kicking foot on move-frame mf (or None when it's tucked in)."""
        a, b = hb["f"]
        tx, ty = hb_pos(hb, min(max(mf, a), b))
        ax, ay = anchor
        # don't reach further than the hitbox centre, but at least a little out of the body
        if mf < a:                                  # wind-up: pull back
            k = mf / max(1.0, a)
            dx, dy = tx - ax, ty - ay
            n = math.hypot(dx, dy) or 1.0
            return ax - dx / n * 7 * k, ay - dy / n * 7 * k
        if mf <= b:
            return tx, ty
        k = (mf - b) / 12.0
        if k >= 1.0:
            return None
        return tx + (ax - tx) * k, ty + (ay - ty) * k

    def draw_limbs(self, surf, f, c, move):
        kind = limb_kind(f["c"], f["mv"], move)
        if kind in (None, "body", "head", "weapon"):
            if kind == "head":
                self.draw_head_impact(f, c, move)
            return
        mf = f["mf"]
        col = LIMB_COLOR.get(f["c"], (255, 255, 255))
        h, w = c["h"], c["w"]
        fr = h * 0.2
        cam = self.cam
        face = f["fa"]
        pcol = tuple(f["col"])
        if kind == "grab":
            self.draw_grab_hands(surf, f, c, move)
            return
        hits = move.get("hits", [])
        if not hits and kind == "fists":
            hits = [{"f": (0, move["frames"]), "x": w * 0.9, "y": -h * 0.05, "r": 20}]
            move = dict(move, hits=hits)
        if not hits:
            return
        hb = self.lead_hitbox(move, mf)
        if kind in ("fist", "foot"):
            lx, ly = hb_pos(hb, hb["f"][0])
            back = lx < 0
            if kind == "fist":
                anchor = (-w * 0.28 if back else w * 0.28, -h * 0.02)
            else:
                anchor = (-w * 0.18 if back else w * 0.18, h * 0.40)
            # motion trail on the fx layer
            a, b = hb["f"]
            if a <= mf <= b + 1:
                for k_, al in ((2, 60), (1, 110)):
                    p = self.limb_local(f, c, move, hb, mf - k_, anchor)
                    if p:
                        sx, sy = self.lpt(f, c, *p)
                        pygame.draw.circle(self.fx, col + (al,), (int(sx), int(sy)), max(2, int(cam.s(fr))))
            p = self.limb_local(f, c, move, hb, mf, anchor)
            if not p:
                return
            A = self.lpt(f, c, *anchor)
            P = self.lpt(f, c, *p)
            if a <= mf <= b + 1:     # glow in the player's colour so you can see who is hitting
                pygame.draw.circle(self.fx, pcol + (130,), (int(P[0]), int(P[1])), max(4, int(cam.s(fr * 1.9))))
            draw_arm(surf, A, P, cam.s(h * 0.11), col)
            self.draw_part(surf, f, c, "hand" if kind == "fist" else "foot", A, P)
            if a <= mf <= b:   # speed lines behind the fist/foot
                dx, dy = P[0] - A[0], P[1] - A[1]
                n = math.hypot(dx, dy) or 1.0
                for o in (-1, 1):
                    ox, oy = -dy / n * o * cam.s(fr) * 0.7, dx / n * o * cam.s(fr) * 0.7
                    pygame.draw.line(self.fx, (255, 255, 255, 170), (P[0] - dx / n * cam.s(fr * 1.6) + ox, P[1] - dy / n * cam.s(fr * 1.6) + oy),
                                     (P[0] - dx / n * cam.s(fr * 3.4) + ox, P[1] - dy / n * cam.s(fr * 3.4) + oy), 2)
        elif kind == "fists":
            lx, ly = hb_pos(hb, min(max(mf, hb["f"][0]), hb["f"][1]))
            for i, side in enumerate((-1, 1)):
                anchor = (w * 0.25, -h * 0.02 + side * h * 0.08)
                ph = mf * 0.95 + i * math.pi
                ext = (math.sin(ph) + 1) / 2 if hb["f"][0] <= mf <= hb["f"][1] + 2 else 0.3
                if f["mv"] in ("usmash",):
                    anchor = (side * w * 0.25, -h * 0.25)
                    ext = 1.0 if hb["f"][0] <= mf <= hb["f"][1] + 4 else min(1.0, mf / max(1.0, hb["f"][0]))
                    tx, ty = side * w * 0.22, ly
                else:
                    tx, ty = lx, ly + side * h * 0.08
                p = (anchor[0] + (tx - anchor[0]) * ext, anchor[1] + (ty - anchor[1]) * ext)
                A, P = self.lpt(f, c, *anchor), self.lpt(f, c, *p)
                if ext > 0.6:
                    pygame.draw.circle(self.fx, pcol + (110,), (int(P[0]), int(P[1])), max(4, int(cam.s(fr * 1.6))))
                draw_arm(surf, A, P, cam.s(h * 0.1), col)
                self.draw_part(surf, f, c, "hand", A, P, 0.9)
        elif kind == "feet":
            act = [hb_ for hb_ in hits if hb_["f"][0] - 6 <= mf <= hb_["f"][1] + 10] or [hb]
            used = set()
            for hb_ in act:
                lx, ly = hb_pos(hb_, hb_["f"][0])
                side = -1 if lx < -5 else 1
                if side in used:
                    continue
                used.add(side)
                anchor = (side * w * 0.18, h * 0.40)
                p = self.limb_local(f, c, move, hb_, mf, anchor)
                if not p:
                    continue
                A, P = self.lpt(f, c, *anchor), self.lpt(f, c, *p)
                if hb_["f"][0] <= mf <= hb_["f"][1] + 1:
                    pygame.draw.circle(self.fx, pcol + (130,), (int(P[0]), int(P[1])), max(4, int(cam.s(fr * 1.9))))
                draw_arm(surf, A, P, cam.s(h * 0.11), col)
                self.draw_part(surf, f, c, "foot", A, P)

    def draw_head_impact(self, f, c, move):
        hb = self.lead_hitbox(move, f["mf"])
        if not hb or not (hb["f"][0] <= f["mf"] <= hb["f"][1]):
            return
        lx, ly = hb_pos(hb, f["mf"])
        x, y = self.lpt(f, c, lx, ly)
        star(self.fx, x, y, self.cam.s(c["h"] * 0.22), (255, 255, 255, 200))

    def draw_grab_hands(self, surf, f, c, move, victim=None):
        cam = self.cam
        h, w = c["h"], c["w"]
        col = LIMB_COLOR.get(f["c"], (255, 255, 255))
        mf = f["mf"]
        if victim is not None:
            tx, ty = victim
            ext = 1.0
        elif move and move.get("grabbox"):
            (a, b), gx, gy, gr = move["grabbox"]
            tx, ty = gx, gy
            ext = min(1.0, mf / max(1.0, a)) if mf <= b else max(0.0, 1.0 - (mf - b) / 10.0)
        else:
            return
        claw = f["c"] == "kani" and self.images.claw is not None
        for side in (-1, 1):
            anchor = (w * 0.25, side * h * 0.1)
            p = (anchor[0] + (tx - anchor[0]) * ext, anchor[1] + (ty + side * h * 0.12 - anchor[1]) * ext)
            A, P = self.lpt(f, c, *anchor), self.lpt(f, c, *p)
            draw_arm(surf, A, P, cam.s(h * 0.11), col)
            if claw:
                sz = max(8, cam.s(h * 0.36))
                img = self.images.scaled(self.images.claw, sz * 1.3, sz)
                if f["fa"] < 0:
                    img = pygame.transform.flip(img, True, False)
                surf.blit(img, img.get_rect(center=(int(P[0]), int(P[1]))))
            else:
                self.draw_part(surf, f, c, "hand", A, P)

    def draw_extras(self, surf, f, c, move, centre, h, snap):
        cam = self.cam
        face = f["fa"]
        mv = f["mv"] if f["st"] == "attack" else ""
        # Hachiware's reflector: a hexagon shield while it's up
        if move and move.get("reflect") and move["reflect"][0] <= f["mf"] <= move["reflect"][1]:
            rr = cam.s(move.get("reflect_r", 72))
            rot = snap["fr"] * 0.05
            pts = [(centre[0] + math.cos(rot + i * math.tau / 6) * rr, centre[1] + math.sin(rot + i * math.tau / 6) * rr) for i in range(6)]
            pygame.draw.polygon(self.fx, (90, 220, 255, 60), pts)
            pygame.draw.polygon(self.fx, (160, 240, 255, 220), pts, max(2, int(cam.s(5))))
        # Chiikawa's pink pochette as a parachute
        if f["st"] == "parachute" or (mv == "uspec" and f["c"] == "chiikawa" and f["mf"] > 12):
            top = centre[1] - h * 0.95
            w = cam.s(c["w"] * 1.5)
            canopy = pygame.Rect(int(centre[0] - w / 2), int(top - cam.s(26)), int(w), int(cam.s(52)))
            pygame.draw.ellipse(surf, INK, canopy.inflate(6, 6))
            pygame.draw.ellipse(surf, (250, 160, 190), canopy)
            pygame.draw.rect(surf, (250, 160, 190), pygame.Rect(canopy.x, canopy.centery, canopy.w, canopy.h // 2 + 4))
            pygame.draw.line(surf, INK, (canopy.x, canopy.centery), (canopy.right, canopy.centery), max(2, int(cam.s(4))))
            pygame.draw.circle(surf, (255, 235, 120), (canopy.centerx, int(canopy.y + canopy.h * 0.32)), max(3, int(cam.s(6))))
            for sx_ in (canopy.x + 4, canopy.centerx, canopy.right - 4):
                pygame.draw.line(surf, INK, (sx_, canopy.centery), (centre[0], centre[1] - h * 0.3), 2)
        # sleeping: Zzz
        if f["st"] == "sleep":
            for i in range(3):
                t = (snap["fr"] * 0.02 + i / 3.0) % 1.0
                zx = centre[0] + cam.s(20 + 30 * t)
                zy = centre[1] - h * 0.6 - cam.s(60 * t)
                text(surf, "z" if i < 2 else "Z", int(max(12, cam.s(18 + 10 * t))), (150, 130, 255), (zx, zy), outline=WHITE, ow=2)
        # Momonga holding Kani out (counter) / Kani snipping back
        posed = getattr(self, "_posed", False)
        if f["c"] == "momonga" and mv == "counter_hit" and posed:
            if self.images.claw is not None and (f["mf"] // 4) % 2 == 0:
                cimg = self.images.scaled(self.images.claw, cam.s(40), cam.s(30))
                if face < 0:
                    cimg = pygame.transform.flip(cimg, True, False)
                surf.blit(cimg, cimg.get_rect(center=(int(centre[0] + face * cam.s(c["w"] * 1.5)), int(centre[1]))))
        elif f["c"] == "momonga" and mv in ("nspec", "counter_hit") and not posed:
            big = mv == "counter_hit"
            kh = cam.s(c["h"] * (1.15 if big else 0.75))
            kimg = self.images.sprite("kani", kh, flip=face < 0)
            bob = math.sin(f["mf"] * 0.8) * cam.s(4) if big else 0
            kx = centre[0] + face * cam.s(c["w"] * (0.95 if big else 0.6))
            surf.blit(kimg, kimg.get_rect(midbottom=(int(kx), int(centre[1] + h * 0.45 + bob))))
            if big and self.images.claw is not None and (f["mf"] // 4) % 2 == 0:
                cimg = self.images.scaled(self.images.claw, cam.s(40), cam.s(30))
                if face < 0:
                    cimg = pygame.transform.flip(cimg, True, False)
                surf.blit(cimg, cimg.get_rect(center=(int(kx + face * cam.s(34)), int(centre[1] - h * 0.05))))
        # Kani reading a book
        if f["c"] == "kani" and mv == "dspec":
            bw, bh_ = cam.s(46), cam.s(30)
            bx, by = centre[0] + face * cam.s(22), centre[1] + h * 0.05
            for side in ((-1, 1) if not posed else ()):
                page = [(bx, by - bh_ / 2), (bx + side * bw / 2, by - bh_ / 2 - cam.s(5)), (bx + side * bw / 2, by + bh_ / 2 - cam.s(5)), (bx, by + bh_ / 2)]
                pygame.draw.polygon(surf, CREAM, page)
                pygame.draw.polygon(surf, INK, page, 2)
            if 30 <= f["mf"] <= 66:
                rr = cam.s(88) * (0.6 + 0.4 * ((f["mf"] - 30) % 12) / 12.0)
                pygame.draw.circle(self.fx, (170, 150, 255, 70), (int(centre[0]), int(centre[1])), int(rr), max(2, int(cam.s(4))))
                for i in range(3):
                    ang = f["mf"] * 0.15 + i * 2.1
                    text(surf, "z", int(max(12, cam.s(20))), (150, 130, 255),
                         (centre[0] + math.cos(ang) * cam.s(70), centre[1] + math.sin(ang) * cam.s(40)), outline=WHITE, ow=1)
        # Kani's tether yanking someone in
        if f["c"] == "kani" and mv == "tether_kick" and f["mf"] <= 13:
            v = next((o for o in snap["f"] if o["st"] == "grabbed"), None)
            if v is not None:
                vc = characters.CHARACTERS[v["c"]]
                A = self.lpt(f, c, 10, -10)
                P = cam.pt(v["x"], v["y"] - vc["h"] / 2)
                pygame.draw.line(surf, INK, A, P, max(3, int(cam.s(8))))
                pygame.draw.line(surf, (236, 104, 90), A, P, max(2, int(cam.s(5))))

    def draw_tether(self, surf, f, c, move):
        cam = self.cam
        A = self.lpt(f, c, 10, -10)
        if f["st"] == "tether" and f.get("tt"):
            P = cam.pt(f["tt"][0], f["tt"][1])
        else:
            a, b, reach, ang = move["tether"]
            mf = f["mf"]
            if mf < a:
                return
            k = min(1.0, (mf - a) / float(max(1, b - a))) if mf <= b else max(0.0, 1.0 - (mf - b) / 8.0)
            r = math.radians(ang)
            P = self.lpt(f, c, math.cos(r) * reach * k, -math.sin(r) * reach * k)
        # a dotted 'arm' out to the claw
        n = max(2, int(math.hypot(P[0] - A[0], P[1] - A[1]) / max(4, cam.s(14))))
        for i in range(n + 1):
            t = i / float(n)
            x, y = A[0] + (P[0] - A[0]) * t, A[1] + (P[1] - A[1]) * t
            pygame.draw.circle(surf, INK, (int(x), int(y)), max(2, int(cam.s(6))))
            pygame.draw.circle(surf, (236, 104, 90), (int(x), int(y)), max(1, int(cam.s(4))))
        if self.images.claw is not None:
            sz = max(8, cam.s(40))
            img = self.images.scaled(self.images.claw, sz * 1.3, sz)
            ang_s = math.degrees(math.atan2(-(P[1] - A[1]), P[0] - A[0]))
            if P[0] < A[0]:
                img = pygame.transform.flip(img, False, True)
            img = pygame.transform.rotate(img, ang_s)
            surf.blit(img, img.get_rect(center=(int(P[0]), int(P[1]))))

    def draw_callouts(self, surf, snap):
        """Special move names float up above whoever used them."""
        for f in snap["f"]:
            key = f["s"]
            art = f.get("art", "")
            if art != self.prev_art.get(key, ""):
                if art:
                    self.callouts.append({"s": key, "txt": ARTS[art]["name"] + "!", "t": 0, "col": ARTS[art]["col"]})
                self.prev_art[key] = art
            mv = f["mv"] if f["st"] == "attack" else ""
            if mv and mv != self.prev_move.get(key):
                name = characters.SPECIAL_NAMES.get(f["c"], {}).get(mv)
                if name:
                    self.callouts.append({"s": key, "txt": name, "t": 0, "col": tuple(f["col"])})
            self.prev_move[key] = mv
        keep = []
        for co in self.callouts:
            co["t"] += 1
            f = next((x for x in snap["f"] if x["s"] == co["s"]), None)
            if f is None or co["t"] > 55:
                continue
            c = characters.CHARACTERS[f["c"]]
            x, y = self.cam.pt(f["x"], f["y"] - c["h"] * 1.32)
            y -= 48
            y -= co["t"] * 0.5
            text(surf, co["txt"], 18, WHITE, (x, y), outline=co["col"], ow=2)
            keep.append(co)
        self.callouts = keep

    def draw_tag(self, surf, f):
        c = characters.CHARACTERS[f["c"]]
        x, y = self.cam.pt(f["x"], f["y"] - c["h"] * 1.32 - 14)
        col = tuple(f["col"])
        label = "CPU" if f["cpu"] else "P%d" % (f["s"] + 1)
        pygame.draw.polygon(surf, col, [(x - 7, y - 4), (x + 7, y - 4), (x, y + 5)])
        text(surf, label, 15, col, (x, y - 14), outline=WHITE, ow=2)

    # ---------- projectiles
    def draw_projectile(self, surf, p, snap):
        cam = self.cam
        x, y = cam.pt(p["x"], p["y"])
        r = max(3, cam.s(p["r"]))
        k = p["k"]
        if k in ("weed", "weed_big"):
            ang = p["a"] * 0.3
            for i in range(3):
                a = ang + i * 2.1
                tip = (x + math.cos(a) * r * 1.2, y + math.sin(a) * r * 1.2)
                pygame.draw.line(surf, (60, 120, 50), (x, y), tip, max(2, int(r * 0.35)))
                pygame.draw.circle(surf, (110, 190, 90), (int(tip[0]), int(tip[1])), max(2, int(r * 0.4)))
            pygame.draw.circle(surf, (150, 110, 80), (int(x), int(y)), max(2, int(r * 0.4)))
        elif k == "note":
            col = (40, 40, 70)
            pygame.draw.ellipse(surf, col, pygame.Rect(int(x - r * 0.7), int(y), int(r * 1.0), int(r * 0.75)))
            pygame.draw.line(surf, col, (x + r * 0.25, y + r * 0.3), (x + r * 0.25, y - r), max(2, int(r * 0.14)))
            pygame.draw.line(surf, col, (x + r * 0.25, y - r), (x + r * 0.8, y - r * 0.6), max(2, int(r * 0.2)))
            pygame.draw.circle(self.fx, (130, 170, 255, 70), (int(x), int(y)), int(r * 1.3))
        elif k == "seed":
            fa = 1 if p["vx"] >= 0 else -1
            pts = [(x + fa * r * 1.3, y), (x, y - r * 0.7), (x - fa * r, y), (x, y + r * 0.7)]
            pygame.draw.polygon(surf, (35, 30, 30), pts)
            pygame.draw.polygon(surf, WHITE, pts, 1)
        elif k == "anvil":
            img = self.images.dekatsuyo
            if img is not None:
                s_ = self.images.scaled(img, r * 2.4, r * 2.4 * img.get_height() / img.get_width())
                surf.blit(s_, s_.get_rect(center=(int(x), int(y))))
            else:
                pygame.draw.circle(surf, (245, 200, 55), (int(x), int(y)), int(r))
            for i in range(3):   # falling speed lines
                lx = x + (i - 1) * r * 0.7
                pygame.draw.line(self.fx, (255, 255, 255, 170), (lx, y - r * 1.3), (lx, y - r * 1.3 - min(60, abs(p["vy"]) * 4)), 3)
        elif k == "dekatsuyo":
            img = self.images.dekatsuyo
            if img is not None:
                s = self.images.scaled(img, r * 2.4, r * 2.4 * img.get_height() / img.get_width())
                if p["vx"] < 0:
                    s = pygame.transform.flip(s, True, False)
                s = pygame.transform.rotate(s, math.sin(p["a"] * 0.5) * 6)
                surf.blit(s, s.get_rect(center=(int(x), int(y - r * 0.2))))
            else:
                pygame.draw.circle(surf, (245, 200, 55), (int(x), int(y)), int(r))
                pygame.draw.circle(surf, INK, (int(x), int(y)), int(r), 3)
            for i in range(4):
                lx = x - (1 if p["vx"] > 0 else -1) * (r + 10 + i * 14)
                pygame.draw.line(self.fx, (255, 255, 255, 150), (lx, y - r * 0.5 + i * r * 0.3), (lx - (1 if p["vx"] > 0 else -1) * 30, y - r * 0.5 + i * r * 0.3), 3)
        elif k == "book":
            colours = [(110, 160, 230), (240, 170, 70), (150, 200, 120), (225, 120, 170)]
            b = pygame.Surface((int(r * 2.2) + 2, int(r * 1.6) + 2), pygame.SRCALPHA)
            br = b.get_rect()
            pygame.draw.rect(b, colours[(p["o"] + p["a"] // 40) % 4], br, border_radius=3)
            pygame.draw.rect(b, CREAM, pygame.Rect(br.w - br.w // 5, 2, br.w // 6, br.h - 4))
            pygame.draw.rect(b, INK, br, 2, border_radius=3)
            b = pygame.transform.rotate(b, p["a"] * 12)
            surf.blit(b, b.get_rect(center=(int(x), int(y))))
        elif k == "letter":
            ch = self.letters[(p["a"] // 6 + p["o"] * 5 + int(abs(p["vy"]) * 3)) % len(self.letters)]
            text(surf, ch, max(10, int(r * 2.2)), (230, 90, 80), (x, y), outline=WHITE, ow=2)
        elif k == "tear":
            pts = [(x, y - r * 1.4), (x + r * 0.8, y + r * 0.2), (x, y + r * 0.9), (x - r * 0.8, y + r * 0.2)]
            pygame.draw.polygon(surf, (120, 190, 250), pts)
            pygame.draw.polygon(surf, WHITE, pts, 2)
            pygame.draw.circle(surf, WHITE, (int(x - r * 0.25), int(y - r * 0.1)), max(1, int(r * 0.25)))
        elif k == "chord":
            fa = 1 if p["vx"] >= 0 else -1
            a_ = max(0, min(255, int(255 * min(1.0, p["lf"] / 8.0))))
            for i in range(3):
                rr = int(r * (0.5 + 0.3 * i))
                base = 0 if fa > 0 else math.pi
                pygame.draw.arc(self.fx, (255, 255, 255, a_), pygame.Rect(int(x - rr), int(y - rr), rr * 2, rr * 2),
                                base - 0.8, base + 0.8, max(2, int(r * 0.14)))
                pygame.draw.arc(self.fx, (130, 170, 255, a_), pygame.Rect(int(x - rr - 3), int(y - rr), rr * 2, rr * 2),
                                base - 0.8, base + 0.8, max(1, int(r * 0.08)))
        elif k == "bottle":
            b = pygame.Surface((int(r * 1.0) + 4, int(r * 2.4) + 4), pygame.SRCALPHA)
            br = b.get_rect()
            pygame.draw.rect(b, (120, 80, 40), pygame.Rect(2, int(br.h * 0.35), br.w - 4, int(br.h * 0.62)), border_radius=4)
            pygame.draw.rect(b, (120, 80, 40), pygame.Rect(br.w // 2 - 3, 2, 6, int(br.h * 0.4)))
            pygame.draw.rect(b, (250, 220, 120), pygame.Rect(4, int(br.h * 0.5), br.w - 8, int(br.h * 0.2)))
            b = pygame.transform.rotate(b, p["a"] * 14)
            surf.blit(b, b.get_rect(center=(int(x), int(y))))
        elif k == "puddle":
            a_ = max(0, min(150, int(150 * min(1.0, p["lf"] / 30.0))))
            pr = pygame.Rect(0, 0, int(r * 2.2), int(r * 0.6))
            pr.center = (int(x), int(y + r * 0.1))
            pygame.draw.ellipse(self.fx, (240, 190, 70, a_), pr)
            pygame.draw.ellipse(self.fx, (255, 240, 200, a_), pr.inflate(-pr.w * 0.5, -pr.h * 0.5).move(-pr.w * 0.1, -pr.h * 0.1))
            for i in range(2):
                bx = x + math.sin(p["a"] * 0.07 + i * 3) * r * 0.6
                pygame.draw.circle(self.fx, (255, 255, 255, a_), (int(bx), int(y - (p["a"] * 0.6 + i * 9) % 16)), max(1, int(r * 0.08)))
        else:
            pygame.draw.circle(surf, WHITE, (int(x), int(y)), int(r))

    # ---------- effects
    def draw_effect(self, surf, e):
        cam = self.cam
        k = e["k"]
        t, life = e["t"], e["l"]
        p = min(1.0, t / max(1, life))
        x, y = cam.pt(e["x"], e["y"])
        s = e.get("s", 1.0)
        col = tuple(e.get("col", (255, 255, 255)))
        if FX_SPRITES and k in SPARK_FX and self.images.fx_sheets:
            sheet, size = SPARK_FX[k](s)
            frame = 1 + min(10, int(p * 11))          # frames 1-11 hold the burst; the rest is near-empty
            img = self.images.fx_frame(sheet, frame, cam.s(size), (e["id"] * 73) % 360)
            if img is not None:
                self.fx.blit(img, img.get_rect(center=(int(x), int(y))))
            if k == "counter":
                text(surf, "!", int(max(14, cam.s(40))), (90, 160, 255), (x, y - cam.s(70)), outline=WHITE)
            return
        if k == "hit":
            n = 10
            rad = cam.s(30 + 70 * s) * (0.4 + 0.6 * p)
            a = int(255 * (1 - p))
            for i in range(n):
                ang = i * math.tau / n + e["id"]
                ln = rad * (0.6 if i % 2 else 1.0)
                pygame.draw.line(self.fx, (255, 255, 255, a), (x, y), (x + math.cos(ang) * ln, y + math.sin(ang) * ln),
                                 max(2, int(cam.s(6 * s) * (1 - p))))
            star(self.fx, x, y, cam.s(22 * s) * (1 - p * 0.6), col + (a,))
            star(self.fx, x, y, cam.s(12 * s) * (1 - p * 0.6), (255, 255, 255, a))
        elif k in ("dust", "jump", "smoke"):
            a = int(160 * (1 - p))
            for i in range(5 if k != "smoke" else 2):
                dx = (i - 2) * cam.s(14 * s) * (0.5 + p)
                rr = max(2, int(cam.s(10 * s) * (1 - p * 0.5)))
                c = (230, 225, 215, a) if k != "smoke" else (200, 200, 200, a)
                pygame.draw.circle(self.fx, c, (int(x + dx), int(y - cam.s(6) - p * cam.s(14))), rr)
        elif k == "ko":
            a = max(0, int(255 * (1 - p)))
            ang = math.atan2(-(e["y"] + 200), -e["x"]) if (e["x"] or e["y"] + 200) else 0
            L = cam.s(1500) * min(1.0, p * 4)
            w = cam.s(160) * (1 - p)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx
            pts = [(x + px * w * 0.15, y + py * w * 0.15), (x + dx * L + px * w, y + dy * L + py * w),
                   (x + dx * L - px * w, y + dy * L - py * w), (x - px * w * 0.15, y - py * w * 0.15)]
            pygame.draw.polygon(self.fx, col + (a,), pts)
            pts2 = [(x, y), (x + dx * L + px * w * 0.4, y + dy * L + py * w * 0.4), (x + dx * L - px * w * 0.4, y + dy * L - py * w * 0.4)]
            pygame.draw.polygon(self.fx, (255, 255, 255, a), pts2)
            if t < 6:
                self.flash = max(self.flash, 90 - t * 15)
        elif k == "shieldbreak":
            a = int(255 * (1 - p))
            for i in range(10):
                ang = i * math.tau / 10
                d = cam.s(30 + 120 * p)
                star(self.fx, x + math.cos(ang) * d, y + math.sin(ang) * d, cam.s(10), col + (a,))
        elif k in ("heal", "buff"):
            c = (110, 220, 120) if k == "heal" else (255, 90, 60)
            a = int(220 * (1 - p))
            for i in range(6):
                ang = i * math.tau / 6 + p * 3
                px = x + math.cos(ang) * cam.s(36)
                py = y + math.sin(ang) * cam.s(20) - cam.s(60) * p
                if k == "heal":
                    pygame.draw.line(self.fx, c + (a,), (px - 6, py), (px + 6, py), 4)
                    pygame.draw.line(self.fx, c + (a,), (px, py - 6), (px, py + 6), 4)
                else:
                    pygame.draw.circle(self.fx, c + (a,), (int(px), int(py)), max(2, int(cam.s(7))))
        elif k == "counter":
            a = int(255 * (1 - p))
            pygame.draw.circle(self.fx, (120, 200, 255, a), (int(x), int(y)), int(cam.s(40 + 60 * p)), max(2, int(cam.s(6))))
            text(surf, "!", int(max(14, cam.s(40))), (90, 160, 255), (x, y - cam.s(70)), outline=WHITE)
        elif k in ("ring", "respawn", "tech"):
            a = int(220 * (1 - p))
            pygame.draw.circle(self.fx, col + (a,), (int(x), int(y)), int(cam.s(20 + 80 * p)), max(2, int(cam.s(5))))
        elif k == "sweet":
            a = int(255 * (1 - p))
            pygame.draw.circle(self.fx, (255, 255, 255, a), (int(x), int(y)), int(cam.s(30 + 90 * p)), max(2, int(cam.s(8) * (1 - p))))
            star(self.fx, x, y, cam.s(34) * (1 - p * 0.5), (255, 255, 255, a))
        elif k == "armor":
            a = int(220 * (1 - p))
            for i in range(6):
                ang = i * math.tau / 6 + 0.3
                pygame.draw.line(self.fx, (255, 170, 60, a), (x + math.cos(ang) * cam.s(26), y + math.sin(ang) * cam.s(26)),
                                 (x + math.cos(ang) * cam.s(46 + 20 * p), y + math.sin(ang) * cam.s(46 + 20 * p)), max(2, int(cam.s(6))))
        elif k == "reflect":
            a = int(230 * (1 - p))
            pts = [(x + math.cos(i * math.tau / 6) * cam.s(24 + 30 * p), y + math.sin(i * math.tau / 6) * cam.s(24 + 30 * p)) for i in range(6)]
            pygame.draw.polygon(self.fx, (90, 220, 255, a), pts, max(2, int(cam.s(5))))
        elif k in ("spark", "clank"):
            a = int(255 * (1 - p))
            star(self.fx, x, y, cam.s(18 * s) * (1 - p * 0.5), col + (a,))

    # ---------- off-screen bubbles
    def draw_offscreen(self, surf, snap):
        view = pygame.Rect(0, HUD_H if HUD_TOP else 0, WIDTH, HEIGHT - HUD_H)
        for f in snap["f"]:
            if not f["al"] or f["dd"]:
                continue
            c = characters.CHARACTERS[f["c"]]
            x, y = self.cam.pt(f["x"], f["y"] - c["h"] / 2)
            if view.collidepoint(x, y):
                continue
            bx = max(40, min(WIDTH - 40, x))
            by = max(view.top + 40, min(view.bottom - 40, y))
            pygame.draw.circle(surf, WHITE, (int(bx), int(by)), 32)
            pygame.draw.circle(surf, tuple(f["col"]), (int(bx), int(by)), 32, 4)
            spr = self.images.sprite(f["c"], 44)
            surf.blit(spr, spr.get_rect(center=(int(bx), int(by))))
            ang = math.atan2(y - by, x - bx)
            tip = (bx + math.cos(ang) * 44, by + math.sin(ang) * 44)
            pygame.draw.polygon(surf, tuple(f["col"]), [tip, (bx + math.cos(ang + 0.4) * 33, by + math.sin(ang + 0.4) * 33),
                                                         (bx + math.cos(ang - 0.4) * 33, by + math.sin(ang - 0.4) * 33)])

    # ---------- HUD
    def draw_hud(self, surf, snap, local_slots):
        fs = sorted(snap["f"], key=lambda f: f["s"])
        n = len(fs)
        cw = 250
        gap = 18
        x0 = WIDTH / 2 - (n * cw + (n - 1) * gap) / 2
        y0 = 6 if HUD_TOP else HEIGHT - HUD_H + 8
        for i, f in enumerate(fs):
            r = pygame.Rect(int(x0 + i * (cw + gap)), int(y0), cw, HUD_H - 16)
            col = tuple(f["col"])
            alive = f["al"]
            panel = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, (30, 26, 34, 170 if alive else 90), panel.get_rect(), border_radius=16)
            pygame.draw.rect(panel, col + (255,), pygame.Rect(0, 0, 10, r.h), border_top_left_radius=16, border_bottom_left_radius=16)
            surf.blit(panel, r)
            spr = self.images.sprite(f["c"], 72)
            if not alive:
                spr = spr.copy()
                spr.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(spr, spr.get_rect(center=(r.x + 56, r.centery)))
            name = f["n"] if not f["cpu"] else "CPU"
            text(surf, name, 15, col, (r.x + 98, r.y + 8), anchor="topleft", outline=BLACK, ow=1)
            # damage with a jiggle when it goes up
            d = f["d"]
            prev = self.prev_dmg.get(f["s"], d)
            if d > prev + 0.05:
                self.dmg_jiggle[f["s"]] = 10
            self.prev_dmg[f["s"]] = d
            j = self.dmg_jiggle.get(f["s"], 0)
            if j > 0:
                self.dmg_jiggle[f["s"]] = j - 1
            jx = random.uniform(-j, j) * 0.6
            jy = random.uniform(-j, j) * 0.6
            if alive:
                if f["dd"]:
                    text(surf, "--", 40, (200, 200, 200), (r.right - 20, r.y + 26), anchor="topright", outline=BLACK)
                else:
                    whole = int(d)
                    tr = text(surf, "%" , 22, damage_color(d), (r.right - 16 + jx, r.y + 34 + jy), anchor="topright", outline=BLACK)
                    text(surf, str(whole), 44 + min(8, j), damage_color(d), (tr.left - 2 + jx, r.y + 20 + jy), anchor="topright",
                         outline=BLACK, ow=3)
            else:
                text(surf, "OUT", 32, (190, 190, 190), (r.right - 20, r.y + 28), anchor="topright", outline=BLACK)
            for k in range(min(f["k"], 8)):
                cx = r.x + 104 + k * 22
                cy = r.bottom - 16
                pygame.draw.circle(surf, WHITE, (cx, cy), 9)
                mini = self.images.sprite(f["c"], 16)
                surf.blit(mini, mini.get_rect(center=(cx, cy)))
            if f.get("art"):
                a_ = ARTS[f["art"]]
                badge = pygame.Rect(r.x + 98, r.y + 26, 76, 18)
                pygame.draw.rect(surf, a_["col"], badge, border_radius=8)
                fill = badge.copy()
                fill.w = max(2, int(badge.w * f["art_t"] / 900.0))
                pygame.draw.rect(surf, WHITE, fill, 2, border_radius=8)
                text(surf, a_["name"], 12, WHITE, badge.center, outline=BLACK, ow=1)
            if f["s"] in local_slots:
                text(surf, "YOU", 12, WHITE, (r.right - 14, r.bottom - 10), anchor="bottomright", outline=col, ow=1)
            cd = f.get("cd") or {}
            if cd:
                cdx = r.x + 104 + min(f["k"], 8) * 22 + 6
                for name_, v in cd.items():
                    text(surf, "%s %.0fs" % ({"sspec": "side-B", "dspec": "down-B", "nspec": "B", "uspec": "up-B"}.get(name_, name_), v / 60.0),
                         11, (220, 220, 230), (cdx, r.bottom - 16), anchor="midleft")
                    cdx += 70

    def draw_overlay(self, surf, snap):
        cd = snap["cd"]
        if cd > 0:
            n = int(math.ceil(cd / 50.0))
            label = str(n) if n > 0 else "GO!"
            k = (cd % 50) / 50.0
            text(surf, label, int(110 + 60 * k), (255, 230, 90), (WIDTH / 2, VIEW_CY), outline=INK, ow=5)
        elif COUNTDOWN_F <= snap["fr"] < COUNTDOWN_F + 40 and not snap["over"]:
            text(surf, "GO!", 150, (255, 120, 90), (WIDTH / 2, VIEW_CY), outline=INK, ow=6)
        if snap["over"]:
            k = min(1.0, snap["et"] / 20.0)
            text(surf, "GAME!", int(60 + 110 * k), (255, 90, 80), (WIDTH / 2, VIEW_CY), outline=WHITE, ow=6)


COUNTDOWN_F = 151


# effect kind -> (sheet, on-screen size in world px) for the sprite hit sparks
SPARK_FX = {
    "hit": lambda s: ("yellow" if s >= 1.35 else "white", 120 + 110 * s),
    "sweet": lambda s: ("yellow", 300),
    "shieldbreak": lambda s: ("yellow", 340),
    "counter": lambda s: ("white", 240),
    "armor": lambda s: ("yellow", 130),
    "spark": lambda s: ("white", 50 + 60 * s),
    "clank": lambda s: ("white", 140),
}


def star(surf, x, y, r, col):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    pygame.draw.polygon(surf, col, pts)


def stick(surf, a, b, w):
    w = max(2, int(w))
    pygame.draw.line(surf, INK, a, b, w + 4)
    pygame.draw.line(surf, (170, 120, 70), a, b, w)
    pygame.draw.circle(surf, (170, 120, 70), (int(b[0]), int(b[1])), max(2, w // 2 + 1))


def crescent(surf, cx, cy, r, a0, a1, thick, inner_col, edge_col):
    """A slash 'swoosh': filled band between radius r-thick and r from angle a0 to a1 (screen angles)."""
    n = 14
    outer, inner = [], []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        taper = math.sin(i / n * math.pi)
        outer.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        inner.append((cx + math.cos(a) * (r - thick * taper), cy + math.sin(a) * (r - thick * taper)))
    pts = outer + inner[::-1]
    if len(pts) >= 3:
        pygame.draw.polygon(surf, inner_col, pts)
        pygame.draw.lines(surf, edge_col, False, outer, max(3, int(thick * 0.35)))
