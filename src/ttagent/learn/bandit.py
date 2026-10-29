"""Pick experiment variables with Thompson sampling, plus a guaranteed share of random exploration.

With ~30 videos per niche a month the data is thin, so the rule is intentionally conservative:
- a video is a 'win' if its score beats the channel's median score, else a 'loss';
- each option gets a Beta(wins+1, losses+1) draw; the highest draw is picked;
- `explore_rate` of the time the stats are ignored completely;
- below `min_scored` scored videos the channel just explores evenly.
"""
from __future__ import annotations

import random
import statistics

from .scoring import score_row


def outcomes(rows: list[dict], key: str) -> tuple[dict[str, int], dict[str, int]]:
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    if not rows:
        return wins, losses
    scores = [score_row(r) for r in rows]
    median = statistics.median(scores)
    for r, s in zip(rows, scores):
        bucket = wins if s > median else losses
        bucket[r[key]] = bucket.get(r[key], 0) + 1
    return wins, losses


def pick(levels: list[str], rows: list[dict], key: str, rng: random.Random, explore_rate: float, min_scored: int) -> str:
    if not levels:
        return ""
    if len(rows) < min_scored or rng.random() < explore_rate:
        # under-sampled options first, so exploration covers every option evenly
        counts = {l: sum(1 for r in rows if r[key] == l) for l in levels}
        least = min(counts.values())
        return rng.choice([l for l in levels if counts[l] == least])
    wins, losses = outcomes(rows, key)
    draws = {l: rng.betavariate(wins.get(l, 0) + 1, losses.get(l, 0) + 1) for l in levels}
    return max(draws, key=draws.get)
