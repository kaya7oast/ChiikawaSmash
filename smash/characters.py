"""
Character stats + hand-made move data (pure data, no pygame).

Coordinates: hitbox x/y are offsets from the fighter's CENTRE, x = FORWARD, y = DOWN, in pixels.
Angles: 0 = forward, 90 = up, 180 = back, 270 = straight down (meteor).

Hitbox shapes
  hb(...)   fixed circle
  mv(...)   circle that slides from (x, y) to (x2, y2) over its active frames (thrusts, rising hits)
  arc(...)  circle that travels along an arc around (cx, cy) from angle a0 to a1 (swings)
  weapon(...)  a swing with a strong SWEETSPOT at the tip and a weaker sourspot near the handle
Hitboxes that share a grp hit a target only once; the FIRST one listed wins (so put sweetspots first).

Move keys
  frames, hits, land (landing lag), drift [(first, last, vx, vy)], grav, steer, anim, weapon
  charge (frame that holds while the button is held), charge_max, charge_mult, charge_speed, proj_charged
  rapid (button, back_to_frame, at_frame, max_loops, finisher)   hold/mash to loop (rapid jabs, seed spit)
  follow [(button, first, last, move)]                            press during the window to chain a move
  next (move, first_frame)                                        jab combos
  proj [(frame, projectile)]   projectile options: wave=(amp, speed), bounces, linger={...}, pierce
  grabbox ((first,last), x, y, r), grab_air, on_grab (command grabs), pummels [(frame, dmg)], throw
  armor (first, last), armor_kb      super armor (hits under armor_kb knockback don't flinch you)
  reflect (first, last)               sends projectiles back
  counter (first, last)               getting hit plays counter_hit instead
  hit_bounce (vx, vy), hit_end       bounce off whoever you hit (pogo / brave charge)
  helpless, glide, land_move, side_once, cooldown, heal, buff, intang
"""
import math

ARC = "arc"


def hb(f, x, y, r, dmg, ang, bkb, kbg, **kw):
    d = {"f": f, "x": x, "y": y, "r": r, "dmg": dmg, "ang": ang, "bkb": bkb, "kbg": kbg}
    d.update(kw)
    return d


def mv(f, x, y, x2, y2, r, dmg, ang, bkb, kbg, **kw):
    d = hb(f, x, y, r, dmg, ang, bkb, kbg, **kw)
    d["x2"], d["y2"] = x2, y2
    return d


def arc(f, cx, cy, rad, a0, a1, r, dmg, ang, bkb, kbg, **kw):
    kw.setdefault("fx", ARC)
    x, y = cx + math.cos(math.radians(a0)) * rad, cy - math.sin(math.radians(a0)) * rad
    d = hb(f, x, y, r, dmg, ang, bkb, kbg, **kw)
    d["arc"] = (cx, cy, rad, a0, a1)
    return d


def weapon(f, cx, cy, a0, a1, length, r, dmg, ang, bkb, kbg, tip=None, grp=1, **kw):
    """Sweetspot circle at the tip of the weapon + a sourspot halfway down, both following the swing arc."""
    t = dict(dmg=round(dmg * 1.25, 1), ang=ang, bkb=bkb, kbg=kbg + 6)
    t.update(tip or {})
    sweet = arc(f, cx, cy, length, a0, a1, r, t["dmg"], t["ang"], t["bkb"], t["kbg"], grp=grp, sweet=True, **kw)
    sour = arc(f, cx, cy, length * 0.5, a0, a1, r * 1.05, dmg, ang, bkb, kbg, grp=grp, **kw)
    return [sweet, sour]


def hb_pos(h, mf):
    """Where a hitbox is on move-frame mf (fighter-local: x forward, y down)."""
    a, b = h["f"]
    t = 0.0 if b <= a else min(1.0, max(0.0, (mf - a) / float(b - a)))
    if "arc" in h:
        cx, cy, rad, a0, a1 = h["arc"]
        ang = math.radians(a0 + (a1 - a0) * t)
        return cx + math.cos(ang) * rad, cy - math.sin(ang) * rad
    if "x2" in h:
        return h["x"] + (h["x2"] - h["x"]) * t, h["y"] + (h["y2"] - h["y"]) * t
    return h["x"], h["y"]


def throws(f, b, u, d):
    """(frame, dmg, ang, bkb, kbg) for each throw."""
    return {"fthrow": {"frames": 30, "anim": "fthrow", "throw": f},
            "bthrow": {"frames": 34, "anim": "bthrow", "throw": b},
            "uthrow": {"frames": 34, "anim": "uthrow", "throw": u},
            "dthrow": {"frames": 30, "anim": "dthrow", "throw": d}}


def common(grab_x, grab_r=24, getup_x=44):
    return {
        "grab": {"frames": 30, "anim": "grab", "grabbox": ((6, 8), grab_x, -4, grab_r)},
        "pummel": {"frames": 16, "anim": "pummel", "pummel": (4, 1.5)},
        "getup": {"frames": 34, "anim": "ftilt", "intang": (1, 16),
                  "hits": [hb((16, 19), getup_x, 0, 30, 7, 40, 45, 30, fx="big")]},
    }


def rapid_jab(x, r, finisher, mx=14, rate=3, y=-4, fx="flurry"):
    return {"frames": 24, "anim": "rapid", "rapid": ("atk", 2, 10, mx, finisher),
            "hits": [hb((2, 10), x, y, r, 0.6, 30, 4, 8, rehit=rate, fx=fx)]}


