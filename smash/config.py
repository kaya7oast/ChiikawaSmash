"""Global settings. Everything gameplay-related is in frames at 60 fps and world pixels (y points DOWN)."""
import os
import sys

WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "Chiikawa Smash"

# Running in a browser (pygbag / WebAssembly)? Then there's no LAN play and we show touch controls.
IS_WEB = sys.platform == "emscripten"
# Touch UI: on in the browser; on desktop you can force it with  set SMASH_TOUCH=1  to try the phone layout.
TOUCH_UI = IS_WEB or os.environ.get("SMASH_TOUCH") == "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets")
SAVE_FILE = os.path.join(ROOT, "settings.json")

NET_PORT = 5055
MAX_PLAYERS = 4
DEFAULT_STOCKS = 3

# Player colours (P1 red, P2 blue, P3 yellow, P4 green - like Smash)
SLOT_COLORS = [(235, 70, 70), (70, 125, 235), (240, 190, 40), (70, 185, 90)]
SLOT_NAMES = ["P1", "P2", "P3", "P4"]
CPU_COLOR = (150, 150, 160)

WHITE = (255, 255, 255)
BLACK = (25, 25, 30)
INK = (60, 40, 35)          # the brown outline colour used by the Chiikawa art
CREAM = (255, 248, 235)
