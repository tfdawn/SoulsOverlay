## What's new in 1.0.2

- **Dark Souls Remastered is supported.** Deaths, boss names and boss health are now set up from real
  game footage, so it's no longer marked as a work in progress. The preset matches an in-game HUD scale
  of 0.80. If yours is different, open **Calibrate** and type your HUD scale in, or use **Auto-find boss bar**.
- **Auto-find boss bar** on the Calibrate page finds the boss bar on a frame and places the boss boxes
  for you. Grab a frame with a boss at full health (or just after its first hit), click it, check, then save.
- Game presets you haven't calibrated yourself are now updated along with the app.
- Boss names are recognised even when the text reader runs words together.
- Updating no longer ends with a "Failed to remove temporary directory" warning. The fix is in the updater of the
  version you update from, so you may still see it once when updating to this version.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept; refresh the Browser source in OBS afterwards.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
