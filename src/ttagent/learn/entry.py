"""Getting TikTok numbers into the database: interactive prompts, or a CSV you fill in from TikTok Studio."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from ..db import Store

FIELDS = ["views", "avg_watch_s", "shares", "saves", "likes", "comments"]


def _num(text: str, cast, default=0):
    text = text.strip().replace(",", "")
    return cast(text) if text else default


def log_interactive(store: Store, min_hours: float, input_fn: Callable[[str], str] = input,
                    out: Callable[[str], None] = print) -> int:
    pending = store.awaiting(min_hours)
    if not pending:
        out("Nothing waiting: no passed videos older than the minimum age without results.")
        return 0
    logged = 0
    for e in pending:
        out(f"\n[{e['channel']}] {e['id']}  \"{e['caption']}\"  ({e['hook_style']}/{e['topic']}, {e['duration_s']:.0f}s)")
        views = input_fn("  views (Enter = ask later, s = never posted): ").strip().lower()
        if views == "":
            continue
        if views == "s":
            store.dismiss(e["id"])
            continue
        try:
            avg = _num(input_fn("  average watch time in seconds: "), float)
            shares = _num(input_fn("  shares (Enter = 0): "), int)
            saves = _num(input_fn("  saves (Enter = 0): "), int)
            likes = _num(input_fn("  likes (Enter = 0): "), int)
            comments = _num(input_fn("  comments (Enter = 0): "), int)
            store.add_result(e["id"], _num(views, int), avg, shares, saves, likes, comments)
            logged += 1
        except ValueError:
            out("  Could not read that number; skipped. Run `ttagent log` again to retry.")
    return logged


def write_template(store: Store, min_hours: float, path: Path) -> int:
    pending = store.awaiting(min_hours)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "channel", "caption", *FIELDS])
        for e in pending:
            w.writerow([e["id"], e["channel"], e["caption"], "", "", "", "", "", ""])
    return len(pending)


def import_csv(store: Store, path: Path) -> tuple[int, list[str]]:
    done, errors = 0, []
    with path.open(newline="") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            exp_id = (row.get("id") or "").strip()
            if not (row.get("views") or "").strip():
                continue  # unfilled row
            if store.experiment(exp_id) is None:
                errors.append(f"line {n}: unknown id '{exp_id}'")
                continue
            try:
                store.add_result(
                    exp_id, _num(row["views"], int), _num(row.get("avg_watch_s", ""), float),
                    _num(row.get("shares", ""), int), _num(row.get("saves", ""), int),
                    _num(row.get("likes", ""), int), _num(row.get("comments", ""), int),
                )
                done += 1
            except ValueError as exc:
                errors.append(f"line {n}: {exc}")
    return done, errors
