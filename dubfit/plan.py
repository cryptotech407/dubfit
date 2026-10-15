"""The planner: pure logic, no ffmpeg.

This is the part worth testing, so it is deliberately free of I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SceneSpan:
    id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Slice:
    """One scene's piece of the output."""
    index: int
    scene_id: str
    src_start: float
    src_end: float
    speed: float          # atempo factor; >1 means sped up
    out_samples: int      # exact output length, in samples


@dataclass
class FitPlan:
    slices: list[Slice]
    sample_rate: int = 48000
    target_total: float = 0.0
    source_total: float = 0.0
    max_drift: float = 0.0
    worst_scene: str = ""
    drift: list[tuple[float, str]] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return sum(s.out_samples for s in self.slices) / self.sample_rate

    @property
    def speeds(self) -> list[float]:
        return [s.speed for s in self.slices]

    def summary(self) -> str:
        sp = self.speeds or [1.0]
        return (f"{len(self.slices)} scenes | out {self.total_seconds:.2f}s vs target "
                f"{self.target_total:.2f}s | speed {min(sp):.3f}-{max(sp):.3f} | "
                f"max drift {self.max_drift:+.2f}s ({self.worst_scene})")


def _bounds(spans: list[SceneSpan]) -> list[float]:
    """Scene start times, plus the final end."""
    b = [s.start for s in spans]
    b[0] = 0.0
    b.append(spans[-1].end)
    return b


def plan_fit(source: list[SceneSpan], target: list[SceneSpan], *,
             source_duration: float | None = None, sample_rate: int = 48000,
             min_speed: float = 0.90, max_speed: float = 1.12,
             last_speed_cap: float = 1.6) -> FitPlan:
    """Plan how to fit `source` narration onto `target` scene boundaries.

    `source` and `target` must have identical scene ids in the same order -- if they do
    not, the two timing files describe different cuts and fitting would silently produce
    nonsense. That is asserted here rather than downstream.

    Per scene:
      available = target_end - output_so_far
      speed     = clamp(source_scene_len / available, min_speed, max_speed)
      out_len   = source_scene_len / speed
    The residual (`out_len - target_scene_len`) is carried into the next scene's
    `available`, which is what stops drift accumulating.

    The final scene is handled differently: it absorbs whatever remains so the output
    lands exactly on the target length, with a looser cap.
    """
    if len(source) != len(target):
        raise ValueError(f"scene count differs: source {len(source)}, target {len(target)}")
    if [s.id for s in source] != [s.id for s in target]:
        bad = next(i for i, (a, b) in enumerate(zip(source, target)) if a.id != b.id)
        raise ValueError(
            f"scene ids differ at index {bad}: source {source[bad].id!r} vs "
            f"target {target[bad].id!r}. The timing files describe different cuts.")

    src_dur = source_duration if source_duration is not None else source[-1].end
    sb, tb = _bounds(source), _bounds(target)
    # The SOURCE's final bound is replaced by the real audio length: timings can disagree
    # with the file (a trailing pause, a re-export), and the file is what actually exists.
    # Getting this backwards silently shifts the whole tail -- caught by a synthetic test.
    sb[-1] = src_dur

    t_total = target[-1].end
    slices: list[Slice] = []
    drift: list[tuple[float, str]] = []
    out = 0.0
    n = len(source)

    for i in range(n):
        src_start, src_end = sb[i], sb[i + 1]
        seg = src_end - src_start
        is_last = i == n - 1
        available = tb[i + 1] - out
        speed = seg / available if available > 0.5 else max_speed

        if is_last:
            speed = min(last_speed_cap, max(0.7, speed))
            samples = round((t_total - out) * sample_rate)
        else:
            speed = min(max_speed, max(min_speed, speed))
            samples = round(seg / speed * sample_rate)

        out += samples / sample_rate
        drift.append((round(out - tb[i + 1], 3), source[i].id))
        slices.append(Slice(i, source[i].id, src_start, src_end, round(speed, 6), samples))

    worst = max(drift, key=lambda d: abs(d[0])) if drift else (0.0, "")
    return FitPlan(slices=slices, sample_rate=sample_rate, target_total=t_total,
                   source_total=src_dur, max_drift=worst[0], worst_scene=worst[1],
                   drift=drift)
