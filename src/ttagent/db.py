"""Tiny SQLite state store: remembers premises so the pipeline does not repeat itself."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS premises (id INTEGER PRIMARY KEY, channel TEXT, premise TEXT, created REAL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY, channel TEXT, path TEXT, passed INTEGER, "
            "ai_score REAL, created REAL)"
        )
        self.conn.commit()

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

    def add_video(self, channel: str, path: str, passed: bool, ai_score: float) -> None:
        self.conn.execute(
            "INSERT INTO videos (channel, path, passed, ai_score, created) VALUES (?,?,?,?,?)",
            (channel, path, int(passed), ai_score, time.time()),
        )
        self.conn.commit()
