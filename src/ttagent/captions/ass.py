"""Build word-by-word highlighted ASS subtitles (the 'karaoke' caption style)."""
from __future__ import annotations

from .align import Word

# ASS colours are &HBBGGRR&. Active word = yellow, others = white.
ACTIVE, NORMAL = "&H0000E6FF&", "&H00FFFFFF&"


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def group_words(words: list[Word], max_words: int = 3) -> list[list[Word]]:
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or w.text[-1] in ".!?,;:":
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(words: list[Word], width: int, height: int, font: str = "Arial", size: int = 84) -> str:
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
        "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,"
        "MarginV,Encoding\n"
        f"Style: Default,{font},{size},{NORMAL},{NORMAL},&H00000000&,&H64000000&,-1,0,0,0,100,100,0,0,1,6,2,5,"
        "80,80,0,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    lines = []
    for group in group_words(words):
        for i, active in enumerate(group):
            start = active.start
            end = group[i + 1].start if i + 1 < len(group) else active.end
            if end <= start:
                end = start + 0.05
            parts = []
            for j, w in enumerate(group):
                colour = ACTIVE if j == i else NORMAL
                parts.append(f"{{\\c{colour}}}{_esc(w.text.upper())}")
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"
