<p align="center">
  <img src="docs/banner.png" alt="SoulsOverlay showing deaths, PB and a New PB callout on Elden Ring's boss health bar">
</p>

SoulsOverlay is a death counter and boss PB tracker for OBS. It shows your deaths and your best
attempt on the boss you're fighting, right under the game's boss health bar.

<p align="center">
  <img src="docs/new-pb.gif" alt="The New PB light running along a boss's health bar, with New PB 11% under it" width="800"><br>
  <sub>The New PB effect. Colours and effects can be changed in the Overlay Editor.</sub>
</p>

## What it does

SoulsOverlay gets the game picture from OBS and reads it the same way you would: it sees the boss
name, the boss health bar and the You Died screen. From that it counts your deaths per boss and
remembers how low you got each boss's health. That's your PB. When you beat it, the overlay
shows New PB, and the first time you kill a boss it shows Defeated.

Bosses with more than one phase, and fights with two bosses like Ornstein and Smough, count as one
fight. Deaths and PBs are saved per character, so starting a new run doesn't wipe the old one.

It never touches the game itself. No mods, no memory reading, nothing injected.

## Souls Overlay

<img src="docs/window.png" alt="The SoulsOverlay window" width="380" align="right">

- **Start / Stop:** turns tracking on and off.
- **Game:** pick the game at the top. If you start a different game on Steam, SoulsOverlay
  switches to it, along with that game's characters. You can turn this off in Settings.
- **Character:** each character has its own deaths and PBs. Switch, add or rename them at the top.
- **Settings:** the Overlay Editor, where you change how the overlay looks. Save it in the browser
  and the overlay in OBS updates. Hotkeys and the auto-switch option are here too.
- **Calibrate:** if you play on an ultrawide screen, or changed the HUD scale in Dark Souls
  Remastered, use this to mark where the game draws the boss bar. **Auto-find boss bar** does it
  from a screenshot with a boss at full health, or you can type in your HUD scale.
- **Updates:** when there's a new version, the window offers to install it. The download is
  checked against the checksum published with the release, and the update stops if it doesn't
  match. Your settings and stats are kept.

<br clear="right">

## Get started

1. Download **SoulsOverlay.exe** from [Releases](../../releases/latest) and put it in its own folder.
2. In OBS, open **Tools → WebSocket Server Settings**, tick **Enable WebSocket server**, click
   **Show Connect Info** and copy the password.
3. Run **SoulsOverlay.exe**, then enter the password and the name of your game capture source.
4. Click **Copy** next to the overlay link and add it in OBS as a **Browser** source at your
   canvas size. Right-click the source and choose **Transform → Fit to screen** so the overlay
   lines up with the boss bar.

Your deaths and PB show up the next time a boss health bar is on screen.

> **"Windows protected your PC"?** Click **More info**, then **Run anyway**. The exe isn't
> code-signed (that costs money), but it's built by GitHub from the code in this repository.

## Supported games

- **Start / Stop** the tracking.
- **Game:** Switches by itself to the game you're playing on Steam (Elden Ring, Dark Souls Remastered, II or III), with that game's characters.
- **Character:** Keep separate deaths and PBs for each in-game character. Switch, add or rename them at the top.
- **Settings** has the Overlay Editor for personalizing the overlay to your liking, save in browser and it auto-applies.
- **Calibrate** Shows where the program is drawing the games boss bar, if you play on an ultrawide screen or
  changed the HUD scale in Dark Souls Remastered. **Auto-find boss bar** does it for you from a
  frame with a boss at full health, or type in your HUD scale.
- **Updates:** Auto-update built in, checks against your checksum to make sure it's the correct file otherwise it fails.

<br clear="right">

> **Ultrawide?** The presets are tested at 16:9 (2560x1440, 1920x1080 and 1280x720). On other
> aspect ratios the boss bar is in a different place, so run **Calibrate** once.

## Hotkeys

| Keys | What it does |
|---|---|
| Ctrl+Alt+= | Add a death the counter missed |
| Ctrl+Alt+- | Remove the last death |
| Ctrl+Alt+R | Reset the current boss's deaths and PB |

## Something not working?

The window tells you what's wrong, for example when it can't reach OBS or can't see the game.
There's a log at `data\soulsoverlay.log` next to the exe. Custom CSS, game profiles, chat bot
events and running from source are covered in the [advanced guide](docs/ADVANCED.md).

## Credits

- [cerkie](https://github.com/cerkie) - Created The Lab in the Overlay Editor.