# =================================================================== CHIIKAWA
def chiikawa():
    h = 64
    mv_ = {
        # brave little punches -> flurry -> headbutt
        "jab1": {"frames": 15, "anim": "jab", "next": ("jab2", 5), "hits": [hb((2, 3), 32, -4, 16, 2.0, 20, 6, 15, fx="poke")]},
        "jab2": {"frames": 15, "anim": "jab2", "next": ("jab_rapid", 5), "hits": [hb((2, 3), 34, -2, 16, 2.0, 20, 6, 15, fx="poke")]},
        "jab_rapid": rapid_jab(38, 22, "jab_fin"),
        "jab_fin": {"frames": 28, "anim": "jab3", "hits": [hb((3, 5), 40, -6, 26, 3.0, 40, 50, 80, fx="big")]},
        # shove that slides forward
        "ftilt": {"frames": 26, "anim": "ftilt", "hits": [mv((6, 9), 18, -4, 46, -4, 22, 8, 32, 32, 90, fx="poke")]},
        # headbutt arc from the front to behind - juggles
        "utilt": {"frames": 26, "anim": "utilt", "hits": [arc((5, 10), 0, -6, 34, 40, 150, 22, 6, 95, 40, 104)]},
        # fast low poke that pops them up - combo starter
        "dtilt": {"frames": 16, "anim": "dtilt", "hits": [hb((4, 5), 36, 22, 18, 5, 72, 40, 35, fx="poke")]},
        "dash": {"frames": 36, "anim": "dash", "drift": [(1, 16, 8, None)],
                 "hits": [hb((5, 9), 20, 0, 30, 5, 70, 40, 40, grp=1, fx="dash"),
                          hb((12, 16), 24, 0, 30, 6, 40, 50, 70, grp=2, fx="dash")]},
        # haymaker: fist = sweetspot
        "fsmash": {"frames": 50, "anim": "fsmash", "charge": 8,
                   "hits": [hb((15, 16), 52, -6, 18, 17, 38, 35, 102, grp=1, sweet=True, fx="big"),
                            hb((15, 17), 28, -6, 22, 11, 40, 30, 90, grp=1, fx="big")]},
        # hop-headbutt that travels upward
        "usmash": {"frames": 46, "anim": "usmash", "charge": 6,
                   "hits": [mv((10, 16), 0, -20, 0, -72, 28, 15, 88, 32, 98, fx="arc_up")]},
        # tantrum: two weak stomps then two strong
        "dsmash": {"frames": 50, "anim": "dsmash", "charge": 5,
                   "hits": [hb((9, 10), 36, 20, 22, 3, 30, 30, 10, grp=1, fx="ground"),
                            hb((9, 10), -36, 20, 22, 3, 150, 30, 10, grp=1, fx="ground"),
                            hb((15, 16), 36, 20, 24, 10, 30, 35, 95, grp=2, fx="ground"),
                            hb((15, 16), -36, 20, 24, 10, 150, 35, 95, grp=2, fx="ground")]},
        # panic flail: arms everywhere, then a shove
        "nair": {"frames": 38, "anim": "flail", "land": 7,
                 "hits": [hb((3, 15), 0, 0, 38, 1.4, 60, 10, 0, rehit=3, grp=1, fx="flurry"),
                          hb((17, 19), 0, 0, 40, 4, 45, 45, 85, grp=2, fx="spin")]},
        # double-fist hammer: the fists meteor mid-swing
        "fair": {"frames": 40, "anim": "fair", "land": 14,
                 "hits": [arc((11, 15), 0, -10, 40, 80, -40, 18, 12, 290, 25, 85, grp=1, sweet=True),
                          hb((11, 15), 20, -6, 20, 8, 45, 30, 80, grp=1, fx="poke")]},
        "bair": {"frames": 32, "anim": "bair", "land": 10,
                 "hits": [hb((7, 8), -42, 4, 18, 14, 145, 34, 100, grp=1, sweet=True, fx="kick"),
                          hb((7, 11), -26, 4, 20, 9, 145, 25, 85, grp=1, fx="kick")]},
        # weed whip: swings a freshly pulled weed overhead, the leafy tip is the sweetspot
        "uair": {"frames": 32, "anim": "uair_still", "land": 8, "weapon": "weed",
                 "hits": weapon((5, 12), 0, -8, 20, 165, 52, 20, 8, 85, 30, 100)},
        # drill feet then a small meteor
        "dair": {"frames": 42, "anim": "dair", "land": 16,
                 "hits": [hb((8, 18), 0, 34, 22, 1.5, 270, 10, 0, rehit=3, grp=1, fx="drill"),
                          hb((20, 22), 0, 36, 26, 5, 285, 30, 70, grp=2, fx="stomp")]},
        # specials
        "nspec": {"frames": 40, "anim": "throw_fwd", "charge": 9, "charge_max": 60, "charge_speed": 0.1, "charge_full": 40,
                  "proj": [(14, {"kind": "weed", "vx": 8.5, "vy": -7, "grav": 0.38, "r": 16, "dmg": 6,
                                 "ang": 45, "bkb": 30, "kbg": 55, "life": 110})],
                  "proj_charged": [(14, {"kind": "weed_big", "vx": 9, "vy": -7.5, "grav": 0.38, "r": 26, "dmg": 9,
                                         "ang": 42, "bkb": 40, "kbg": 72, "life": 120})]},
        # Weeding Onslaught (Mii Brawler style): a dash punch - if it HITS (shields block it) it becomes a barrage
        "sspec": {"frames": 46, "anim": "charge", "side_once": True, "drift": [(6, 24, 13, 0)], "grav": 0.3,
                  "on_grab": "onslaught",
                  "hits": [hb((6, 24), 28, 0, 28, 3, 45, 30, 10, lock=True, fx="dash")]},
        "onslaught": {"frames": 74, "anim": "rapid", "grav": 0.0,
                      "pummels": [(6 + 5 * i, 1.2) for i in range(10)], "throw": (62, 6, 40, 70, 88)},
        # Pochette Parachute (Game & Watch style): bounce up, then float down under her pink bag.
        # Not helpless: you can still attack / air dodge, but only one up-B per trip into the air.
        "uspec": {"frames": 30, "anim": "trampoline", "parachute": True, "once_air": True, "ledge_ok": True,
                  "drift": [(4, 4, None, -18.5)], "steer": 0.7,
                  "hits": [hb((4, 10), 0, -20, 30, 6, 85, 55, 50, fx="arc_up")]},
        # Crying Fountain: hold B to cry harder, then tears burst out both ways
        "dspec": {"frames": 48, "anim": "cry", "charge": 8, "charge_max": 50, "charge_mult": 0.6, "charge_speed": 0.3,
                  "hits": [hb((10, 13), 0, -4, 40, 2, 70, 40, 20, radial=True, fx="burp")],
                  "proj": [(12, {"kind": "tear", "vx": vx, "vy": vy, "grav": 0.5, "r": 11, "dmg": 3, "ang": 60,
                                 "bkb": 25, "kbg": 45, "life": 70, "start_x": 10})
                           for vx, vy in ((4.5, -9.5), (8, -7.5), (11, -4.5), (-4.5, -9.5), (-8, -7.5), (-11, -4.5))]},
    }
    mv_.update(common(34))
    mv_.update(throws((10, 7, 40, 55, 65), (14, 10, 135, 55, 80), (12, 6, 90, 70, 60), (14, 5, 80, 50, 40)))
    return {"name": "Chiikawa", "image": "chiikawa", "color": (238, 130, 158), "w": 56, "h": h, "weight": 82,
            "run": 9.6, "walk": 5.0, "air": 6.6, "accel": 0.42, "grav": 0.52, "fall": 8.3, "ff": 13.2,
            "jump": 14.2, "hop": 9.8, "djump": 13.6, "jumps": 2, "moves": mv_,
            "air_desc": "a bit floaty",
            "desc": "Small but brave."}


