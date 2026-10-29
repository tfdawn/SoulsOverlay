## What's new in 1.0.8

- **Dark Souls III works out of the box on 16:9 screens.** The preset is now measured from real game footage at 1080p, so it fits 1920x1080, 2560x1440, 3840x2160 and other 16:9 sizes without calibrating. It reads the boss bar with its yellow damage trail and the boss name, catches YOU DIED with a proper template, and shows DEFEATED the moment the bar hits 0%. Two-boss fights like Demon in Pain and Demon from Below are tracked as well. It's no longer marked WiP.
- If you calibrated Dark Souls III yourself, your own profile is kept. To switch to the new preset, delete `profiles/dark_souls_3.json` next to the exe and restart.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
