## What's new in 1.0.4

- **Dark Souls II** is no longer a work in progress. Deaths, boss names and boss health are set up from real Scholar of the First Sin footage, with its own YOU DIED image, boss bar colours and up to three boss bars (Ruin Sentinels, Skeleton Lords and the other group fights).
- The boss list covers the original game, Scholar of the First Sin and all three DLCs, and recognises each bar's own name in group fights (for example "Ruin Sentinel Yahim").
- Your Dark Souls II preset updates with the app, unless you've saved your own calibration for it.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept; refresh the Browser source in OBS afterwards.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