# =================================================================== HACHIWARE (guitar)
def hachiware():
    h = 72                       # full-body art now (was a floating head)
    G = "guitar"
    mv_ = {
        "jab1": {"frames": 16, "anim": "jab", "next": ("jab2", 5), "hits": [hb((3, 4), 34, -2, 18, 2.5, 20, 8, 20, fx="poke")]},
        "jab2": {"frames": 16, "anim": "jab2", "next": ("jab3", 5), "hits": [hb((3, 4), 38, -2, 18, 2.0, 20, 8, 20, fx="poke")]},
        "jab3": {"frames": 30, "anim": "jab3", "weapon": G, "hits": weapon((5, 8), 0, -4, 70, -10, 52, 20, 5, 40, 45, 85)},
        # guitar swing - head of the guitar is the sweetspot
        "ftilt": {"frames": 30, "anim": "ftilt", "weapon": G, "hits": weapon((7, 10), 0, -6, 40, -25, 60, 22, 8, 35, 30, 88,
                                                                            tip={"dmg": 10, "kbg": 94})},
        "utilt": {"frames": 30, "anim": "utilt", "weapon": G, "hits": weapon((6, 12), 0, -8, 30, 170, 54, 22, 7, 95, 35, 106)},
        "dtilt": {"frames": 22, "anim": "dtilt", "weapon": G, "hits": weapon((5, 7), 0, 10, 10, -12, 62, 18, 6, 25, 30, 58)},
        # rock-star knee slide
        "dash": {"frames": 40, "anim": "slide", "drift": [(1, 20, 10, None)],
                 "hits": [hb((6, 20), 34, 16, 26, 7, 70, 55, 45, fx="dash")]},
        # power chord: guitar smash + a short sound wave
        "fsmash": {"frames": 54, "anim": "fsmash", "charge": 9, "weapon": G,
                   "hits": weapon((16, 18), 0, -6, 70, 0, 64, 26, 15, 37, 32, 100, tip={"dmg": 17, "kbg": 104}),
                   "proj": [(18, {"kind": "chord", "vx": 9, "vy": 0, "grav": 0, "r": 26, "dmg": 5, "ang": 40, "bkb": 45,
                                  "kbg": 45, "life": 18, "pierce": True, "start_x": 70})]},
        # encore: notes burst above, then a launcher
        "usmash": {"frames": 50, "anim": "usmash", "charge": 7, "weapon": G,
                   "hits": [hb((12, 20), 0, -60, 30, 2, 90, 20, 0, rehit=4, grp=1, fx="note"),
                            hb((22, 24), 0, -66, 38, 8, 88, 40, 110, grp=2, fx="arc_up")]},
        "dsmash": {"frames": 50, "anim": "dsmash", "charge": 6, "weapon": G,
                   "hits": [hb((12, 14), 46, 20, 30, 14, 30, 32, 96, grp=1, fx="ground"),
                            hb((12, 14), -46, 20, 30, 14, 150, 32, 96, grp=1, fx="ground")]},
        # guitar circles the whole body once
        "nair": {"frames": 38, "anim": "nair_still", "land": 8, "weapon": G,
                 "hits": [arc((5, 14), 0, -2, 48, 0, 360, 22, 9, 45, 28, 90)]},
        # overhead chop: the guitar head METEORS
        "fair": {"frames": 42, "anim": "fair", "land": 15, "weapon": G,
                 "hits": weapon((10, 15), 0, -6, 110, -60, 54, 22, 12, 40, 30, 92,
                                tip={"dmg": 14, "ang": 285, "bkb": 30, "kbg": 80})},
        "bair": {"frames": 36, "anim": "bair", "land": 11, "weapon": G,
                 "hits": weapon((8, 10), 0, -4, 210, 160, 56, 22, 12, 145, 32, 98, tip={"dmg": 14})},
        "uair": {"frames": 34, "anim": "uair_still", "land": 8, "weapon": G,
                 "hits": weapon((6, 12), 0, -6, 160, 20, 50, 22, 9, 82, 28, 102)},
        "dair": {"frames": 46, "anim": "dair", "land": 18, "weapon": G,
                 "hits": [hb((14, 16), 0, 46, 20, 14, 275, 28, 82, grp=1, sweet=True, fx="stomp"),
                          hb((14, 20), 0, 30, 24, 9, 300, 25, 70, grp=1, fx="stomp")]},
        # specials
        # Personality Arts (Monado style): each press switches art - green JUMP, blue SPEED, yellow SHIELD, red SMASH, off
        "nspec": {"frames": 22, "anim": "art", "art_switch": 8},
        # Tail Tornado (Ken's Tatsumaki): spins forward on his tail, many hits, small lift in the air
        "sspec": {"frames": 52, "anim": "tatsu", "side_once": True, "drift": [(6, 34, 8.5, None)], "grav": 0.15,
                  "hits": [hb((6, 32), 10, -4, 44, 2.2, 70, 20, 8, rehit=6, grp=1, fx="spin"),
                           hb((36, 38), 18, -4, 48, 6, 40, 55, 85, grp=2, fx="big")]},
        "sspec_air": {"frames": 52, "anim": "tatsu", "side_once": True,
                      "drift": [(6, 6, None, -6), (6, 34, 8.5, None)], "grav": 0.15,
                      "hits": [hb((6, 32), 10, -4, 44, 2.2, 70, 20, 8, rehit=6, grp=1, fx="spin"),
                               hb((36, 38), 18, -4, 48, 6, 40, 55, 85, grp=2, fx="big")]},
        # Shoryuken (Ken): rising uppercut, invincible on startup, the first hit is the strong one
        "uspec": {"frames": 44, "anim": "shoryu", "helpless": True, "intang": (1, 5), "drift": [(4, 4, 3, -18)],
                  "steer": 0.4,
                  "hits": [hb((4, 6), 22, -26, 24, 13, 80, 50, 95, grp=1, sweet=True, fx="arc_up"),
                           mv((7, 18), 16, -30, 8, -64, 22, 4, 85, 40, 55, grp=1, fx="arc_up")]},
        # Reflector (Fox style): hold B to keep it up forever; nicks anyone who gets too close for 1%
        "dspec": {"frames": 26, "anim": "reflect", "reflect": (3, 14), "reflect_r": 80, "grav": 0.3,
                  "rapid": ("spc", 6, 12, 99999, None),
                  "hits": [hb((3, 5), 0, -4, 44, 1, 50, 50, 15, radial=True, fx="burp"),
                           hb((7, 12), 0, -4, 40, 1, 50, 45, 10, radial=True, grp=2, fx="none")]},
    }
    mv_.update(common(38))
    mv_.update(throws((10, 8, 40, 55, 70), (12, 11, 140, 60, 78), (12, 7, 90, 65, 70), (11, 6, 70, 45, 52)))
    return {"name": "Hachiware", "image": "hachiware", "color": (104, 142, 206), "w": 60, "h": h, "weight": 92,
            "run": 10.0, "walk": 5.2, "air": 7.0, "accel": 0.45, "grav": 0.56, "fall": 9.4, "ff": 14.6,
            "jump": 14.6, "hop": 10.0, "djump": 13.8, "jumps": 2, "moves": mv_,
            "air_desc": "standard",
            "desc": "Four personalities."}


