"""
The fight simulation. Pure Python (no pygame): the host runs this, clients only draw snapshots.

Raw input per player per frame (sent over the network as a short list):
    [x, y, held_bits, jump_count, atk_count, spc_count, shield_count, grab_count, smash_count, sx, sy]
x/y: move stick -1..1 (y = -1 is UP). *_count: how many times that button has ever been pressed
(lets the host notice taps even if a packet is lost). sx/sy: smash stick (right stick), 0 if none.
"""
import math
import random

from . import characters
from .characters import hb_pos
from .stages import STAGES, ledges, main_poly

B_JUMP, B_ATK, B_SPC, B_SHD, B_GRB, B_SMS = 1, 2, 4, 8, 16, 32
BUTTONS = ["jump", "atk", "spc", "shd", "grb", "sms"]

# v5 characters
BIG_FORM_FRAMES = 20 * 60        # Chikkabu's muscle form lasts 20 s
BULK_HOLD_FRAMES = 150           # holding down-B from empty fills the meter in 2.5 s
BULK_FROM_DAMAGE = 80.0          # dealing 80% also fills it
LATCH_FRAMES = 3 * 60            # latch lasts 3 s, can't be shaken off
LATCH_DMG_PER_S = 5.0
LATCH_HEAL_PER_S = 2.0
MERMAIDS_MAX = 2
MERMAID_REGEN = 7 * 60           # a mermaid comes back every 7 s
SIREN_RAGE_AT = 100.0
BUTTON_BITS = [B_JUMP, B_ATK, B_SPC, B_SHD, B_GRB, B_SMS]
BIT = dict(zip(BUTTONS, BUTTON_BITS))
SPECIALS = ("nspec", "sspec", "uspec", "dspec")
NEUTRAL = [0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0]

BUFFER = 6            # frames a button press is remembered
JUMPSQUAT = 3
SHIELD_MAX = 50.0
LEDGE_MAX_HANG = 300
COUNTDOWN = 150       # "3, 2, 1, GO!"
GAME_END_FRAMES = 150
KB_TO_SPEED = 0.165   # knockback units -> pixels/frame
KB_DECAY = 0.32       # launch speed lost per frame
TUMBLE_KB = 80
STALE_WEIGHTS = [0.08, 0.0754, 0.0687, 0.062, 0.0553, 0.0486, 0.0419, 0.0352, 0.0285]   # Smash's stale-move queue
DI_STRENGTH = 0.30          # radians of launch-angle change at full stick (~17 degrees)
AIRDODGE_CANCEL = 34        # tumbling: frames of hitstun before you may air dodge out
ACTION_CANCEL = 40          # ...or attack / jump out


# Hachiware's arts (Monado-style). Multipliers on stats / damage / knockback.
ARTS = {
    "jump":   {"name": "JUMP",   "col": (90, 200, 110), "jump": 1.3, "hop": 1.3, "djump": 1.3, "air": 1.2,
               "grav": 0.9, "taken": 1.22},
    "speed":  {"name": "SPEED",  "col": (80, 150, 240), "run": 1.45, "walk": 1.4, "air": 1.25, "accel": 1.3,
               "jump": 0.85, "hop": 0.85, "djump": 0.85, "dealt": 0.8},
    "shield": {"name": "SHIELD", "col": (240, 200, 60), "taken": 0.67, "kb_taken": 0.67, "run": 0.7, "air": 0.8,
               "jump": 0.75, "hop": 0.75, "djump": 0.75, "dealt": 0.85},
    "smash":  {"name": "SMASH",  "col": (230, 70, 70), "kb_dealt": 1.2, "dealt": 0.7, "kb_taken": 1.13},
}
ART_ORDER = ["jump", "speed", "shield", "smash"]      # green, blue, yellow, red
ART_TIME = 900                                        # 15 seconds
ART_COOLDOWN = 300


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def knockback(percent_after, dmg, weight, bkb, kbg):
    """Smash 4 / Ultimate knockback formula."""
    return (((percent_after / 10.0 + percent_after * dmg / 20.0) * (200.0 / (weight + 100.0)) * 1.4) + 18.0) \
        * (kbg / 100.0) + bkb


class Inp:
    """One frame of input for a fighter, with button 'pressed this frame' worked out from the counters."""
    __slots__ = ("x", "y", "held", "pressed", "sx", "sy", "flick_x", "flick_y", "tap_down", "down_cross")

    def __init__(self):
        self.x = self.y = self.sx = self.sy = 0.0
        self.held = 0
        self.pressed = set()
        self.flick_x = self.flick_y = False
        self.tap_down = self.down_cross = False

    def h(self, bit):
        return bool(self.held & bit)


class Fighter:
    def __init__(self, slot, char_key, x, y, stocks, name, color, cpu=False):
        self.slot, self.char_key, self.name, self.color, self.cpu = slot, char_key, name, color, cpu
        self.c = characters.get(char_key)
        self.moves = self.c["moves"]
        self.w, self.h = self.c["w"], self.c["h"]
        self.x, self.y = float(x), float(y)       # x = centre, y = FEET
        self.vx = self.vy = 0.0
        self.kvx = self.kvy = 0.0                 # launch velocity
        self.facing = 1 if x < 0 else -1
        self.grounded = True
        self.ground = None                        # "main" or platform index
        self.state, self.sf = "idle", 0           # state + frames spent in it
        self.move, self.mf = None, 0              # current move name + frame
        self.move_hit = {}                        # (grp, target slot) -> frame last hit
        self.rapid = 0                            # rapid-jab loops done
        self.landed = False                       # current move has connected
        self._bounced = False
        self.dj_pending = 0                       # tap-jump: double jump waits a few frames for an up-attack
        self.stale = []                           # last moves that connected, newest first (stale-move negation)
        self.art, self.art_t = None, 0            # Hachiware's active art
        self.air_once = set()                     # moves used this trip into the air (parachute up-B...)
        self.sleep_t = 0
        self._stale_pushed = False
        self.charge = 0
        self.charging = False
        self.dmg_mult = 1.0                       # charge multiplier of the current move
        self.damage = 0.0
        self.stocks = stocks
        self.jumps_left = self.c["jumps"] - 1
        self.ff = False
        self.side_used = False
        self.airdodge_used = False
        self.hitlag = 0
        self.hitstun = 0
        self.tumble = False
        self.shield = SHIELD_MAX
        self.invuln = 0                           # respawn / ledge invincibility (hits pass through)
        self.intang = 0                           # dodge intangibility
        self.buf = {b: 0 for b in BUTTONS}
        self.last_counts = None
        self.prev_x = self.prev_y = 0.0
        self.ledge = None                         # (lx, ly, dir) while hanging
        self.ledge_cd = 0
        self.drop_timer = 0
        self.grabbing = None                      # Fighter we hold
        self.grabbed_by = None
        self.grab_timer = 0
        self.cooldowns = {}
        self.buff = 1.0
        self.buff_timer = 0
        self.counter_dmg = 0.0
        self.respawn_timer = 0
        self.alive = True                         # still has stocks
        self.dead = False                         # waiting to respawn
        self.landlag = 0
        self.tech_window = 0
        self.dizzy = 0
        self.tumble_spin = 0.0
        self.inp = Inp()
        self.stats = {"kos": 0, "falls": 0, "dealt": 0.0, "taken": 0.0, "sd": 0}
        self.last_hit_by = None
        self.last_hit_time = 0
        self.place = 0
        # v5 characters
        self.bulk = 0.0                           # Chikkabu: bulk meter 0..1
        self.form_t = 0                           # Chikkabu: frames left in the big form
        self.mermaids = 2 if char_key == "siren" else 0
        self.mer_t = 0
        self.latch_on = None                      # Chikkabu: who he's latched onto
        self.latch_t = 0

    # ------------------------------------------------------------------ helpers
    def set_form(self, key):
        """Swap to another body (Chikkabu small <-> big): stats, moves and size change, feet stay put."""
        self.c = characters.get(key)
        self.moves = self.c["moves"]
        self.w, self.h = self.c["w"], self.c["h"]
        self.jumps_left = min(self.jumps_left, self.c["jumps"] - 1)

    def st(self, key):
        """A movement stat, with the current art's multiplier applied."""
        v = self.c[key]
        if self.art:
            v *= ARTS[self.art].get(key, 1.0)
        return v

    def art_mult(self, key):
        return ARTS[self.art].get(key, 1.0) if self.art else 1.0

    @property
    def cy(self):
        return self.y - self.h / 2

    def hurtbox(self):
        h = self.h * (0.65 if self.state == "crouch" else 1.0)
        return (self.x - self.w / 2, self.y - h, self.w, h)

    def actionable(self):
        return self.state in ("idle", "run", "crouch", "air", "land_soft") and self.hitlag == 0

    def set_state(self, st):
        self.state, self.sf = st, 0
        if st not in ("attack",):
            self.move = None
            self.charging = False

    def start_move(self, name, game):
        m = self.moves[name]
        self.state, self.sf = "attack", 0
        self.move, self.mf = name, 0
        self.move_hit = {}
        self.rapid = 0
        self.landed = False
        self._bounced = False
        self._stale_pushed = False
        self.charge = 0
        self.charging = False
        self.dmg_mult = 1.0
        if m.get("cooldown"):
            self.cooldowns[name.replace("_air", "")] = m["cooldown"]
        if m.get("side_once"):
            if not self.grounded:
                self.side_used = True
        if m.get("once_air") and not self.grounded:
            self.air_once.add(name)
        if self.grounded and name in ("jab1", "jab2", "jab3", "ftilt", "utilt", "dtilt", "fsmash", "usmash",
                                      "dsmash", "grab", "nspec", "dspec"):
            self.vx *= 0.3

    def air_land(self, game, lag):
        self.grounded = True
        self.vy = 0.0
        self.kvy = 0.0
        self.ff = False
        self.dj_pending = 0
        self.glide_t = 0
        self.air_once = set()
        self.jumps_left = self.c["jumps"] - 1
        self.side_used = False
        self.airdodge_used = False
        self.ledge_cd = 0
        if lag > 0:
            self.set_state("land")
            self.landlag = lag
        else:
            self.set_state("idle")
        game.fx("dust", self.x, self.y, s=0.6)

    def move_data(self):
        return self.moves.get(self.move) if self.move else None


