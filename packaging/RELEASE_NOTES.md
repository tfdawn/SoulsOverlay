## What's new in 1.0.12

- **SoulsOverlay switches to the game you're playing.** Start Dark Souls III while SoulsOverlay is set to Elden Ring, and it switches to Dark Souls III and its characters by itself, so your deaths and PBs land in the right place. It asks Steam which game is running (one registry value, `RunningAppID`) and reads nothing else: not your list of programs, and nothing of the game. It never switches mid-fight, the window tells you when it has switched, and **Back to** undoes it.
- Prefer to choose yourself? Click **Don't switch by itself, ask first** on that notice, and from then on the window only asks *"You're playing Dark Souls III. Switch?"*.
- Playing on a console through a capture card, or on a second PC? Nothing changes: pick the game in the window as before.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
