import base64

import cv2
import numpy as np
import pytest

from soulsoverlay.capture import ObsCapture


class FakeObs:
    """Behaves like obs-websocket: screenshots are stretched to exactly the
    requested size, and a request without a size fails (as on the user's PC)."""

    def __init__(self, native, scenes=None, canvas=(1920, 1080)):
        self.native = native
        self.scenes = scenes if scenes is not None else {"Gaming": [("Game", 1)]}
        self.canvas = canvas
        self.requests = []

    def send(self, request, data=None, raw=False):
        assert raw
        self.requests.append((request, data))
        if request == "GetSceneList":
            return {"scenes": [{"sceneName": s} for s in self.scenes]}
        if request == "GetSceneItemList":
            return {"sceneItems": [{"sourceName": n, "sceneItemId": i} for n, i in self.scenes[data["sceneName"]]]}
        if request == "GetSceneItemTransform":
            h, w = self.native.shape[:2]
            return {"sceneItemTransform": {"sourceWidth": w, "sourceHeight": h}}
        if request == "GetInputList":
            return {"inputs": [{"inputName": n} for items in self.scenes.values() for n, _ in items]}
        if request == "GetVideoSettings":
            return {"baseWidth": self.canvas[0], "baseHeight": self.canvas[1]}
        assert request == "GetSourceScreenshot"
        if "imageWidth" not in data:
            raise RuntimeError("Failed to render screenshot")
        img = cv2.resize(self.native, (data["imageWidth"], data["imageHeight"]))
        ok, buf = cv2.imencode(".jpg", img)
        return {"imageData": "data:image/jpg;base64," + base64.b64encode(buf.tobytes()).decode()}

    def disconnect(self):
        pass


def make(native_w, native_h, width=1280, **kw):
    cap = ObsCapture("127.0.0.1", 4455, "", "Game", width)
    cap._client = FakeObs(np.zeros((native_h, native_w, 3), np.uint8), **kw)
    return cap


def shots(cap):
    return [d for r, d in cap._client.requests if r == "GetSourceScreenshot"]


@pytest.mark.parametrize("native,expected", [((2560, 1440), (720, 1280)), ((3440, 1440), (536, 1280)),
                                             ((1280, 720), (720, 1280))])
def test_keeps_source_aspect_ratio(native, expected):
    cap = make(*native)
    assert cap.grab().shape[:2] == expected
    assert cap.grab().shape[:2] == expected
    assert len([r for r, _ in cap._client.requests if r == "GetSceneList"]) == 1  # probed once


def test_falls_back_to_canvas_and_names_real_sources(caplog):
    cap = make(2560, 1440, scenes={"Other": [("Webcam", 3), ("Game", 4)]}, canvas=(2560, 1080))
    cap.source = "Game Capture"  # renamed in OBS, config not updated
    assert cap.grab().shape[:2] == (540, 1280)
    assert "no source called 'Game Capture'" in caplog.text and "'Game'" in caplog.text
