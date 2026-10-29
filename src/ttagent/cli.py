from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import httpx

from .captions.align import Aligner
from .config import load_channel, load_settings
from .db import Store
from .learn.entry import import_csv, log_interactive, write_template
from .learn.report import build_report
from .llm.client import OpenAICompatClient
from .pipeline import make_video
from .tts.kokoro import KokoroTTS
from .video.render import list_footage


def _root() -> Path:
    return Path.cwd()


def cmd_run(args: argparse.Namespace) -> int:
    root = _root()
    settings = load_settings(root)
    store = Store(root / settings.paths.data_dir / "state.db")
    llm = OpenAICompatClient(settings.llm.base_url, settings.llm.model, settings.llm.api_key, settings.llm.timeout_s)
    tts = KokoroTTS(root / settings.voice.model_path, root / settings.voice.voices_path, settings.voice.speed)
    aligner = Aligner(settings.align.engine, settings.align.model, settings.align.compute_type)
    failures = 0
    for channel_name in args.channel:
        channel = load_channel(root, channel_name)
        for _ in range(args.count):
            try:
                res = make_video(root, settings, channel, llm, tts, aligner, store)
                print(("OK   " if res.passed else "FAIL ") + str(res.folder))
                failures += 0 if res.passed else 1
            except Exception as exc:  # one bad run must not stop a scheduled batch
                logging.exception("run failed: %s", exc)
                failures += 1
    return 1 if failures and args.strict else 0


def cmd_log(args: argparse.Namespace) -> int:
    root = _root()
    settings = load_settings(root)
    store = Store(root / settings.paths.data_dir / "state.db")
    hours = settings.learn.min_hours_before_logging
    if args.template:
        n = write_template(store, hours, Path(args.template))
        print(f"Wrote {n} pending videos to {args.template}. Fill in the number columns, then run `ttagent log --csv`.")
    elif args.csv:
        done, errors = import_csv(store, Path(args.csv))
        print(f"Imported {done} results.")
        for e in errors:
            print("  !!", e)
        return 1 if errors else 0
    else:
        print(f"Logged {log_interactive(store, hours)} results.")
    return 0


def cmd_report(_: argparse.Namespace) -> int:
    root = _root()
    settings = load_settings(root)
    store = Store(root / settings.paths.data_dir / "state.db")
    print(build_report(store, ["horror", "facts"], settings))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    root = _root()
    settings = load_settings(root)
    ok = True

    def check(name: str, good: bool, hint: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"[{'ok' if good else '!!'}] {name}" + ("" if good else f"  -> {hint}"))

    check("ffmpeg", bool(shutil.which("ffmpeg")), "brew install ffmpeg")
    try:
        r = httpx.get(settings.llm.base_url.rstrip("/") + "/models", timeout=5)
        models = [m["id"] for m in r.json().get("data", [])]
        check(f"LLM server reachable ({settings.llm.base_url})", True)
        check(f"model '{settings.llm.model}' pulled", settings.llm.model in models, f"ollama pull {settings.llm.model}")
    except Exception:
        check("LLM server reachable", False, "install Ollama and run `ollama serve`")
    check("kokoro model", (root / settings.voice.model_path).exists(),
          "download kokoro-v1.0.onnx and voices-v1.0.bin from the kokoro-onnx releases into ./models")
    check("kokoro voices", (root / settings.voice.voices_path).exists(), "see above")
    for tag in ("horror", "facts"):
        n = len(list_footage(root / settings.paths.footage_dir, tag))
        check(f"footage for '{tag}' ({n} clips)", n > 0, f"add licensed clips to assets/footage/{tag}/")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="ttagent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="generate videos")
    run.add_argument("--channel", nargs="+", default=["horror", "facts"])
    run.add_argument("--count", type=int, default=1, help="videos per channel")
    run.add_argument("--strict", action="store_true", help="non-zero exit if any video fails its gates")
    run.set_defaults(fn=cmd_run)
    lg = sub.add_parser("log", help="enter TikTok results for videos you posted")
    lg.add_argument("--template", help="write a CSV of pending videos to fill in")
    lg.add_argument("--csv", help="import a filled-in CSV")
    lg.set_defaults(fn=cmd_log)
    rp = sub.add_parser("report", help="show which hook styles and topics are performing")
    rp.set_defaults(fn=cmd_report)
    doc = sub.add_parser("doctor", help="check the environment")
    doc.set_defaults(fn=cmd_doctor)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(args.fn(args))
