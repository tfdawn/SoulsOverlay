import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))


# The synthetic frames in synth.py are drawn with this layout, not the real
# calibrated one, so most tests run against a copy of the Elden Ring profile
# with these regions and the generic colour heuristic instead of the real
# death template. Real screenshots are tested in test_real_frames.py.
SYNTH_LAYOUT = {
    "regions": {"death": [0.25, 0.42, 0.5, 0.16]},
    "boss_slots": [
        {"name": [0.245, 0.826, 0.36, 0.034], "bar": [0.2525, 0.8645, 0.495, 0.009]},
        {"name": [0.245, 0.776, 0.36, 0.034], "bar": [0.2525, 0.8145, 0.495, 0.009]},
    ],
    "death": {"template": None, "heuristic": None},
    "bar_colors": None,
}


@pytest.fixture
def profiles_dir(tmp_path):
    dst = tmp_path / "profiles"
    shutil.copytree(ROOT / "profiles", dst)
    path = dst / "elden_ring.json"
    data = json.loads(path.read_text())
    for key, value in SYNTH_LAYOUT.items():
        if key == "death":
            data["death"] = {k: v for k, v in data.get("death", {}).items() if k not in value}
        elif value is None:
            data.pop(key, None)
        else:
            data[key] = value
    path.write_text(json.dumps(data))
    return dst


@pytest.fixture
def er(profiles_dir):
    from soulsoverlay.profiles import load_profile

    return load_profile(profiles_dir, "elden_ring")


@pytest.fixture
def config(tmp_path, profiles_dir):
    from soulsoverlay.config import Config

    cfg = Config()
    cfg.data_dir = tmp_path / "data"
    cfg.profiles_dir = profiles_dir
    cfg.hotkeys.enabled = False
    return cfg
