## What's new in 1.0.10

- **Dark Souls III: the overlay no longer flickers when you look at a bright sky.** The empty part of the boss bar is see-through, and against the sky in the Iudex Gundyr fight it turns pale grey. The overlay didn't recognise that as part of the bar, so it kept losing the bar and hiding. It now reads the bar steadily there.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
