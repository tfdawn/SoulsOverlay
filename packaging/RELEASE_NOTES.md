## What's new in 1.0.9

- **Dark Souls III: Abyss Watchers' second phase now carries on the same fight.** The cutscene between the phases is almost a minute long, and the overlay used to give up on the fight halfway through, so phase 2 started over as a new fight. Now it waits for the bar to come back and counts it as phase 2, and DEFEATED doesn't show when phase 1 empties. Fire and blood in the cutscene can't pass for the boss bar any more either.
- **Dark Souls III: the boss bar reads in dark arenas.** The empty part of the bar is see-through, and in dark places like the Abyss Watchers' arena the overlay could lose the bar.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
