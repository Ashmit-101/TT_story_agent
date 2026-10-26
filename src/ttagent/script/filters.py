"""Heuristic detector for 'AI-sounding' narration, plus TTS text cleanup.

The score is deliberately simple and transparent: a weighted sum of tells that show up in
LLM-written short-form scripts. It is a cheap first filter, not a quality guarantee.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

STOCK_PHRASES = [
    "buckle up", "little did i know", "let that sink in", "plot twist", "game changer", "game-changer",
    "you won't believe", "what happened next", "dive into", "delve", "tapestry", "testament to",
    "in conclusion", "at the end of the day", "it's important to note", "shiver down", "shivers down",
    "my heart sank", "my blood ran cold", "heart pounding", "heart racing", "little did", "unbeknownst",
    "follow for more", "like and subscribe", "stay tuned", "the lesson here", "moral of the story",
    "and that's when i realized", "that's when i realized", "from that day on", "to this day",
    "couldn't help but", "a sense of", "send shivers", "hold on to your", "mind-blowing", "fascinating",
]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z0-9'’-]+")


@dataclass
class AiScore:
    score: float
    reasons: list[str]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def banned_hits(text: str, extra: list[str] | None = None) -> list[str]:
    low = text.lower()
    return [p for p in STOCK_PHRASES + [e.lower() for e in (extra or [])] if p in low]


def ai_score(text: str, extra_banned: list[str] | None = None) -> AiScore:
    """Return 0..1 (higher = more AI-sounding) and the reasons that contributed."""
    reasons: list[str] = []
    score = 0.0
    sentences = split_sentences(text)
    if not sentences:
        return AiScore(1.0, ["empty text"])

    hits = banned_hits(text, extra_banned)
    if hits:
        score += min(0.5, 0.15 * len(hits))
        reasons.append(f"stock phrases: {', '.join(hits[:5])}")

    lengths = [word_count(s) for s in sentences]
    if len(lengths) >= 5:
        mean = statistics.mean(lengths)
        spread = statistics.pstdev(lengths) / mean if mean else 0
        if spread < 0.35:
            score += 0.2
            reasons.append("sentence lengths too uniform")
        if mean > 17:
            score += 0.15
            reasons.append(f"sentences too long for speech (avg {mean:.0f} words)")

    openers = [s.split()[0].lower() for s in sentences if s.split()]
    if openers:
        top = max(set(openers), key=openers.count)
        if openers.count(top) / len(openers) > 0.3 and len(openers) >= 6:
            score += 0.15
            reasons.append(f"repetitive sentence openers ('{top}')")

    dashes = text.count("—") + text.count(" - ")
    if dashes >= 3:
        score += 0.1
        reasons.append("heavy dash use")

    if len(re.findall(r"\bnot (?:just|only)\b.{0,40}\bbut\b", text, flags=re.I)) >= 1:
        score += 0.1
        reasons.append("'not just X but Y' construction")

    questions = sum(s.endswith("?") for s in sentences)
    if questions >= 3:
        score += 0.1
        reasons.append("too many rhetorical questions")

    if re.search(r"\b(?:ethereal|palpable|visceral|intricate|vibrant|profound)\b", text, flags=re.I):
        score += 0.1
        reasons.append("ornate vocabulary")

    return AiScore(min(1.0, score), reasons)


def clean_for_tts(text: str) -> str:
    """Strip markup and stage directions so the voice reads only the spoken words."""
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)           # [pause], (beat)
    text = re.sub(r"[*_#>`]+", "", text)                           # markdown
    text = text.replace("—", ", ").replace("–", ", ").replace("…", "...")
    text = re.sub(r"^(?:hook|script|cta|title)\s*:\s*", "", text, flags=re.I | re.M)
    return re.sub(r"\s+", " ", text).strip()
