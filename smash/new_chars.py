"""
Rakko, Chikkabu (small beetle + big muscle form) and Siren - added in v5.
Same data format as characters.py (see the notes at the top of that file). New move keys used here:
  cart          Rakko's minecart: the cart is drawn under him while the move runs
  warp_behind   counter_hit: reappear behind whoever hit you, then strike
  latch         counter: instead of a counter attack, latch onto the attacker (3s, 5%/s, heals 2%/s)
  bulk          hold to fill Chikkabu's bulk meter; full = big form for 20s
  mermaid       the projectile only fires if Siren has a mermaid left (2 max, they come back over time)
"""
from .characters import hb, mv, arc, weapon, common, throws, rapid_jab

N = "none"
S = "stick"


# =================================================================== RAKKO (the master swordsman)
def rakko():
    h = 72
    m = {
        "jab1": {"frames": 15, "anim": "jab", "next": ("jab2", 5), "hits": [hb((3, 4), 34, -4, 16, 2.5, 30, 10, 25, fx="poke")]},
        "jab2": {"frames": 15, "anim": "jab2", "next": ("jab3", 5), "hits": [hb((3, 4), 38, -4, 16, 2.5, 30, 10, 25, fx="poke")]},
        "jab3": {"frames": 30, "anim": "jab3", "weapon": S, "hits": weapon((4, 7), 0, -6, 80, -10, 58, 18, 5, 40, 50, 92)},
        # tipper thrust: the tip is the sweetspot
        "ftilt": {"frames": 28, "anim": "lunge", "weapon": S,
                  "hits": [mv((6, 9), 66, -8, 94, -8, 16, 11, 34, 34, 94, grp=1, sweet=True, fx=N),
                           mv((6, 9), 20, -8, 64, -8, 18, 7, 38, 30, 82, grp=1, fx=N)]},
        "utilt": {"frames": 30, "anim": "utilt", "weapon": S, "hits": weapon((5, 11), 0, -6, 170, 10, 58, 20, 7, 88, 40, 100)},
        "dtilt": {"frames": 20, "anim": "dtilt", "weapon": S, "hits": weapon((4, 6), 4, 0, -10, -35, 64, 16, 6, 25, 36, 50)},
        "dash": {"frames": 40, "anim": "lunge", "weapon": S, "drift": [(2, 14, 10, None)],
                 "hits": weapon((6, 10), 0, -6, 40, -20, 60, 20, 10, 40, 45, 78)},
        "fsmash": {"frames": 54, "anim": "fsmash", "weapon": S, "charge": 9,
                   "hits": weapon((15, 18), 0, -8, 88, -20, 84, 22, 14, 36, 34, 100, tip={"dmg": 20, "kbg": 104})},
        "usmash": {"frames": 48, "anim": "usmash", "weapon": S, "charge": 6,
                   "hits": weapon((10, 16), 0, -10, 0, 180, 64, 22, 13, 90, 34, 100, tip={"dmg": 17})},
        "dsmash": {"frames": 48, "anim": "ganon", "weapon": S, "charge": 5,
                   "hits": weapon((8, 10), 0, 24, 40, -20, 64, 20, 12, 30, 32, 96, grp=1)
                   + weapon((15, 17), 0, 24, 140, 200, 64, 20, 14, 150, 34, 98, grp=2)},
        "nair": {"frames": 34, "anim": "nair", "land": 8, "weapon": S, "hits": weapon((5, 14), 0, -4, 90, 450, 56, 20, 8, 40, 30, 90)},
        "fair": {"frames": 34, "anim": "fair", "land": 9, "weapon": S,
                 "hits": weapon((6, 10), 0, -6, 100, -40, 62, 20, 9, 40, 30, 92, tip={"dmg": 12})},
        "bair": {"frames": 36, "anim": "bair", "land": 11, "weapon": S, "hits": weapon((7, 11), 0, -6, 80, 200, 62, 20, 11, 145, 32, 100)},
        "uair": {"frames": 32, "anim": "uair_still", "land": 8, "weapon": S, "hits": weapon((5, 12), 0, -10, 160, 20, 58, 20, 9, 88, 32, 100)},
        "dair": {"frames": 42, "anim": "dair", "land": 14, "weapon": S,
                 "hits": weapon((10, 13), 0, 4, -40, -140, 60, 20, 13, 275, 28, 84, tip={"ang": 280})},
        # specials
        # Charged Slam: hold to charge, slams the ground for a blast all around him
        "nspec": {"frames": 50, "anim": "slam", "charge": 8, "charge_max": 60, "charge_mult": 0.8,
                  "hits": [hb((18, 21), 0, 20, 84, 10, 60, 50, 70, radial=True, fx="ground")]},
        # Minecart (Steve style): rides forward fast; jump to hop out. Careful near edges!
        "sspec": {"frames": 104, "anim": "cart", "side_once": True, "cart": True, "drift": [(6, 92, 11.5, None)],
                  "follow": [("jump", 10, 92, "cart_jump")],
                  "hits": [hb((6, 92), 30, 4, 30, 12, 40, 55, 72, grp=1, fx=N)]},
        "cart_jump": {"frames": 24, "anim": "flip", "drift": [(1, 1, None, -14)]},
        # Rising slash
        "uspec": {"frames": 48, "anim": "rise", "helpless": True, "ledge_ok": True, "drift": [(6, 6, None, -18)], "steer": 0.4,
                  "weapon": S, "hits": weapon((6, 14), 0, -10, 20, 120, 56, 20, 9, 85, 50, 80)},
        # Shadow Counter: get hit during the window -> reappear BEHIND the attacker and strike
        "dspec": {"frames": 44, "anim": "hold_out", "counter": (4, 26), "grav": 0.4},
        "counter_hit": {"frames": 36, "anim": "lunge", "warp_behind": True, "weapon": S, "intang": (1, 10),
                        "hits": weapon((6, 9), 0, -6, 90, -20, 62, 22, 0, 40, 50, 92, counter=True)},
    }
    m.update(common(40, 24))
    m.update(throws((10, 9, 40, 60, 72), (16, 11, 140, 60, 80), (12, 8, 90, 70, 72), (14, 7, 70, 50, 60)))
    return {"name": "Rakko", "image": "rakko", "color": (196, 160, 120), "w": 64, "h": h, "weight": 98,
            "run": 9.4, "walk": 4.6, "air": 6.4, "accel": 0.4, "grav": 0.78, "fall": 10.2, "ff": 15.5,
            "jump": 15.4, "hop": 10.6, "djump": 13.4, "jumps": 2, "moves": m,
            "air_desc": "balanced", "desc": "Master swordsman: long reach, tippers, a minecart and a counter that warps behind you."}


