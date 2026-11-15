"""Renders preview images of every character's moves (no window needed).
Run from the game folder:  python tools/contact_sheet.py      -> writes preview_*.png into the game folder."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from smash import characters  # noqa: E402
from smash.render import Renderer, text  # noqa: E402
from smash.sim import Game  # noqa: E402
from smash.bot import Bot  # noqa: E402

R = Renderer()
TW, TH = 426, 240                     # thumbnail size (3 per row)
MOVES = ["jab1", "jab_rapid", "ftilt", "utilt", "dtilt", "fsmash", "usmash", "dsmash", "nair", "fair", "bair",
         "uair", "dair", "grab", "fthrow", "nspec", "sspec", "uspec", "dspec"]


def frame_for(move):
    hits = move.get("hits", [])
    if hits:
        a, b = hits[0]["f"]
        return (a + b) // 2 + 1
    if move.get("grabbox"):
        return move["grabbox"][0][1]
    if move.get("throw"):
        return move["throw"][0] - 1
    if move.get("proj"):
        return move["proj"][0][0] + 6
    return move["frames"] // 2


def snap_move(ck, mv):
    g = Game([{"slot": 0, "char": ck, "name": "P1", "color": (235, 70, 70)},
              {"slot": 1, "char": "kurimanju", "name": "CPU", "color": (70, 125, 235), "cpu": True}], "battlefield", 3)
    g.countdown = 0
    f, t = g.fighters
    f.x, t.x = -40, 60
    f.facing, t.facing = 1, -1
    t.damage = 40
    air = mv in ("nair", "fair", "bair", "uair", "dair") or mv == "uspec"
    if air:
        for x in (f, t):
            x.grounded, x.ground, x.state, x.y = False, None, "air", -160
    m = f.moves.get(mv)
    if m is None:
        return None
    if mv in ("fthrow", "pummel"):
        f.start_move("grab", g)
        for _ in range(10):
            g.step({})
        if f.state != "holding":
            return None
    f.start_move(mv, g)
    target = frame_for(m)
    for _ in range(400):
        if f.state != "attack" or f.mf >= target:
            break
        g.step({})
        for x in (f, t):
            if air:
                x.vy = 0
                x.y = -160 if x is t else x.y
    R.stage_key = None
    R.draw(screen, g.snapshot(), local_slots=(0,))
    # zoom the thumbnail onto the attacker
    cx, cy = R.cam.pt(f.x + 20 * f.facing, f.y - f.h / 2)
    area = pygame.Rect(0, 0, 640, 360)
    area.center = (int(cx), int(cy))
    area.clamp_ip(screen.get_rect())
    thumb = pygame.transform.smoothscale(screen.subsurface(area).copy(), (TW, TH))
    text(thumb, "%s  %s  (frame %d)" % (characters.CHARACTERS[ck]["name"], mv, f.mf), 18, (255, 255, 255), (8, 6),
         anchor="topleft", outline=(20, 20, 20))
    return thumb


def sheet(ck, debug):
    R.debug = debug
    thumbs = [s for s in (snap_move(ck, mv) for mv in MOVES) if s is not None]
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    out = pygame.Surface((cols * TW, rows * TH))
    for i, th in enumerate(thumbs):
        out.blit(th, ((i % cols) * TW, (i // cols) * TH))
    name = os.path.join(ROOT, "preview_%s%s.png" % (ck, "_hitboxes" if debug else ""))
    pygame.image.save(out, name)
    print("wrote", name)


def match_shot():
    R.debug = False
    chars = characters.ROSTER[:4]
    g = Game([{"slot": i, "char": c, "name": "P%d" % (i + 1), "color": col, "cpu": True}
              for i, (c, col) in enumerate(zip(chars, [(235, 70, 70), (70, 125, 235), (240, 190, 40), (70, 185, 90)]))],
             "battlefield", 3, seed=2)
    bots = [Bot(i, 3) for i in range(4)]
    R.stage_key = None
    for i in range(60 * 25):
        g.step({b.slot: b.update(g) for b in bots})
        R.draw(screen, g.snapshot())
        if i in (60 * 8, 60 * 16, 60 * 24):
            pygame.image.save(screen, os.path.join(ROOT, "preview_match_%d.png" % (i // 60)))
    print("wrote match previews")


def select_shot():
    from smash.app import App, CharSelectScene
    app = App()
    sc = CharSelectScene(app, hosting=False)
    app.scene = sc
    app.devices.kb1.menu_presses.append("ok")
    sc.update()
    sc.add_cpu()
    for _ in range(20):
        sc.update()
    sc.draw(app.screen)
    pygame.image.save(app.screen, os.path.join(ROOT, "preview_select.png"))
    print("wrote select preview")


if __name__ == "__main__":
    select_shot()
    for ck in characters.ROSTER:
        sheet(ck, False)
    sheet("hachiware", True)
    match_shot()
    pygame.quit()
