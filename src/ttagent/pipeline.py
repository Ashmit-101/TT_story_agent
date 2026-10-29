"""End-to-end orchestration for one video. Every dependency is injectable so stages can be tested in isolation."""
from __future__ import annotations

import logging
import random
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .captions.align import Aligner
from .captions.ass import build_ass
from .config import Channel, load_style_examples
from .db import Store
from .gates import Gate, run_gates
from .learn.select import choose_plan
from .llm.client import LLM
from .package import write_package
from .script.chain import generate_script
from .script.filters import clean_for_tts
from .tts.kokoro import TTS
from .video.render import list_footage, render

log = logging.getLogger("ttagent.pipeline")


@dataclass
class RunResult:
    folder: Path
    passed: bool
    gates: list[Gate]
    exp_id: str = ""


def make_video(
    root: Path, settings: SimpleNamespace, channel: Channel, llm: LLM, tts: TTS, aligner: Aligner, store: Store,
    rng: random.Random | None = None,
) -> RunResult:
    examples = load_style_examples(root, settings, channel)
    rng = rng or random.Random()
    plan = choose_plan(store, channel, settings, rng)
    log.info("[%s] generating script (hook=%s, topic=%s)", channel.name, plan.hook_style or "-", plan.topic or "-")
    result = generate_script(llm, channel, store, settings, examples, plan)
    spoken = clean_for_tts(result.text)

    with tempfile.TemporaryDirectory(prefix="ttagent-") as tmp_s:
        tmp = Path(tmp_s)
        log.info("synthesising voice (%s)", channel.voice)
        wav = tmp / "voice.wav"
        duration = tts.synthesize(spoken, channel.voice, wav)

        log.info("aligning captions")
        words = aligner.align(spoken, wav, duration)
        ass = tmp / "captions.ass"
        ass.write_text(build_ass(words, settings.video.width, settings.video.height))

        footage_files = list_footage(root / settings.paths.footage_dir, channel.footage_tag)
        if not footage_files:
            log.warning("no footage in assets/footage/%s - using a placeholder background", channel.footage_tag)
        footage = rng.choice(footage_files) if footage_files else None

        log.info("rendering")
        video = render(wav, ass, tmp / "video.mp4", settings, footage, rng)

        lo, hi = channel.target_words
        gates = run_gates(video, spoken, result.score.score, channel.extra_banned, lo, hi, settings)
        exp_id = secrets.token_hex(3)
        folder = write_package(
            root / settings.paths.output_dir, channel, result.caption, spoken, result.premise, video, ass, gates,
            result.score.score, settings.llm.model, exp_id=exp_id, plan=plan, duration_s=duration,
        )
    passed = all(g.passed for g in gates)
    store.add_experiment(
        id=exp_id, channel=channel.name, hook_style=plan.hook_style, topic=plan.topic, duration_s=duration,
        hook=result.hook, script=spoken, caption=result.caption, folder=str(folder), passed=passed,
        ai_score=result.score.score,
    )
    log.info("done: %s id=%s (%s)", folder, exp_id, "passed all gates" if passed else "FAILED gates")
    return RunResult(folder, passed, gates, exp_id)
