"""Renders the special pose sprites in-game -> preview_poses.png.  Run: python tools/pose_preview.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contact_sheet as cs  # noqa: E402  (sets up a hidden pygame window)
import pygame  # noqa: E402

SHOTS = [("chiikawa", "bair", 10), ("chiikawa", "nair", 4), ("chiikawa", "nair", 10), ("chiikawa", "sspec", 12),
         ("hachiware", "sspec", 6), ("hachiware", "sspec", 10), ("hachiware", "sspec", 14), ("hachiware", "sspec", 18),
         ("momonga", "nspec", 12), ("momonga", "counter_hit", 10), ("kurimanju", "dspec", 16), ("kurimanju", "dspec", 44),
         ("kani", "dspec", 40)]
thumbs = []
for ck, mv, fr in SHOTS:
    cs.frame_for = lambda move, fr=fr: fr
    try:
        th = cs.snap_move(ck, mv)
    except Exception as e:      # some moves need a setup; show the error instead of crashing
        th = pygame.Surface((cs.TW, cs.TH)); th.fill((60, 30, 30))
        cs.text(th, "%s %s: %s" % (ck, mv, e), 14, (255, 255, 255), (8, 8), anchor="topleft")
    if th is not None:
        thumbs.append(th)
cols = 4
rows = (len(thumbs) + cols - 1) // cols
out = pygame.Surface((cols * cs.TW, rows * cs.TH))
for i, th in enumerate(thumbs):
    out.blit(th, ((i % cols) * cs.TW, (i // cols) * cs.TH))
pygame.image.save(out, os.path.join(cs.ROOT, "preview_poses.png"))
print("wrote preview_poses.png")
