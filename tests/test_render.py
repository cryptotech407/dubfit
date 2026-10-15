import shutil
import subprocess

import pytest

from dubfit import SceneSpan, plan_fit
from dubfit.render import duration, render, to_aac

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def tone(path, seconds, freq=440):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={freq}:duration={seconds}",
                    "-ar", "48000", "-ac", "2", str(path)], check=True)
    return path


def test_render_produces_the_target_length(tmp_path):
    src = tone(tmp_path / "vo.wav", 30.0)
    spans_src = [SceneSpan(f"s{i}", i * 10.0, (i + 1) * 10.0) for i in range(3)]
    spans_tgt = [SceneSpan(f"s{i}", i * 9.0, (i + 1) * 9.0) for i in range(3)]
    plan = plan_fit(spans_src, spans_tgt)
    out = tmp_path / "fitted.wav"
    res = render(src, plan, out)
    assert res["ok"], res
    assert abs(res["seconds"] - 27.0) < 0.5


def test_to_aac_leaves_headroom(tmp_path):
    src = tone(tmp_path / "vo.wav", 5.0)
    plan = plan_fit([SceneSpan("a", 0, 5)], [SceneSpan("a", 0, 5)])
    wav = tmp_path / "f.wav"
    render(src, plan, wav)
    m4a = tmp_path / "f.m4a"
    to_aac(wav, m4a, headroom_db=-1.5)
    assert duration(m4a) > 0
    # peak must not be sitting at 0 dBFS
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(m4a), "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    peak = [l for l in err.splitlines() if "max_volume" in l]
    assert peak and float(peak[0].split()[-2]) < -1.0
