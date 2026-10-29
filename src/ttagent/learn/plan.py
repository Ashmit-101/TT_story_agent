from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Plan:
    """The experiment variables chosen for one video."""
    hook_style: str = ""
    hook_instruction: str = ""
    topic: str = ""
    topic_desc: str = ""
    winners: list[str] = field(default_factory=list)   # opening lines of past top performers (style reference only)
