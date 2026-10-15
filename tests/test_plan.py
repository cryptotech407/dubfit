"""The planner is pure logic, so these tests need no ffmpeg."""
import pytest

from dubfit import SceneSpan, plan_fit


def mk(scene_len, n=5, offset=0.0):
    return [SceneSpan(f"s{i}", offset + i * scene_len, offset + (i + 1) * scene_len)
            for i in range(n)]


def test_uniform_expansion_uses_one_constant_speed():
    """A source uniformly 6% long should need one ratio and no drift anywhere."""
    p = plan_fit(mk(10.0), mk(9.4))
    assert p.max_drift == 0.0
    assert {round(s, 3) for s in p.speeds} == {1.064}


def test_output_lands_exactly_on_the_target_length():
    """Exact to within a single sample. The residual is round()-to-integer-samples, which
    at 48 kHz is under 21 microseconds -- not a drift.""" 
    for ratio in (0.85, 0.94, 1.0, 1.06, 1.30):
        p = plan_fit(mk(10.0), mk(10.0 / ratio))
        assert abs(p.total_seconds - p.target_total) < 1.0 / p.sample_rate, (ratio, p.total_seconds)


def test_speeds_stay_inside_the_window_for_non_final_scenes():
    src = [SceneSpan("a", 0, 10), SceneSpan("b", 10, 42), SceneSpan("c", 42, 52)]
    tgt = [SceneSpan("a", 0, 8), SceneSpan("b", 8, 20), SceneSpan("c", 20, 30)]
    p = plan_fit(src, tgt, min_speed=0.9, max_speed=1.12)
    for sl in p.slices[:-1]:
        assert 0.9 <= sl.speed <= 1.12, sl


def test_an_unfittable_scene_is_clamped_and_REPORTED():
    """Scene b needs 2.0x but the window caps at 1.12, so it cannot fit.

    The contract is not "drift stays small" -- it is that the tool clamps rather than
    producing a rushed scene, still lands on the target length, and TELLS you which scene
    it could not fit and by how much. Silent drift is the failure mode to avoid.
    """
    src = [SceneSpan("a", 0, 10), SceneSpan("b", 10, 30), SceneSpan("c", 30, 40)]
    tgt = [SceneSpan("a", 0, 9), SceneSpan("b", 9, 19), SceneSpan("c", 19, 28)]
    p = plan_fit(src, tgt, max_speed=1.12)

    assert p.slices[1].speed == 1.12                 # clamped, not rushed to 2.0x
    assert p.slices[1].out_samples / 48000 > 17.0    # it overran by ~7.9s...
    assert p.max_drift > 3.0                         # ...and says so
    assert p.worst_scene == "b"
    assert abs(p.total_seconds - p.target_total) < 1e-3   # last scene absorbs the overrun
    # the overrun is carried into the remainder, not compounded per scene
    assert p.drift[1][0] == pytest.approx(7.857, abs=0.01)


def test_mismatched_ids_are_refused():
    """Different cuts must fail loudly -- fitting them would silently produce nonsense."""
    a = [SceneSpan("e01", 0, 5), SceneSpan("e02", 5, 10)]
    b = [SceneSpan("e01", 0, 5), SceneSpan("s99", 5, 10)]
    with pytest.raises(ValueError, match="scene ids differ"):
        plan_fit(a, b)


def test_mismatched_scene_counts_are_refused():
    with pytest.raises(ValueError, match="scene count differs"):
        plan_fit(mk(10, 4), mk(10, 5))


def test_extra_source_audio_beyond_the_timings_is_respected():
    """The real audio length overrides a trailing timings disagreement."""
    src = mk(10.0, 3)          # timings say 30s
    tgt = mk(10.0, 3)
    p = plan_fit(src, tgt, source_duration=33.0)
    assert p.source_total == 33.0
    assert abs(p.total_seconds - p.target_total) < 1e-6


def test_summary_is_human_readable():
    s = plan_fit(mk(10.0), mk(9.4)).summary()
    assert "scenes" in s and "max drift" in s
