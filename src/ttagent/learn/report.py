from __future__ import annotations

import statistics
from types import SimpleNamespace

from ..db import Store
from .scoring import retention, score_row


def _table(rows: list[dict], key: str) -> list[str]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)
    out = [f"  {key:<18} n   avg score  avg retention  avg views"]
    for name, g in sorted(groups.items(), key=lambda kv: -statistics.mean(score_row(x) for x in kv[1])):
        out.append(
            f"  {name:<18} {len(g):<3} {statistics.mean(score_row(x) for x in g):<10.2f} "
            f"{statistics.mean(retention(x['avg_watch_s'], x['duration_s']) for x in g):<14.2f}"
            f"{statistics.mean(x['views'] for x in g):.0f}"
        )
    return out


def build_report(store: Store, channels: list[str], settings: SimpleNamespace) -> str:
    lines: list[str] = []
    lc = settings.learn
    for name in channels:
        rows = store.scored(name)
        pending = store.awaiting(lc.min_hours_before_logging, name)
        lines.append(f"== {name}: {len(rows)} scored, {len(pending)} awaiting results ==")
        if not rows:
            lines.append("  No results logged yet. Run `ttagent log` 24-48h after posting.\n")
            continue
        scores = [score_row(r) for r in rows]
        lines.append(f"  median score {statistics.median(scores):.2f}, best {max(scores):.2f}, "
                     f"best views {max(r['views'] for r in rows)}")
        lines += _table(rows, "hook_style") + _table(rows, "topic")
        if len(rows) < lc.min_scored_for_learning:
            lines.append(f"  (fewer than {lc.min_scored_for_learning} scored videos: still exploring evenly)")
        else:
            lines.append("  Treat any option with fewer than ~5 videos as noise, not a verdict.")
        top = sorted(rows, key=score_row, reverse=True)[:3]
        lines.append("  Top hooks: " + " | ".join(f'"{r["hook"][:60]}"' for r in top))
        lines.append("")
    return "\n".join(lines)
