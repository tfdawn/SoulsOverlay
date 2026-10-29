import json

from soulsoverlay.launcher import Api


def test_window_prefs_default_save_and_ignore_junk(config):
    api = Api(config)
    assert api.get_prefs() == {"close_to_tray": False, "tray_notice": True}
    assert api.set_pref("close_to_tray", True) == {"close_to_tray": True, "tray_notice": True}
    assert Api(config).get_prefs()["close_to_tray"] is True
    assert api.set_pref("nonsense", True) == {"close_to_tray": True, "tray_notice": True}
    (config.data_dir / "launcher.json").write_text(json.dumps({"tray_notice": "no"}))
    assert api.get_prefs() == {"close_to_tray": False, "tray_notice": True}
    # Turning the notice off doesn't pin the tray setting to today's default.
    api.set_pref("tray_notice", False)
    assert json.loads((config.data_dir / "launcher.json").read_text()) == {"tray_notice": False}
    (config.data_dir / "launcher.json").write_text("{broken")
    assert api.get_prefs()["tray_notice"] is True


def test_js_api_exposes_only_methods(config):
    # pywebview walks every public attribute of js_api to build window.pywebview.api.
    # A window object there makes it crawl the native WinForms/WebView2 objects from
    # the wrong thread, which logged errors and froze the window.
    api = Api(config)
    api._window = object()
    public = {k: v for k, v in vars(api).items() if not k.startswith("_")}
    assert public == {}