# =================================================================== CHIKKABU (small beetle form)
def chikkabu():
    h = 58
    m = {
        "jab1": {"frames": 13, "anim": "jab", "next": ("jab2", 4), "hits": [hb((2, 3), 30, -4, 16, 2, 30, 8, 20, fx="poke")]},
        "jab2": {"frames": 13, "anim": "jab2", "next": ("jab_rapid", 4), "hits": [hb((2, 3), 32, -4, 16, 2, 30, 8, 20, fx="poke")]},
        "jab_rapid": rapid_jab(34, 20, "jab_fin"),
        "jab_fin": {"frames": 26, "anim": "jab3", "limb": "head", "hits": [hb((3, 5), 36, -6, 24, 3, 40, 50, 80, fx=N)]},
        "ftilt": {"frames": 24, "anim": "lunge", "limb": "head", "hits": [mv((5, 8), 20, -14, 46, -14, 18, 7, 35, 32, 86, fx=N)]},
        "utilt": {"frames": 26, "anim": "hop", "limb": "head", "hits": [arc((4, 9), 0, -14, 30, 30, 150, 20, 6, 92, 40, 100, fx=N)]},
        "dtilt": {"frames": 18, "anim": "dtilt", "limb": "foot", "hits": [hb((3, 5), 32, 24, 16, 5, 70, 38, 38, fx=N)]},
        "dash": {"frames": 36, "anim": "dash", "limb": "head", "drift": [(2, 12, 9.5, None)],
                 "hits": [hb((5, 12), 26, 0, 26, 8, 45, 40, 70, fx=N)]},
        "fsmash": {"frames": 48, "anim": "lunge", "limb": "head", "charge": 7, "drift": [(12, 18, 6, None)],
                   "hits": [hb((13, 18), 32, -8, 24, 15, 38, 32, 98, fx=N)]},
        "usmash": {"frames": 44, "anim": "hop", "limb": "head", "charge": 5,
                   "hits": [mv((9, 14), 10, -10, 0, -58, 26, 14, 88, 32, 98, fx=N)]},
        "dsmash": {"frames": 44, "anim": "breakdance", "limb": "feet", "charge": 5,
                   "hits": [hb((8, 10), 30, 24, 20, 12, 30, 34, 94, grp=1, fx=N),
                            hb((8, 10), -30, 24, 20, 12, 150, 34, 94, grp=1, fx=N)]},
        "nair": {"frames": 32, "anim": "nair", "land": 7, "limb": "body", "hits": [hb((4, 16), 0, 0, 34, 8, 45, 30, 80, fx=N)]},
        "fair": {"frames": 32, "anim": "fair", "land": 9, "limb": "head", "hits": [hb((6, 9), 34, -6, 20, 9, 40, 34, 88, fx=N)]},
        "bair": {"frames": 32, "anim": "bair", "land": 9, "limb": "foot", "hits": [hb((6, 9), -34, 4, 20, 11, 145, 32, 98, fx=N)]},
        "uair": {"frames": 30, "anim": "uair_still", "land": 7, "limb": "head",
                 "hits": [arc((5, 11), 0, -6, 34, 30, 160, 20, 8, 88, 32, 100, fx=N)]},
        "dair": {"frames": 36, "anim": "dair", "land": 12, "limb": "feet", "hits": [hb((8, 11), 0, 30, 20, 10, 280, 30, 80, fx=N)]},
        # Latch Counter: get hit during the window and he latches onto the attacker for 3s
        "nspec": {"frames": 40, "anim": "hold_out", "counter": (4, 24), "latch": True, "grav": 0.4},
        # Horn Charge: vibrates, then rushes forward
        "sspec": {"frames": 46, "anim": "charge", "side_once": True, "drift": [(10, 26, 12, 0)], "grav": 0.3, "limb": "head",
                  "hits": [hb((10, 26), 28, 0, 26, 10, 38, 55, 78, fx=N)]},
        # Flight (Pit style): a long, steerable flight upward
        "uspec": {"frames": 56, "anim": "rise", "helpless": True, "ledge_ok": True, "drift": [(6, 36, None, -11.5)], "steer": 0.9},
        # Bulk Up: hold to fill the bulk meter. Full = big muscle form for 20 seconds.
        "dspec": {"frames": 30, "anim": "bulk", "charge": 6, "charge_max": 600, "bulk": True},
    }
    m.update(common(34, 22))
    m.update(throws((10, 7, 40, 55, 70), (14, 9, 140, 55, 78), (12, 7, 90, 65, 70), (12, 6, 70, 45, 58)))
    return {"name": "Chikkabu", "image": "chikkabu", "color": (150, 100, 62), "w": 54, "h": h, "weight": 72,
            "run": 9.6, "walk": 4.6, "air": 6.6, "accel": 0.45, "grav": 0.76, "fall": 9.4, "ff": 14.5,
            "jump": 14.6, "hop": 10.0, "djump": 13.0, "jumps": 2, "moves": m,
            "air_desc": "light, flies up", "desc": "Small beetle that latches on, then bulks up into a 20s muscle form."}


