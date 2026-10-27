## What's new in 1.0.3

- **Fixed:** the SoulsOverlay window could freeze ("Not Responding") after being minimized.
- SoulsOverlay now always opens **stopped**. Click **Start** when you want it to count.
- **Dark Souls Remastered:** Ornstein and Smough's second health bar is now set up from a real screenshot.
- Updating from this version on no longer ends with a "Failed to remove temporary directory" warning.

## How to install

1. Download **SoulsOverlay.exe** below and put it in a folder of its own.
2. In OBS, open **Tools → WebSocket Server Settings**, enable the server and copy the password from **Show Connect Info**.
3. Double-click `SoulsOverlay.exe`. If Windows says "Windows protected your PC", click **More info**, then **Run anyway** (the exe isn't code-signed). In the SoulsOverlay window, enter the OBS password and your game source name.
4. Click **Copy** next to the OBS link and add it as a Browser source in OBS, at your canvas size.

Updating: from this version on, the SoulsOverlay window offers new versions itself (Update…, then confirm). Or replace the old exe with this one by hand. Either way your settings and stats are kept; refresh the Browser source in OBS afterwards.

Check your download: `certutil -hashfile SoulsOverlay.exe SHA256` should match `SHA256SUMS.txt`.
