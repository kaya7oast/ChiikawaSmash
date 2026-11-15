"""Cut each wiki character card down to just the character (drops the name + pronunciation text)."""
import sys
import numpy as np
from PIL import Image
from collections import deque

NAMES = ["chiikawa", "hachiware", "usagi", "momonga", "kurimanju", "kani"]


def components(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    comps = []
    n = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n += 1
                q = deque([(y, x)])
                lab[y, x] = n
                ys, xs = [], []
                while q:
                    cy, cx = q.popleft()
                    ys.append(cy); xs.append(cx)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                                lab[ny, nx] = n
                                q.append((ny, nx))
                comps.append((n, len(ys), min(ys), max(ys), min(xs), max(xs)))
    return lab, comps


for name in NAMES:
    im = Image.open(name + ".webp").convert("RGBA")
    a = np.array(im)
    mask = a[:, :, 3] > 20
    lab, comps = components(mask)
    big = max(comps, key=lambda c: c[1])
    _, _, y0, y1, x0, x1 = big
    keep = np.zeros_like(mask)
    for n, size, cy0, cy1, cx0, cx1 in comps:
        # keep pieces that sit inside the character's box (fur strokes, eyes, tail...), drop text above/below
        if cy0 >= y0 - 4 and cy1 <= y1 + 4 and cx0 >= x0 - 60 and cx1 <= x1 + 60:
            keep |= lab == n
    a[~keep, 3] = 0
    out = Image.fromarray(a)
    out = out.crop(out.getbbox())
    out.save("cut_" + name + ".png")
    print(name, out.size)
