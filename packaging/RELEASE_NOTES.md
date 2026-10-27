## What's in it

- **One-click updates:** the SoulsOverlay window tells you when a new version is out. Click **Update…**, confirm, and it restarts on the new version. Your settings and stats are kept.
- **Characters:** keep separate deaths and PBs for each character, and switch between them at the top of the window.
- **Settings** holds the **Overlay Editor** (colours, text and the NEW PB effect) and **Hotkeys**. You can change the keys, turn each hotkey on or off, and hover over one to see what it does.
- **Colour themes** (Gold, Ice, Crimson, Emerald, Violet, Pink and White) recolour the whole HUD the same way, and **Text colours** lets you set each part on its own: the DEATHS word, death count, PB %, PB marker, NEW PB, DEFEATED and more.
- **Games:** Elden Ring is first in the list, followed by Dark Souls Remastered, Dark Souls II and Dark Souls III in release order. The Dark Souls presets are marked WiP and haven't been tested in game yet; switching to one shows a warning first.
- Closing the window keeps SoulsOverlay running in the tray, and says so. **Keep running in the tray** in Settings turns that off.
- The window reminds you to use **Transform → Fit to screen** on the Browser source in OBS.
- A shorter README with a banner.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept; refresh the Browser source in OBS afterwards.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
