"""Word-level timing for captions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float


def even_alignment(text: str, duration: float) -> list[Word]:
    """Fallback: spread words across the audio in proportion to their length. Good enough for tests only."""
    tokens = text.split()
    weights = [max(len(re.sub(r"\W", "", t)), 1) + (4 if t[-1] in ".,!?;:" else 0) for t in tokens]
    total, t, words = sum(weights), 0.0, []
    for tok, w in zip(tokens, weights):
        span = duration * w / total
        words.append(Word(tok, t, t + span))
        t += span
    return words


def whisper_alignment(wav: Path, model: str = "small.en", compute_type: str = "int8") -> list[Word]:
    from faster_whisper import WhisperModel  # lazy: optional dependency

    engine = WhisperModel(model, device="cpu", compute_type=compute_type)
    segments, _ = engine.transcribe(str(wav), word_timestamps=True, language="en", vad_filter=False)
    return [Word(w.word.strip(), w.start, w.end) for seg in segments for w in (seg.words or []) if w.word.strip()]


def merge_script_with_timings(script: str, timed: list[Word]) -> list[Word]:
    """Show the script's own punctuation/casing with Whisper's timings when the word counts line up."""
    tokens = script.split()
    if len(tokens) == len(timed):
        return [Word(tok, w.start, w.end) for tok, w in zip(tokens, timed)]
    return timed


class Aligner:
    def __init__(self, engine: str, model: str, compute_type: str):
        self.engine, self.model, self.compute_type = engine, model, compute_type

    def align(self, script: str, wav: Path, duration: float) -> list[Word]:
        if self.engine == "even":
            return even_alignment(script, duration)
        return merge_script_with_timings(script, whisper_alignment(wav, self.model, self.compute_type))
