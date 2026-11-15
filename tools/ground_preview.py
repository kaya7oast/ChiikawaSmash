"""All ground tilts / dash attacks / smashes mid-swing -> preview_ground_<char>.png  (python tools/ground_preview.py)"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contact_sheet as cs  # noqa: E402
import pygame  # noqa: E402
from smash import characters  # noqa: E402

MOVES = ["ftilt", "utilt", "dtilt", "dash", "fsmash", "usmash", "dsmash"]
orig = cs.frame_for


def late(move):
    hits = move.get("hits", [])
    if len(hits) > 1 and hits[-1]["f"][0] > hits[0]["f"][1]:     # multi-part moves: show the last part
        a, b = hits[-1]["f"]
        return (a + b) // 2 + 1
    return orig(move)


for ck in characters.ROSTER:
    thumbs = []
    for mv in MOVES:
        for fn in ((orig, late) if mv in ("dsmash", "fsmash", "dash") else (orig,)):
            cs.frame_for = fn
            th = cs.snap_move(ck, mv)
            if th is not None:
                thumbs.append(th)
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    out = pygame.Surface((cols * cs.TW, rows * cs.TH))
    for i, th in enumerate(thumbs):
        out.blit(th, ((i % cols) * cs.TW, (i // cols) * cs.TH))
    pygame.image.save(out, os.path.join(cs.ROOT, "preview_ground_%s.png" % ck))
    print("wrote", ck)
