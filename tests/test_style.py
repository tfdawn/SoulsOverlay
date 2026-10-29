import json
import re
from pathlib import Path

import pytest

from soulsoverlay import style
from test_server import AUTH, with_client

WEB = Path(__file__).resolve().parents[1] / "soulsoverlay" / "web"


def root_vars(css_file):
    block = re.search(r":root\s*\{(.*?)\n\}", (WEB / css_file).read_text(), re.S).group(1)
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    return {k.strip(): v.strip() for k, v in re.findall(r"(--[\w-]+):([^;]+);", block)}


@pytest.mark.parametrize("target,css_file", [("hud", "hud.css")])
def test_schema_defaults_match_the_css(target, css_file):
    css = root_vars(css_file)
    for f in style.SCHEMA:
        if f["target"] != target or "var" not in f:
            continue
        if f["type"] == "enum":
            want = next(o["css"] for o in f["options"] if o["value"] == f["default"])
        else:
            want = f"{f['default']}{f.get('unit', '')}" if f["type"] == "number" else f["default"]
        assert f["var"] in css, f["key"]
        got = css[f["var"]]
        if f["type"] == "number":
            assert float(got.rstrip("vhpxs%")) == pytest.approx(f["default"]), f["key"]
        else:
            assert got == want, f["key"]


def test_validate_keeps_changes_and_drops_defaults():
    vals = style.validate({"hud.pb_color": "#7fd1ff", "hud.size": 1.75, "hud.label_pb": "Best", "hud.aura": "rgba(1, 2, 3, 0.5)"})
    assert vals == {"hud.pb_color": "#7fd1ff", "hud.label_pb": "Best",
                    "hud.aura": "rgba(1, 2, 3, 0.5)"}


@pytest.mark.parametrize("key,value", [
    ("hud.pb_color", "red; } body { display: none"),
    ("hud.pb_color", "url(http://x)"),
    ("hud.font", "Arial; color: red"),
    ("hud.font", "x</style>"),
    ("hud.size", 99),
    ("hud.size", "2"),
    ("hud.show_pb", "yes"),
    ("hud.shadow", "rainbow"),
    ("box.width", 420),
    ("hud.label_pb", "x" * 41),
    ("nope.key", 1),
])
def test_validate_rejects_bad_values(key, value):
    with pytest.raises(ValueError):
        style.validate({key: value})


def test_load_skips_bad_entries(tmp_path):
    p = tmp_path / "style.json"
    p.write_text(json.dumps({"values": {"hud.pb_color": "#123456", "hud.size": "huge", "old.thing": 1}}))
    assert style.load(p) == {"hud.pb_color": "#123456"}
    p.write_text("{not json")
    assert style.load(p) == {}


def test_settings_endpoints(config):
    async def body(client, service):
        r = await client.get("/overlay/settings.json")
        assert r.status == 200
        data = await r.json()
        assert data["values"] == {} and any(f["key"] == "hud.glow_time" for f in data["schema"])

        assert (await client.get("/settings")).status == 200
        assert (await client.get("/overlay/style.js")).status == 200
        # Saving needs the token, like every other change.
        assert (await client.post("/api/settings", json={"values": {}})).status == 401
        r = await client.post("/api/settings", json={"values": {"hud.pb_color": "bad;"}}, headers=AUTH)
        assert r.status == 400

        ws = await client.ws_connect("/overlay/ws")
        for _ in range(3):  # hello, the initial state and hud_status
            await ws.receive_json()
        r = await client.post("/api/settings", json={"values": {"hud.pb_color": "#7fd1ff", "hud.size": 1.75}},
                              headers=AUTH)
        assert r.status == 200
        assert (await r.json())["values"] == {"hud.pb_color": "#7fd1ff"}
        msg = await ws.receive_json(timeout=2)
        assert msg == {"kind": "settings", "values": {"hud.pb_color": "#7fd1ff"}}
        await ws.close()
        saved = json.loads(service.config.style_path.read_text())
        assert saved["values"] == {"hud.pb_color": "#7fd1ff"}
        data = await (await client.get("/overlay/settings.json")).json()
        assert data["values"] == {"hud.pb_color": "#7fd1ff"}

        # Reset to default: save nothing.
        r = await client.post("/api/settings", json={"values": {}}, headers=AUTH)
        assert (await r.json())["values"] == {}

    with_client(config, body=body)


def test_only_overlays_can_be_framed_and_only_by_this_server(config):
    async def body(client, service):
        hud = (await client.get("/overlay/hud")).headers["Content-Security-Policy"]
        assert "frame-ancestors 'self'" in hud
        for page in ("/settings", "/calibrate"):
            csp = (await client.get(page)).headers["Content-Security-Policy"]
            assert "frame-ancestors 'none'" in csp

    with_client(config, body=body)


def test_custom_effect_takes_the_labs_own_file():
    lab = {"hp": 100, "barWidth": 860, "reach": 80, "curveType": "points", "curve": [0.16, 1, 0.3, 1],
           "points": [[0, 0], [0.1, 0.45], [0.35, 0.5], [1, 1]], "interp": "smooth",
           "spread": 1200, "particles": {"on": True, "count": 5000, "mode": "burst"}, "pb": True,
           "partColor": "#aabbcc", "speed": 0.5}
    fx = style.validate({"hud.fx": lab})["hud.fx"]
    assert fx["reach"] == 80 and fx["curveType"] == "points" and fx["spread"] == 1200
    assert fx["particles"]["count"] == 600  # capped
    assert fx["particles"]["mode"] == "burst" and fx["partColor"] == "#aabbcc"
    assert fx["hp"] == 100 and fx["speed"] == 0.5 and fx["pb"] is True
    assert fx["streak"] == style.FX_DEFAULTS["streak"]  # missing keys keep the defaults


@pytest.mark.parametrize("bad", [
    {"warm": "red; x"}, {"curveType": "wobble"}, {"particles": {"mode": "x"}}, {"curve": [1, 2]},
    {"points": [[0, 0]]}, {"spread": "fast"}, {"glow": {"on": "yes"}}, "nope",
])
def test_custom_effect_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        style.validate({"hud.fx": bad})
