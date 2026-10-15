"""Load scene timings from JSON or SRT.

Accepted JSON shapes, because every project invents its own:
  [{"id": "e01", "start": 0.0, "end": 12.5}, ...]
  {"scenes": [{"id": ..., "start": ..., "end": ...}], "total": 1082.1}
  {"e01": [0.0, 12.5], "e02": [12.5, 30.0]}
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from .plan import SceneSpan


def _norm(seq) -> list[SceneSpan]:
    out = []
    for i, s in enumerate(seq):
        sid = str(s.get("id", f"s{i}"))
        start = float(s.get("start", 0.0))
        end = float(s.get("end", start + float(s.get("dur", 0.0))))
        out.append(SceneSpan(sid, start, end))
    return out


def load_timings(path: str | Path) -> list[SceneSpan]:
    """Read scene spans from a .json or .srt file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".srt":
        return parse_srt(text)
    data = json.loads(text)
    if isinstance(data, list):
        return _norm(data)
    if isinstance(data, dict):
        if "scenes" in data:
            return _norm(data["scenes"])
        # {"id": [start, end], ...}
        spans = []
        for sid, v in data.items():
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                spans.append(SceneSpan(str(sid), float(v[0]), float(v[1])))
        if spans:
            return sorted(spans, key=lambda s: s.start)
    raise ValueError(f"unrecognised timings shape in {p}")


_SRT_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _secs(t: str) -> float:
    m = _SRT_TIME.search(t)
    if not m:
        raise ValueError(f"bad SRT timestamp: {t!r}")
    h, mi, s, ms = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def parse_srt(text: str) -> list[SceneSpan]:
    """One SceneSpan per subtitle cue, id = the cue number.

    Cue boundaries are a reasonable proxy for scene boundaries, which is what makes
    dubfit usable on material that has subtitles but no machine-readable timings.
    """
    spans: list[SceneSpan] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        idx = lines[0].strip()
        if "-->" not in lines[1]:
            continue
        a, b = lines[1].split("-->")
        spans.append(SceneSpan(idx, _secs(a), _secs(b)))
    if not spans:
        raise ValueError("no cues found in SRT")
    return spans
