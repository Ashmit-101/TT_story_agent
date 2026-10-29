"""Configuration loading. Secrets come only from environment variables, never from files in the repo."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml


def _ns(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in value.items()})
    return value


def load_settings(root: Path) -> SimpleNamespace:
    raw = yaml.safe_load((root / "config" / "settings.yaml").read_text())
    env = os.environ
    raw["llm"]["base_url"] = env.get("TTAGENT_LLM_BASE_URL", raw["llm"]["base_url"])
    raw["llm"]["model"] = env.get("TTAGENT_LLM_MODEL", raw["llm"]["model"])
    raw["llm"]["api_key"] = env.get("TTAGENT_LLM_API_KEY", "")
    settings = _ns(raw)
    settings.root = root
    return settings


@dataclass
class Channel:
    name: str
    footage_tag: str
    voice: str
    target_words: tuple[int, int]
    hashtags: list[str]
    persona: str
    premise_brief: str
    style_rules: list[str]
    extra_banned: list[str] = field(default_factory=list)
    hook_styles: dict[str, str] = field(default_factory=dict)
    topics: dict[str, str] = field(default_factory=dict)


def load_channel(root: Path, name: str) -> Channel:
    path = root / "config" / "channels" / f"{name}.yaml"
    if not path.exists():
        raise SystemExit(f"Unknown channel '{name}'. Expected {path}")
    raw = yaml.safe_load(path.read_text())
    lo, hi = raw["target_words"]
    return Channel(
        name=raw["name"],
        footage_tag=raw["footage_tag"],
        voice=raw["voice"],
        target_words=(int(lo), int(hi)),
        hashtags=list(raw["hashtags"]),
        persona=raw["persona"].strip(),
        premise_brief=raw["premise_brief"].strip(),
        style_rules=list(raw["style_rules"]),
        extra_banned=list(raw.get("extra_banned", [])),
        hook_styles=dict(raw.get("hook_styles", {})),
        topics=dict(raw.get("topics", {})),
    )


def load_style_examples(root: Path, settings: SimpleNamespace, channel: Channel) -> list[str]:
    path = root / settings.paths.style_refs_dir / f"{channel.name}.txt"
    if not path.exists():
        return []
    return [chunk.strip() for chunk in path.read_text().split("\n---\n") if chunk.strip()][:5]
