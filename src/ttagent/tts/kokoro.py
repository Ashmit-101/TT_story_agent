"""Local text-to-speech with Kokoro (Apache-2.0) via kokoro-onnx. Runs on Apple Silicon CPU/CoreML."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..script.filters import split_sentences


class TTS(Protocol):
    def synthesize(self, text: str, voice: str, out_wav: Path) -> float: ...


class KokoroTTS:
    def __init__(self, model_path: Path, voices_path: Path, speed: float = 1.0):
        if not model_path.exists() or not voices_path.exists():
            raise FileNotFoundError(
                f"Kokoro model files missing ({model_path}, {voices_path}). Run `ttagent doctor` for download steps."
            )
        from kokoro_onnx import Kokoro  # lazy: optional dependency

        self.engine = Kokoro(str(model_path), str(voices_path))
        self.speed = speed

    def synthesize(self, text: str, voice: str, out_wav: Path) -> float:
        import numpy as np
        import soundfile as sf

        chunks, buf = [], ""
        for sentence in split_sentences(text):  # keep each call well under the model's token limit
            if len((buf + " " + sentence).split()) > 55 and buf:
                chunks.append(buf)
                buf = sentence
            else:
                buf = f"{buf} {sentence}".strip()
        if buf:
            chunks.append(buf)

        audio, sr = [], 24000
        for chunk in chunks:
            samples, sr = self.engine.create(chunk, voice=voice, speed=self.speed, lang="en-us")
            audio.append(samples)
            audio.append(np.zeros(int(sr * 0.18), dtype=samples.dtype))  # short breath between chunks
        full = np.concatenate(audio)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_wav), full, sr)
        return len(full) / sr
