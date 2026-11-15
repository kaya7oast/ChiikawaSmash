"""Simple CPU player. Runs on the host and produces raw inputs exactly like a controller would."""
import math
import random

from .sim import BUTTONS, BUTTON_BITS, B_SHD, B_JUMP


class Bot:
    def __init__(self, slot, level=2, seed=None):
        self.slot = slot
        self.level = level                    # 1 easy, 2 normal, 3 hard
        self.rng = random.Random(seed if seed is not None else slot * 7919)
        self.counts = {b: 0 for b in BUTTONS}
        self.held = set()
        self.x = self.y = 0.0
        self.think = 0
        self.hold_timer = 0
        self.plan = None
        self.react = {1: 18, 2: 9, 3: 4}[level]

    def tap(self, b):
        self.counts[b] += 1

    def raw(self):
        held = sum(bit for b, bit in zip(BUTTONS, BUTTON_BITS) if b in self.held)
        return [self.x, self.y, held] + [self.counts[b] for b in BUTTONS] + [0.0, 0.0]

    # ------------------------------------------------------------------
    def update(self, game):
        me = next((f for f in game.fighters if f.slot == self.slot), None)
        if me is None or not me.alive or game.countdown > 0 or game.over:
            self.x = self.y = 0.0
            self.held.clear()
            return self.raw()
        self.held.discard("jump")
        if self.hold_timer > 0:
            self.hold_timer -= 1
            return self.raw()
        self.x = self.y = 0.0
        self.held.discard("shd")
        st = game.stage["main"]
        left, top, right = st[0], st[1], st[0] + st[2]

        if me.dead:
            return self.raw()
        if me.state == "respawn":
            if me.sf > 30 + self.rng.randint(0, 40):
                self.x = 1.0 if me.x < 0 else -1.0
            return self.raw()
        if me.state == "grabbed":
            if self.rng.random() < 0.3 * self.level:
                self.tap(self.rng.choice(["atk", "jump", "spc"]))
            return self.raw()

        # ---------------- recovery
        offstage = (me.x < left - 5 or me.x > right + 5) and not me.grounded or me.y > top + 30
        if me.state == "ledge":
            if me.sf > 10 + self.rng.randint(0, 25):
                r = self.rng.random()
                d = 1 if me.x < 0 else -1
                if r < 0.4:
                    self.x = d
                elif r < 0.65:
                    self.tap("jump")
                elif r < 0.85:
                    self.tap("atk")
                else:
                    self.tap("shd")
            return self.raw()
        if offstage and not me.grounded:
            home = left + 60 if me.x < 0 else right - 60
            self.x = 1.0 if home > me.x else -1.0
            if me.state in ("air",) and me.vy > -2:
                below_ledge = me.y > top - 40
                if me.jumps_left > 0 and (below_ledge or abs(me.x - home) > 300):
                    self.tap("jump")
                    self.hold_timer = 8
                    self.held.add("jump")
                elif me.jumps_left == 0 and below_ledge:
                    self.y = -1.0
                    self.tap("spc")
                    self.hold_timer = 3
            return self.raw()

        # ---------------- fighting
        foes = [f for f in game.fighters if f is not me and f.alive and not f.dead and f.state != "respawn"]
        if not foes:
            return self.raw()
        t = min(foes, key=lambda f: abs(f.x - me.x) + abs(f.y - me.y) * 0.7)
        dx, dy = t.x - me.x, t.y - me.y
        dist = abs(dx)
        face = 1 if dx > 0 else -1

        # react to an incoming attack with shield / dodge
        if me.grounded and t.state == "attack" and dist < 140 and t.move not in ("grab",):
            if self.rng.random() < 0.04 * self.level * self.level:
                if self.rng.random() < 0.7:
                    self.held.add("shd")
                    self.hold_timer = self.rng.randint(6, 16)
                else:
                    self.held.add("shd")
                    self.x = -face
                    self.hold_timer = 2
                return self.raw()

        self.think -= 1
        if self.think > 0 and me.state in ("idle", "run", "air"):
            # keep walking toward them between decisions, but don't run off the stage
            if dist > 70:
                self.x = face
            if me.grounded and ((me.x < left + 40 and self.x < 0) or (me.x > right - 40 and self.x > 0)):
                self.x = 0.0
            return self.raw()
        self.think = self.react + self.rng.randint(0, self.react)

        if not me.actionable():
            if me.state == "holding":
                r = self.rng.random()
                if r < 0.3:
                    self.tap("atk")
                else:
                    self.x = self.rng.choice([1.0, -1.0]) if r < 0.7 else 0.0
                    self.y = 0.0 if self.x else self.rng.choice([-1.0, 1.0])
            return self.raw()

        ch = me.c["moves"]
        has_proj = bool(ch.get("nspec", {}).get("proj"))
        if me.grounded:
            if dist > 260 and has_proj and self.rng.random() < 0.25:
                me.facing = face
                self.tap("spc")
                return self.raw()
            if dy < -110 and dist < 150:
                self.tap("jump")
                self.held.add("jump")
                self.hold_timer = 6
                return self.raw()
            if dist < 75 + me.w / 2 and abs(dy) < 40:
                r = self.rng.random()
                if t.damage > 95 and r < 0.45:
                    self.x = face if self.rng.random() < 0.7 else 0
                    self.y = 0 if self.x else -1
                    self.tap("sms")
                elif r < 0.18:
                    self.tap("grb")
                elif r < 0.55:
                    self.x = face
                    self.tap("atk")
                elif r < 0.7:
                    self.y = -1.0
                    self.tap("atk")
                elif r < 0.8:
                    self.y = 1.0
                    self.tap("atk")
                elif r < 0.9:
                    self.tap("atk")
                else:
                    self.x = face
                    self.tap("spc")
                self.hold_timer = 2
                return self.raw()
            if 120 < dist < 230 and self.rng.random() < 0.15:
                self.tap("jump")
                self.held.add("jump")
                self.hold_timer = 4
                self.x = face
                return self.raw()
            self.x = face
            if (me.x < left + 40 and face < 0) or (me.x > right - 40 and face > 0):
                self.x = 0.0
            return self.raw()

        # in the air: aerials when close
        if dist < 110 and abs(dy) < 110:
            if dy < -40 and dist < 60:
                self.y = -1.0
            elif dy > 40 and dist < 60:
                self.y = 1.0
            elif face == me.facing:
                self.x = face
            else:
                self.x = face
            self.tap("atk")
            self.hold_timer = 2
            return self.raw()
        self.x = face
        return self.raw()
