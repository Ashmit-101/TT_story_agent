"""FFmpeg-based 9:16 render: background footage + narration + burned-in captions + loudness normalisation."""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from types import SimpleNamespace

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out.stdout)["format"]["duration"])


def list_footage(footage_dir: Path, tag: str) -> list[Path]:
    folder = footage_dir / tag
    return sorted(p for p in folder.glob("**/*") if p.suffix.lower() in VIDEO_EXT) if folder.exists() else []


def _filter_path(path: Path) -> str:
    # Escape for the ffmpeg filtergraph: backslash, colon, quote.
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render(
    audio: Path,
    ass: Path,
    out: Path,
    settings: SimpleNamespace,
    footage: Path | None,
    rng: random.Random | None = None,
) -> Path:
    v = settings.video
    duration = probe_duration(audio) + 0.4  # tiny tail so the last word is not clipped
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = rng or random.Random()

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if footage is not None:
        total = probe_duration(footage)
        start = rng.uniform(0, max(total - duration, 0)) if total > duration + 1 else 0
        cmd += ["-ss", f"{start:.2f}", "-stream_loop", "-1", "-i", str(footage)]
    else:  # no footage yet: dark placeholder so the pipeline still runs end to end
        cmd += ["-f", "lavfi", "-i", f"color=c=0x14141f:s={v.width}x{v.height}:r={v.fps}"]
    cmd += ["-i", str(audio)]

    vf = (
        f"scale={v.width}:{v.height}:force_original_aspect_ratio=increase,crop={v.width}:{v.height},"
        f"fps={v.fps},setsar=1,ass='{_filter_path(ass)}',format=yuv420p"
    )
    af = f"loudnorm=I={settings.gates.target_lufs}:TP=-1.5:LRA=11"
    cmd += ["-vf", vf, "-af", af, "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.2f}"]
    if "videotoolbox" in v.encoder:
        cmd += ["-c:v", v.encoder, "-b:v", "8M"]
    else:
        cmd += ["-c:v", v.encoder, "-crf", str(v.crf), "-preset", "medium"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(out)]
    run(cmd)
    return out
