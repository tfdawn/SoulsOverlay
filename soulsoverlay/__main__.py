"""Command line entry point.

    soulsoverlay run                  start capture + overlay server
    soulsoverlay calibrate            open the calibration page (server must be running)
    soulsoverlay settings             open the settings page to change the overlay's look
    soulsoverlay ctl death_add        manual control (also: death_undo, boss_reset,
                                      boss_clear, boss_set "Name", game_set elden_ring)
    soulsoverlay analyze shot.png     run detection on a screenshot and print the result
    soulsoverlay stats                deaths and PBs for the current game
    soulsoverlay launcher             the SoulsOverlay window: start/stop, settings, OBS link
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from . import __version__, app
from .config import load_config


def _cmd_run(cfg, args):
    from aiohttp import web

    from .capture import FolderCapture
    from .events import load_plugins
    from .hotkeys import start_hotkeys
    from .server import OverlayServer
    from .service import Service

    capture = FolderCapture(Path(args.replay)) if args.replay else None
    service = Service(cfg, capture=capture)
    server = OverlayServer(service, cfg.control_token())
    load_plugins(cfg.plugins, service.bus, service.store, cfg)

    async def main():
        runner = web.AppRunner(server.app(), access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, cfg.server.host, cfg.server.port)
        await site.start()
        base = f"http://{cfg.server.host}:{cfg.server.port}"
        print(f"SoulsOverlay {__version__}")
        print(f"HUD (OBS Browser Source, canvas size): {base}/overlay/hud")
        print(f"Calibration: run `soulsoverlay calibrate` in another terminal")
        print(f"Change the look: run `soulsoverlay settings` in another terminal")
        print(f"Game: {service.profile.name}  |  death detector: {service.analyzer.death.mode}"
              f"  |  OCR: {service.status['ocr']}")
        server.hotkeys = start_hotkeys(cfg.hotkeys, service, asyncio.get_running_loop())
        try:
            await service.run()
        finally:
            await runner.cleanup()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


def _post(cfg, path: str, body: dict) -> dict:
    url = f"http://{cfg.server.host}:{cfg.server.port}{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {cfg.control_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"error {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise SystemExit(f"could not reach the counter at {url} (is `soulsoverlay run` running?): {e.reason}")


def _cmd_ctl(cfg, args):
    cmd_args = {}
    if args.command == "boss_set":
        cmd_args["boss"] = " ".join(args.value)
    elif args.command == "game_set":
        cmd_args["game"] = " ".join(args.value)
    elif args.command == "boss_reset" and args.value:
        cmd_args["boss"] = " ".join(args.value)
    print(json.dumps(_post(cfg, "/api/control", {"command": args.command, "args": cmd_args}), indent=2))


def _page_url(cfg, page: str) -> str:
    return f"http://{cfg.server.host}:{cfg.server.port}/{page}#token={cfg.control_token()}"


def _open_page(cfg, args, page: str, what: str):
    url = _page_url(cfg, page)
    if args.print_url:
        print(url)
        return
    print(f"Opening the {what} page in your browser (keep the URL private, it contains your token).")
    webbrowser.open(url)


def _cmd_calibrate(cfg, args):
    _open_page(cfg, args, "calibrate", "calibration")


def _cmd_settings(cfg, args):
    _open_page(cfg, args, "settings", "settings")


def _cmd_analyze(cfg, args):
    import cv2

    from .detect import bossname
    from .detect.analyzer import Analyzer
    from .profiles import load_profile

    profile = load_profile(cfg.profiles_dir, args.game or cfg.game)
    bossname.configure(cfg.tesseract_cmd)
    analyzer = Analyzer(profile)
    for path in args.images:
        frame = cv2.imread(path, cv2.IMREAD_COLOR)
        if frame is None:
            print(f"{path}: could not read")
            continue
        r = analyzer.analyze(frame, force_ocr=True).to_json()
        r.pop("t")
        print(json.dumps({"image": path, "size": [frame.shape[1], frame.shape[0]],
                          "detector": analyzer.death.mode, **r}, indent=2))


def _cmd_stats(cfg, args):
    from .store import Store

    game = args.game or cfg.game
    store = Store(cfg.db_path)
    print(f"{game}: {store.game_stats(game)['deaths']} deaths")
    for b in store.all_bosses(game):
        pb = b["pb"]
        pbs = "defeated" if pb and pb["killed"] else (f"{pb['pct']}% (phase {pb['phase']})" if pb else "-")
        print(f"  {b['name']:<45} {b['deaths']:>5} deaths   PB {pbs}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="soulsoverlay")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=f"SoulsOverlay {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--replay", help="read frames from a folder of images instead of OBS")
    p = sub.add_parser("calibrate")
    p.add_argument("--print-url", action="store_true")
    p = sub.add_parser("settings")
    p.add_argument("--print-url", action="store_true")
    p = sub.add_parser("ctl")
    p.add_argument("command", choices=["death_add", "death_undo", "boss_reset", "boss_set",
                                       "boss_clear", "game_set", "snapshot"])
    p.add_argument("value", nargs="*")
    p = sub.add_parser("analyze")
    p.add_argument("images", nargs="+")
    p.add_argument("--game")
    p = sub.add_parser("stats")
    p.add_argument("--game")
    p = sub.add_parser("launcher", help="the SoulsOverlay window (what the exe opens)")
    p.add_argument("--after-update", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # obsws-python logs its connection parameters, password included, at INFO.
    # The terminal may well be on stream, so keep that library quiet; capture
    # failures are reported once by the service instead of on every retry.
    logging.getLogger("obsws_python").setLevel(logging.CRITICAL)
    cfg = load_config(args.config)
    {"run": _cmd_run, "ctl": _cmd_ctl, "calibrate": _cmd_calibrate, "settings": _cmd_settings,
     "analyze": _cmd_analyze, "stats": _cmd_stats, "launcher": _cmd_launcher}[args.cmd](cfg, args)


def _cmd_launcher(cfg, args):
    from . import launcher

    launcher.run(cfg, after_update=args.after_update)


def frozen_main():
    """Entry point of SoulsOverlay.exe. With no arguments it opens the launcher
    window; other commands print to the terminal they were typed in."""
    argv = app.prepare(sys.argv[1:])
    app.attach_console(want="launcher" not in argv)
    try:
        main(argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        if e.code in (None, 0):
            raise
        if isinstance(e.code, str):
            print(e.code)
        sys.exit(1 if isinstance(e.code, str) else e.code)
    except Exception as e:
        logging.getLogger("soulsoverlay").exception("SoulsOverlay stopped with an error")
        app.error_box(f"SoulsOverlay stopped with an error:\n\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(frozen_main() if app.FROZEN else main())
