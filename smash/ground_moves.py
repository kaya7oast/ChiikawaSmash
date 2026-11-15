"""
Ground tilts, dash attacks and smash attacks - one distinct move per character (v4).
Layered over each character's base moves in characters.py (anything not listed here is unchanged).

Smash attack "families", so no two feel alike:
  fsmash  Chiikawa  haymaker, fist sweetspot (unchanged)      usmash  Chiikawa  hop headbutt (unchanged)
          Hachiware two guitar thrusts: long reach, low dmg           Hachiware strummed notes (unchanged)
          Usagi     stick lunge, TIPPER (only the tip is strong)      Usagi     pole-vault kick
          Momonga   lunging shove (travels forward)                   Momonga   back-flip kick
          Kurimanju belly bump with super armor                       Kurimanju burp geyser (unchanged)
          Kani      shield-crusher pinch (huge shield damage)         Kani      overhead claw clap
  dsmash  Chiikawa  floor tantrum (multi-hit then pop)
          Hachiware guitar sweep front THEN back (Ganon style)
          Usagi     breakdance stick sweep
          Momonga   tail spin (multi-hit, Pikachu style)
          Kurimanju butt-drop ground pound (jumps, then crashes both sides)
          Kani      claw slam both sides, low semi-spike angle (G&W style)
"""
from .characters import hb, mv, arc, weapon   # (imported at the end of characters.py, after these exist)

N = "none"   # no code-drawn swoosh; the hit-spark sprite does the impact


def chiikawa():
    return {
        # panicky two-slap flail: first slap keeps them close, second shoves
        "ftilt": {"frames": 24, "anim": "slap2", "limb": "fist",
                  "hits": [hb((4, 5), 34, -4, 18, 3, 75, 25, 8, grp=1, fx=N),
                           hb((10, 12), 40, -6, 20, 5, 35, 34, 88, grp=2, fx=N)]},
        # startled hop, arms up: "Ha!"
        "utilt": {"frames": 28, "anim": "hop", "limb": "fists",
                  "hits": [mv((5, 10), 0, -26, 0, -58, 24, 6, 90, 42, 100, fx=N)]},
        # yanks a weed out of the ground - pops them up (combo starter)
        "dtilt": {"frames": 18, "anim": "dtilt", "weapon": "weed",
                  "hits": weapon((4, 7), 6, 14, -100, -15, 34, 16, 4, 76, 40, 34, grp=1, fx=N)},
        # trips and tumbles into you, ends face-down (very punishable)
        "dash": {"frames": 52, "anim": "tumble", "limb": "body", "drift": [(2, 26, 7.5, None)],
                 "hits": [hb((6, 24), 22, 4, 30, 1.2, 30, 10, 0, rehit=5, grp=1, fx=N),
                          hb((26, 28), 24, 8, 32, 4, 40, 55, 62, grp=2, fx=N)]},
        # floor tantrum: flops down and pounds the floor with both fists, then a pop
        "dsmash": {"frames": 52, "anim": "tantrum", "limb": "fists", "charge": 5,
                   "hits": [hb((10, 20), 34, 26, 22, 1.5, 70, 15, 0, rehit=4, grp=1, fx=N),
                            hb((10, 20), -34, 26, 22, 1.5, 110, 15, 0, rehit=4, grp=1, fx=N),
                            hb((22, 23), 40, 26, 26, 8, 35, 38, 95, grp=2, fx="ground"),
                            hb((22, 23), -40, 26, 26, 8, 145, 38, 95, grp=2, fx="ground")]},
    }


