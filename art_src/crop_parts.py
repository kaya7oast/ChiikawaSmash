"""Crop each character's own right hand + right foot out of their wiki art (boxes are in cut_<name>.png pixels)."""
from PIL import Image
HANDS = {"chiikawa": (209, 181, 238, 213), "hachiware": (200, 188, 232, 218), "usagi": (183, 228, 213, 262),
         "momonga": (200, 220, 232, 245), "kurimanju": (207, 186, 238, 214), "kani": (200, 214, 228, 244)}
FEET = {"chiikawa": (148, 252, 172, 279), "hachiware": (140, 262, 166, 287), "usagi": (126, 296, 155, 319),
        "momonga": (136, 276, 166, 303), "kurimanju": (138, 258, 166, 282), "kani": (140, 284, 168, 308)}
if __name__ == "__main__":
    import os
    os.makedirs("../assets/parts", exist_ok=True)
    for kind, boxes in (("hand", HANDS), ("foot", FEET)):
        for n, b in boxes.items():
            im = Image.open("cut_%s.png" % n).crop(b)
            im.save("../assets/parts/%s_%s.png" % (kind, n))
    print("saved")
