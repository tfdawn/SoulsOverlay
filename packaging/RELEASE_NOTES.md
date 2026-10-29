## What's new in 1.0.6

- **DEFEATED now shows the moment the boss dies**, also when Elden Ring drops the boss bar before it's ever drawn empty (in 1.0.5 that case still waited several seconds).
- If YOU DIED comes up while the boss is still on screen (it survived on a sliver of health), DEFEATED is taken back and it counts as a death instead.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept; refresh the Browser source in OBS afterwards.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
