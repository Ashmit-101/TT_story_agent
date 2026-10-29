"""Multi-pass script generation: premise -> several drafts -> editor pass -> hook pick -> score.

One LLM call rarely sounds human. Splitting ideation, drafting, editing and hook selection, and
rejecting drafts that the heuristic filter flags, is what moves output away from 'AI voice'.
The experiment `Plan` (hook style + topic chosen by the feedback loop) steers premise and hook.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from types import SimpleNamespace

from ..config import Channel
from ..db import Store
from ..learn.plan import Plan
from ..llm.client import LLM, extract_json
from .filters import STOCK_PHRASES, AiScore, ai_score, clean_for_tts, split_sentences, word_count

log = logging.getLogger("ttagent.script")


@dataclass
class ScriptResult:
    premise: str
    text: str
    caption: str
    hook: str
    score: AiScore


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def _too_similar(candidate: str, recent: list[str], threshold: float = 0.5) -> bool:
    a = _tokens(candidate)
    for r in recent:
        b = _tokens(r)
        if a and b and len(a & b) / len(a | b) >= threshold:
            return True
    return False


def system_prompt(channel: Channel, examples: list[str], plan: Plan | None = None) -> str:
    plan = plan or Plan()
    lo, hi = channel.target_words
    banned = ", ".join(sorted(set(STOCK_PHRASES + channel.extra_banned)))
    rules = "\n".join(f"- {r}" for r in channel.style_rules)
    extra = ""
    if plan.hook_instruction:
        extra += f"\n- Opening line style for this script: {plan.hook_instruction}"
    ex = ""
    if examples:
        ex += "\n\nStyle references (match the rhythm and specificity, never copy content):\n" + "\n\n".join(
            f"<example>\n{e}\n</example>" for e in examples
        )
    if plan.winners:
        ex += ("\n\nOpening lines that kept viewers watching on this channel (study the pattern, do not copy):\n"
               + "\n".join(f"- {w}" for w in plan.winners))
    return (
        f"You write voiceover scripts for vertical short videos.\nPersona: {channel.persona}\n\n"
        f"Hard rules:\n- {lo}-{hi} words. Spoken English only: contractions, short sentences, some fragments.\n"
        f"- Plain text output: no headings, labels, stage directions, emojis, or markdown.\n"
        f"- Vary sentence length. Prefer concrete specifics over emotion words.\n"
        f"- Never use these phrases: {banned}.\n{rules}{extra}{ex}"
    )


def pick_premise(llm: LLM, channel: Channel, store: Store, settings: SimpleNamespace, plan: Plan | None = None) -> str:
    plan = plan or Plan()
    recent = store.recent_premises(channel.name)
    avoid = "\n".join(f"- {p}" for p in recent[:15]) or "(none yet)"
    topic = f"\nTopic area for this one: {plan.topic_desc}" if plan.topic_desc else ""
    reply = llm.chat(
        "You are a sharp short-form content strategist. Reply with JSON only.",
        f"Channel brief: {channel.premise_brief}{topic}\n\nGive 6 distinct premises, each one sentence, as a JSON "
        f'array of strings. Avoid anything similar to these recent ones:\n{avoid}',
        temperature=settings.llm.premise_temperature,
    )
    try:
        options = [str(x) for x in extract_json(reply)]
    except (ValueError, TypeError):
        options = [reply.strip().splitlines()[0]]
    fresh = [o for o in options if not _too_similar(o, recent)] or options
    return fresh[0]


def draft(llm: LLM, channel: Channel, premise: str, examples: list[str], settings: SimpleNamespace,
          plan: Plan | None = None) -> str:
    lo, hi = channel.target_words
    out = llm.chat(
        system_prompt(channel, examples, plan),
        f"Premise: {premise}\n\nWrite the full voiceover script now ({lo}-{hi} words). Output the script only.",
        temperature=settings.llm.draft_temperature,
    )
    return clean_for_tts(out)


def edit(llm: LLM, channel: Channel, text: str, reasons: list[str], settings: SimpleNamespace,
         plan: Plan | None = None) -> str:
    lo, hi = channel.target_words
    notes = "; ".join(reasons) or "none flagged automatically"
    out = llm.chat(
        system_prompt(channel, [], plan),
        "You are a ruthless script editor. Rewrite the script below so it sounds like a real person talking, "
        "not a language model. Cut cliches, filler, over-explained emotions and any moral or recap. Swap vague "
        "words for specific ones, break up long sentences, vary the rhythm, keep the best line. "
        f"Known problems to fix: {notes}. Keep {lo}-{hi} words. Output only the rewritten script.\n\n"
        f"SCRIPT:\n{text}",
        temperature=settings.llm.edit_temperature,
    )
    return clean_for_tts(out)


def pick_hook(llm: LLM, channel: Channel, text: str, settings: SimpleNamespace, plan: Plan | None = None) -> str:
    """Generate alternative opening lines and let the model choose the strongest; fall back to draft."""
    plan = plan or Plan()
    n = settings.script.hook_candidates
    style = f" Every option must follow this style: {plan.hook_instruction}" if plan.hook_instruction else ""
    try:
        reply = llm.chat(
            "You write scroll-stopping opening lines for short videos. Reply with JSON only.",
            f"Persona: {channel.persona}\nScript:\n{text}\n\nWrite {n} alternative opening lines (max 14 words "
            f"each, spoken, specific, no clickbait cliches).{style} Return them as a JSON array of strings.",
            temperature=1.0,
        )
        hooks = [h.strip() for h in extract_json(reply) if isinstance(h, str) and 3 <= word_count(h) <= 16]
        if not hooks:
            return ""
        numbered = "\n".join(f"{i}: {h}" for i, h in enumerate(hooks))
        pick = llm.chat(
            "You judge hooks by whether a stranger would stop scrolling. Reply with JSON only.",
            f"Choose the strongest opening line.\n{numbered}\nReturn {{\"index\": <number>}}.",
            temperature=0.2,
        )
        idx = int(extract_json(pick)["index"])
        return hooks[idx] if 0 <= idx < len(hooks) else hooks[0]
    except Exception as exc:  # hook polishing is optional
        log.warning("hook selection skipped: %s", exc)
        return ""


def apply_hook(text: str, hook: str) -> str:
    if not hook:
        return text
    sentences = split_sentences(text)
    rest = sentences[1:] if len(sentences) > 1 else []
    return " ".join([hook.rstrip() if hook.rstrip()[-1] in ".!?" else hook.rstrip() + ".", *rest])


def make_caption(llm: LLM, channel: Channel, text: str) -> str:
    try:
        cap = llm.chat(
            "You write short, natural TikTok captions. Plain text only.",
            f"Write one caption (max 90 characters, no hashtags, no emojis) for this script:\n{text}",
            temperature=0.7,
            max_tokens=80,
        ).strip().strip('"')
        return cap[:100] if cap else split_sentences(text)[0][:100]
    except Exception:
        return split_sentences(text)[0][:100]


def generate_script(
    llm: LLM, channel: Channel, store: Store, settings: SimpleNamespace, examples: list[str],
    plan: Plan | None = None,
) -> ScriptResult:
    plan = plan or Plan()
    lo, hi = channel.target_words
    best: tuple[float, str, str, AiScore] | None = None
    for attempt in range(settings.script.max_regenerations + 1):
        premise = pick_premise(llm, channel, store, settings, plan)
        for _ in range(settings.script.candidates):
            text = draft(llm, channel, premise, examples, settings, plan)
            s = ai_score(text, channel.extra_banned)
            text = edit(llm, channel, text, s.reasons, settings, plan)
            text = apply_hook(text, pick_hook(llm, channel, text, settings, plan))
            s = ai_score(text, channel.extra_banned)
            words = word_count(text)
            penalty = 0.0 if lo - 15 <= words <= hi + 15 else 0.3
            total = s.score + penalty
            log.info("candidate: %d words, ai_score=%.2f (%s)", words, s.score, "; ".join(s.reasons) or "clean")
            if best is None or total < best[0]:
                best = (total, premise, text, s)
        if best and best[0] <= settings.gates.max_ai_score:
            break
        log.info("attempt %d did not clear the AI-sounding threshold; regenerating", attempt + 1)
    assert best is not None
    _, premise, text, s = best
    store.add_premise(channel.name, premise)
    hook = (split_sentences(text) or [""])[0]
    return ScriptResult(premise=premise, text=text, caption=make_caption(llm, channel, text), hook=hook, score=s)