def hachiware():
    return {
        # guitar-neck poke: long reach, the headstock tip is the sweetspot
        "ftilt": {"frames": 28, "anim": "lunge", "weapon": "guitar",
                  "hits": [mv((7, 10), 30, -6, 82, -6, 16, 10, 32, 32, 92, grp=1, sweet=True, fx=N),
                           mv((7, 10), 18, -6, 50, -6, 18, 7, 35, 30, 85, grp=1, fx=N)]},
        # overhead guitar arc, back to front
        "utilt": {"frames": 30, "anim": "utilt", "weapon": "guitar",
                  "hits": weapon((6, 12), 0, -10, 165, 15, 58, 20, 7, 88, 40, 100, grp=1)},
        # low leg sweep from behind to in front - trips (pops them a little)
        "dtilt": {"frames": 22, "anim": "sweep", "limb": "foot",
                  "hits": [mv((5, 9), -40, 30, 46, 30, 18, 6, 80, 32, 30, fx=N)]},
        # rock-star knee slide with the guitar: strong early, weak late, slides a long way
        "dash": {"frames": 46, "anim": "kneeslide", "weapon": "guitar", "drift": [(2, 26, 9.5, None)],
                 "hits": [hb((4, 10), 34, 8, 28, 9, 40, 45, 72, grp=1, fx=N),
                          hb((11, 24), 34, 8, 24, 5, 55, 32, 52, grp=1, fx=N)]},
        # two guitar thrusts: the first holds them, the second reaches far. Long range, less damage.
        "fsmash": {"frames": 54, "anim": "lunge", "weapon": "guitar", "charge": 9,
                   "hits": [mv((12, 13), 30, -6, 66, -6, 20, 5, 15, 25, 8, grp=1, fx=N),
                            mv((20, 23), 40, -6, 98, -6, 20, 10, 36, 38, 100, grp=2, fx=N)]},
        # Ganon style: guitar swept low in front, THEN behind (the back hit is stronger)
        "dsmash": {"frames": 56, "anim": "ganon", "weapon": "guitar", "charge": 6,
                   "hits": weapon((11, 14), 0, 22, 70, -20, 54, 20, 11, 30, 32, 95, grp=1)
                   + weapon((20, 23), 0, 22, 110, 200, 54, 20, 13, 145, 34, 100, grp=2)},
    }


def usagi():
    return {
        # stick thrust, tip is the sweetspot
        "ftilt": {"frames": 26, "anim": "lunge", "weapon": "stick",
                  "hits": [mv((6, 9), 26, -12, 86, -12, 16, 10, 33, 32, 90, grp=1, sweet=True, fx=N),
                           mv((6, 9), 20, -12, 50, -12, 18, 7, 35, 28, 82, grp=1, fx=N)]},
        # stick twirled above the head: multi-hit, then a pop
        "utilt": {"frames": 38, "anim": "twirl", "weapon": "stick",
                  "hits": [arc((5, 15), 0, -50, 26, 0, 720, 26, 1.4, 90, 6, 0, rehit=3, grp=1, fx=N),
                           arc((16, 18), 0, -52, 30, 0, 180, 30, 5, 90, 45, 110, grp=2, fx=N)]},
        # quick ankle whack
        "dtilt": {"frames": 18, "anim": "dtilt", "weapon": "stick",
                  "hits": weapon((4, 6), 4, 0, -15, -42, 56, 16, 5, 18, 30, 40, grp=1, fx=N)},
        # "YAHA!" flying dropkick: fast and far, but you land on your back
        "dash": {"frames": 52, "anim": "dropkick", "limb": "feet", "drift": [(4, 20, 12, None)],
                 "hits": [hb((8, 15), 40, 4, 24, 13, 38, 45, 84, grp=1, fx=N),
                          hb((16, 24), 34, 4, 22, 7, 45, 30, 60, grp=1, fx=N)]},
        # TIPPER lunge: only the very tip of the stick is strong
        "fsmash": {"frames": 52, "anim": "lunge", "weapon": "stick", "charge": 9,
                   "hits": [mv((14, 17), 92, -10, 118, -10, 16, 19, 36, 36, 100, grp=1, sweet=True, fx=N),
                            mv((14, 17), 24, -10, 86, -10, 22, 8, 42, 30, 76, grp=1, fx=N)]},
        # pole-vault: plants the stick and kicks straight up
        "usmash": {"frames": 48, "anim": "vault", "limb": "body", "charge": 6,
                   "hits": [mv((10, 13), 0, -30, 0, -96, 30, 16, 88, 34, 100, grp=1, fx=N),
                            hb((14, 20), 0, -86, 26, 8, 85, 30, 80, grp=1, fx=N)]},
        # breakdance sweep: stick round the floor, front then back
        "dsmash": {"frames": 50, "anim": "breakdance", "weapon": "stick", "charge": 5,
                   "hits": [mv((10, 12), 20, 30, 70, 30, 22, 13, 30, 34, 96, grp=1, fx=N),
                            mv((14, 17), -20, 30, -70, 30, 22, 14, 150, 34, 98, grp=1, fx=N)]},
    }


