<p align="center">
  <img src="docs/banner.png" alt="SoulsOverlay showing deaths, PB and a NEW PB callout on Elden Ring's boss health bar">
</p>

**SoulsOverlay** counts your deaths and tracks your best attempt (PB) on every boss, all by
itself, and shows them in OBS right on the game's own health bar. Beat your best and the bar
lights up with **NEW PB**.

<p align="center">
  <img src="docs/new-pb.gif" alt="The NEW PB light running along a boss's health bar, with NEW PB 11% under it" width="800"><br>
  <sub>Beat your PB and the light runs along the boss's health bar. Pick a colour theme, or colour each part yourself, in the Overlay Editor.</sub>
</p>

## Souls Overlay

<img src="docs/window.png" alt="The SoulsOverlay window" width="380" align="right">

- **Start / Stop** the tracking.
- **Game:** Switches by itself to the game you're playing on Steam (Elden Ring, Dark Souls Remastered, II or III), with that game's characters.
- **Character:** Keep separate deaths and PBs for each in-game character. Switch, add or rename them at the top.
- **Settings** has the Overlay Editor for personalizing the overlay to your liking, save in browser and it auto-applies.
- **Calibrate** Shows where the program is drawing the games boss bar, if you play on an ultrawide screen or
  changed the HUD scale in Dark Souls Remastered. **Auto-find boss bar** does it for you from a
  frame with a boss at full health, or type in your HUD scale.
- **Updates:** Auto-update built in, checks against your checksum to make sure it's the correct file otherwise it fails.

<br clear="right">


## Get started

1. Download **SoulsOverlay.exe** from [Releases](../../releases/latest) and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, tick **Enable WebSocket server**, click
   **Show Connect Info** and copy the password.
3. Double-click **SoulsOverlay.exe**, then paste the password and the name of your game capture source.
4. Click **Copy** next to the OBS link, add it in OBS as a **Browser** source, and set it to your
   canvas size. Then right-click the new source and choose **Transform → Fit to screen**, so the
   overlay lines up with the game's health bar.

That's it. Fight a boss, and your deaths and PB appear under its health bar.

> **"Windows protected your PC"?** Click **More info**, then **Run anyway**. The exe isn't
> code-signed, which costs money. It's built by GitHub straight from this code.

## Supported games:

- **Elden Ring**
- **Dark Souls Remastered**
- **Dark Souls II: Scholar of the First Sin**, including the DLCs
  - ⚠️ It can't yet tell the **Twin Dragonriders** from the Heide's Tower **Dragonrider**, or the
    DLC's **blue Smelter Demon** from the Iron Keep one, because the game gives them the same name.
    Those fights share their deaths and PB.
- **Dark Souls III**

> **Playing on ultrawide?** The presets are tested on 16:9 screens (2560x1440, 1920x1080 and
> 1280x720). On other aspect ratios the boss bar sits somewhere else, so use **Calibrate** once.
> **Auto-find boss bar** does most of it for you.

## Hotkeys

| Keys | What it does |
|---|---|
| Ctrl+Alt+= | Add a death the counter missed |
| Ctrl+Alt+- | Remove the last death |
| Ctrl+Alt+R | Reset the current boss's deaths and PB |

## Something not working?

The window says what's wrong, for example when it can't reach OBS or can't see the game.
The log is in `data\soulsoverlay.log` next to the exe. For everything else, such as custom CSS,
game profiles, chat bot events and running from source, see the [advanced guide](docs/ADVANCED.md).

## Credits

- [cerkie](https://github.com/cerkie) - Created The Lab in the Overlay Editor.
