## What's new in 1.0.11

- **SoulsOverlay remembers your game.** It starts on the game you last picked instead of always opening on Elden Ring.
- **Closing the window now quits SoulsOverlay.** To keep it counting from the tray when you close the window, turn on **Keep running in the tray** in Settings. If you had already changed your window settings, your tray setting stays as it was.
- **The game list only shows the supported games:** Elden Ring, Dark Souls Remastered, Dark Souls II and Dark Souls III. "Generic (calibrate me)" is gone from it.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