def momonga():
    return {
        # spins to whip the big fluffy tail over and in front
        "ftilt": {"frames": 26, "anim": "whip", "limb": "body",
                  "hits": [arc((6, 9), 0, 4, 42, 150, 20, 20, 7, 40, 30, 86, fx=N)]},
        # ear flick: tiny and very fast
        "utilt": {"frames": 22, "anim": "flick", "limb": "head",
                  "hits": [hb((4, 7), 0, -38, 22, 5, 95, 40, 92, fx=N)]},
        # two quick nibbles at the feet
        "dtilt": {"frames": 18, "anim": "nibble", "limb": "body",
                  "hits": [hb((3, 4), 30, 18, 16, 2, 70, 15, 5, grp=1, fx=N),
                           hb((8, 9), 32, 18, 18, 3.5, 65, 38, 40, grp=2, fx=N)]},
        # belly glide: flat and low, slides under things, weak
        "dash": {"frames": 38, "anim": "bellyglide", "limb": "body", "drift": [(2, 24, 10.5, None)],
                 "hits": [hb((4, 22), 22, 18, 22, 5, 50, 30, 52, fx=N)]},
        # lunging two-paw shove that travels forward
        "fsmash": {"frames": 48, "anim": "lunge", "limb": "fists", "charge": 7, "drift": [(12, 18, 7, None)],
                   "hits": [hb((13, 18), 34, -4, 24, 15, 38, 30, 96, fx=N)]},
        # back-flip kick: feet swing from in front up over the head
        "usmash": {"frames": 46, "anim": "flip", "limb": "body", "charge": 5,
                   "hits": [arc((9, 16), 0, -10, 40, 0, 200, 22, 14, 85, 32, 98, fx=N)]},
        # tail spin on the floor: multi-hit both sides, then a pop
        "dsmash": {"frames": 48, "anim": "tailspin", "limb": "body", "charge": 5,
                   "hits": [hb((8, 18), 0, 20, 46, 1.3, 80, 12, 0, rehit=3, grp=1, fx=N),
                            hb((19, 21), 0, 18, 50, 6, 40, 45, 92, grp=2, fx=N)]},
    }


