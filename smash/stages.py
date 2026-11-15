"""Stage data (pure data, no pygame). y = 0 is the top of the main platform; y grows downward.
Stages are 1.8x wider than the first version. Blast zones keep about the same distance from the stage edges,
so edge KOs still happen around the same percents (centre-stage KOs need more)."""

SCALE = 1.8
EDGE_TO_BLAST = 880          # horizontal distance from a stage edge to the side blast zone


def _stage(name, half_w, depth, platforms, theme, top=-1100, bottom=800):
    hw = half_w * SCALE
    return {
        "name": name,
        "main": (-hw, 0, hw * 2, depth),
        # platforms: (centre_x, y, width) in old units -> scaled horizontally, heights kept reachable
        "platforms": [(cx * SCALE - w * SCALE / 2, y, w * SCALE) for cx, y, w in platforms],
        "blast": (-hw - EDGE_TO_BLAST, top, hw + EDGE_TO_BLAST, bottom),
        "spawns": [(-hw * 0.62, 0), (hw * 0.62, 0), (-hw * 0.24, 0), (hw * 0.24, 0)],
        "respawn_y": -440,
        "theme": theme,
    }


STAGES = {
    "battlefield": _stage("Picnic Hill", 470, 90, [(-220, -165, 220), (220, -165, 220), (0, -330, 220)], "day"),
    "final": _stage("Moonlit Pond", 560, 100, [], "night"),
    "village": _stage("Weed Field", 520, 90, [(-320, -150, 200), (320, -150, 200), (0, -270, 200)], "sunset"),
}
STAGE_ORDER = ["battlefield", "final", "village"]


ISLAND_EXTRA = 170   # the island hangs this far below the main platform's thickness


def main_poly(stage):
    """The solid island shape (same as what's drawn): flat top, sides that slope inward underneath."""
    x, y, w, h = stage["main"]
    x1 = x + w
    d = h + ISLAND_EXTRA
    return [(x, y), (x1, y), (x1 - 40, y + d * 0.55), (x1 - w * 0.3, y + d),
            (x + w * 0.3, y + d), (x + 40, y + d * 0.55)]


def ledges(stage):
    x, y, w, h = stage["main"]
    return [(x, y, 1), (x + w, y, -1)]  # (x, y, direction you face while hanging: toward the stage)
