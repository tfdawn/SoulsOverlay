# SoulsOverlay: advanced guide

Everything the [README](../README.md) leaves out: calibration, the HUD's options, custom CSS, game
profiles, events for chat bots, running from source and development.

## Downloading and updating

**"Windows protected your PC"?** The exe isn't code-signed, so Windows warns about it the first
time. Click **More info**, then **Run anyway**. Only download it from this repository's Releases
page. Each release lists the exe's SHA-256 checksum in `SHA256SUMS.txt`, and you can check it with
`certutil -hashfile SoulsOverlay.exe SHA256`. The exe is built by GitHub Actions straight from this
code ([.github/workflows/release.yml](../.github/workflows/release.yml)).

**Updating:** when a new version is out, the SoulsOverlay window says so when it starts (or
click **Check for updates** at the bottom). Click **Update…** and confirm: it downloads the new
exe from this repository's Releases page, checks it against the release's SHA-256 checksum,
swaps it in and restarts. Your `config.toml`, `data` and calibrated profiles are kept. Nothing
is downloaded until you confirm, and `check_updates = false` in `config.toml` turns the check
off. Afterwards, refresh the Browser Source in OBS. You can also update by hand: download the
new `SoulsOverlay.exe` over the old one.

## Running from source (Python)

1. Install **Python 3.11+** from python.org (tick "Add to PATH").
2. Install **Tesseract OCR** using the UB Mannheim build (https://github.com/UB-Mannheim/tesseract/wiki).
   The default install path is found automatically.
3. In this folder, run:
   ```
   py -m pip install -e ".[hotkeys,launcher]"
   copy config.example.toml config.toml
   ```
4. Copy the OBS WebSocket password into `config.toml` under `[obs]`, and set `source` to the
   exact name of your game capture source.
5. Start it with `py -m soulsoverlay launcher` for the window, or `py -m soulsoverlay run` to
   keep it in the terminal. (pip may warn that its Scripts folder isn't on PATH.
   That's harmless: every command in this README also works as `py -m soulsoverlay ...`.)

To build the exe yourself: `pip install pyinstaller`, put a Tesseract install in
`build\tesseract`, and run `pyinstaller packaging/soulsoverlay.spec`.

Coming from Death Counter (0.3.28 or older)? The app is now called SoulsOverlay. Copy your
`config.toml` and `data` folder next to `SoulsOverlay.exe` (or into the new source folder); your
deaths and PBs carry over on the first start. If you installed the old version with pip, run
`py -m pip uninstall deathcounter`.

## Calibrate once per game

The Elden Ring, Dark Souls Remastered and Dark Souls II presets have been calibrated against
real screenshots and come with a death template, so on a 16:9 screen they should work as they are.
The Dark Souls III preset is a work in progress (marked WiP in the game list) and still uses
*estimated* regions. Check it, and the others if you play ultrawide, before you rely on it.

Dark Souls Remastered lets you change the HUD scale, which moves the boss bar. Its preset
matches a HUD scale of 0.80. For any other value, open the calibration page, type your HUD
scale under **HUD scale**, click **Apply**, then **Save profile**.

**Auto-find boss bar** places the boss boxes for you on any game: get a frame with a boss at
full health (or just after its first hit), click it, check the boxes, and save. It finds the
bar and moves the name box and the second boss slot along with it.

To calibrate by hand:

1. With SoulsOverlay running, click **Calibrate** in its window (or run `soulsoverlay calibrate`
   in a second terminal).
   This opens the calibration page in your browser.
2. Get a frame. Either fight a boss and click **Grab frame from OBS**, or **Load screenshot**
   from a file. Live detection pauses while you calibrate.
3. Pick a region on the right and drag a box on the frame:
   * **Boss 1 health bar:** only the inside of the bar, with no border or ornaments. Use the
     arrow keys to nudge the box and Shift+arrows to resize it. The zoom panel shows both
     ends of the bar.
   * **Boss 1 name:** the text above the bar. Make it wide enough for the longest name.
   * **Death text:** a generous box around "YOU DIED".
   * **Boss 2:** only for fights with two bars, such as Ornstein and Smough.
4. Click **Save profile**, then **Test detection** to see the health %, the OCR text and the
   matched boss.
5. Load a screenshot with "YOU DIED" fully faded in, then click **Capture death template**.
   Template matching is much more reliable than the colour heuristic used until then.
6. Click **Resume live capture**.

Grabbing a frame from the calibration page means alt-tabbing out of the game, and Game Capture
goes black while the game isn't in front. To get a frame mid-fight, press **Ctrl+Alt+S** in the
game instead: the frame is saved to `data/snapshots` and the terminal prints what the counter
detects in it. On the calibration page, use **Load screenshot** to open that file.

To check a set of screenshots without OBS, run
`soulsoverlay analyze shot1.png shot2.png --game elden_ring`.

## Manual controls

| Hotkey (default)  | Command                          | What it does                                       |
|-------------------|----------------------------------|----------------------------------------------------|
| Ctrl+Alt+=        | `soulsoverlay ctl death_add`     | +1 death on the current boss                       |
| Ctrl+Alt+-        | `soulsoverlay ctl death_undo`    | removes the last death                             |
| Ctrl+Alt+R        | `soulsoverlay ctl boss_reset`    | clears the current boss's deaths and PB            |
| Ctrl+Alt+C        | `soulsoverlay ctl boss_clear`    | clears the manual boss                             |
| Ctrl+Alt+S        | `soulsoverlay ctl snapshot`      | saves the current frame to `data/snapshots` and prints what it detects |
|                   | `soulsoverlay ctl boss_set Name` | sets the boss manually (fuzzy-matched to the list) |
|                   | `soulsoverlay ctl game_set dark_souls_3` | switches game                              |

Hotkeys need `pynput`. If you'd rather not run a global key listener, set
`hotkeys.enabled = false` and bind the `ctl` commands to Stream Deck buttons instead.
Nothing is ever really deleted: undo and reset mark rows as voided in the database.

`soulsoverlay stats` prints deaths and PBs per boss.

## The HUD: on the game's own boss bar

The counter draws straight onto the game's boss bar. It adds a
gold PB marker on the bar, puts deaths and PB under it, and shows NEW PB and DEFEATED callouts.
It appears while a boss bar is on screen and fades out a few seconds after the fight ends.

1. Add a **Browser Source** with the URL `http://127.0.0.1:8765/overlay/hud`.
2. Set its width and height to your OBS canvas size (Settings → Video → Base Resolution, for
   example 2560 × 1440). Delete the default custom CSS.
3. Make it cover the whole canvas, exactly like your game capture: right-click it, then
   Transform → Fit to screen.

It uses the bar position from the game profile, so it lines up as long as your game fills the
canvas.

NEW PB fires live, on the bar: as soon as the boss's health drops below your PB (or you reach a
later phase), the bar shines, NEW PB shows, and the marker follows the health down for the rest
of the attempt. It doesn't wait for the death, because Elden Ring hides the boss bar before
"YOU DIED" appears. The PB is still only saved when the attempt ends.

Options: `?always=1` keeps it visible between fights, `?hide=deaths,pb,phase,mark` hides
parts, `?banner=0` turns off the callouts, and `?demo=pb`, `?demo=live` or `?demo=first` (a first attempt, no PB yet) previews it. In `data/overlay.css`,
`--size` sets the text size and `--linger` sets how long the text stays after the game hides its boss bar, and `--death-hold` how long it stays to show a new death (both 0s: the counter spots YOU DIED while the bar is still up, so the HUD leaves with the bar). The PB marker always leaves with the bar.

## Changing the look (settings page)

With SoulsOverlay running, click **Settings** in its window. From source, open a second terminal and run:

```
py -m soulsoverlay settings
```

This opens the settings page in your browser. It has two tabs: **Simplified** and
**The Lab**. As you change things, two previews play the same moment side by side: **Default**
and **Your look**. Use the buttons above them to replay NEW PB, a death, DEFEATED or a first
attempt, and switch between a close-up of the bar and the full screen. **Slow-mo** plays the
previews at down to 0.05× speed so you can see exactly what a change does; it's never saved
and never affects OBS.

The **Simplified** tab has the everyday choices for the boss bar HUD: ready-made colour themes
(Default, Ice, Crimson, Emerald, Violet, Pink and White), the font, text size, outline and text colours,
the NEW PB colours, the words on screen ("Deaths", "PB", "NEW PB", "DEFEATED"), which parts show,
the space under the bar, how long the HUD stays, and the preview background (**Scene**).

* **Save** writes your changes to `data/style.json`. The HUD in OBS updates straight away,
  no refresh needed. Only the settings you changed are stored; the default look is never edited.
* The **↺** next to a setting puts that one back to its default. **Reset all**, then **Save**,
  goes back to the default look. So does deleting `data/style.json`.
* **The Lab** is for advanced users who want to build the NEW PB effect itself. It's the HP Bar
  Lab: a bar to play the effect on with a timeline to scrub, a speed slider, Undo/Redo
  (Ctrl+Z / Ctrl+Y), effect presets (save your own, or **Randomize**), then every setting as
  panels you can fold up: fill direction, speed curve, flash, lens streak, glow, fill light,
  landing flash, sheen, shockwaves, sparks, grain and shake. This is the effect that plays in game
  for NEW PB. Colours stay on the Simplified tab. Last is the settings
  JSON: its **Import .json file** and **Save .json file** use the lab's own files.
  Screen shake moves only the HUD's text and light, not the game's own bar.
* **Export** downloads your settings as a file; **Import** loads one. That's how to share a look
  with someone else, or keep a backup.

Like the calibration page, the address it opens holds your control token, so keep it off stream.
The HUD only reads the settings; changing them needs the token.

## Styling the HUD with CSS

For anything the settings page doesn't cover, create `data/overlay.css`. It is loaded after the
default theme and the settings page's choices, so it wins over both. For example:

```css
:root { --font: "Bebas Neue", sans-serif; --accent: #7fd1ff; }
```

## Game profiles

Profiles are JSON files in `profiles/`. The boss list is where most of the tuning happens:

```json
{"name": "Malenia, Blade of Miquella", "phase_names": {"Malenia, Goddess of Rot": 2}, "phases": 2}
{"name": "Ornstein and Smough", "aliases": ["Dragon Slayer Ornstein", "Executioner Smough"], "bars": 2, "phases": 2}
{"name": "Margit, the Fell Omen", "aliases": ["Margit"]}
```

* `aliases` are other names that mean the same fight.
* `phase_names` are names that only appear in a later phase.
* `phases` tells the tracker that a bar emptying at the end of phase 1 isn't a kill.
* `bars: 2` averages both bars in phase 1, then tracks the survivor in phase 2.
* `bars` without `phases` (Dark Souls II's Ruin Sentinels, `bars: 3`) keeps one average for the
  whole fight: a bar that hasn't appeared yet counts as full, and a fallen one as empty.

For other games, start from `profiles/generic.json`. It has
`tracking.accept_unlisted = true`, so any stable OCR'd name is used even if it isn't in the
boss list. Bar and death colours can be tuned under `bar_colors` and `death.heuristic` (OpenCV
HSV ranges). An optional `bar_colors.empty` colour (the drained part of the bar) stops scenery
next to an unused boss slot reading as a sliver of bar, and `ocr.prefix_match` matches only the
start of the name strip, for games whose names sit on bright, busy floors.

## Events and the chat bot hook

Every state change is published on an internal event bus: `death`, `death_undone`, `new_pb`,
`defeated`, `defeated_cancel`, `kill`, `boss_engaged`, `boss_changed`, `boss_reset`, `phase` and
`game_changed`. `defeated` fires the moment a boss's bar hits 0%; `kill` follows once its bar and
name have left the screen, or `defeated_cancel` if YOU DIED came first (a sliver was left). A plugin is
a Python module with `setup(bus, store, config)`, listed under `plugins` in `config.toml`.
`examples/webhook_forwarder.py` forwards events to a bot on a VPS as outbound, HMAC-signed
HTTPS requests, so nothing on your PC has to be reachable from the internet.

## Security

* The server only listens on 127.0.0.1 and refuses to start on any other address.
* Requests must name 127.0.0.1 or localhost in the Host header, which blocks DNS rebinding.
* The HUD URL is read-only and contains no secrets, so it's safe if it shows on stream.
* Everything that changes data or exposes frames needs the control token from
  `data/control_token` in an `Authorization` header. Browser requests also need an allowed
  `Origin`, and JSON POSTs need the JSON content type. No CORS headers are ever sent.
* The calibration page gets the token through the URL fragment, which browsers never send to
  a server. The page then removes it from the address bar.

## Troubleshooting

* **The overlay never shows a boss, or the frames are black.** Check that `obs.source` in
  `config.toml` exactly matches the name of the game source in OBS's Sources list. If you rename
  it in OBS, rename it in `config.toml` too. With the game in front, press Ctrl+Alt+S: the
  terminal prints what the counter sees.
* **The counter can't connect to OBS.** The WebSocket password in `config.toml` must match OBS
  (Tools → WebSocket Server Settings → Show Connect Info).

## Known limits

* Elden Ring is checked against real screenshots (full health, a fresh damage trail, about 20%
  health, and the death screen) at 2560, 1920 and 1280 wide, and so are Dark Souls Remastered
  and Dark Souls II. The Dark Souls III preset hasn't been checked against real screenshots yet.
* In Dark Souls II, both Twin Dragonriders bars are labelled "Dragonrider", and the DLC's blue
  Smelter Demon is labelled "Smelter Demon", so those fights count as the Dragonrider and the
  Smelter Demon. Use `boss_set` to keep them apart.
* The Elden Ring preset has one boss slot. Two-bar fights need a second slot, added on the
  calibration page.
* OCR depends on Tesseract and a reasonably clean name strip. If a name won't read, use
  `boss_set` to set the boss manually.
* Bosses whose health carries over between phases without the bar refilling or the name
  changing (for example, Radahn in the DLC) are tracked as one phase.

## Development

```
pip install -e .[dev]
pytest
```

The tests build synthetic souls-style frames (`tests/synth.py`) and cover the bar reader,
death detection (heuristic and template, across resolutions), OCR and fuzzy matching, the
tracker (attribution, phases, duos, kills), storage and PBs, the server's security checks,
and an end-to-end run through the capture loop.
