# Chiikawa Smash

A small Smash Bros-style platform fighter in pygame, for up to 4 players: local, vs CPU, or over your Wi-Fi.

## Run
```
pip install pygame
python main.py
```
or double-click `play.bat`.

## Playing with friends on the same Wi-Fi
1. Everyone copies this folder to their PC.
2. One person picks **Host LAN Game**. Their IP appears at the top of the screen (e.g. `192.168.1.23`).
3. Friends pick **Join LAN Game**. The host should appear in the list; if it doesn't, type the IP and press Enter.
4. Everyone picks a character (A/D to browse, click / A = ready). The host can add CPUs (C), change the stage (Tab) and
   stocks (-/+), then presses **Enter** to fight.

Windows Firewall will ask about Python the first time you host. Tick **Private networks** and allow it.
If your Wi-Fi is set to **Public**, either tick Public too or change that network to Private
(Settings > Network > Wi-Fi > your network). Friends at other houses can use Tailscale / ZeroTier /
Radmin VPN and join using the IP that app gives the host.

How it works: the host runs the game. Friends only send button presses (UDP port 5055) and get back a
~400-byte snapshot 60 times a second, so it's quick on home Wi-Fi.

## Controls
| | Keyboard + Mouse | Keyboard 2 | Gamepad |
|---|---|---|---|
| Move | A / D (S = down) | Arrows | Left stick / D-pad |
| Jump (hold = full hop) | W | Num0 / R-Shift | X / Y |
| Attack | Left click (or J) | Num1 / . | A |
| Special | Right click (or K) | Num2 / / | B |
| Shield | Left Shift (or L) | Num3 / R-Ctrl | RB / RT / LT |
| Grab | Space (or U) | Num4 / ; | LB |
| Smash attack (hold = charge) | E / middle click (or A/D + click together) | Num5 / ' | Right stick |

- W is both up and jump. **W + click at the same time = up-tilt**, W + right-click = up-B, no jump wasted
  (in the air too: tap W and click right away = up-air, and you keep your double jump).
- Shift + A/D = roll, Shift + S = spot dodge, Shift in the air = air dodge (aim it with a direction).
- Jab: click, click, then **hold click** for a rapid jab (Chiikawa, Usagi, Momonga) or a 3rd hit (others).
- **Jump height depends on how long you hold W**: a light tap = short hop, hold = full jump.
- Hold S at the top of a jump / while falling to **fast-fall**. Tap S on a platform to drop through.
- Getting launched: you can air dodge out of tumble after ~0.5s, or attack/jump out after ~0.65s.
- Repeating the same move weakens it (stale moves, like Smash) - mix it up.
- `tools/make_previews.bat` renders preview_*.png screenshots of every move (no window needed).
- Grab, then A/D/W/S to throw (click = pummel). Mash to escape grabs.
- Ledges are grabbed automatically. From the ledge: jump, climb (toward/up), attack, roll (shield) or let go (down).
- Press shield just before landing while tumbling to **tech**.
- **F2 = show hitboxes** (yellow hurtbox, red hitbox, pink sweetspot, purple grab, cyan reflector/projectiles).
- F11 = fullscreen, F3 = FPS, Esc twice = leave a match.

## Roster
Weapon moves have a **sweetspot at the tip** (sparkles when active).

| | Air feel | Neutral B | Side B | Up B | Down B |
|---|---|---|---|---|---|
| Chiikawa | a bit floaty | Weed pull (hold to charge) | Weeding Onslaught - dash punch, on hit a 10-hit barrage (shields block it) | **Pochette Parachute** - bounce up, float down under her pink bag (can still attack) | **Crying Fountain** - hold to cry harder, tears burst both ways |
| Hachiware | standard | **Personality Arts** (Monado) - each press: green JUMP, blue SPEED, yellow SHIELD, red SMASH, off | **Tail Tornado** (Ken's tatsu, spins on his tail) | **Shoryuken** - invincible start, strong first hit | **Reflector** - hold forever (Fox), 1% to anyone too close |
| Usagi | huge jumps, fast faller | Seed spit (hold) | Crazy rush (B again: YAHA!) | **YAHA Warp** - hold a direction, teleport ~240px (Mewtwo) | Snack (heal, armored) |
| Momonga | 3 jumps, hold jump to glide | **Kani Guard** - counter, Kani snips back (Peach's Toad) | Nibble Leap - ride their head, nibble, kick off | Glide | Dekatsuyo charges across |
| Kurimanju | heavy, falls fast | Burp (hold) | Bottle lob (puddle) | Beer geyser | Drink up (+35% next hit) |
| Kani | 3 crab hops, fast sideways | Book toss | **Pound Snip** - quick snip that wrecks shields | **Claw Tether** - reels onto ledges OR yanks an enemy in and kicks them up | **Bedtime Reading** - puts nearby grounded enemies to sleep (Sing) |

Chiikawa's nair is a panic flail, her up-air swings a weed. Momonga's **down-air drops Dekatsuyo like an anvil** (meteors anyone below).

## Recovering
- The island's slanted underside is a real slope: jumping into it slides you along it instead of stopping you.
- Ledges grab automatically from just above your head down to your feet, including during up-Bs.
- Kani's tether auto-aims at a ledge in front of him within reach.

## Code map
- `smash/sim.py` – the whole fight simulation, no pygame (physics, states, hits, knockback, shields, grabs, ledges, KOs)
- `smash/characters.py` – stats and move data (frame data, hitboxes, specials). Tweak balance here.
- `smash/stages.py` – stage layouts
- `smash/render.py` – drawing (camera, animated character pictures, effects, HUD)
- `smash/net.py` – LAN host/join (UDP)
- `smash/bot.py` – CPU players
- `smash/controls.py` – keyboard/gamepad mapping
- `smash/app.py` – menus, lobby, match loop, results

Knockback uses the real Smash Ultimate formula, so move numbers (damage / base KB / KB growth / angle)
behave like Smash frame data.

## Art
- `assets/parts/hand_*.png`, `foot_*.png` are each character's own hands/feet, cropped from their character
  art on the Chiikawa wiki (`art_src/` has the source cards + the scripts: `cutout.py` removes the name text,
  `crop_parts.py` holds the crop boxes, `clean_parts.py` keeps only the nub + its outline). The game rotates them
  along the arm/leg for punches, kicks, grabs and holding weapons.
- `assets/hachiware.png` is now the full-body Hachiware (old floating head kept in `assets/old/`).
- `assets/full/` has full-body versions of everyone from the same wiki set - copy one over `assets/<name>.png`
  if you prefer it.

## Play on your phone (browser version)

The game also runs in a phone browser, with touch controls and battles against CPUs. LAN play isn't available there because browsers can't do it.

1. On github.com, create a **new empty repo** called `ChiikawaSmash` (don't add a README).
2. Double-click `connect_github.bat` to upload this folder.
3. On GitHub, open the repo's **Settings → Pages** and set **Source** to **GitHub Actions**.
4. About 3 minutes later the game is live at **https://kaya7oast.github.io/ChiikawaSmash/**. The first load takes a while.

To publish changes later, run `push_update.bat`.

Playing on the phone:
- Turn the phone sideways.
- Drag anywhere on the left half to move.
- Use the buttons on the right to attack, special, jump, shield, grab and smash.
- The **||** button in the top-left pauses the game.
- On iPhone, "Add to Home Screen" makes it open full screen.

To try the phone layout on your PC, run `play_touch_layout.bat`. The mouse acts as a single finger.