# =================================================================== USAGI (stick, chaos)
def usagi():
    h = 84
    S = "stick"
    mv_ = {
        "jab1": {"frames": 14, "anim": "jab", "weapon": S, "next": ("jab2", 5), "hits": [hb((2, 3), 44, -6, 16, 2, 20, 6, 15, fx="poke")]},
        "jab2": {"frames": 14, "anim": "jab2", "weapon": S, "next": ("jab_rapid", 5), "hits": [hb((2, 3), 50, -6, 16, 2, 20, 6, 15, fx="poke")]},
        "jab_rapid": dict(rapid_jab(52, 24, "jab_fin", mx=16, rate=2, y=-6), weapon=S),
        "jab_fin": {"frames": 30, "anim": "jab3", "weapon": S, "hits": weapon((4, 8), 0, -6, 100, -40, 60, 22, 3, 42, 55, 90)},
        # long stick thrust: tip sweetspot
        "ftilt": {"frames": 28, "anim": "ftilt", "weapon": S,
                  "hits": [hb((7, 9), 74, -6, 14, 11, 35, 35, 95, grp=1, sweet=True, fx="poke"),
                           hb((7, 10), 44, -6, 18, 7, 35, 30, 80, grp=1, fx="poke")]},
        "utilt": {"frames": 30, "anim": "utilt", "weapon": S, "hits": weapon((5, 13), 0, -14, 30, 160, 58, 20, 7, 92, 35, 104)},
        "dtilt": {"frames": 18, "anim": "dtilt", "weapon": S, "hits": weapon((4, 6), 0, 18, -5, -15, 66, 16, 5, 20, 35, 40)},
        "dash": {"frames": 38, "anim": "dash", "weapon": S, "drift": [(1, 12, 11, None)],
                 "hits": weapon((8, 12), 0, -10, 100, -30, 60, 24, 10, 50, 40, 80)},
        # huge overhead slam, tip = sweetspot
        "fsmash": {"frames": 52, "anim": "fsmash", "charge": 9, "weapon": S,
                   "hits": weapon((15, 19), 0, -10, 110, -30, 80, 24, 15, 40, 32, 100, tip={"dmg": 18, "kbg": 104})},
        # stick shoots straight up: multi-hit then launch
        "usmash": {"frames": 48, "anim": "usmash", "charge": 6, "weapon": S,
                   "hits": [mv((10, 18), 0, -30, 0, -100, 22, 2, 90, 15, 0, rehit=3, grp=1, fx="poke"),
                            hb((19, 21), 0, -104, 26, 7, 88, 40, 115, grp=2, fx="arc_up")]},
        # low 360 sweep
        "dsmash": {"frames": 48, "anim": "dsmash", "charge": 5, "weapon": S,
                   "hits": [arc((10, 16), 0, 16, 64, 0, 360, 22, 14, 28, 30, 96)]},
        "nair": {"frames": 38, "anim": "nair_still", "land": 8, "weapon": S,
                 "hits": [arc((4, 16), 0, -6, 58, 0, 720, 20, 1.8, 50, 15, 5, rehit=4, grp=1),
                          hb((18, 20), 0, -6, 50, 4, 45, 40, 90, grp=2, fx="spin")]},
        # quick far poke
        "fair": {"frames": 34, "anim": "ftilt", "land": 11, "weapon": S,
                 "hits": [hb((6, 8), 76, -4, 16, 12, 38, 34, 92, grp=1, sweet=True, fx="poke"),
                          hb((6, 9), 44, -4, 18, 7, 40, 28, 80, grp=1, fx="poke")]},
        "bair": {"frames": 34, "anim": "bair", "land": 10, "weapon": S,
                 "hits": weapon((7, 10), 0, -6, 210, 150, 66, 22, 12, 145, 32, 98, tip={"dmg": 14})},
        "uair": {"frames": 30, "anim": "uair_still", "land": 7, "weapon": S,
                 "hits": weapon((4, 10), 0, -10, 150, 30, 60, 22, 8, 85, 30, 100)},
        # POGO: bounce off whoever you hit
        "dair": {"frames": 40, "anim": "pogo", "land": 14, "weapon": S, "hit_bounce": (0, -12), "hit_end": 12,
                 "hits": [mv((8, 24), 0, 30, 0, 72, 18, 9, 275, 25, 70, fx="poke")]},
        # specials
        "nspec": {"frames": 30, "anim": "spit", "rapid": ("spc", 6, 14, 8, None),
                  "proj": [(10, {"kind": "seed", "vx": 15, "vy": 0, "grav": 0, "r": 9, "dmg": 2.5,
                                 "ang": 30, "bkb": 10, "kbg": 15, "life": 50})]},
        "sspec": {"frames": 54, "anim": "crazy", "side_once": True, "drift": [(8, 40, 15, 0)], "grav": 0.2,
                  "follow": [("spc", 12, 44, "sspec_yaha")],
                  "hits": [hb((8, 40), 20, 0, 34, 2.5, 50, 25, 10, rehit=7, fx="spin"),
                           hb((44, 47), 30, 0, 38, 6, 40, 55, 90, grp=2, fx="big")]},
        "sspec_yaha": {"frames": 34, "anim": "uair_still", "weapon": S, "drift": [(1, 4, 4, -6)], "grav": 0.6,
                       "hits": weapon((4, 10), 0, -10, -40, 120, 56, 26, 8, 70, 60, 90)},
        # YAHA Warp (Mewtwo-style teleport): hold a direction, vanish, reappear ~240px that way
        "uspec": {"frames": 34, "anim": "teleport", "helpless": True, "grav": 0.0, "steer": 0.0,
                  "intang": (3, 16), "teleport": (6, 14, 240), "ledge_ok": True},
        "dspec": {"frames": 60, "anim": "eat", "heal": (40, 6), "cooldown": 360, "armor": (8, 44), "armor_kb": 100},
    }
    mv_.update(common(40))
    mv_.update(throws((10, 8, 40, 52, 68), (14, 10, 140, 55, 80), (12, 6, 90, 60, 65), (11, 6, 75, 40, 50)))
    return {"name": "Usagi", "image": "usagi", "color": (245, 208, 76), "w": 58, "h": h, "weight": 86,
            "run": 11.2, "walk": 5.6, "air": 7.6, "accel": 0.5, "grav": 0.72, "fall": 11.2, "ff": 17.0,
            "jump": 18.6, "hop": 12.0, "djump": 17.6, "jumps": 2, "moves": mv_,
            "air_desc": "huge jumps, fast faller",
            "desc": "Fast and chaotic with a long stick. Pogo dair. "
                    "B: seed spit (hold). Side-B: crazy rush (press B again: YAHA!). Down-B: snack heal w/ armor."}


