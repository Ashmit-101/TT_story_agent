"""Turn raw TikTok numbers into one comparable score.

Views mostly measure how widely TikTok chose to distribute a video, so the score is built from retention and
engagement per view instead: avg watch time / duration (above 1.0 means people rewatched) and weighted
shares/saves/comments/likes per view. Weights are deliberately simple and easy to change.
"""
from __future__ import annotations


def retention(avg_watch_s: float, duration_s: float) -> float:
    return avg_watch_s / duration_s if duration_s > 0 else 0.0


def engagement(views: int, shares: int, saves: int, likes: int, comments: int) -> float:
    return (3 * shares + 2 * saves + comments + 0.5 * likes) / max(views, 1)


def score(duration_s: float, avg_watch_s: float, views: int, shares: int = 0, saves: int = 0, likes: int = 0,
          comments: int = 0) -> float:
    r = min(retention(avg_watch_s, duration_s), 1.2) / 1.2          # 0..1
    e = min(engagement(views, shares, saves, likes, comments) * 5, 1.0)  # 0..1
    return round(0.7 * r + 0.3 * e, 4)


def score_row(row: dict) -> float:
    return score(row["duration_s"], row["avg_watch_s"], row["views"], row["shares"], row["saves"], row["likes"],
                 row["comments"])
