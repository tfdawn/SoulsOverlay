# PyInstaller spec for the one-file SoulsOverlay.exe. Build from the repo root:
#   pyinstaller packaging/soulsoverlay.spec
# Put a Tesseract install (tesseract.exe, its DLLs and tessdata/) in
# build/tesseract first to pack it in; the release workflow does this.
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "soulsoverlay" / "web"), "soulsoverlay/web"),
    (str(ROOT / "profiles"), "profiles"),
    (str(ROOT / "config.example.toml"), "."),
    (str(ROOT / "packaging" / "soulsoverlay.ico"), "packaging"),
]
tesseract = ROOT / "build" / "tesseract"
if tesseract.exists():
    datas.append((str(tesseract), "tesseract"))

hiddenimports = ["pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32"] if sys.platform == "win32" else []

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="SoulsOverlay",
    icon=str(ROOT / "packaging" / "soulsoverlay.ico"),
    # No terminal window: the exe opens the launcher window. Commands typed in
    # a terminal still print there (app.attach_console).
    console=False,
    upx=False,
)