# =================================================================== MOMONGA (floaty brat)
def momonga():
    h = 58
    mv_ = {
        "jab1": {"frames": 13, "anim": "jab", "next": ("jab2", 4), "hits": [hb((2, 3), 30, -2, 14, 1.5, 20, 6, 15, fx="poke")]},
        "jab2": {"frames": 13, "anim": "jab2", "next": ("jab_rapid", 4), "hits": [hb((2, 3), 32, -2, 14, 1.5, 20, 6, 15, fx="poke")]},
        "jab_rapid": rapid_jab(34, 20, "jab_fin", mx=18, rate=2),
        "jab_fin": {"frames": 26, "anim": "jab3", "hits": [hb((3, 5), 36, -4, 24, 3, 40, 55, 70, fx="big")]},
        "ftilt": {"frames": 26, "anim": "ftilt", "hits": [mv((6, 8), 18, -2, 42, -2, 20, 7, 30, 40, 85, fx="poke")]},
        "utilt": {"frames": 24, "anim": "utilt", "hits": [arc((4, 9), 0, -4, 30, 20, 170, 18, 6, 95, 35, 100)]},
        "dtilt": {"frames": 18, "anim": "dtilt", "hits": [hb((4, 6), 36, 22, 18, 5, 15, 30, 30, fx="ground")]},
        "dash": {"frames": 38, "anim": "slide", "drift": [(1, 20, 11, None)], "hits": [hb((4, 20), 26, 14, 24, 7, 60, 45, 50, fx="dash")]},
        "fsmash": {"frames": 46, "anim": "fsmash", "charge": 7,
                   "hits": [hb((13, 15), 40, -4, 22, 14, 35, 40, 100, grp=1, sweet=True, fx="big"),
                            hb((13, 16), 22, -4, 24, 9, 40, 35, 90, grp=1, fx="big")]},
        "usmash": {"frames": 44, "anim": "usmash", "charge": 5,
                   "hits": [mv((9, 15), 0, -10, 0, -60, 26, 2, 90, 15, 0, rehit=3, grp=1, fx="spin"),
                            hb((17, 18), 0, -62, 30, 7, 88, 40, 108, grp=2, fx="arc_up")]},
        "dsmash": {"frames": 44, "anim": "dsmash", "charge": 5,
                   "hits": [hb((10, 12), 40, 20, 22, 12, 25, 30, 95, grp=1, fx="kick"),
                            hb((10, 12), -40, 20, 22, 12, 155, 30, 95, grp=1, fx="kick")]},
        "nair": {"frames": 36, "anim": "nair", "land": 6,
                 "hits": [hb((4, 14), 0, 0, 36, 1.5, 70, 12, 5, rehit=4, grp=1, fx="spin"),
                          hb((16, 18), 0, 0, 38, 4, 45, 45, 85, grp=2, fx="spin")]},
        "fair": {"frames": 40, "anim": "fair", "land": 12,
                 "hits": [hb((8, 18), 32, 4, 22, 1.4, 40, 10, 0, rehit=3, grp=1, fx="drill"),
                          hb((20, 22), 34, 4, 24, 4, 40, 45, 95, grp=2, fx="kick")]},
        "bair": {"frames": 32, "anim": "bair", "land": 9,
                 "hits": [hb((6, 7), -36, 0, 18, 12, 145, 35, 98, grp=1, sweet=True, fx="kick"),
                          hb((6, 10), -22, 0, 20, 7, 145, 25, 85, grp=1, fx="kick")]},
        "uair": {"frames": 30, "anim": "uair", "land": 7, "hits": [arc((4, 10), 0, -4, 32, 0, 180, 20, 8, 85, 30, 100)]},
        # Dekatsuyo Drop: drops Dekatsuyo underneath like an anvil (meteor), Momonga hops up a little
        "dair": {"frames": 42, "anim": "summon_down", "land": 12, "drift": [(8, 8, None, -5)],
                 "proj": [(8, {"kind": "anvil", "vx": 0, "vy": 3, "grav": 0.9, "r": 34, "dmg": 15, "ang": 275,
                               "bkb": 30, "kbg": 82, "life": 120, "noreflect": True, "start_x": 0, "start_y": 48})]},
        # specials
        # Kani Guard (Peach's Toad style): holds Kani out - get hit during it and Kani snips back
        "nspec": {"frames": 46, "anim": "hold_out", "counter": (5, 28), "grav": 0.4},
        "counter_hit": {"frames": 50, "anim": "summon", "intang": (1, 14),
                        "hits": [hb((8, 30), 46, -6, 42, 2, 60, 20, 5, rehit=6, grp=1, fx="claw"),
                                 hb((34, 36), 50, -6, 48, 6, 40, 60, 82, grp=2, fx="big")]},
        # Nibble Leap (like Diddy's flip): leap forward; catch someone and he rides their head, nibbles, kicks off
        "sspec": {"frames": 50, "anim": "flip", "side_once": True, "drift": [(4, 4, 9.5, -9.5)], "grav": 0.8,
                  "steer": 0.3, "ledge_ok": True,
                  "grabbox": ((6, 34), 22, 0, 30), "grab_air": True, "on_grab": "nibble"},
        "nibble": {"frames": 58, "anim": "nibble", "ride": True, "grav": 0.0,
                   "pummels": [(10, 2), (20, 2), (30, 2)], "throw": (42, 5, 80, 60, 58), "drift": [(44, 44, -5, -10)]},
        "uspec": {"frames": 22, "anim": "rise", "glide": True, "drift": [(4, 4, None, -15.5)],
                  "hits": [hb((4, 10), 0, -16, 28, 5, 80, 45, 40, fx="spin")]},
        # Dekatsuyo charges across the stage
        "dspec": {"frames": 44, "anim": "summon", "cooldown": 600,
                  "proj": [(15, {"kind": "dekatsuyo", "vx": 16, "vy": 0, "grav": 0, "r": 62, "dmg": 18, "ang": 40,
                                 "bkb": 60, "kbg": 85, "life": 140, "pierce": True, "noreflect": True, "start_x": -260})]},
    }
    mv_.update(common(30, 22))
    mv_.update(throws((10, 7, 40, 55, 65), (12, 9, 135, 60, 75), (10, 5, 90, 65, 60), (12, 5, 75, 45, 45)))
    return {"name": "Momonga", "image": "momonga", "color": (96, 178, 230), "w": 56, "h": h, "weight": 70,
            "run": 10.2, "walk": 5.4, "air": 8.0, "accel": 0.55, "grav": 0.42, "fall": 6.4, "ff": 11.0,
            "jump": 13.2, "hop": 9.2, "djump": 12.4, "jumps": 3, "moves": mv_, "float": 180,
            "air_desc": "3 jumps, hold jump to glide",
            "desc": "Floaty brat with 3 jumps and drill aerials. "
                    "B: scream (hold to charge). Side-B: Dekatsuyo. Up-B: glide. Down-B: belly flop."}


