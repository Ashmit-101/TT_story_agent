"""Write the finished video plus everything needed for the manual upload step."""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from .config import Channel
from .gates import Gate
from .learn.plan import Plan


def slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n] or "video"


def write_package(
    out_root: Path, channel: Channel, caption: str, script: str, premise: str, video: Path, ass: Path,
    gates: list[Gate], ai_score: float, model: str, exp_id: str = "", plan: Plan | None = None,
    duration_s: float = 0.0,
) -> Path:
    plan = plan or Plan()
    stamp = time.strftime("%Y-%m-%d")
    folder = out_root / stamp / f"{channel.name}-{exp_id or int(time.time()) % 100000}-{slug(caption, 30)}"
    folder.mkdir(parents=True, exist_ok=True)
    passed = all(g.passed for g in gates)
    shutil.copy2(video, folder / "video.mp4")
    shutil.copy2(ass, folder / "captions.ass")
    (folder / "script.txt").write_text(script + "\n")
    tags = " ".join(channel.hashtags)
    meta = {
        "channel": channel.name, "caption": caption, "hashtags": channel.hashtags, "premise": premise,
        "ai_generated_label_required": True, "passed_all_gates": passed, "ai_score": round(ai_score, 3),
        "experiment": {"id": exp_id, "hook_style": plan.hook_style, "topic": plan.topic, "duration_s": round(duration_s, 1)},
        "gates": [g.__dict__ for g in gates], "llm_model": model, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (folder / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    status = "READY" if passed else "FAILED GATES - review before posting"
    (folder / "POST_CHECKLIST.md").write_text(
        f"# {status}\n\nVideo ID: {exp_id}\n\nCaption: {caption} {tags}\n\n"
        "- [ ] Watch the video once (voice, captions, anything off-brand or inaccurate)\n"
        "- [ ] Turn on TikTok's 'AI-generated content' label when uploading\n"
        "- [ ] Paste the caption and hashtags above\n"
        "- [ ] Comments/Duet/Stitch settings as you prefer; check music/licence for any added sound\n"
        "- [ ] 24-48h after posting, run `ttagent log` and enter views / avg watch time / shares / saves\n"
    )
    return folder
