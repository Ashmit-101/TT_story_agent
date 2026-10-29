import csv
import random
import time
from types import SimpleNamespace

from ttagent.config import load_settings
from ttagent.db import Store
from ttagent.learn.bandit import pick
from ttagent.learn.entry import import_csv, log_interactive, write_template
from ttagent.learn.report import build_report
from ttagent.learn.scoring import score
from ttagent.learn.select import choose_plan
from ttagent.config import load_channel
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_score_rewards_retention_and_rewatch():
    weak = score(40, 8, 1000, 1, 1, 20, 1)
    strong = score(40, 40, 1000, 20, 30, 80, 10)
    rewatch = score(40, 52, 1000, 20, 30, 80, 10)
    assert weak < strong <= rewatch <= 1.0


def _store_with(rows):
    """rows: list of (channel, hook_style, topic, avg_watch_s). Duration fixed at 40s."""
    st = Store(Path(":memory:"))
    for i, (ch, h, t, aw) in enumerate(rows):
        st.add_experiment(id=f"id{i}", channel=ch, hook_style=h, topic=t, duration_s=40.0, hook=f"hook {i}",
                          script="s", caption=f"cap {i}", folder="f", passed=True, ai_score=0.1,
                          created=time.time() - 3 * 86400)
        st.add_result(f"id{i}", 1000, aw, 5, 5, 50, 2)
    return st


def test_bandit_prefers_winning_option_but_keeps_exploring():
    rows = [("horror", "a", "x", 38)] * 8 + [("horror", h, "x", 10) for h in "bcd" for _ in range(4)]
    st = _store_with(rows)
    scored = st.scored("horror")
    rng = random.Random(0)
    picks = [pick(list("abcd"), scored, "hook_style", rng, explore_rate=0.25, min_scored=6) for _ in range(400)]
    assert picks.count("a") / 400 > 0.6
    assert all(picks.count(x) > 0 for x in "bcd")  # still explores


def test_bandit_explores_evenly_when_data_is_thin():
    st = _store_with([("horror", "a", "x", 38)] * 2)
    rng = random.Random(1)
    picks = {pick(list("abc"), st.scored("horror"), "hook_style", rng, 0.25, 6) for _ in range(60)}
    assert picks == {"b", "c"}  # options with no data yet are tried before the one that already has some


def test_choose_plan_feeds_winning_hooks_once_enough_data():
    settings = load_settings(ROOT)
    ch = load_channel(ROOT, "horror")
    st = _store_with([("horror", "mid_action", "night_shift", 38 if i % 2 else 10) for i in range(8)])
    plan = choose_plan(st, ch, settings, random.Random(2))
    assert plan.hook_style in ch.hook_styles and plan.topic in ch.topics
    assert len(plan.winners) == settings.learn.winners_to_show

    empty = choose_plan(Store(Path(":memory:")), ch, settings, random.Random(2))
    assert empty.winners == []


def test_awaiting_log_and_dismiss(tmp_path):
    st = Store(Path(":memory:"))
    st.add_experiment(id="old", channel="facts", hook_style="h", topic="t", duration_s=40.0, hook="x", script="s",
                      caption="Old video", folder="f", passed=True, ai_score=0.1, created=time.time() - 3 * 86400)
    st.add_experiment(id="fresh", channel="facts", hook_style="h", topic="t", duration_s=40.0, hook="x", script="s",
                      caption="Fresh", folder="f", passed=True, ai_score=0.1)
    st.add_experiment(id="failed", channel="facts", hook_style="h", topic="t", duration_s=40.0, hook="x", script="s",
                      caption="Failed gates", folder="f", passed=False, ai_score=0.9, created=time.time() - 3 * 86400)
    assert [e["id"] for e in st.awaiting(24)] == ["old"]  # too new / failed videos are not asked about

    answers = iter(["1,200", "31", "10", "", "80", "4"])
    n = log_interactive(st, 24, input_fn=lambda _: next(answers), out=lambda _: None)
    assert n == 1 and st.scored("facts")[0]["views"] == 1200 and st.scored("facts")[0]["saves"] == 0
    assert st.awaiting(24) == []

    st.add_experiment(id="skipme", channel="facts", hook_style="h", topic="t", duration_s=40.0, hook="x", script="s",
                      caption="Never posted", folder="f", passed=True, ai_score=0.1, created=time.time() - 3 * 86400)
    log_interactive(st, 24, input_fn=lambda _: "s", out=lambda _: None)
    assert st.awaiting(24) == []


def test_csv_template_roundtrip(tmp_path):
    st = Store(Path(":memory:"))
    for i in range(2):
        st.add_experiment(id=f"c{i}", channel="horror", hook_style="h", topic="t", duration_s=40.0, hook="x",
                          script="s", caption=f"cap{i}", folder="f", passed=True, ai_score=0.1,
                          created=time.time() - 2 * 86400)
    path = tmp_path / "pending.csv"
    assert write_template(st, 24, path) == 2
    rows = list(csv.DictReader(path.open()))
    rows[0].update(views="5000", avg_watch_s="30.5", shares="40")
    rows[1]["id"] = "nope"; rows[1]["views"] = "10"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    done, errors = import_csv(st, path)
    assert done == 1 and len(errors) == 1 and "nope" in errors[0]
    assert st.scored("horror")[0]["shares"] == 40


def test_report_mentions_options_and_noise_warning():
    settings = load_settings(ROOT)
    rows = [("horror", "mid_action", "night_shift", 35)] * 4 + [("horror", "confession", "neighbors", 12)] * 4
    text = build_report(_store_with(rows), ["horror", "facts"], settings)
    assert "mid_action" in text and "confession" in text and "noise" in text
    assert "No results logged yet" in text  # facts has none
