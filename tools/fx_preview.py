"""Renders hit sparks in real matches -> preview_fx.png.  Run: python tools/fx_preview.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contact_sheet as cs  # noqa: E402
import pygame  # noqa: E402

SHOTS = [("chiikawa", "jab1", 2), ("usagi", "ftilt", 2), ("hachiware", "fsmash", 2), ("hachiware", "fsmash", 6),
         ("kurimanju", "fsmash", 3), ("momonga", "fair", 3), ("kani", "usmash", 3), ("usagi", "fsmash", 8)]
thumbs = []
for ck, mv, after in SHOTS:
    def ff(move, after=after):
        hits = move.get("hits", [])
        return (hits[0]["f"][0] + after) if hits else move["frames"] // 2
    cs.frame_for = ff
    th = cs.snap_move(ck, mv)
    if th is not None:
        thumbs.append(th)
cols = 4
rows = (len(thumbs) + cols - 1) // cols
out = pygame.Surface((cols * cs.TW, rows * cs.TH))
for i, th in enumerate(thumbs):
    out.blit(th, ((i % cols) * cs.TW, (i // cols) * cs.TH))
pygame.image.save(out, os.path.join(cs.ROOT, "preview_fx.png"))
print("wrote preview_fx.png")