# =================================================================== KURIMANJU (heavy, armored)
def kurimanju():
    h = 74
    S = "stick"
    mv_ = {
        "jab1": {"frames": 18, "anim": "jab", "next": ("jab2", 6), "hits": [hb((3, 4), 40, -2, 20, 3, 20, 10, 25, fx="poke")]},
        "jab2": {"frames": 18, "anim": "jab2", "next": ("jab3", 6), "hits": [hb((3, 4), 42, -2, 20, 3, 20, 10, 25, fx="poke")]},
        "jab3": {"frames": 34, "anim": "jab3", "weapon": S, "hits": weapon((5, 8), 0, -10, 100, 10, 54, 22, 6, 40, 50, 90)},
        "ftilt": {"frames": 34, "anim": "ftilt", "weapon": S,
                  "hits": weapon((8, 11), 0, -8, 60, -20, 66, 24, 10, 35, 32, 92, tip={"dmg": 13, "kbg": 96})},
        "utilt": {"frames": 32, "anim": "utilt", "weapon": S, "hits": weapon((7, 14), 0, -10, 20, 170, 60, 24, 9, 95, 38, 105)},
        "dtilt": {"frames": 24, "anim": "dtilt", "weapon": S, "hits": weapon((6, 8), 0, 16, -10, -20, 70, 18, 8, 30, 38, 65)},
        "dash": {"frames": 44, "anim": "dash", "drift": [(1, 14, 9, None)], "hits": [hb((8, 14), 30, 4, 34, 12, 45, 45, 80, fx="big")]},
        # home-run swing with super armor during the wind-up
        "fsmash": {"frames": 60, "anim": "fsmash", "charge": 10, "armor": (4, 19), "armor_kb": 130, "weapon": S,
                   "hits": weapon((18, 21), 0, -10, 120, -30, 78, 28, 18, 38, 34, 102, tip={"dmg": 22, "kbg": 106})},
        "usmash": {"frames": 52, "anim": "usmash", "charge": 7,
                   "hits": [hb((12, 22), 0, -60, 34, 2, 90, 20, 0, rehit=4, grp=1, fx="burp"),
                            hb((24, 26), 0, -70, 40, 9, 88, 45, 110, grp=2, fx="arc_up")]},
        "dsmash": {"frames": 56, "anim": "dsmash", "charge": 8, "armor": (3, 15), "armor_kb": 130,
                   "hits": [hb((16, 18), 0, 20, 90, 15, 50, 40, 96, radial=True, fx="ground")]},
        "nair": {"frames": 40, "anim": "nair", "land": 9,
                 "hits": [hb((6, 10), 0, 0, 46, 11, 45, 30, 90, grp=1, fx="spin"),
                          hb((11, 20), 0, 0, 42, 7, 45, 20, 75, grp=1, fx="spin")]},
        "fair": {"frames": 46, "anim": "fair", "land": 16, "weapon": S,
                 "hits": weapon((12, 17), 0, -10, 120, -40, 66, 24, 13, 45, 30, 90,
                                tip={"dmg": 16, "ang": 280, "bkb": 30, "kbg": 82})},
        "bair": {"frames": 38, "anim": "bair", "land": 12,
                 "hits": [hb((9, 11), -44, 0, 26, 15, 145, 32, 100, grp=1, sweet=True, fx="big"),
                          hb((9, 13), -26, 0, 28, 10, 145, 28, 90, grp=1, fx="big")]},
        "uair": {"frames": 34, "anim": "uair_still", "land": 9, "hits": [hb((7, 11), 0, -46, 30, 12, 85, 30, 102, fx="arc_up")]},
        # stall in the air, then plummet - meteor on the way down, shockwave on landing
        "dair": {"frames": 70, "anim": "dair", "land": 22, "drift": [(1, 8, 0, -3), (10, 70, None, 19)], "land_move": "drop_land",
                 "hits": [hb((10, 70), 0, 34, 30, 13, 275, 30, 80, fx="stomp")]},
        "drop_land": {"frames": 26, "anim": "land_slam", "hits": [hb((1, 3), 0, 10, 80, 7, 60, 55, 60, radial=True, fx="ground")]},
        # specials
        "nspec": {"frames": 50, "anim": "burp", "charge": 12, "charge_max": 60, "charge_mult": 0.6,
                  "hits": [hb((18, 21), 0, -4, 96, 11, 45, 45, 70, radial=True, fx="burp")]},
        # bottle lob that shatters into a slippery puddle
        "sspec": {"frames": 44, "anim": "throw_fwd", "cooldown": 240,
                  "proj": [(14, {"kind": "bottle", "vx": 8, "vy": -9, "grav": 0.45, "r": 16, "dmg": 7, "ang": 50,
                                 "bkb": 35, "kbg": 55, "life": 120,
                                 "linger": {"kind": "puddle", "frames": 240, "r": 50, "dmg": 2, "ang": 80, "bkb": 45,
                                            "kbg": 0, "rehit": 40}})]},
        "uspec": {"frames": 46, "anim": "rise", "helpless": True, "drift": [(8, 8, None, -19.5)], "steer": 0.5,
                  "hits": [hb((8, 16), 0, -10, 38, 10, 88, 50, 75, fx="burp")]},
        "dspec": {"frames": 56, "anim": "drink", "buff": (40, 1.35), "cooldown": 420},
    }
    mv_.update(common(42, 28))
    mv_.update(throws((10, 10, 40, 60, 72), (16, 12, 140, 60, 82), (12, 9, 90, 70, 72), (14, 8, 70, 50, 60)))
    return {"name": "Kurimanju", "image": "kurimanju", "color": (176, 118, 70), "w": 72, "h": h, "weight": 116,
            "run": 8.6, "walk": 4.4, "air": 6.0, "accel": 0.36, "grav": 0.74, "fall": 11.8, "ff": 17.6,
            "jump": 15.2, "hop": 10.4, "djump": 12.6, "jumps": 2, "moves": mv_,
            "air_desc": "heavy, falls fast",
            "desc": "Heavy hitter with armored smashes and a meteor drop. "
                    "B: burp (hold). Side-B: bottle lob (puddle). Down-B: drink up (+35% next hit)."}


