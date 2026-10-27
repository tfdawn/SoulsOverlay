import json

from soulsoverlay.launcher import Api


def test_window_prefs_default_save_and_ignore_junk(config):
    api = Api(config)
    assert api.get_prefs() == {"close_to_tray": True, "tray_notice": True}
    assert api.set_pref("close_to_tray", False) == {"close_to_tray": False, "tray_notice": True}
    assert Api(config).get_prefs()["close_to_tray"] is False
    assert api.set_pref("nonsense", True) == {"close_to_tray": False, "tray_notice": True}
    (config.data_dir / "launcher.json").write_text(json.dumps({"tray_notice": "no"}))
    assert api.get_prefs() == {"close_to_tray": True, "tray_notice": True}
    (config.data_dir / "launcher.json").write_text("{broken")
    assert api.get_prefs()["tray_notice"] is True
