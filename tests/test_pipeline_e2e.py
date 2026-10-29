"""End-to-end test with a stub LLM and stub TTS but REAL ffmpeg rendering and quality gates."""
import json
import math
import random
import shutil
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ttagent.captions.align import Aligner
from ttagent.config import load_channel, load_settings
from ttagent.db import Store
from ttagent.pipeline import make_video

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

SCRIPT = (
    "The night shift ended at six. I walked to my car in the empty lot. "
    "Someone had parked right behind it. A grey van. Engine off, windows fogged from the inside. "
    "Then the fog on the driver's window cleared in a small circle, like someone wiped it with a thumb. "
    "I couldn't see a face. Just the circle, and a bit of orange light. "
    "I went back inside and asked Dana at the desk to walk me out. She checked the camera feed and "
    "said there was no van. Only my car. I watched the footage myself. She was right. "
    "My car sat alone in the frame, and the driver's window was fogged from the inside. "
    "I park under the light now, near the door. "
    "Every morning there's a clean little circle in the glass. "
    "Always on the inside. Always at the height of a thumb."
)


class StubLLM:
    def chat(self, system, user, temperature=0.8, max_tokens=1200):
        if "content strategist" in system:
            return json.dumps(["A night worker finds a van behind their car", "A baby monitor hums"])
        if "ruthless script editor" in user or "Write the full voiceover" in user:
            return SCRIPT
        if "opening lines" in system:
            return json.dumps(["The night shift ended at six and the van was already there."])
        if "judge hooks" in system:
            return '{"index": 0}'
        return "Someone keeps wiping my car window from the inside"


class StubTTS:
    def synthesize(self, text, voice, out_wav: Path):
        seconds, sr = 28.0, 16000
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
            frames = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 180 * i / sr))) for i in range(int(seconds * sr)))
            w.writeframes(frames)
        return seconds


def test_full_pipeline_produces_passing_package(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    root = tmp_path / "proj"
    shutil.copytree(repo / "config", root / "config")
    (root / "assets" / "footage" / "horror").mkdir(parents=True)
    settings = load_settings(root)
    settings.script.candidates = 1
    settings.script.max_regenerations = 0
    channel = load_channel(root, "horror")
    store = Store(root / "data" / "state.db")

    result = make_video(
        root, settings, channel, StubLLM(), StubTTS(), Aligner("even", "", ""), store, rng=random.Random(1)
    )

    assert result.passed, [g for g in result.gates if not g.passed]
    files = {p.name for p in result.folder.iterdir()}
    assert {"video.mp4", "script.txt", "captions.ass", "metadata.json", "POST_CHECKLIST.md"} <= files
    meta = json.loads((result.folder / "metadata.json").read_text())
    assert meta["ai_generated_label_required"] is True and meta["passed_all_gates"] is True
    assert store.recent_premises("horror")  # premise remembered to avoid repeats
    exp = store.experiment(result.exp_id)
    assert exp and exp["channel"] == "horror" and exp["hook_style"] in channel.hook_styles
    assert exp["topic"] in channel.topics and exp["duration_s"] == 28.0
    assert meta["experiment"]["id"] == result.exp_id
