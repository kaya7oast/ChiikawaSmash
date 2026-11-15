"""Clean the cropped hands/feet: keep only the main outline stroke (the 'U' of the nub) and what's inside it."""
import numpy as np
from PIL import Image, ImageDraw
from collections import deque
from crop_parts import HANDS, FEET


def biggest_dark_component(dark):
    h, w = dark.shape
    seen = np.zeros_like(dark)
    best = []
    for y in range(h):
        for x in range(w):
            if dark[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = True; pts = []
                while q:
                    cy, cx = q.popleft(); pts.append((cx, cy))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and dark[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; q.append((ny, nx))
                if len(pts) > len(best):
                    best = pts
    return best


def hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def clean(name, kind, box, body_rgb):
    im = Image.open("cut_%s.png" % name).crop(box).convert("RGBA")
    a = np.array(im).astype(np.int32)
    rgb, al = a[:, :, :3], a[:, :, 3]
    dark = (al > 60) & (rgb.sum(axis=2) < 200)
    stroke = biggest_dark_component(dark)
    poly = hull(stroke)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon([(x + 0.5, y + 0.5) for x, y in poly], fill=255)
    m = np.array(mask) > 0
    for x, y in stroke:
        m[y, x] = True
    out = a.copy()
    out[~m, 3] = 0
    # inside the nub: anything that isn't outline becomes the character's body colour (removes Momonga's tail blue)
    inside = m & ~dark
    out[inside, 0], out[inside, 1], out[inside, 2] = body_rgb
    out[inside, 3] = 255
    res = Image.fromarray(out.astype(np.uint8))
    res = res.crop(res.getbbox())
    res.save("../assets/parts/%s_%s.png" % (kind, name))
    return res


BODY = {"chiikawa": (255, 255, 255), "hachiware": (255, 255, 255), "usagi": (253, 236, 200),
        "momonga": (255, 255, 255), "kurimanju": (252, 230, 200), "kani": (253, 236, 232)}

if __name__ == "__main__":
    # sample each body colour from the middle of the character to be exact
    for n in BODY:
        im = Image.open("cut_%s.png" % n).convert("RGBA")
        px = im.getpixel((im.width // 2 + 10, int(im.height * 0.72)))
        if px[3] > 200 and sum(px[:3]) > 500:
            BODY[n] = px[:3]
    for kind, boxes in (("hand", HANDS), ("foot", FEET)):
        for n, b in boxes.items():
            clean(n, kind, b, BODY[n])
    print("cleaned", BODY)
