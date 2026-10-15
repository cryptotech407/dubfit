"""Render a FitPlan with ffmpeg: cut each source scene, stretch it, concatenate.

`-ss`/`-to` go BEFORE `-i`. Placed after, they become output options and trim the wrong
timeline -- which produced a 9-second file from a 27-second plan before this was fixed.
For audio, input seeking is sample-accurate; there are no keyframes to land between.
"""
from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path

from .plan import FitPlan


class FFmpegMissing(RuntimeError):
    pass


def _require_ffmpeg() -> None:
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe) is None:
            raise FFmpegMissing(f"{exe} not found on PATH")


def duration(path: str | Path) -> float:
    _require_ffmpeg()
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0.0)


def render(source_audio: str | Path, plan: FitPlan, out_path: str | Path,
           *, sample_rate: int | None = None) -> dict:
    """Produce a single audio file of exactly `plan.target_total` seconds."""
    _require_ffmpeg()
    sr = sample_rate or plan.sample_rate
    out = Path(out_path)
    tmp = Path(tempfile.mkdtemp(prefix="dubfit-"))
    parts: list[Path] = []
    try:
        for sl in plan.slices:
            part = tmp / f"{sl.index:04d}.wav"
            subprocess.run(
                # -ss/-to BEFORE -i is input seeking. After -i they are OUTPUT options and
                # would trim the output timeline instead of the input -- silent misalignment.
                # Audio has no keyframes, so input seeking is sample-accurate here.
                ["ffmpeg", "-v", "error", "-y",
                 "-ss", f"{sl.src_start:.4f}", "-to", f"{sl.src_end:.4f}",
                 "-i", str(source_audio),
                 "-af", f"aresample={sr},atempo={sl.speed:.6f},apad,"
                        f"atrim=end_sample={sl.out_samples}",
                 "-ar", str(sr), "-ac", "2", str(part)], check=True)
            parts.append(part)

        listing = tmp / "concat.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-c:a", "pcm_s16le", str(out)], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    real = duration(out)
    return {
        "output": str(out),
        "seconds": round(real, 3),
        "target_seconds": round(plan.target_total, 3),
        "delta": round(real - plan.target_total, 3),
        "max_drift": plan.max_drift,
        "worst_scene": plan.worst_scene,
        "ok": abs(real - plan.target_total) < 1.0,
    }


def to_aac(wav: str | Path, out: str | Path, bitrate: str = "192k",
           headroom_db: float = -1.5) -> str:
    """Encode for upload. `headroom_db` guards against AAC peak overshoot -- a source
    peaking at -4 dBFS can leave the encoder at -0.3 and clip on some decoders."""
    _require_ffmpeg()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav),
                    "-af", f"volume={headroom_db}dB",
                    "-c:a", "aac", "-b:a", bitrate, "-ar", "48000", "-ac", "2",
                    str(out)], check=True)
    return str(out)