class Game:
    def __init__(self, players, stage_key="battlefield", stocks=3, seed=None):
        """players: list of dicts {slot, char, name, color, cpu}"""
        self.stage_key = stage_key
        self.stage = STAGES[stage_key]
        self.ledges = ledges(self.stage)
        self.poly = main_poly(self.stage)
        pts = self.poly
        self.poly_c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        self.frame = 0
        self.countdown = COUNTDOWN
        self.over = False
        self.end_timer = 0
        self.winner = None
        self.shake = 0.0
        self.rng = random.Random(seed)
        self.fighters = []
        self.projectiles = []
        self.effects = []
        self.fx_id = 0
        self.ko_order = []
        spawns = self.stage["spawns"]
        for i, p in enumerate(players):
            sx, sy = spawns[i % len(spawns)]
            f = Fighter(p["slot"], p["char"], sx, sy, stocks, p.get("name", "P%d" % (p["slot"] + 1)),
                        p.get("color", (200, 200, 200)), p.get("cpu", False))
            f.ground = "main"
            self.fighters.append(f)

    # ------------------------------------------------------------------ effects (data only)
    def fx(self, kind, x, y, life=None, **kw):
        lives = {"hit": 14, "dust": 18, "ko": 60, "shieldbreak": 40, "heal": 40, "buff": 40, "counter": 24,
                 "smoke": 24, "spark": 10, "ring": 20, "clank": 12, "jump": 14, "tech": 20, "respawn": 30,
                 "sweet": 16, "armor": 14, "reflect": 18, "sleep": 40}
        self.fx_id += 1
        e = {"k": kind, "x": round(x, 1), "y": round(y, 1), "t": 0, "l": life or lives.get(kind, 20), "id": self.fx_id}
        e.update(kw)
        self.effects.append(e)
        return e

    # ------------------------------------------------------------------ input
    def build_input(self, f, raw):
        raw = raw or NEUTRAL
        inp = Inp()
        inp.x = clamp(float(raw[0]), -1, 1)
        inp.y = clamp(float(raw[1]), -1, 1)
        if abs(inp.x) < 0.25:
            inp.x = 0.0
        if abs(inp.y) < 0.25:
            inp.y = 0.0
        inp.held = int(raw[2])
        counts = list(raw[3:9])
        if f.last_counts is None:
            f.last_counts = counts
        for i, b in enumerate(BUTTONS):
            if counts[i] != f.last_counts[i]:
                inp.pressed.add(b)
        f.last_counts = counts
        if "sms" in inp.pressed:
            f._sdir = None  # smash BUTTON: direction comes from the move stick
        inp.sx = float(raw[9]) if len(raw) > 9 else 0.0
        inp.sy = float(raw[10]) if len(raw) > 10 else 0.0
        # flick = stick slammed from neutral to the edge this frame (smash attacks / rolls / platform drops)
        inp.flick_x = abs(inp.x) > 0.75 and abs(f.prev_x) < 0.3
        inp.flick_y = abs(inp.y) > 0.75 and abs(f.prev_y) < 0.3
        inp.tap_down = inp.flick_y and inp.y > 0
        inp.down_cross = inp.y > 0.75 and f.prev_y <= 0.75
        # right stick acts as a smash button with a direction
        if (abs(inp.sx) > 0.6 or abs(inp.sy) > 0.6) and not getattr(f, "_sstick", False):
            inp.pressed.add("sms")
            f._sstick = True
            f._sdir = (inp.sx, inp.sy)
        elif abs(inp.sx) < 0.3 and abs(inp.sy) < 0.3:
            f._sstick = False
        f.prev_x, f.prev_y = inp.x, inp.y
        for b in inp.pressed:
            f.buf[b] = BUFFER
        if inp.flick_x or inp.flick_y:
            f._flick = 4
        return inp

    # ------------------------------------------------------------------ main step
    def step(self, raw_inputs):
        """raw_inputs: {slot: raw list}. Advances the game one frame."""
        self.frame += 1
        self.shake = max(0.0, self.shake - 0.8)
        for e in self.effects:
            e["t"] += 1
        self.effects = [e for e in self.effects if e["t"] < e["l"]]

        for f in self.fighters:
            f.inp = self.build_input(f, raw_inputs.get(f.slot))

        if self.countdown > 0:
            self.countdown -= 1
            for f in self.fighters:
                for b in BUTTONS:
                    f.buf[b] = 0
            return
        if self.over:
            self.end_timer += 1
            return

        for f in self.fighters:
            if f.alive:
                self.update_fighter(f)
        self.update_projectiles()
        self.resolve_hits()
        self.push_apart()
        for f in self.fighters:
            if f.alive and not f.dead:
                self.check_blastzone(f)
        self.check_game_over()

    # ------------------------------------------------------------------ fighter update
    def update_fighter(self, f):
        inp = f.inp
        if f.dead:
            f.respawn_timer -= 1
            if f.respawn_timer <= 0:
                self.respawn(f)
            return

        if f.hitlag > 0:
            f.hitlag -= 1        # frozen: buffered presses wait for hitlag to end
            return
        for b in BUTTONS:
            if f.buf[b] > 0:
                f.buf[b] -= 1
        if getattr(f, "_flick", 0) > 0:
            f._flick -= 1

        for k in list(f.cooldowns):
            f.cooldowns[k] -= 1
            if f.cooldowns[k] <= 0:
                del f.cooldowns[k]
        if f.invuln > 0:
            f.invuln -= 1
        if f.intang > 0:
            f.intang -= 1
        if f.ledge_cd > 0:
            f.ledge_cd -= 1
        if f.drop_timer > 0:
            f.drop_timer -= 1
        if f.tech_window > 0:
            f.tech_window -= 1
        if "shd" in inp.pressed and not f.grounded:
            f.tech_window = 20
        if f.art:
            f.art_t -= 1
            if f.art_t <= 0:
                f.art = None
                f.cooldowns["nspec"] = ART_COOLDOWN
                self.fx("ring", f.x, f.cy, s=0.8, col=(200, 200, 200))
        if f.buff_timer > 0:
            f.buff_timer -= 1
            if f.buff_timer == 0:
                f.buff = 1.0
        if f.form_t > 0:                     # Chikkabu's big form wears off
            f.form_t -= 1
            if f.form_t == 0:
                self.shrink(f)
        if f.char_key == "siren" and f.mermaids < MERMAIDS_MAX:
            f.mer_t += 1
            if f.mer_t >= MERMAID_REGEN:
                f.mer_t = 0
                f.mermaids += 1
        if f.state != "shield":
            f.shield = min(SHIELD_MAX, f.shield + 0.09)

        st = f.state
        handler = getattr(self, "st_" + st, None)
        f.sf += 1
        if handler:
            handler(f, inp)
        if f.dead or not f.alive:
            return
        if f.state in ("ledge", "grabbed", "respawn", "tether", "latched"):
            return
        self.physics(f, inp)

    # ---------- Chikkabu: forms + latch
    def grow(self, f):
        f.set_form(f.char_key + "_big")
        f.form_t = BIG_FORM_FRAMES
        f.bulk = 0.0
        f.intang = max(f.intang, 20)
        f.set_state("idle" if f.grounded else "air")
        self.fx("buff", f.x, f.cy, s=1.6)
        self.fx("dust", f.x, f.y, s=2.0)
        self.shake = max(self.shake, 8)

    def shrink(self, f):
        if f.c.get("form_of"):
            f.set_form(f.c["form_of"])
            self.fx("smoke", f.x, f.cy, s=1.4)
        f.form_t = 0
        f.bulk = 0.0

    def st_latched(self, f, inp):
        """Stuck on someone's head: 5%/s to them, heals 2%/s, can't be knocked off for 3s."""
        v = f.latch_on
        if v is None or v.dead or not v.alive or f.latch_t <= 0 or v.state == "respawn":
            self.unlatch(f)
            return
        f.latch_t -= 1
        f.x, f.y = v.x - v.facing * 6, v.y - v.h + 10
        f.vx = f.vy = f.kvx = f.kvy = 0.0
        f.grounded = False
        f.ground = None
        f.intang = max(f.intang, 2)
        if f.latch_t % 20 == 0:
            d = LATCH_DMG_PER_S / 3.0
            v.damage = min(999.0, v.damage + d)
            v.last_hit_by, v.last_hit_time = f.slot, self.frame
            f.stats["dealt"] += d
            v.stats["taken"] += d
            f.damage = max(0.0, f.damage - LATCH_HEAL_PER_S / 3.0)
            self.fx("hit", v.x, v.y - v.h * 0.8, s=0.3, col=f.color)

    def unlatch(self, f):
        v = f.latch_on
        f.latch_on = None
        f.latch_t = 0
        f.set_state("air")
        f.grounded = False
        f.vy = -9.0
        f.vx = (3.0 if v is None or f.x >= v.x else -3.0)


    # ---------- actionable states
    def try_actions(self, f, inp):
        """Common inputs for idle/run/crouch/air. Returns True if an action started."""
        g = f.grounded
        # specials
        if f.buf["spc"]:
            f.buf["spc"] = 0
            name = self.pick_special(f, inp)
            if name:
                self.start_special(f, name, inp)
                return True
        # smash button / flick-attack
        smash = f.buf["sms"] > 0 or (f.buf["atk"] > 0 and getattr(f, "_flick", 0) > 0 and g)
        if smash:
            sd = getattr(f, "_sdir", None) if f.buf["sms"] else None
            dx, dy = sd if sd else (inp.x, inp.y)
            f.buf["sms"] = 0
            f.buf["atk"] = 0
            if g:
                if dy < -0.5 and abs(dy) >= abs(dx):
                    name = "usmash"
                elif dy > 0.5 and abs(dy) >= abs(dx):
                    name = "dsmash"
                else:
                    if dx > 0.3:
                        f.facing = 1
                    elif dx < -0.3:
                        f.facing = -1
                    name = "fsmash"
                f.start_move(name, self)
                return True
            name = self.pick_aerial(f, dx, dy)
            f.start_move(name, self)
            return True
        if f.buf["grb"] or (f.buf["atk"] and inp.h(B_SHD) and g):
            f.buf["grb"] = 0
            f.buf["atk"] = 0
            if g:
                f.start_move("grab", self)
                return True
            # grab in the air = air dodge in Smash? no - just do nair
            f.start_move("nair", self)
            return True
        if f.buf["atk"]:
            f.buf["atk"] = 0
            if g:
                if f.state == "run" and abs(f.vx) > f.st("run") * 0.6:
                    f.start_move("dash", self)
                elif inp.y < -0.5 and abs(inp.y) >= abs(inp.x):
                    f.start_move("utilt", self)
                elif inp.y > 0.5 and abs(inp.y) >= abs(inp.x):
                    f.start_move("dtilt", self)
                elif abs(inp.x) > 0.5:
                    f.facing = 1 if inp.x > 0 else -1
                    f.start_move("ftilt", self)
                else:
                    f.start_move("jab1", self)
            else:
                f.start_move(self.pick_aerial(f, inp.x, inp.y), self)
            return True
        # shield / dodges
        if g and inp.h(B_SHD):
            f.set_state("shield")
            return True
        if not g and f.buf["shd"] and not f.airdodge_used:
            f.buf["shd"] = 0
            self.start_airdodge(f, inp)
            return True
        # jump
        if f.buf["jump"]:
            if g:
                f.buf["jump"] = 0
                f.set_state("jumpsquat")
                return True
            if f.jumps_left > 0:
                f.buf["jump"] = 0
                if inp.y < -0.5 and f.state == "air":
                    f.dj_pending = 3
                    return True
                self.double_jump(f, inp)
                return True
        return False

    def pick_aerial(self, f, x, y):
        if y < -0.5 and abs(y) >= abs(x):
            return "uair"
        if y > 0.5 and abs(y) >= abs(x):
            return "dair"
        if x * f.facing > 0.4:
            return "fair"
        if x * f.facing < -0.4:
            return "bair"
        return "nair"

    def pick_special(self, f, inp):
        if inp.y < -0.5 and abs(inp.y) >= abs(inp.x):
            name = "uspec"
        elif inp.y > 0.5 and abs(inp.y) >= abs(inp.x):
            name = "dspec"
        elif abs(inp.x) > 0.5:
            name = "sspec"
            f.facing = 1 if inp.x > 0 else -1
            if not f.grounded and f.side_used:
                return None
        else:
            name = "nspec"
        if not f.grounded and (name + "_air") in f.moves:
            name += "_air"
        if f.cooldowns.get(name.replace("_air", ""), 0) > 0:
            return None
        if not f.grounded and name in f.air_once:
            return None
        return name

    def start_special(self, f, name, inp):
        f.start_move(name, self)

    def double_jump(self, f, inp):
        f.jumps_left -= 1
        f.vy = -f.st("djump")
        f.vx = inp.x * f.st("air")
        f.kvy = 0.0             # a jump stops you rising/falling from a hit, but not the sideways launch
        f.ff = False
        if inp.x:
            f.facing = f.facing  # no turning in the air (like Smash)
        f.set_state("air")
        f._djump_anim = 14
        self.fx("jump", f.x, f.y, s=0.8)

    def start_airdodge(self, f, inp):
        f.airdodge_used = True
        f.set_state("airdodge")
        mag = math.hypot(inp.x, inp.y)
        if mag > 0.4:
            f._ad_dir = (inp.x / mag, inp.y / mag)
            f.vx, f.vy = f._ad_dir[0] * 13.0, f._ad_dir[1] * 13.0
        else:
            f._ad_dir = None
            f.vx *= 0.3
            f.vy = min(f.vy, 1.0)
        f.ff = False            # launch momentum (kvx/kvy) carries on - you can't dodge out of a KO

    def st_idle(self, f, inp):
        if self.try_actions(f, inp):
            return
        if inp.tap_down and f.ground not in (None, "main"):
            self.drop_through(f)
            return
        if inp.y > 0.5:
            f.set_state("crouch")
            return
        if inp.x:
            f.facing = 1 if inp.x > 0 else -1
            f.set_state("run")

    def st_run(self, f, inp):
        if self.try_actions(f, inp):
            return
        if inp.tap_down and f.ground not in (None, "main"):
            self.drop_through(f)
            return
        if not inp.x:
            f.set_state("idle")
            return
        f.facing = 1 if inp.x > 0 else -1

    def st_crouch(self, f, inp):
        if self.try_actions(f, inp):
            return
        if inp.tap_down and f.ground not in (None, "main"):
            self.drop_through(f)
            return
        if inp.y <= 0.5:
            f.set_state("idle")

    def drop_through(self, f):
        f.grounded = False
        f.ground = None
        f.drop_timer = 12
        f.y += 3
        f.vy = 2.0
        f.set_state("air")

    def st_air(self, f, inp):
        if getattr(f, "_djump_anim", 0) > 0:
            f._djump_anim -= 1
        if f.dj_pending > 0:
            if f.buf["atk"] or f.buf["spc"] or f.buf["sms"]:
                f.dj_pending = 0          # up + attack/special right after tapping W: no jump, just the move
            else:
                f.dj_pending -= 1
                if f.dj_pending == 0 and f.jumps_left > 0:
                    self.double_jump(f, inp)
                    return
        self.try_actions(f, inp)

    def st_jumpsquat(self, f, inp):
        # W is both 'up' and 'jump' on keyboard: up + attack/special during jumpsquat = grounded up-attack instead
        if inp.y < -0.5 and (f.buf["atk"] or f.buf["spc"] or f.buf["sms"]):
            f.buf["jump"] = 0
            f.set_state("idle")
            if f.buf["atk"] and not f.buf["sms"]:
                f.buf["atk"] = 0
                f.start_move("utilt", self)
            else:
                self.try_actions(f, inp)
            return
        if f.sf >= JUMPSQUAT:
            full = inp.h(B_JUMP)
            f.vy = -(f.st("jump") if full else f.st("hop"))
            f.vx = clamp(f.vx + inp.x * 2.0, -f.st("air") * 1.1, f.st("air") * 1.1)
            f.grounded = False
            f.ground = None
            f.set_state("air")
            f._cut_ok = full          # releasing jump while rising = lower jump (variable height)
            f._jump_t = 0
            self.fx("jump", f.x, f.y, s=0.7)
            # buffered aerial straight out of jumpsquat
            self.try_actions(f, inp)

    def st_land(self, f, inp):
        if f.sf >= f.landlag:
            f.set_state("idle")
            self.st_idle(f, inp)

    def st_shield(self, f, inp):
        f.shield -= 0.14
        if f.shield <= 0:
            self.shield_break(f)
            return
        if f.sf < 2:
            return
        if f.buf["jump"]:
            f.buf["jump"] = 0
            f.set_state("jumpsquat")
            return
        if f.buf["atk"] or f.buf["grb"]:
            f.buf["atk"] = f.buf["grb"] = 0
            f.start_move("grab", self)
            return
        if f.buf["spc"]:
            f.buf["spc"] = 0
            name = self.pick_special(f, inp)
            if name:
                self.start_special(f, name, inp)
                return
        if inp.flick_x or (getattr(f, "_flick", 0) > 0 and abs(inp.x) > 0.75):
            f._flick = 0
            f.set_state("roll")
            f._roll_dir = 1 if inp.x > 0 else -1
            return
        if inp.flick_y and inp.y > 0 or (getattr(f, "_flick", 0) > 0 and inp.y > 0.75):
            f._flick = 0
            f.set_state("spotdodge")
            return
        if not inp.h(B_SHD):
            f.set_state("shield_drop")

    def st_shield_drop(self, f, inp):
        if f.sf >= 7:
            f.set_state("idle")

    def st_shieldstun(self, f, inp):
        if f.sf >= getattr(f, "_sstun", 4):
            f.set_state("shield" if inp.h(B_SHD) else "shield_drop")

    def shield_break(self, f):
        f.shield = 30.0
        f.set_state("dizzy")
        f.dizzy = int(max(120, 260 - f.damage))
        f.grounded = False
        f.vy = -13.0
        self.shake = 10
        self.fx("shieldbreak", f.x, f.cy, s=1.0, col=f.color)

    def st_dizzy(self, f, inp):
        f.dizzy -= 1 + (1 if inp.pressed else 0) * 3
        if f.dizzy <= 0 and f.grounded:
            f.set_state("idle")

    def st_roll(self, f, inp):
        total, a, b = 30, 4, 18
        if a <= f.sf <= b:
            f.intang = max(f.intang, 1)
        if f.sf <= 22:
            f.vx = f._roll_dir * 10.5
        else:
            f.vx = 0
        if f.sf >= total:
            f.facing = -f._roll_dir
            f.set_state("idle")

    def st_spotdodge(self, f, inp):
        if 3 <= f.sf <= 17:
            f.intang = max(f.intang, 1)
        f.vx = 0
        if f.sf >= 26:
            f.set_state("shield" if inp.h(B_SHD) else "idle")

    def st_airdodge(self, f, inp):
        d = f._ad_dir
        if 3 <= f.sf <= (20 if d else 28):
            f.intang = max(f.intang, 1)
        if d:
            k = max(0.0, 1.0 - f.sf / 22.0)
            f.vx, f.vy = d[0] * 13.0 * k, d[1] * 13.0 * k
        if f.sf >= (36 if d else 44):
            f.set_state("air")

    def st_helpless(self, f, inp):
        pass

    def st_parachute(self, f, inp):
        """Chiikawa floating down under her bag: can still attack / air dodge (that closes the bag)."""
        self.try_actions(f, inp)

    def st_sleep(self, f, inp):
        f.vx = 0.0
        f.sleep_t -= 1 + (4 if inp.pressed else 0)
        if f.sleep_t <= 0:
            f.set_state("idle" if f.grounded else "air")

    def st_glide(self, f, inp):
        if f.sf > 240 or f.buf["spc"] or (inp.y > 0.6):
            f.buf["spc"] = 0
            f.set_state("helpless")

    def st_hitstun(self, f, inp):
        # tumbling for a long time? you may air dodge / act out of it early (like Smash Ultimate)
        if f.tumble and not f.grounded and f.hitlag == 0:
            if f.sf >= AIRDODGE_CANCEL and f.buf["shd"] and not f.airdodge_used:
                f.buf["shd"] = 0
                f.hitstun = 0
                f.tech_window = 0
                self.start_airdodge(f, inp)
                return
            if f.sf >= ACTION_CANCEL and (f.buf["atk"] or f.buf["spc"] or f.buf["jump"] or f.buf["sms"]):
                f.hitstun = 0
                f.set_state("air")
                self.try_actions(f, inp)
                return
        f.hitstun -= 1
        if f.tumble:
            f.tumble_spin += 18
        if f.hitstun <= 0:
            if f.grounded:
                f.set_state("idle")
            else:
                f.set_state("air")  # tumble: can act again (renderer still shows tumbling until you act)
                f._tumbling = f.tumble

    def st_knockdown(self, f, inp):
        if f.sf >= 26 or (f.sf > 8 and (inp.pressed or inp.x)):
            f.set_state("getup")
            f.intang = 18

    def st_getup(self, f, inp):
        if f.sf >= 18:
            f.set_state("idle")

    def st_tech(self, f, inp):
        f.intang = max(f.intang, 1) if f.sf <= 14 else f.intang
        if f.sf >= 20:
            f.set_state("idle")

    def st_respawn(self, f, inp):
        f.vx = f.vy = 0
        f.invuln = 120
        if f.sf > 20 and (inp.x or inp.y > 0.5 or inp.pressed) or f.sf > 300:
            f.set_state("air")
            f.grounded = False

    # ---------- attacks
    def st_attack(self, f, inp):
        m = f.move_data()
        if m is None:
            f.set_state("idle" if f.grounded else "air")
            return
        # charge: hold at the charge frame while the button is held
        # (smash attacks: smash/attack button, specials: special button)
        if m.get("bulk") and f.bulk >= 1.0:          # meter full: transform right away
            self.grow(f)
            return
        if m.get("charge") and f.mf == m["charge"]:
            cmax = m.get("charge_max", 60)
            if f.move.startswith(SPECIALS):
                held = inp.h(B_SPC)
            else:
                held = inp.h(B_SMS) or inp.h(B_ATK)
            if held and m.get("bulk"):
                f.bulk = min(1.0, f.bulk + 1.0 / BULK_HOLD_FRAMES)
                f.charging = True
                f.sf -= 1
                if f.bulk >= 1.0:
                    self.grow(f)
                return
            if held and f.charge < cmax:
                f.charge += 1
                f.charging = True
                f.dmg_mult = 1.0 + m.get("charge_mult", 0.4) * f.charge / float(cmax)
                f.sf -= 1
                return
        f.charging = False
        f.mf += 1
        mf = f.mf

        # Monado-style art switch: cycles green -> blue -> yellow -> red -> off
        if m.get("art_switch") and mf == m["art_switch"]:
            nxt = ART_ORDER[0] if f.art is None else (
                ART_ORDER[ART_ORDER.index(f.art) + 1] if ART_ORDER.index(f.art) + 1 < len(ART_ORDER) else None)
            f.art = nxt
            f.art_t = ART_TIME if nxt else 0
            if nxt is None:
                f.cooldowns["nspec"] = 60
            self.fx("ring", f.x, f.cy, s=1.2, col=ARTS[nxt]["col"] if nxt else (200, 200, 200))
        # teleport (Usagi): pick a direction with the stick, vanish, reappear further along
        tp = m.get("teleport")
        if tp:
            a_, b_, dist_ = tp
            if mf == a_:
                mag = math.hypot(inp.x, inp.y)
                f._tp = (inp.x / mag, inp.y / mag) if mag > 0.3 else (0.0, -1.0)
                self.fx("respawn", f.x, f.cy, col=f.color)
            if a_ <= mf <= b_:
                sp = dist_ / float(b_ - a_ + 1)
                f.vx, f.vy = f._tp[0] * sp, f._tp[1] * sp
                if f.vy < 0:
                    f.grounded = False
                    f.ground = None
            elif mf == b_ + 1:
                f.vx *= 0.15
                f.vy = min(0.0, f.vy * 0.15)
                self.fx("respawn", f.x, f.cy, col=f.color)
        # riding on someone's head (Momonga's nibble)
        if m.get("ride") and f.grabbing:
            t = f.grabbing
            f.x, f.y = t.x, t.y - t.h + 8
            f.vx = f.vy = f.kvx = f.kvy = 0.0
            f.grounded = False
            f.ground = None
        # claw tether: if the claw tip reaches a ledge, reel in
        tt = m.get("tether")
        if tt and tt[0] <= mf <= tt[1]:
            k = (mf - tt[0]) / float(max(1, tt[1] - tt[0]))
            reach_now = tt[2] * k + 30
            # the claw grabs the first opponent it touches and yanks them in (like Byleth / Joker)
            ang_ = math.radians(tt[3])
            tipx = f.x + math.cos(ang_) * tt[2] * k * f.facing
            tipy = f.cy - math.sin(ang_) * tt[2] * k
            if m.get("tether_grab"):
                for t in self.fighters:
                    if t is f or not t.alive or t.dead or t.intang or t.invuln or t.grabbed_by or t.state in ("ledge", "respawn"):
                        continue
                    if circle_rect(tipx, tipy, 26, t.hurtbox()):
                        f.grabbing, t.grabbed_by = t, f
                        t.set_state("grabbed")
                        t._pull_from = (t.x, t.y)
                        t.vx = t.vy = t.kvx = t.kvy = 0
                        self.fx("spark", tipx, tipy, s=0.9, col=f.color)
                        f.start_move(m["tether_grab"], self)
                        return
            for lx, ly, d in self.ledges:
                if d != f.facing or any(o.ledge and o.ledge[0] == lx for o in self.fighters if o is not f):
                    continue
                fwd = (lx - f.x) * f.facing          # ledge must be in front of us
                up = f.cy - ly
                if fwd <= 0 or up < -40:
                    continue
                dist = math.hypot(fwd, up)
                ang_to = math.degrees(math.atan2(up, fwd))
                # auto-aim like Smash tethers: anything within ~40 degrees of the claw's aim and within reach
                if -35 <= ang_to <= tt[3] + 45 and dist <= reach_now:
                    f.tether_to = (lx, ly, d)
                    f.set_state("tether")
                    self.fx("spark", lx, ly, s=0.9, col=(255, 255, 255))
                    return

        # rapid jabs / seed spit: keep looping while the button is held or mashed
        rp = m.get("rapid")
        if rp and mf == rp[2]:
            btn, back, at, mx, fin = rp
            if (inp.h(BIT[btn]) or f.buf[btn]) and f.rapid < mx:
                f.rapid += 1
                f.buf[btn] = 0
                f.mf = mf = back
                f.move_hit = {}
            elif fin:
                f.start_move(fin, self)
                return
        # chained follow-ups (press a button during a window)
        for fl in m.get("follow", []):
            btn, fa, fb, nm = fl[:4]
            if fa <= mf <= fb and f.buf[btn]:
                f.buf[btn] = 0
                f.start_move(nm, self)
                return

        if m.get("intang") and m["intang"][0] <= mf <= m["intang"][1]:
            f.intang = max(f.intang, 1)
        # velocity scripts
        for a, b, vx, vy in m.get("drift", []):
            if a <= mf <= b:
                if vx is not None:
                    f.vx = vx * f.facing
                if vy is not None:
                    f.vy = vy
                    if vy < 0:
                        f.grounded = False
                        f.ground = None
        # projectiles (charged specials can swap to a bigger version)
        projs = m.get("proj", [])
        if m.get("proj_charged") and f.charge >= m.get("charge_full", m.get("charge_max", 60) * 0.66):
            projs = m["proj_charged"]
        for pf, pd in projs:
            if mf == pf:
                if m.get("mermaid"):              # Siren: only if a mermaid is home
                    if f.mermaids <= 0:
                        continue
                    f.mermaids -= 1
                self.spawn_projectile(f, pd, m)
        if m.get("heal") and mf == m["heal"][0]:
            f.damage = max(0.0, f.damage - m["heal"][1])
            self.fx("heal", f.x, f.cy, s=1.0)
        if m.get("buff") and mf == m["buff"][0]:
            f.buff = m["buff"][1]
            f.buff_timer = 600
            self.fx("buff", f.x, f.cy, s=1.0)
        if m.get("pummel") and mf == m["pummel"][0] and f.grabbing:
            t = f.grabbing
            t.damage += m["pummel"][1]
            f.stats["dealt"] += m["pummel"][1]
            t.stats["taken"] += m["pummel"][1]
            t.hitlag = f.hitlag = 3
            self.fx("hit", t.x, t.cy, s=0.5, col=f.color)
        for pf, pd in m.get("pummels", []):
            if mf == pf and f.grabbing:
                t = f.grabbing
                t.damage += pd
                f.stats["dealt"] += pd
                t.stats["taken"] += pd
                t.hitlag = f.hitlag = 4
                self.fx("hit", t.x, t.cy, s=0.6, col=f.color)
                self.shake = max(self.shake, 3)
        if m.get("throw") and f.grabbing and mf == m["throw"][0]:
            self.do_throw(f, m["throw"])
        if m.get("grabbox") and not f.grabbing:
            (a, b), gx, gy, gr = m["grabbox"]
            if a <= mf <= b:
                self.try_grab(f, gx, gy, gr, air_ok=m.get("grab_air", False))
                if f.grabbing:
                    return
        # jab combo
        nxt = m.get("next")
        if nxt and mf >= nxt[1] and f.buf["atk"] and f.grounded:
            f.buf["atk"] = 0
            f.start_move(nxt[0], self)
            return
        if mf >= m["frames"]:
            self.end_move(f, m)

    def end_move(self, f, m):
        name = f.move
        if f.grabbing and name in ("grab", "pummel"):
            f.set_state("holding")
            return
        if f.grabbing:            # a command grab that never threw
            self.grab_release(f)
            return
        if f.grounded:
            f.set_state("idle")
        elif m.get("parachute"):
            f.set_state("parachute")
        elif m.get("glide"):
            f.set_state("glide")
        elif m.get("helpless"):
            f.set_state("helpless")
        else:
            f.set_state("air")

    # ---------- grabs
    def try_grab(self, f, gx, gy, gr, air_ok=False):
        cx, cy = f.x + gx * f.facing, f.cy + gy
        for t in self.fighters:
            if t is f or not t.alive or t.dead or t.intang or t.invuln or t.grabbed_by or (not t.grounded and not air_ok):
                continue
            if t.state in ("ledge", "respawn"):
                continue
            if circle_rect(cx, cy, gr, t.hurtbox()):
                f.grabbing = t
                t.grabbed_by = f
                t.set_state("grabbed")
                t.vx = t.vy = t.kvx = t.kvy = 0
                if t.grabbing:  # break their grab
                    t.grabbing.grabbed_by = None
                    t.grabbing.set_state("idle")
                    t.grabbing = None
                f.grab_timer = int(70 + t.damage * 0.9)
                self.fx("spark", cx, cy, s=0.6, col=f.color)
                m = f.move_data() if f.state == "attack" else None
                if m and m.get("on_grab"):
                    f.start_move(m["on_grab"], self)      # command grab: straight into its own pinch/throw
                    f.vx = 0.0
                    f.vy = min(f.vy, 0.0) if not f.grounded else 0.0
                else:
                    f.set_state("holding")
                return

    def st_holding(self, f, inp):
        t = f.grabbing
        if not t or not t.alive or t.dead:
            f.grabbing = None
            f.set_state("idle")
            return
        f.vx = 0
        f.grab_timer -= 1
        if t.inp.pressed or (abs(t.inp.x) > 0.5 and t.inp.flick_x):
            f.grab_timer -= 5 * max(1, len(t.inp.pressed))
        if f.grab_timer <= 0:
            self.grab_release(f)
            return
        if f.sf < 6:
            return
        x = inp.x * f.facing
        if x > 0.6:
            f.start_move("fthrow", self)
        elif x < -0.6:
            f.start_move("bthrow", self)
        elif inp.y < -0.6:
            f.start_move("uthrow", self)
        elif inp.y > 0.6:
            f.start_move("dthrow", self)
        elif f.buf["atk"]:
            f.buf["atk"] = 0
            f.start_move("pummel", self)

    def grab_release(self, f):
        t = f.grabbing
        f.grabbing = None
        f.set_state("idle")
        f.vx = -4 * f.facing
        if t:
            t.grabbed_by = None
            t.set_state("idle" if t.grounded else "air")
            t.vx = 6 * f.facing

    def st_grabbed(self, f, inp):
        g = f.grabbed_by
        if not g or g.grabbing is not f:
            f.grabbed_by = None
            f.set_state("idle" if f.grounded else "air")
            return
        gm = g.move_data() if g.state == "attack" else None
        if gm and gm.get("ride"):          # someone is sitting on our head: we stay put
            f.vx = f.vy = 0
            return
        fx_, fy_ = g.x + g.facing * (g.w / 2 + f.w / 2 - 12), g.y
        if gm and gm.get("pull"):            # being reeled in toward the holder
            a_, b_ = gm["pull"]
            k = clamp((g.mf - a_) / float(max(1, b_ - a_)), 0.0, 1.0)
            sx_, sy_ = getattr(f, "_pull_from", (fx_, fy_))
            fx_, fy_ = sx_ + (fx_ - sx_) * k, sy_ + (fy_ - sy_) * k
        f.x, f.y = fx_, fy_
        f.facing = -g.facing
        f.vx = f.vy = 0

    def do_throw(self, f, th):
        _, dmg, ang, bkb, kbg = th
        t = f.grabbing
        f.grabbing = None
        t.grabbed_by = None
        t.state = "air"
        hb = {"dmg": dmg, "ang": ang, "bkb": bkb, "kbg": kbg, "throw": True}
        self.apply_hit(f, t, hb, f.facing, t.x, t.cy, unblockable=True)

    # ---------- ledges
    def st_tether(self, f, inp):
        """Being reeled in by Kani's claw toward a ledge."""
        lx, ly, d = f.tether_to
        hx, hy = lx - d * (f.w / 2 - 6), ly + f.h * 0.72
        dx, dy = hx - f.x, hy - f.y
        dist = math.hypot(dx, dy)
        f.vx = f.vy = f.kvx = f.kvy = 0.0
        if dist < 26 or f.sf > 40:
            if dist < 26 and not any(o.ledge and o.ledge[0] == lx for o in self.fighters if o is not f):
                self.grab_ledge(f, (lx, ly, d))
            else:
                f.set_state("helpless")
            return
        f.x += dx / dist * 24
        f.y += dy / dist * 24

    def st_ledge(self, f, inp):
        lx, ly, d = f.ledge
        f.x = lx - d * (f.w / 2 - 6)
        f.y = ly + f.h * 0.72
        f.facing = d
        f.vx = f.vy = 0
        f.grounded = False
        if f.sf < 8:
            return
        toward = inp.x * d
        if f.buf["jump"] or (inp.y < -0.6 and f.inp.flick_y):
            f.buf["jump"] = 0
            self.leave_ledge(f)
            f.vy = -f.st("jump") * 1.02
            f.vx = d * 2.5
            f.set_state("air")
            f.jumps_left = f.c["jumps"] - 1
            self.fx("jump", f.x, f.y, s=0.6)
        elif f.buf["atk"] or f.buf["spc"] or f.buf["sms"]:
            f.buf["atk"] = f.buf["spc"] = f.buf["sms"] = 0
            self.climb(f)
            f.start_move("getup", self)
        elif f.buf["shd"]:
            f.buf["shd"] = 0
            self.climb(f)
            f.set_state("roll")
            f._roll_dir = d
            f.intang = 20
        elif toward > 0.6 or inp.y < -0.6:
            self.climb(f)
            f.set_state("getup")
            f.intang = 18
            f.vx = d * 3
        elif toward < -0.6 or inp.y > 0.6 or f.sf > LEDGE_MAX_HANG:
            self.leave_ledge(f)
            f.ledge_cd = 30
            f.set_state("air")

    def leave_ledge(self, f):
        f.ledge = None

    def climb(self, f):
        lx, ly, d = f.ledge
        f.ledge = None
        f.x = lx + d * (f.w / 2 + 4)
        f.y = ly
        f.grounded = True
        f.ground = "main"
        f.jumps_left = f.c["jumps"] - 1
        f.side_used = f.airdodge_used = False

    def try_ledge(self, f):
        if f.grounded or f.ledge_cd > 0:
            return
        st = f.state
        if st == "air":
            if f.vy < -4.0:            # still rising fast from a jump: no grab (like Smash)
                return
        elif st in ("helpless", "glide", "airdodge", "parachute"):
            pass
        elif st == "attack":
            m = f.move_data()
            # recovery moves snap to the ledge at any point once they're going
            if not (m and (m.get("helpless") or m.get("glide") or m.get("ledge_ok")) and f.mf >= 3):
                return
        else:
            return
        for lx, ly, d in self.ledges:
            if any(o.ledge and o.ledge[0] == lx for o in self.fighters if o is not f):
                continue  # someone is hogging it
            out = (lx - f.x) * d       # > 0 when we're outside the stage on that ledge's side
            # generous grab zone: ledge anywhere from just above your head down to your feet
            if -14 <= out <= f.w / 2 + 58 and f.y - f.h - 40 <= ly <= f.y + 26:
                self.grab_ledge(f, (lx, ly, d))
                return

    def grab_ledge(self, f, ledge):
        f.ledge = ledge
        f.set_state("ledge")
        f.ff = False
        f.kvx = f.kvy = 0
        f.vx = f.vy = 0
        regrabs = getattr(f, "_regrabs", 0)
        f.invuln = max(f.invuln, 40 if regrabs == 0 else 0)
        f._regrabs = regrabs + 1
        f.jumps_left = f.c["jumps"] - 1
        f.side_used = f.airdodge_used = False
        f.glide_t = 0
        f.air_once = set()
        self.fx("spark", ledge[0], ledge[1], s=0.6, col=(255, 255, 255))
        self.st_ledge(f, f.inp)

    # ------------------------------------------------------------------ physics
    def physics(self, f, inp):
        c = f.c
        st = f.state
        m = f.move_data() if st == "attack" else None
        g = f.grounded

        # ---- horizontal control
        if g:
            if st == "run":
                target = inp.x * f.st("run")
                f.vx += clamp(target - f.vx, -1.6, 1.6)
            elif st in ("idle", "crouch", "land", "shield", "shield_drop", "shieldstun", "attack", "jumpsquat",
                        "holding", "getup", "knockdown", "tech", "dizzy", "hitstun", "sleep"):
                drifting = m and any(a <= f.mf <= b and vx is not None for a, b, vx, vy in m.get("drift", []))
                if not drifting:
                    fr = 0.9 if st == "hitstun" else 0.7
                    f.vx = f.vx - fr if f.vx > fr else f.vx + fr if f.vx < -fr else 0.0
        else:
            steer = 1.0
            if st == "attack":
                steer = m.get("steer", 1.0 if f.move in ("nair", "fair", "bair", "uair", "dair") else 0.5)
                if any(a <= f.mf <= b and vx is not None for a, b, vx, vy in m.get("drift", [])):
                    steer = 0.0
            elif st in ("hitstun", "airdodge", "dizzy"):
                steer = 0.0
            elif st == "helpless":
                steer = 0.75
            elif st in ("glide", "parachute"):
                steer = 1.0
            if steer > 0:
                top = f.st("air") * (1.1 if st == "glide" else 1.0)
                if inp.x:
                    nv = f.vx + inp.x * f.st("accel") * steer
                    if abs(nv) <= top or abs(nv) < abs(f.vx):
                        f.vx = nv
                    elif abs(f.vx) < top:
                        f.vx = math.copysign(top, nv)
                else:
                    f.vx = f.vx - 0.1 if f.vx > 0.1 else f.vx + 0.1 if f.vx < -0.1 else 0.0

            # ---- gravity / fast fall
            grav = f.st("grav")
            if st == "attack":
                grav *= m.get("grav", 1.0)
            if st == "airdodge" and f._ad_dir:
                grav = 0.0
            fall = f.st("ff") if f.ff else f.st("fall")
            if st == "glide":
                fall = 2.2
            if st == "parachute":
                fall = 2.4
            # floaty characters (Momonga): hold jump while falling to glide, up to c["float"] frames per trip
            f.gliding = False
            if c.get("float") and st in ("air", "attack") and inp.h(B_JUMP) and f.vy >= 0 and not f.ff \
                    and getattr(f, "glide_t", 0) < c["float"] and f.dj_pending == 0:
                f.glide_t = getattr(f, "glide_t", 0) + 1
                f.gliding = True
                fall = 2.0
                if f.vy > fall:
                    f.vy = max(fall, f.vy - 1.2)
            # variable jump height: let go of jump while still rising and you stop going up as high
            if getattr(f, "_cut_ok", False):
                f._jump_t += 1
                if st not in ("air", "attack") or f.vy >= -1.0 or f._jump_t > 22:
                    f._cut_ok = False
                elif not inp.h(B_JUMP):
                    f.vy = max(f.vy, -f.st("hop") * 0.92)
                    f._cut_ok = False
            scripted = st == "attack" and any(a <= f.mf <= b and vy is not None for a, b, vx, vy in m.get("drift", []))
            if not scripted and not (st == "airdodge" and f._ad_dir):
                if f.vy <= fall:
                    f.vy = min(f.vy + grav, fall)
                else:
                    f.vy = max(fall, f.vy - grav)
            # fast fall: hold down once you're at the top of your jump or falling
            if st in ("air", "attack", "helpless") and not f.ff and f.vy > -0.5 and inp.y > 0.6 and not scripted:
                f.ff = True
                f.vy = f.st("ff")
                self.fx("spark", f.x, f.cy - f.h * 0.4, s=0.4, col=(255, 255, 255))

        # ---- launch velocity decays
        if f.kvx or f.kvy:
            sp = math.hypot(f.kvx, f.kvy)
            if sp <= KB_DECAY:
                f.kvx = f.kvy = 0.0
            else:
                k = (sp - KB_DECAY) / sp
                f.kvx *= k
                f.kvy *= k
            if f.tumble and sp > 12 and self.frame % 3 == 0:
                self.fx("smoke", f.x, f.cy, s=min(1.6, sp / 20))

        px, py = f.x, f.y
        f.x += f.vx + f.kvx
        f.y += f.vy + f.kvy
        self.collide_stage(f, px, py)
        if not f.grounded and f.state != "ledge":
            self.try_ledge(f)

    def collide_stage(self, f, px, py):
        sx, sy, sw, sh = self.stage["main"]
        left, right, top, bottom = sx, sx + sw, sy, sy + sh
        hw = f.w / 2
        if f.grounded:
            # are we still standing on something?
            if f.ground == "main":
                if left - 2 <= f.x <= right + 2:
                    f.y = top
                    return
            elif f.ground is not None:
                plx, ply, plw = self.stage["platforms"][f.ground]
                if plx - 2 <= f.x <= plx + plw + 2:
                    f.y = ply
                    return
            # walked off an edge - only some states may leave the platform (others stop at the edge, like Smash)
            can_leave = f.state in ("idle", "run", "crouch", "hitstun", "dizzy", "air") or (
                f.state == "attack" and f.move and f.move.startswith(("sspec", "nspec", "dspec", "uspec")))
            if not can_leave:
                if f.ground == "main":
                    f.x = clamp(f.x, left, right)
                    f.y = top
                else:
                    plx, ply, plw = self.stage["platforms"][f.ground]
                    f.x = clamp(f.x, plx, plx + plw)
                    f.y = ply
                f.vx = 0.0
                return
            f.grounded = False
            f.ground = None
            if f.state in ("idle", "run", "crouch"):
                f.set_state("air")
            elif f.state == "attack":
                pass
            f.jumps_left = f.c["jumps"] - 1
            return

        moving_down = f.y >= py
        # main stage top
        if moving_down and py <= top + 1 and f.y >= top and left <= f.x <= right:
            self.land(f, top, "main")
            return
        # the island underneath: push out along whichever surface we touch (slopes make you slide, not stop)
        if f.y > top and f.state not in ("ledge", "grabbed", "respawn", "dead"):
            n = self.push_out_of_island(f)
            if n is not None and n[1] < -0.8 and left <= f.x <= right:     # popped out through the top
                f.y = top
                self.land(f, top, "main")
                return
        # soft platforms
        if moving_down and f.drop_timer <= 0:
            for i, (plx, ply, plw) in enumerate(self.stage["platforms"]):
                if py <= ply + 1 and f.y >= ply and plx <= f.x <= plx + plw:
                    if f.state == "hitstun" and f.kvy < -2:
                        continue
                    self.land(f, ply, i)
                    return

    def push_out_of_island(self, f):
        poly = self.poly
        r = min(f.w, f.h) * 0.42
        cx, cy = f.x, f.y - f.h * 0.5
        inside = point_in_poly(cx, cy, poly)
        best = None
        for i in range(len(poly)):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % len(poly)]
            ex, ey = bx - ax, by - ay
            L2 = ex * ex + ey * ey or 1.0
            t = clamp(((cx - ax) * ex + (cy - ay) * ey) / L2, 0.0, 1.0)
            qx, qy = ax + ex * t, ay + ey * t
            dist = math.hypot(cx - qx, cy - qy)
            if best is None or dist < best[0]:
                L = math.sqrt(L2)
                nx, ny = ey / L, -ex / L
                mx, my = (ax + bx) / 2, (ay + by) / 2
                if (mx - self.poly_c[0]) * nx + (my - self.poly_c[1]) * ny < 0:
                    nx, ny = -nx, -ny
                best = (dist, qx, qy, nx, ny)
        dist, qx, qy, nx, ny = best
        if not inside and dist >= r:
            return None
        # move the body circle just outside the surface
        tx, ty = qx + nx * r, qy + ny * r
        f.x += tx - cx
        f.y += ty - cy
        # slopes redirect you: the speed going INTO the surface turns into sliding ALONG it
        # (so jumping up into the slanted underside carries you out and up toward the ledge)
        d = f.vx * nx + f.vy * ny
        if d < 0:
            speed = math.hypot(f.vx, f.vy)
            tx_, ty_ = f.vx - d * nx, f.vy - d * ny
            tl = math.hypot(tx_, ty_)
            if ny > 0.2 and speed > 2.0:                 # hitting the underside: slide along it, keep most speed
                if tl < 0.5:                             # head-on: pick the direction that leads outward/up
                    tx_, ty_ = (-ny, nx) if nx * -ny + ny * nx >= 0 else (ny, -nx)
                    tx_, ty_ = (ny, -nx) if ny * (f.x - self.poly_c[0]) >= 0 else (-ny, nx)
                    tl = 1.0
                k = speed * 0.85 / tl
                f.vx, f.vy = tx_ * k, ty_ * k
            else:
                f.vx, f.vy = tx_, ty_
        d = f.kvx * nx + f.kvy * ny
        if d < 0:                               # launched into the stage: bounce off a bit
            f.kvx -= 1.6 * d * nx
            f.kvy -= 1.6 * d * ny
        return nx, ny

    def land(self, f, y, ground):
        f.y = y
        f.ground = ground
        f._regrabs = 0
        f._tumbling = False
        st = f.state
        if st == "attack":
            m = f.move_data()
            if m.get("land_move"):
                f.grounded = True
                f.vy = f.kvy = 0
                f.start_move(m["land_move"], self)
                self.shake = max(self.shake, 4)
                return
            lag = m.get("land", 0)
            if f.move in ("nair", "fair", "bair", "uair", "dair"):
                f.air_land(self, lag)
            elif m.get("helpless") or m.get("glide"):
                f.air_land(self, 20)
            else:
                # specials that land: keep going on the ground
                f.grounded = True
                f.vy = f.kvy = 0
                f.ff = False
                f.jumps_left = f.c["jumps"] - 1
                f.side_used = False
                f.airdodge_used = False
            return
        if st == "hitstun":
            if f.tumble:
                if f.tech_window > 0:
                    f.tech_window = 0
                    f.air_land(self, 0)
                    f.set_state("tech")
                    f.intang = 16
                    self.fx("tech", f.x, f.y)
                    return
                if f.kvy > 6 and f.hitstun > 8:      # bounce off the floor
                    f.kvy = -f.kvy * 0.55
                    f.y = y - 1
                    self.fx("dust", f.x, f.y, s=1.2)
                    return
                f.air_land(self, 0)
                f.set_state("knockdown")
                f.kvx *= 0.3
                return
            f.grounded = True
            f.vy = f.kvy = 0
            return
        if st in ("helpless", "glide"):
            f.air_land(self, 20)
            return
        if st == "parachute":
            f.air_land(self, 6)
            return
        if st == "airdodge":
            f.air_land(self, 10 if f._ad_dir else 4)
            return
        if st == "dizzy":
            f.grounded = True
            f.vy = f.kvy = 0
            return
        if st == "respawn":
            return
        f.air_land(self, 3 if st == "air" and f.vy > 6 else 0)

    # ------------------------------------------------------------------ projectiles
    def spawn_projectile(self, f, pd, m=None):
        p = dict(pd)
        p["o"] = f.slot
        p["owner"] = f
        p["x"] = f.x + (p.pop("start_x", 30) * f.facing)
        p["y"] = f.cy + p.pop("start_y", -4)
        k = 0.0
        if m and m.get("charge"):
            k = f.charge / float(m.get("charge_max", 60))
        sp = 1.0 + m.get("charge_speed", 0.0) * k if m else 1.0
        p["vx"] = pd["vx"] * f.facing * sp
        p["vy"] = pd["vy"] * sp
        p["face"] = f.facing
        p["age"] = 0
        p["hit"] = set()
        p["hitf"] = {}
        p["alive"] = True
        p["dmg"] = round(pd["dmg"] * f.dmg_mult * f.buff, 1)
        if p.get("wave"):
            p["by"] = p["y"]
        if f.buff > 1.0:
            f.buff, f.buff_timer = 1.0, 0
        self.projectiles.append(p)

    def update_projectiles(self):
        sx, sy, sw, sh = self.stage["main"]
        for p in self.projectiles:
            p["age"] += 1
            p["vy"] += p.get("grav", 0)
            p["x"] += p["vx"]
            py = p["y"]
            if p.get("wave"):
                amp, spd = p["wave"]
                p["by"] += p["vy"]
                p["y"] = p["by"] + math.sin(p["age"] * spd) * amp
            else:
                p["y"] += p["vy"]
            if p["age"] > p["life"]:
                p["alive"] = False
            if p.get("lingering"):
                continue
            if p.get("linger") and p["vy"] > 0:
                ground = None
                if sx <= p["x"] <= sx + sw and py <= sy <= p["y"] + p["r"] * 0.5:
                    ground = sy
                for (plx, ply, plw) in self.stage["platforms"]:
                    if plx <= p["x"] <= plx + plw and py <= ply <= p["y"] + p["r"] * 0.5:
                        ground = ply
                if ground is not None:
                    L = p["linger"]
                    p.update(kind=L["kind"], vx=0.0, vy=0.0, grav=0.0, r=L["r"], dmg=L["dmg"], ang=L["ang"],
                             bkb=L["bkb"], kbg=L["kbg"], rehit=L.get("rehit", 30), pierce=True, lingering=True,
                             noreflect=True, life=p["age"] + L["frames"])
                    p["y"] = ground - 6
                    p["hit"] = set()
                    p["hitf"] = {}
                    self.fx("dust", p["x"], ground, s=1.2)
                    continue
            if p["kind"] != "dekatsuyo" and sx <= p["x"] <= sx + sw and sy <= p["y"] + p["r"] * 0.5 <= sy + sh:
                if p.get("bounces", 0) > 0 and p["vy"] > 0:
                    p["bounces"] -= 1
                    p["vy"] = -abs(p["vy"]) * 0.6
                    p["y"] = sy - p["r"] * 0.5
                else:
                    p["alive"] = False
                    if p["kind"] == "anvil":
                        self.fx("dust", p["x"], sy, s=2.0)
                        self.fx("ring", p["x"], sy, s=1.0, col=(255, 230, 120))
                        self.shake = max(self.shake, 7)
                    else:
                        self.fx("spark", p["x"], p["y"], s=0.5, col=(255, 255, 255))
        self.projectiles = [p for p in self.projectiles if p["alive"]]

    # ------------------------------------------------------------------ hits
    def resolve_hits(self):
        for f in self.fighters:
            if not f.alive or f.dead or f.state != "attack" or f.hitlag > 0 or f.charging:
                continue
            m = f.move_data()
            for i, hb in enumerate(m.get("hits", [])):
                a, b = hb["f"]
                if not (a <= f.mf <= b):
                    continue
                hx, hy = hb_pos(hb, f.mf)
                cx = f.x + hx * f.facing
                cy = f.cy + hy
                for t in self.fighters:
                    if t is f or not t.alive or t.dead or t.grabbed_by is f:
                        continue
                    key = (hb.get("grp", i), t.slot)
                    last = f.move_hit.get(key)
                    if last is not None and (not hb.get("rehit") or f.mf - last < hb["rehit"]):
                        continue
                    if t.intang > 0 or t.invuln > 0 or t.state == "respawn":
                        continue
                    if not circle_rect(cx, cy, hb["r"], t.hurtbox()):
                        continue
                    f.move_hit[key] = f.mf
                    # other hitboxes of the same group shouldn't hit again this frame
                    self.apply_hit(f, t, hb, f.facing, cx, cy)
        for p in self.projectiles:
            if not p["alive"]:
                continue
            for t in self.fighters:
                if t.slot == p["o"] or not t.alive or t.dead or t.slot in p["hit"]:
                    continue
                if t.intang > 0 or t.invuln > 0 or t.state == "respawn":
                    continue
                if p.get("rehit"):
                    last = p["hitf"].get(t.slot)
                    if last is not None and p["age"] - last < p["rehit"]:
                        continue
                tm = t.move_data() if t.state == "attack" else None
                reflecting = (tm and tm.get("reflect") and tm["reflect"][0] <= t.mf <= tm["reflect"][1]
                              and not p.get("noreflect")
                              and math.hypot(p["x"] - t.x, p["y"] - t.cy) <= tm.get("reflect_r", 72) + p["r"])
                if not reflecting and not circle_rect(p["x"], p["y"], p["r"], t.hurtbox()):
                    continue
                if reflecting:
                    p["o"], p["owner"] = t.slot, t
                    p["vx"] = -p["vx"] * 1.15
                    p["vy"] = -p["vy"] if not p.get("grav") else -abs(p["vy"]) - 2
                    if p.get("wave"):
                        p["by"] = p["y"]
                    p["face"] = -p["face"]
                    p["dmg"] = round(p["dmg"] * 1.25, 1)
                    p["hit"] = set()
                    p["age"] = 0
                    self.fx("reflect", p["x"], p["y"], col=t.color)
                    self.shake = max(self.shake, 3)
                    break
                if p.get("rehit"):
                    p["hitf"][t.slot] = p["age"]
                else:
                    p["hit"].add(t.slot)
                face = 1 if p["vx"] >= 0 else -1
                if p.get("lingering"):
                    face = 1 if t.x >= p["x"] else -1
                self.apply_hit(p["owner"], t, p, face, p["x"], p["y"], projectile=True)
                if not p.get("pierce"):
                    p["alive"] = False
                    break

    def connected(self, f, projectile):
        """Attacker's move touched someone (hit or shield): pogo bounces etc."""
        if projectile or f.state != "attack":
            return
        f.landed = True
        am = f.move_data()
        if am and am.get("hit_bounce") and not f._bounced:
            f._bounced = True
            bx, by = am["hit_bounce"]
            f.vx, f.vy = bx * f.facing, by
            f.kvx = f.kvy = 0.0
            f.ff = False
            if by < 0:
                f.grounded = False
                f.ground = None
            if am.get("hit_end"):
                f.mf = max(f.mf, am["frames"] - am["hit_end"])

    def stale_key(self, f, hb, projectile):
        return ("p:" + hb.get("kind", "?")) if projectile else (f.move or "?")

    def apply_hit(self, f, t, hb, face, cx, cy, projectile=False, unblockable=False):
        dmg = hb["dmg"] * (f.dmg_mult if not projectile else 1.0) * (f.buff if not projectile else 1.0)
        if hb.get("counter"):
            dmg = max(8.0, f.counter_dmg * 1.3)
        dmg *= f.art_mult("dealt") * t.art_mult("taken")
        if f.char_key == "siren" and f.damage >= SIREN_RAGE_AT:      # enraged Siren hits 10% harder
            dmg *= 1.1
        # stale-move negation: the more you've landed this move recently, the weaker it gets
        sk = self.stale_key(f, hb, projectile)
        dmg *= max(0.5, 1.0 - sum(w for w, k in zip(STALE_WEIGHTS, f.stale) if k == sk))
        if projectile or not f._stale_pushed:
            f.stale.insert(0, sk)
            del f.stale[9:]
            if not projectile:
                f._stale_pushed = True

        # counters (Chiikawa's cry)
        tm = t.move_data() if t.state == "attack" else None
        if tm and tm.get("counter") and tm["counter"][0] <= t.mf <= tm["counter"][1] and not unblockable:
            t.counter_dmg = dmg
            t.facing = 1 if f.x > t.x else -1
            if tm.get("latch"):                       # Chikkabu jumps onto the attacker's head
                t.latch_on, t.latch_t = f, LATCH_FRAMES
                t.set_state("latched")
                t.intang = 10
                if not projectile:
                    f.hitlag = 10
                self.fx("counter", t.x, t.cy, s=1.0)
                self.shake = max(self.shake, 5)
                return
            t.start_move("counter_hit", self)
            if t.moves["counter_hit"].get("warp_behind"):   # Rakko reappears behind the attacker
                self.fx("smoke", t.x, t.cy, s=1.0)
                t.x = f.x - f.facing * (f.w / 2 + t.w / 2 + 8)
                t.y = f.y
                t.facing = f.facing
                t.grounded, t.ground = f.grounded, f.ground
                t.vx = t.vy = t.kvx = t.kvy = 0.0
            t.intang = 10
            if not projectile:
                f.hitlag = 18
            self.fx("counter", t.x, t.cy, s=1.0)
            self.shake = max(self.shake, 6)
            return

        # super armor: take the damage, don't flinch
        if tm and tm.get("armor") and tm["armor"][0] <= t.mf <= tm["armor"][1] and not unblockable and not hb.get("throw"):
            if knockback(t.damage + dmg, dmg, t.c["weight"], hb["bkb"], hb["kbg"]) < tm.get("armor_kb", 999):
                t.damage = min(999.0, t.damage + dmg)
                f.stats["dealt"] += dmg
                t.stats["taken"] += dmg
                hl = int(min(14, dmg * 0.4 + 3))
                t.hitlag = hl
                if not projectile:
                    f.hitlag = hl
                self.connected(f, projectile)
                self.fx("armor", t.x, t.cy, s=0.8, col=(255, 170, 60))
                self.shake = max(self.shake, 4)
                return

        # shields
        if t.state in ("shield", "shieldstun") and not unblockable and not hb.get("throw"):
            t.shield -= dmg * 1.19 * hb.get("shield_mult", 1.0)
            hl = int(min(12, dmg * 0.35 + 3))
            t.hitlag = hl
            if not projectile:
                f.hitlag = hl
            if t.shield <= 0:
                self.shield_break(t)
            else:
                t.set_state("shieldstun")
                t._sstun = int(dmg * 0.6 + 3)
                t.vx = (1 if t.x > (f.x if not projectile else cx - face * 10) else -1) * min(8, 1.5 + dmg * 0.35)
            self.fx("clank", cx, cy, s=0.5 + dmg / 20, col=t.color)
            self.connected(f, projectile)
            return

        self.connected(f, projectile)
        # sleep (Kani's reading): grounded targets doze off instead of flying
        if hb.get("sleep") and t.grounded:
            t.damage = min(999.0, t.damage + dmg)
            if t.grabbing:
                t.grabbing.grabbed_by = None
                t.grabbing.set_state("idle" if t.grabbing.grounded else "air")
                t.grabbing = None
            t.set_state("sleep")
            t.sleep_t = int(hb["sleep"] + t.damage * 0.6)
            t.vx = t.kvx = t.kvy = 0.0
            self.fx("sleep", t.x, t.y - t.h, col=(170, 150, 255))
            return
        # hit-lock (Chiikawa's onslaught): the dash turns into a barrage
        am = f.move_data() if (not projectile and f.state == "attack") else None
        if hb.get("lock") and am and am.get("on_grab") and not t.grabbed_by and not t.grabbing and t.state != "ledge":
            t.damage = min(999.0, t.damage + dmg)
            f.stats["dealt"] += dmg
            t.stats["taken"] += dmg
            f.grabbing, t.grabbed_by = t, f
            t.set_state("grabbed")
            t.vx = t.vy = t.kvx = t.kvy = 0
            f.start_move(am["on_grab"], self)
            f.vx = 0.0
            self.fx("hit", cx, cy, s=0.8, col=f.color)
            return
        if f.buff > 1.0 and not projectile:
            f.buff = 1.0
            f.buff_timer = 0

        t.damage = min(999.0, t.damage + dmg)
        f.stats["dealt"] += dmg
        t.stats["taken"] += dmg
        if f.char_key == "chikkabu" and f.form_t == 0:
            f.bulk = min(1.0, f.bulk + dmg / BULK_FROM_DAMAGE)
        t.last_hit_by = f.slot
        t.last_hit_time = self.frame
        kb = knockback(t.damage, dmg, t.c["weight"], hb["bkb"], hb["kbg"])
        kb *= f.art_mult("kb_dealt") * t.art_mult("kb_taken")

        if hb.get("radial"):
            ang = math.degrees(math.atan2(-(t.cy - (f.cy if not projectile else cy)), (t.x - f.x) or 0.001))
            ang = clamp(ang, 20, 160) if ang >= 0 else (30 if ang > -90 else 150)
            dx, dy = math.cos(math.radians(ang)), -math.sin(math.radians(ang))
        else:
            ang = hb["ang"]
            dx = math.cos(math.radians(ang)) * face
            dy = -math.sin(math.radians(ang))
        # grounded opponents hit by a downward angle pop up instead
        if dy > 0.2 and t.grounded:
            dy = -abs(dy) * 0.6
            kb *= 0.8
        # directional influence: push the launch angle up to ~12 degrees toward your stick
        sx, sy = t.inp.x, t.inp.y
        if (sx or sy) and kb > 40:
            perp = (-dy, dx)
            infl = (sx * perp[0] + sy * perp[1]) * DI_STRENGTH
            na = math.atan2(dy, dx) + infl
            dx, dy = math.cos(na), math.sin(na)

        speed = kb * KB_TO_SPEED
        # interrupt whatever they were doing
        if t.grabbing:
            g = t.grabbing
            t.grabbing = None
            g.grabbed_by = None
            g.set_state("idle" if g.grounded else "air")
        if t.grabbed_by:
            t.grabbed_by.grabbing = None
            t.grabbed_by.set_state("idle")
            t.grabbed_by = None
        if t.ledge:
            t.ledge = None
            t.ledge_cd = 20
        t.set_state("hitstun")
        t.hitstun = max(6, int(kb * 0.4))
        t.tumble = kb >= TUMBLE_KB
        t.tumble_spin = 0.0
        t.vx = t.vy = 0.0
        t.ff = False
        t.kvx, t.kvy = dx * speed, dy * speed
        if t.kvy < -1 or not t.grounded:
            t.grounded = False
            t.ground = None
        hl = int(min(20, dmg * 0.45 + 4)) if not hb.get("throw") else 4
        t.hitlag = hl
        if not projectile:
            f.hitlag = hl
        strong = kb > 140
        sweet = bool(hb.get("sweet")) and dmg >= 8
        self.fx("hit", cx, cy, s=min(2.4, 0.5 + kb / 120.0 + (0.4 if sweet else 0)), col=f.color,
                a=round(math.degrees(math.atan2(dy, dx))), sw=sweet)
        if sweet:
            self.fx("sweet", cx, cy, s=1.0, col=(255, 255, 255))
            if not projectile:
                t.hitlag = f.hitlag = min(24, hl + 3)
        self.shake = max(self.shake, min(16, 2 + kb / 18.0))
        if strong:     # (the big yellow hit spark + screen shake already sell it; no extra ring)
            t._big_hit = 1

    def push_apart(self):
        """Grounded fighters gently push each other apart (like Smash)."""
        fs = [f for f in self.fighters if f.alive and not f.dead and f.grounded and f.state not in ("grabbed", "holding")]
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                dx = b.x - a.x
                overlap = (a.w + b.w) / 2 * 0.7 - abs(dx)
                if overlap > 0 and abs(a.y - b.y) < 10:
                    push = min(2.0, overlap * 0.25)
                    s = 1 if dx >= 0 else -1
                    if dx == 0:
                        s = 1 if a.slot < b.slot else -1
                    a.x -= push * s
                    b.x += push * s

    # ------------------------------------------------------------------ KOs
    def check_blastzone(self, f):
        l, t, r, b = self.stage["blast"]
        ko_top = f.y - f.h < t and f.state == "hitstun"
        if f.x < l or f.x > r or f.y > b + f.h or ko_top or f.y < t - 400:
            self.ko(f)

    def ko(self, f):
        l, t, r, b = self.stage["blast"]
        x, y = clamp(f.x, l, r), clamp(f.y - f.h / 2, t, b)
        self.fx("ko", x, y, col=f.color, a=round(math.degrees(math.atan2(y - (-200), x))))
        self.shake = 18
        f.stocks -= 1
        f.stats["falls"] += 1
        killer = None
        if f.last_hit_by is not None and self.frame - f.last_hit_time < 600:
            killer = next((o for o in self.fighters if o.slot == f.last_hit_by), None)
        if killer and killer is not f:
            killer.stats["kos"] += 1
        else:
            f.stats["sd"] += 1
        if f.grabbing:
            f.grabbing.grabbed_by = None
            f.grabbing.set_state("air")
            f.grabbing = None
        if f.grabbed_by:
            f.grabbed_by.grabbing = None
            f.grabbed_by.set_state("idle")
            f.grabbed_by = None
        f.ledge = None
        if f.form_t or f.c.get("form_of"):
            self.shrink(f)
        f.latch_on, f.latch_t = None, 0
        f.dead = True
        f.respawn_timer = 75
        f.kvx = f.kvy = f.vx = f.vy = 0.0
        f.set_state("dead")
        if f.stocks <= 0:
            f.alive = False
            self.ko_order.append(f.slot)

    def respawn(self, f):
        f.dead = False
        f.damage = 0.0
        sx = 0.0
        others = [o.x for o in self.fighters if o is not f and o.alive and not o.dead]
        if others:
            sx = clamp(-sum(others) / len(others) * 0.4, -200, 200)
        f.x, f.y = sx, self.stage["respawn_y"]
        f.vx = f.vy = f.kvx = f.kvy = 0.0
        f.grounded = False
        f.ground = None
        f.jumps_left = f.c["jumps"] - 1
        f.side_used = f.airdodge_used = False
        f.shield = SHIELD_MAX
        f.buff = 1.0
        if f.char_key == "siren":
            f.mermaids, f.mer_t = MERMAIDS_MAX, 0
        f.set_state("respawn")
        f.invuln = 120
        self.fx("respawn", f.x, f.y, col=f.color)

    def check_game_over(self):
        if self.over:
            return
        alive = [f for f in self.fighters if f.alive]
        if len(alive) <= 1 and len(self.fighters) > 1:
            self.over = True
            self.winner = alive[0].slot if alive else None
            places = ([alive[0].slot] if alive else []) + list(reversed(self.ko_order))
            for i, s in enumerate(places):
                for f in self.fighters:
                    if f.slot == s:
                        f.place = i + 1

    @property
    def finished(self):
        return self.over and self.end_timer >= GAME_END_FRAMES

    # ------------------------------------------------------------------ snapshot (what clients draw)
    def snapshot(self):
        fs = []
        for f in self.fighters:
            m = f.move_data() if f.state == "attack" else None
            fs.append({
                "s": f.slot, "c": f.c.get("key", f.char_key), "bk": round(f.bulk, 2), "ft": f.form_t, "mm": f.mermaids, "n": f.name, "col": list(f.color), "cpu": f.cpu,
                "x": round(f.x, 1), "y": round(f.y, 1), "vx": round(f.vx + f.kvx, 1), "vy": round(f.vy + f.kvy, 1),
                "fa": f.facing, "st": f.state, "sf": f.sf, "mv": f.move or "", "mf": f.mf,
                "d": round(f.damage, 1), "k": f.stocks, "sh": round(f.shield, 1),
                "iv": f.invuln > 0, "it": f.intang > 0, "hl": f.hitlag, "ch": f.charge if f.charging else 0,
                "tu": bool(f.tumble and (f.state == "hitstun" or getattr(f, "_tumbling", False) and f.state == "air")),
                "sp": round(f.tumble_spin), "al": f.alive, "dd": f.dead, "bf": f.buff > 1.0,
                "gr": f.grounded, "lg": bool(f.ledge), "rt": f.respawn_timer, "dz": f.state == "dizzy",
                "dj": getattr(f, "_djump_anim", 0), "pl": f.place, "st8": f.stats,
                "cd": {k: v for k, v in f.cooldowns.items()},
                "ad": list(f._ad_dir) if f.state == "airdodge" and getattr(f, "_ad_dir", None) else None,
                "hit": bool(m and any(h["f"][0] <= f.mf <= h["f"][1] for h in m.get("hits", []))),
                "gl": bool(getattr(f, "gliding", False)),
                "art": f.art or "", "art_t": f.art_t,
                "tt": list(f.tether_to[:2]) if f.state == "tether" else None,
            })
        ps = [{"k": p["kind"], "x": round(p["x"], 1), "y": round(p["y"], 1), "vx": round(p["vx"], 1),
               "vy": round(p["vy"], 1), "r": p["r"], "o": p["o"], "a": p["age"], "fa": p["face"],
               "lf": p["life"] - p["age"]}
              for p in self.projectiles]
        return {"fr": self.frame, "mid": getattr(self, "match_id", 0), "stage": self.stage_key, "cd": self.countdown, "over": self.over,
                "et": self.end_timer, "win": self.winner, "shake": round(self.shake, 1),
                "f": fs, "p": ps, "e": self.effects}


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def circle_rect(cx, cy, r, rect):
    x, y, w, h = rect
    nx = clamp(cx, x, x + w)
    ny = clamp(cy, y, y + h)
    return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r
