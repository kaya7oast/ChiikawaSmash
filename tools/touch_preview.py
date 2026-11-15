"""Renders the phone layout (touch controls) to preview_touch_*.png. Run: python tools/touch_preview.py"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["SMASH_TOUCH"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

pygame.init()
from smash.app import App, TitleScene, CharSelectScene, MatchScene  # noqa: E402
from smash.controls import TOUCH_BUTTONS  # noqa: E402


class E:
    def __init__(self, **k):
        self.__dict__.update(k)


def finger(t, x, y, fid):
    return E(type=t, x=x / 1280, y=y / 720, finger_id=fid)


def save(app, name):
    pygame.image.save(app.screen, os.path.join(ROOT, "preview_touch_%s.png" % name))


app = App()
app._frame_taps = []
sc = TitleScene(app)
app.scene = sc
for _ in range(30):
    sc.update()
sc.draw(app.screen)
save(app, "title")

sc = CharSelectScene(app)
app.scene = sc
sc.draw(app.screen)
app._frame_taps = [sc.portrait_rects[1].center]       # tap Hachiware
sc.update()
app._frame_taps = []
for _ in range(10):
    sc.update()
sc.draw(app.screen)
save(app, "select")
app._frame_taps = [sc.touch_buttons["fight"].center]
sc.update()
app._frame_taps = []
m = app.scene
print("scene after FIGHT:", type(m).__name__)
t = app.devices.touch
for i in range(60 * 9):
    if i == 300:
        t.handle_event(finger(pygame.FINGERDOWN, 220, 520, 1))
        t.handle_event(finger(pygame.FINGERMOTION, 285, 500, 1))
        bx, by = TOUCH_BUTTONS["atk"][:2]
        t.handle_event(finger(pygame.FINGERDOWN, bx, by, 2))
    if i == 330:
        t.handle_event(finger(pygame.FINGERUP, 0, 0, 1))
    app.dt_ms = 1000 / 60
    m.update()
    if i in (180, 315):
        m.draw(app.screen)
        save(app, "match_%d" % i)
t.handle_event(finger(pygame.FINGERUP, 0, 0, 2))
t.handle_event(finger(pygame.FINGERDOWN, 44, 44, 3))
m.update()
m.draw(app.screen)
save(app, "pause")
print("wrote touch previews")
pygame.quit()