# =================================================================== KANI (claws, grabs)
def kani():
    h = 74
    C = "claw"
    mv_ = {
        "jab1": {"frames": 16, "anim": "jab", "weapon": C, "next": ("jab2", 5), "hits": [hb((3, 4), 40, -6, 18, 2.5, 20, 8, 20, fx="poke")]},
        "jab2": {"frames": 16, "anim": "jab2", "weapon": C, "next": ("jab3", 5), "hits": [hb((3, 4), 42, -2, 18, 2.5, 20, 8, 20, fx="poke")]},
        "jab3": {"frames": 32, "anim": "snip", "weapon": C,
                 "hits": [hb((5, 6), 48, -6, 24, 3, 70, 30, 20, grp=1, fx="claw"),
                          hb((11, 13), 52, -6, 26, 4, 40, 45, 90, grp=2, fx="claw")]},
        "ftilt": {"frames": 30, "anim": "ftilt", "weapon": C, "hits": [mv((7, 10), 30, -6, 66, -6, 18, 10, 36, 32, 92, fx="claw")]},
        "utilt": {"frames": 30, "anim": "utilt", "weapon": C,
                  "hits": [hb((6, 7), 18, -48, 22, 4, 90, 40, 20, grp=1, fx="claw"),
                           hb((12, 14), 0, -56, 26, 6, 92, 40, 105, grp=2, fx="claw")]},
        "dtilt": {"frames": 20, "anim": "dtilt", "weapon": C, "hits": [hb((5, 7), 46, 22, 18, 6, 80, 40, 35, fx="claw")]},
        "dash": {"frames": 42, "anim": "dash", "drift": [(1, 24, 10, None)],
                 "hits": [hb((6, 22), 30, 0, 26, 2, 60, 20, 5, rehit=5, grp=1, fx="claw"),
                          hb((24, 26), 34, 0, 28, 5, 45, 50, 75, grp=2, fx="big")]},
        "fsmash": {"frames": 54, "anim": "fsmash", "charge": 9, "weapon": C,
                   "hits": [hb((16, 17), 64, -6, 20, 18, 38, 34, 102, grp=1, sweet=True, fx="claw"),
                            hb((16, 18), 40, -6, 24, 12, 40, 30, 92, grp=1, fx="claw")]},
        "usmash": {"frames": 48, "anim": "usmash", "charge": 6, "weapon": C,
                   "hits": [hb((11, 12), 26, -50, 24, 5, 90, 50, 0, grp=1, fx="claw"),
                            hb((11, 12), -26, -50, 24, 5, 90, 50, 0, grp=1, fx="claw"),
                            hb((16, 18), 0, -66, 30, 11, 90, 40, 108, grp=2, fx="arc_up")]},
        "dsmash": {"frames": 48, "anim": "dsmash", "charge": 6, "weapon": C,
                   "hits": [hb((11, 13), 50, 18, 24, 13, 30, 32, 95, grp=1, fx="claw"),
                            hb((11, 13), -50, 18, 24, 13, 150, 32, 95, grp=1, fx="claw")]},
        "nair": {"frames": 38, "anim": "nair_still", "land": 8, "weapon": C, "hits": [arc((4, 14), 0, -2, 44, 0, 360, 20, 8, 45, 28, 88)]},
        "fair": {"frames": 38, "anim": "snip", "land": 12, "weapon": C,
                 "hits": [hb((6, 7), 42, -4, 22, 4, 60, 30, 20, grp=1, fx="claw"),
                          hb((12, 14), 46, -4, 24, 8, 40, 35, 92, grp=2, fx="claw")]},
        "bair": {"frames": 34, "anim": "bair", "land": 10, "weapon": C,
                 "hits": [hb((8, 9), -46, -2, 20, 14, 145, 34, 100, grp=1, sweet=True, fx="claw"),
                          hb((8, 11), -28, -2, 22, 9, 145, 28, 85, grp=1, fx="claw")]},
        "uair": {"frames": 32, "anim": "uair_still", "land": 8, "weapon": C, "hits": [arc((5, 10), 0, -6, 42, 160, 20, 22, 10, 85, 30, 100)]},
        "dair": {"frames": 44, "anim": "dair", "land": 17, "weapon": C,
                 "hits": [hb((12, 14), 0, 46, 18, 13, 270, 28, 82, grp=1, sweet=True, fx="stomp"),
                          hb((12, 17), 0, 30, 22, 9, 290, 25, 70, grp=1, fx="stomp")]},
        # specials
        "nspec": {"frames": 38, "anim": "throw_fwd", "charge": 10, "charge_max": 40, "charge_speed": 0.25,
                  "proj": [(12, {"kind": "book", "vx": 10, "vy": -9, "grav": 0.45, "r": 20, "dmg": 9,
                                 "ang": 45, "bkb": 30, "kbg": 65, "life": 130, "bounces": 1})]},
        # command grab: lunge, pinch pinch pinch, fling
        # Pound Snip (Jigglypuff's Pound): a quick sideways snip that wrecks shields; small lift in the air
        "sspec": {"frames": 36, "anim": "snip", "weapon": C, "drift": [(4, 10, 8, None)],
                  "hits": [hb((7, 10), 48, -4, 26, 10, 40, 40, 70, shield_mult=3.2, sweet=True, fx="claw")]},
        "sspec_air": {"frames": 36, "anim": "snip", "weapon": C, "side_once": True,
                      "drift": [(4, 4, None, -5), (4, 10, 8, None)], "grav": 0.5,
                      "hits": [hb((7, 10), 48, -4, 26, 10, 40, 40, 70, shield_mult=3.2, sweet=True, fx="claw")]},
        # Claw Tether: shoots a claw up-forward; if it touches a ledge Kani reels in onto it
        # Claw Tether (Byleth / Joker style): grabs a LEDGE to reel in, or an OPPONENT to yank in and kick up
        "uspec": {"frames": 46, "anim": "tether", "helpless": True, "drift": [(3, 3, None, -8)], "grav": 0.5,
                  "steer": 0.5, "tether": (4, 16, 260, 40), "tether_grab": "tether_kick"},
        "tether_kick": {"frames": 36, "anim": "snip", "weapon": C, "pull": (1, 12), "grav": 0.3,
                        "throw": (16, 7, 55, 65, 72)},
        # Bedtime Reading (Jigglypuff's Sing): reads aloud - anyone close on the ground falls asleep
        "dspec": {"frames": 100, "anim": "read", "grav": 0.3,
                  "hits": [hb((34, 64), 0, -10, 88, 0, 0, 0, 0, sleep=150, fx="none")]},
    }
    mv_.update(common(40))
    mv_.update(throws((10, 8, 40, 52, 70), (12, 10, 140, 55, 78), (12, 7, 90, 60, 72), (11, 6, 70, 45, 52)))
    return {"name": "Kani", "image": "kani", "color": (232, 96, 84), "w": 62, "h": h, "weight": 96,
            "run": 9.4, "walk": 4.8, "air": 7.6, "accel": 0.5, "grav": 0.58, "fall": 9.2, "ff": 14.4,
            "jump": 14.2, "hop": 9.8, "djump": 11.4, "jumps": 3, "moves": mv_,
            "air_desc": "3 crab hops, fast sideways",
            "desc": "Crab scholar with claw sweetspots. "
                    "B: book toss. Side-B: crab grab (command grab, works in the air). Down-B: letter storm."}