def kurimanju():
    return {
        # slow, heavy overhead bonk
        "ftilt": {"frames": 36, "anim": "bonk", "weapon": "stick",
                  "hits": weapon((9, 12), 6, -14, 115, -10, 62, 20, 12, 40, 40, 86, grp=1)},
        # belly bounce straight up
        "utilt": {"frames": 38, "anim": "bellybounce", "limb": "body",
                  "hits": [mv((7, 13), 0, -24, 0, -64, 32, 10, 90, 45, 92, fx=N)]},
        # two-fist slam on the floor in front - pops them up
        "dtilt": {"frames": 26, "anim": "slam", "limb": "fists",
                  "hits": [hb((8, 10), 40, 30, 26, 9, 80, 52, 48, fx="ground")]},
        # barrel shoulder charge with armor
        "dash": {"frames": 50, "anim": "shoulder", "limb": "body", "drift": [(2, 22, 8.5, None)],
                 "armor": (4, 18), "armor_kb": 70,
                 "hits": [hb((6, 20), 34, -2, 30, 12, 40, 50, 80, fx=N)]},
        # huge belly bump with super armor: slow, but nothing stops it
        "fsmash": {"frames": 62, "anim": "bellybump", "limb": "body", "charge": 10, "armor": (8, 17), "armor_kb": 90,
                   "hits": [hb((18, 21), 42, -2, 34, 21, 38, 40, 98, fx=N)]},
        # hops up and butt-drops: both sides at once
        "dsmash": {"frames": 58, "anim": "groundpound", "limb": "body", "charge": 8,
                   "hits": [hb((18, 20), 0, 30, 30, 16, 80, 40, 96, grp=1, fx="ground"),
                            hb((18, 20), 52, 30, 30, 15, 35, 40, 96, grp=1, fx="ground"),
                            hb((18, 20), -52, 30, 30, 15, 145, 40, 96, grp=1, fx="ground")]},
    }


def kani():
    return {
        # claw jab that drags them in toward her (sets up grabs / the snip)
        "ftilt": {"frames": 28, "anim": "lunge", "weapon": "claw",
                  "hits": [mv((6, 9), 24, -6, 60, -6, 18, 7, 175, 40, 12, fx=N)]},
        # two snips upward: the first holds, the second launches
        "utilt": {"frames": 30, "anim": "utilt", "weapon": "claw",
                  "hits": [arc((5, 6), 0, 2, 50, 55, 90, 22, 3, 95, 20, 5, grp=1, fx=N),
                           arc((11, 13), 0, 2, 50, 90, 125, 24, 6, 92, 42, 96, grp=2, fx=N)]},
        # pinch at the feet: low angle trip
        "dtilt": {"frames": 20, "anim": "dtilt", "weapon": "claw",
                  "hits": [mv((4, 6), 20, 28, 48, 28, 16, 6, 25, 40, 40, fx=N)]},
        # claw lunge that grabs on hit and tosses them
        "dash": {"frames": 46, "anim": "lunge", "weapon": "claw", "drift": [(2, 18, 9, None)], "on_grab": "dash_toss",
                 "hits": [hb((6, 16), 36, -4, 24, 3, 45, 30, 10, lock=True, fx=N)]},
        "dash_toss": {"frames": 30, "anim": "fthrow", "limb": "grab", "pummels": [(4, 1.0)], "throw": (12, 6, 50, 60, 62)},
        # slow shield-crusher pinch: 2.2x shield damage
        "fsmash": {"frames": 56, "anim": "lunge", "weapon": "claw", "charge": 9,
                   "hits": [mv((17, 20), 30, -6, 68, -6, 22, 16, 36, 34, 98, shield_mult=2.2, fx=N)]},
        # overhead claw clap, back to front
        "usmash": {"frames": 48, "anim": "usmash", "weapon": "claw", "charge": 6,
                   "hits": [arc((11, 15), 0, -20, 52, 150, 30, 24, 15, 90, 32, 98, fx=N)]},
        # G&W style: claws slam both sides at once, low semi-spike angle (great at the ledge)
        "dsmash": {"frames": 50, "anim": "slam", "weapon": "claw", "charge": 6,
                   "hits": [mv((11, 13), 20, 30, 56, 30, 20, 13, 20, 36, 92, grp=1, fx=N),
                            mv((11, 13), -20, 30, -56, 30, 20, 13, 160, 36, 92, grp=1, fx=N)]},
    }


OVERRIDES = {f.__name__: f for f in (chiikawa, hachiware, usagi, momonga, kurimanju, kani)}


def apply(key, c):
    new = OVERRIDES.get(key)
    if new:
        c["moves"].update(new())
    return c