# =================================================================== CHIKKABU (big muscle form, not selectable)
def _wave(vx, start_x, start_y):
    return {"kind": "wave", "vx": vx, "vy": 0, "r": 20, "dmg": 3, "ang": 70, "bkb": 40, "kbg": 30, "life": 24,
            "start_x": start_x, "start_y": start_y, "pierce": True, "noreflect": True}


def chikkabu_big():
    h = 90
    m = {
        "jab1": {"frames": 18, "anim": "jab", "next": ("jab2", 6), "limb": "fist", "hits": [hb((4, 5), 46, -6, 22, 4, 30, 15, 30, fx="poke")]},
        "jab2": {"frames": 18, "anim": "jab2", "next": ("jab3", 6), "limb": "fist", "hits": [hb((4, 5), 50, -6, 22, 4, 30, 15, 30, fx="poke")]},
        "jab3": {"frames": 32, "anim": "jab3", "limb": "fist", "hits": [hb((5, 8), 54, -8, 28, 8, 40, 55, 90, fx=N)]},
        "ftilt": {"frames": 32, "anim": "lunge", "limb": "fist", "hits": [hb((8, 11), 54, -6, 26, 12, 36, 38, 90, fx=N)]},
        "utilt": {"frames": 34, "anim": "hop", "limb": "fists", "hits": [mv((7, 12), 20, -10, 10, -74, 30, 11, 88, 42, 98, fx=N)]},
        "dtilt": {"frames": 28, "anim": "slam", "limb": "fist", "hits": [hb((8, 10), 50, 36, 26, 9, 75, 50, 50, fx="ground")]},
        "dash": {"frames": 46, "anim": "shoulder", "limb": "body", "drift": [(2, 18, 8.5, None)], "armor": (4, 16), "armor_kb": 70,
                 "hits": [hb((6, 18), 40, -4, 32, 12, 40, 50, 80, fx=N)]},
        "fsmash": {"frames": 60, "anim": "lunge", "limb": "fist", "charge": 9, "armor": (8, 16), "armor_kb": 100,
                   "hits": [hb((17, 20), 62, -8, 30, 22, 38, 40, 100, fx=N)]},
        "usmash": {"frames": 52, "anim": "hop", "limb": "fists", "charge": 7, "hits": [hb((12, 16), 0, -80, 40, 18, 88, 36, 98, fx=N)]},
        "dsmash": {"frames": 56, "anim": "slam", "limb": "fists", "charge": 7,
                   "hits": [hb((15, 17), 56, 40, 30, 16, 35, 40, 96, grp=1, fx="ground"),
                            hb((15, 17), -56, 40, 30, 16, 145, 40, 96, grp=1, fx="ground")]},
        "nair": {"frames": 38, "anim": "nair", "land": 10, "limb": "body", "hits": [hb((5, 14), 0, 0, 50, 10, 45, 34, 86, fx=N)]},
        "fair": {"frames": 44, "anim": "fair", "land": 15, "limb": "fist",
                 "hits": [hb((10, 12), 46, 10, 22, 14, 280, 28, 80, grp=1, sweet=True, fx=N),
                          hb((10, 14), 34, -6, 28, 10, 45, 30, 84, grp=1, fx=N)]},
        "bair": {"frames": 40, "anim": "bair", "land": 12, "limb": "foot", "hits": [hb((8, 11), -48, 4, 26, 15, 145, 34, 100, fx=N)]},
        "uair": {"frames": 36, "anim": "uair_still", "land": 10, "limb": "head", "hits": [hb((7, 12), 0, -56, 32, 12, 88, 32, 102, fx=N)]},
        "dair": {"frames": 44, "anim": "dair", "land": 16, "limb": "feet", "hits": [hb((10, 14), 0, 46, 28, 14, 275, 30, 84, fx=N)]},
        # Giant Punch: hold to charge
        "nspec": {"frames": 56, "anim": "lunge", "limb": "fist", "charge": 10, "charge_max": 90, "charge_mult": 1.0,
                  "hits": [hb((14, 17), 60, -6, 30, 14, 40, 45, 95, fx=N)]},
        # Horn Punch: an armored, much stronger horn charge
        "sspec": {"frames": 52, "anim": "charge", "side_once": True, "armor": (8, 22), "armor_kb": 90,
                  "drift": [(10, 24, 13, 0)], "grav": 0.3, "limb": "head", "hits": [hb((10, 24), 36, -4, 30, 17, 38, 60, 90, fx=N)]},
        # Cross Chop (Incineroar style): rise, hang, then dive forward-down - lands with a blast
        "uspec": {"frames": 64, "anim": "crosschop", "helpless": True, "ledge_ok": True, "limb": "fists",
                  "drift": [(6, 16, None, -15), (17, 24, 0, 0), (25, 46, 7, 15)], "land_move": "chop_land",
                  "hits": [hb((6, 16), 0, -30, 30, 4, 88, 40, 30, grp=1, fx=N),
                           hb((25, 46), 30, 20, 34, 13, 300, 35, 80, grp=2, fx=N)]},
        "chop_land": {"frames": 24, "anim": "slam", "hits": [hb((1, 3), 0, 30, 70, 8, 70, 50, 70, radial=True, fx="ground")]},
        # Hand Slap (Donkey Kong style): slaps the ground both sides with shockwaves - mash B to keep slapping
        "dspec": {"frames": 40, "anim": "handslap", "limb": "fists", "rapid": ("spc", 6, 20, 4, None),
                  "hits": [hb((8, 10), 46, 40, 34, 4, 82, 45, 45, grp=1, fx="ground"),
                           hb((14, 16), -46, 40, 34, 4, 82, 45, 45, grp=2, fx="ground")],
                  "proj": [(9, _wave(10, 50, 33)), (15, _wave(-10, -50, 33))]},
    }
    m.update(common(48, 30))
    m.update(throws((12, 11, 40, 70, 80), (18, 13, 140, 70, 88), (14, 10, 90, 75, 78), (16, 9, 70, 55, 66)))
    return {"name": "Chikkabu", "image": "chikkabu_big", "color": (120, 80, 50), "w": 80, "h": h, "weight": 122,
            "run": 7.4, "walk": 3.8, "air": 5.6, "accel": 0.34, "grav": 0.8, "fall": 11.4, "ff": 17.0,
            "jump": 15.4, "hop": 10.6, "djump": 12.8, "jumps": 2, "moves": m, "hidden": True, "form_of": "chikkabu",
            "air_desc": "heavy", "desc": "Chikkabu's 20-second muscle form."}


