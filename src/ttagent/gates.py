"""Automatic quality gates. A video that fails any gate is kept for inspection but flagged, not queued."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .script.filters import banned_hits, word_count
from .video.render import probe_duration


@dataclass
class Gate:
    name: str
    passed: bool
    detail: str


def measure_lufs(video: Path) -> float | None:
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, flags=re.S)
    return float(json.loads(m.group(0))["input_i"]) if m else None


def stream_info(video: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(p.stdout)


def run_gates(video: Path, script: str, ai: float, extra_banned: list[str], lo: int, hi: int, settings: SimpleNamespace) -> list[Gate]:
    g = settings.gates
    gates: list[Gate] = []
    dur = probe_duration(video)
    gates.append(Gate("duration", g.min_duration_s <= dur <= g.max_duration_s, f"{dur:.1f}s"))

    streams = stream_info(video)["streams"]
    vid = next((s for s in streams if s["codec_type"] == "video"), None)
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    ok_res = bool(vid) and (vid["width"], vid["height"]) == (settings.video.width, settings.video.height)
    gates.append(Gate("resolution", ok_res, f"{vid['width']}x{vid['height']}" if vid else "no video"))
    gates.append(Gate("audio_present", has_audio, "yes" if has_audio else "no audio stream"))

    lufs = measure_lufs(video) if has_audio else None
    gates.append(Gate("loudness", lufs is not None and abs(lufs - g.target_lufs) <= 2.5, f"{lufs} LUFS"))

    words = word_count(script)
    gates.append(Gate("word_count", lo - 20 <= words <= hi + 20, f"{words} words"))
    hits = banned_hits(script, extra_banned)
    gates.append(Gate("stock_phrases", not hits, ", ".join(hits) or "none"))
    gates.append(Gate("ai_sounding", ai <= g.max_ai_score, f"score {ai:.2f} (max {g.max_ai_score})"))
    return gates
