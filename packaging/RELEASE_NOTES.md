## What's new in 1.0.14

- **Dark Souls II: Twin Dragonriders** now count as their own fight. Their two health bars both say "Dragonrider", which is how SoulsOverlay tells them from the Heide's Tower Dragonrider.
- **Dark Souls II: blue Smelter Demon (experimental).** Its bar also just says "Smelter Demon", so SoulsOverlay guesses: once you've beaten the Iron Keep Smelter Demon on a character, the next one counts as the blue one.
- When the boss shares its name with another, the SoulsOverlay window shows a button to switch to the other one if the guess is wrong.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept, and the overlay in OBS picks up the new version by itself.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
