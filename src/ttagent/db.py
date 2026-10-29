"""SQLite state: recent premises (no repeats), one row per generated video, and logged TikTok results."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS premises (id INTEGER PRIMARY KEY, channel TEXT, premise TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY, channel TEXT, hook_style TEXT, topic TEXT, duration_s REAL, hook TEXT,
                script TEXT, caption TEXT, folder TEXT, passed INTEGER, ai_score REAL, created REAL);
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY, views INTEGER, avg_watch_s REAL, shares INTEGER, saves INTEGER,
                likes INTEGER, comments INTEGER, logged REAL);
            CREATE TABLE IF NOT EXISTS dismissed (id TEXT PRIMARY KEY);
            """
        )
        self.conn.commit()

    # --- premises -------------------------------------------------------------------------------
    def recent_premises(self, channel: str, limit: int = 40) -> list[str]:
        rows = self.conn.execute(
            "SELECT premise FROM premises WHERE channel=? ORDER BY id DESC LIMIT ?", (channel, limit)
        ).fetchall()
        return [r[0] for r in rows]

    def add_premise(self, channel: str, premise: str) -> None:
        self.conn.execute(
            "INSERT INTO premises (channel, premise, created) VALUES (?,?,?)", (channel, premise, time.time())
        )
        self.conn.commit()

    # --- experiments ----------------------------------------------------------------------------
    def add_experiment(self, **f: Any) -> None:
        f.setdefault("created", time.time())
        f["passed"] = int(f["passed"])
        cols = ",".join(f)
        self.conn.execute(f"INSERT INTO experiments ({cols}) VALUES ({','.join('?' * len(f))})", list(f.values()))
        self.conn.commit()

    def experiment(self, exp_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
        return dict(row) if row else None

    def add_result(self, exp_id: str, views: int, avg_watch_s: float, shares: int = 0, saves: int = 0,
                   likes: int = 0, comments: int = 0) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO results (id, views, avg_watch_s, shares, saves, likes, comments, logged) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (exp_id, views, avg_watch_s, shares, saves, likes, comments, time.time()),
        )
        self.conn.commit()

    def scored(self, channel: str | None = None) -> list[dict]:
        """Experiments that have logged results (joined)."""
        q = "SELECT e.*, r.views, r.avg_watch_s, r.shares, r.saves, r.likes, r.comments " \
            "FROM experiments e JOIN results r ON r.id = e.id"
        args: tuple = ()
        if channel:
            q += " WHERE e.channel=?"
            args = (channel,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY e.created", args).fetchall()]

    def awaiting(self, min_age_hours: float, channel: str | None = None) -> list[dict]:
        """Passed videos older than min_age_hours that have no results logged yet."""
        q = ("SELECT e.* FROM experiments e LEFT JOIN results r ON r.id = e.id "
             "WHERE r.id IS NULL AND e.passed = 1 AND e.created <= ? "
             "AND e.id NOT IN (SELECT id FROM dismissed)")
        args: list = [time.time() - min_age_hours * 3600]
        if channel:
            q += " AND e.channel=?"
            args.append(channel)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY e.created", args).fetchall()]

    def dismiss(self, exp_id: str) -> None:
        """Mark a video as never posted so it stops appearing in the results prompt."""
        self.conn.execute("INSERT OR IGNORE INTO dismissed (id) VALUES (?)", (exp_id,))
        self.conn.commit()