# =================================================================== SIREN (zoner / summoner)
def _vine(vx):
    return {"kind": "seed", "vx": vx, "vy": -6, "grav": 0.55, "r": 12, "dmg": 3, "ang": 60, "bkb": 30, "kbg": 30, "life": 120,
            "linger": {"kind": "vine", "frames": 300, "r": 34, "dmg": 7, "ang": 85, "bkb": 50, "kbg": 45, "rehit": 60}}


def _tide(vx, r=24, dmg=6, life=50):
    return {"kind": "wave", "vx": vx, "vy": 0, "r": r, "dmg": dmg, "ang": 60, "bkb": 40, "kbg": 50, "life": life,
            "start_x": 40 if vx > 0 else -40, "start_y": 22, "pierce": True, "noreflect": True}


def siren():
    h = 72
    m = {
        "jab1": {"frames": 15, "anim": "jab", "next": ("jab2", 5), "hits": [hb((3, 4), 36, -4, 18, 2.5, 30, 10, 25, fx="poke")]},
        "jab2": {"frames": 15, "anim": "jab2", "next": ("jab3", 5), "hits": [hb((3, 4), 38, -4, 18, 2.5, 30, 10, 25, fx="poke")]},
        "jab3": {"frames": 30, "anim": "whip", "limb": "body", "hits": [hb((5, 8), 40, 10, 26, 6, 40, 50, 85, fx=N)]},
        "ftilt": {"frames": 30, "anim": "whip", "limb": "body", "hits": [arc((6, 9), 0, 8, 44, 150, 10, 22, 9, 38, 34, 88, fx=N)]},
        "utilt": {"frames": 28, "anim": "flick", "limb": "head", "hits": [hb((5, 10), 0, -46, 30, 7, 92, 40, 98, fx=N)]},
        "dtilt": {"frames": 22, "anim": "sweep", "limb": "body", "hits": [mv((5, 8), -30, 30, 50, 30, 18, 6, 75, 34, 34, fx=N)]},
        "dash": {"frames": 40, "anim": "bellyglide", "limb": "body", "drift": [(2, 22, 9.5, None)],
                 "hits": [hb((4, 20), 26, 16, 24, 7, 45, 34, 60, fx=N)]},
        # big tail whack: the fin is the sweetspot
        "fsmash": {"frames": 54, "anim": "whip", "limb": "body", "charge": 9,
                   "hits": [arc((14, 17), 0, 10, 54, 160, -10, 22, 17, 36, 34, 100, grp=1, sweet=True, fx=N),
                            hb((14, 17), 24, 0, 26, 11, 40, 30, 88, grp=1, fx=N)]},
        # water burst above her head
        "usmash": {"frames": 48, "anim": "twirl", "limb": "body", "charge": 6,
                   "hits": [hb((10, 20), 0, -60, 30, 2, 90, 15, 0, rehit=4, grp=1, fx=N),
                            hb((21, 23), 0, -70, 38, 9, 90, 45, 108, grp=2, fx=N)]},
        "dsmash": {"frames": 50, "anim": "slam", "limb": "body", "charge": 6,
                   "hits": [hb((12, 14), 50, 30, 28, 13, 30, 34, 94, grp=1, fx="ground"),
                            hb((12, 14), -50, 30, 28, 13, 150, 34, 94, grp=1, fx="ground")]},
        "nair": {"frames": 34, "anim": "nair", "land": 8, "limb": "body", "hits": [hb((4, 14), 0, 0, 40, 8, 45, 30, 80, fx=N)]},
        "fair": {"frames": 36, "anim": "fair", "land": 10, "limb": "body", "hits": [arc((6, 10), 0, 0, 44, 110, -30, 22, 10, 40, 32, 90, fx=N)]},
        "bair": {"frames": 36, "anim": "bair", "land": 10, "limb": "body", "hits": [hb((7, 10), -46, 6, 26, 13, 145, 32, 100, fx=N)]},
        "uair": {"frames": 32, "anim": "uair_still", "land": 8, "limb": "body", "hits": [arc((5, 11), 0, -6, 40, 20, 160, 22, 9, 88, 32, 100, fx=N)]},
        "dair": {"frames": 40, "anim": "dair", "land": 12, "limb": "body", "hits": [hb((8, 12), 0, 40, 22, 12, 275, 30, 82, fx=N)]},
        # Siren Song: two vines sprout from the floor and whip anyone who comes near
        "nspec": {"frames": 50, "anim": "burp", "cooldown": 300, "proj": [(16, _vine(6)), (22, _vine(10))]},
        # Mermaid Rush: send one of her two mermaids to ram someone (they come back over time)
        "sspec": {"frames": 40, "anim": "throw_fwd", "mermaid": True,
                  "proj": [(12, {"kind": "mermaid", "vx": 8.5, "vy": 0, "wave": (6, 0.25), "r": 24, "dmg": 9, "ang": 45,
                                 "bkb": 40, "kbg": 72, "life": 80, "start_x": 34, "start_y": 0})]},
        # Water Spout: rides a geyser upward
        "uspec": {"frames": 50, "anim": "rise", "helpless": True, "ledge_ok": True, "drift": [(6, 24, None, -13)], "steer": 0.5,
                  "hits": [hb((6, 24), 0, 30, 30, 2, 90, 20, 0, rehit=4, grp=1, fx=N),
                           hb((25, 27), 0, -30, 34, 6, 88, 50, 70, grp=2, fx=N)]},
        # Tidal Slam: tail slam with waves rolling out both ways (charge for bigger waves)
        "dspec": {"frames": 56, "anim": "slam", "charge": 8, "charge_max": 60, "charge_mult": 0.5,
                  "hits": [hb((18, 20), 0, 24, 66, 12, 60, 45, 80, radial=True, fx="ground")],
                  "proj": [(19, _tide(9)), (19, _tide(-9))],
                  "proj_charged": [(19, _tide(10, 32, 8, 70)), (19, _tide(-10, 32, 8, 70))]},
    }
    m.update(common(40, 26))
    m.update(throws((10, 8, 40, 60, 70), (16, 10, 140, 60, 78), (12, 8, 90, 70, 72), (14, 7, 70, 50, 60)))
    return {"name": "Siren", "image": "siren", "color": (214, 120, 110), "w": 72, "h": h, "weight": 80,
            "run": 7.6, "walk": 4.0, "air": 6.2, "accel": 0.4, "grav": 0.6, "fall": 7.6, "ff": 12.0,
            "jump": 14.0, "hop": 9.6, "djump": 13.0, "jumps": 2, "moves": m,
            "air_desc": "floaty", "desc": "Zoner: vines, mermaids and tidal waves. Enraged at 100%+ (+10% damage)."}


NEW = (rakko, chikkabu, chikkabu_big, siren)
