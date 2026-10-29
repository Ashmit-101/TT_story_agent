from __future__ import annotations

import random
from types import SimpleNamespace

from ..config import Channel
from ..db import Store
from .bandit import pick
from .plan import Plan
from .scoring import score_row


def choose_plan(store: Store, channel: Channel, settings: SimpleNamespace, rng: random.Random | None = None) -> Plan:
    rng = rng or random.Random()
    lc = settings.learn
    rows = store.scored(channel.name)
    plan = Plan()
    if channel.hook_styles:
        plan.hook_style = pick(list(channel.hook_styles), rows, "hook_style", rng, lc.explore_rate, lc.min_scored_for_learning)
        plan.hook_instruction = channel.hook_styles[plan.hook_style]
    if channel.topics:
        plan.topic = pick(list(channel.topics), rows, "topic", rng, lc.explore_rate, lc.min_scored_for_learning)
        plan.topic_desc = channel.topics[plan.topic]
    if len(rows) >= lc.min_scored_for_learning:
        best = sorted(rows, key=score_row, reverse=True)[: lc.winners_to_show]
        plan.winners = [r["hook"] for r in best if r.get("hook")]
    return plan