# ---------------------------------------------------------------- global tuning
RUN_SCALE = 0.8      # everyone runs 20% slower than v1 (stages are also 1.8x wider)
AIR_SCALE = 0.85     # and drifts a bit slower in the air


def _tune(c):
    for k in ("run", "walk"):
        c[k] = round(c[k] * RUN_SCALE, 2)
    c["air"] = round(c["air"] * AIR_SCALE, 2)
    c["accel"] = round(c["accel"] * AIR_SCALE, 3)
    d = c["moves"].get("dash")
    if d:   # dash attacks slide a little less too
        d["drift"] = [(a, b_, None if vx is None else vx * 0.9, vy) for a, b_, vx, vy in d.get("drift", [])]
    return c


# ---------------------------------------------------------------- balance pass (v3)
# Juggle tools of the fast characters get more end lag / send further (harder to chain),
# slow projectiles come out sooner. Format: move -> {frames, land, kbg (+ added to every hitbox), proj_frame}
BALANCE = {
    "usagi": {"uair": {"frames": 38, "land": 10, "kbg": 8},
              "nair": {"land": 11}, "jab_fin": {"kbg": 6}},
    "momonga": {"uair": {"frames": 36, "kbg": 8}, "nair": {"land": 9}},
    "kurimanju": {"uair": {"frames": 40, "kbg": 8}, "nair": {"frames": 44, "land": 12},
                  "sspec": {"proj_frame": 12}},
    "chiikawa": {"nspec": {"proj_frame": 11}},
    "kani": {"nspec": {"proj_frame": 10}},
}


def _balance(key, c):
    moves = c["moves"]
    for name, ch in BALANCE.get(key, {}).items():
        m = moves[name]
        for k in ("frames", "land"):
            if k in ch:
                m[k] = ch[k]
        if "kbg" in ch:
            for h_ in m.get("hits", []):
                h_["kbg"] += ch["kbg"]
        if "proj_frame" in ch:
            for k in ("proj", "proj_charged"):
                if k in m:
                    m[k] = [(ch["proj_frame"], pd) for _, pd in m[k]]
    return c


from . import ground_moves  # noqa: E402  (new tilts / dash attacks / smashes, layered over the base moves)

CHARACTERS = {f.__name__: _balance(f.__name__, _tune(ground_moves.apply(f.__name__, f())))
              for f in (chiikawa, hachiware, usagi, momonga, kurimanju, kani)}

# names shown above a fighter when they use a special
SPECIAL_NAMES = {
    "chiikawa": {"nspec": "Weed Pull", "sspec": "Weeding Onslaught", "onslaught": "Weed weed weed!",
                 "uspec": "Pochette Parachute", "dspec": "Crying Fountain"},
    "hachiware": {"sspec": "Tail Tornado", "sspec_air": "Tail Tornado", "uspec": "Shoryuken!", "dspec": "Reflector"},
    "usagi": {"nspec": "Seed Spit", "sspec": "Crazy Rush", "sspec_yaha": "YAHA!", "uspec": "YAHA Warp",
              "dspec": "Snack Time"},
    "momonga": {"nspec": "Kani Guard", "counter_hit": "Kani, get 'em!", "sspec": "Nibble Leap", "nibble": "Nom nom!",
                "uspec": "Glide", "dspec": "Dekatsuyo!", "dair": "Dekatsuyo Drop!"},
    "kurimanju": {"nspec": "Burp", "sspec": "Bottle Lob", "uspec": "Beer Geyser", "dspec": "Drink Up"},
    "kani": {"nspec": "Book Toss", "sspec": "Pound Snip", "sspec_air": "Pound Snip", "uspec": "Claw Tether",
             "tether_kick": "Get over here!",
             "dspec": "Bedtime Reading"},
}
ROSTER = list(CHARACTERS.keys())


def get(char_key):
    return CHARACTERS[char_key]
