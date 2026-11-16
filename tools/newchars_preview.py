"""Previews for the v5 characters -> preview_select.png, preview_<char>.png, preview_v5_match.png"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contact_sheet as cs  # noqa: E402
import pygame  # noqa: E402
from smash.sim import Game  # noqa: E402

cs.select_shot()
for ck in ("rakko", "chikkabu", "chikkabu_big", "siren"):
    cs.sheet(ck, False)

# one match frame showing the special visuals
g = Game([{"slot": 0, "char": "rakko", "name": "P1", "color": (235, 70, 70)},
          {"slot": 1, "char": "chikkabu", "name": "P2", "color": (70, 125, 235)},
          {"slot": 2, "char": "siren", "name": "P3", "color": (240, 190, 40)},
          {"slot": 3, "char": "chikkabu", "name": "P4", "color": (70, 185, 90)}], "battlefield", 3, seed=3)
g.countdown = 0
r, c1, s, c2 = g.fighters
r.x, c1.x, s.x, c2.x = -330, -120, 140, 330
for f in g.fighters:
    f.y, f.grounded, f.ground = 0, True, "main"
s.damage = 130
s.mermaids = 1
c1.bulk = 0.6
g.grow(c2)
r.facing = 1
r.start_move("sspec", g)
c1.latch_on, c1.latch_t = s, 150
c1.set_state("latched")
s.facing = -1
s.start_move("sspec", g)
for i in range(20):
    g.step({})
cs.R.stage_key = None
cs.R.draw(cs.screen, g.snapshot())
pygame.image.save(cs.screen, os.path.join(cs.ROOT, "preview_v5_match.png"))
print("wrote previews")
