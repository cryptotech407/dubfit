# dubfit

[![PyPI](https://img.shields.io/pypi/v/dubfit.svg)](https://pypi.org/project/dubfit/)
[![Python](https://img.shields.io/pypi/pyversions/dubfit.svg)](https://pypi.org/project/dubfit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/cryptotech407/dubfit/actions/workflows/publish.yml/badge.svg)](https://github.com/cryptotech407/dubfit/actions/workflows/publish.yml)

**Fit dubbed narration to a video scene by scene** — capping the speed change and carrying
the residual drift forward, so timing never slides and no scene is ever squeezed into
sounding rushed.

```
pip install dubfit        # ffmpeg required on PATH
dubfit plan  es.json en.json      # show the fit, change nothing
dubfit fit   es.json en.json narration_es.wav out.wav --aac out.m4a
```

## The problem

A translation is never the same length as the original. The usual approach is to stretch
the whole track by one constant ratio:

```
60 seconds of narration into a 45 second scene  ->  atempo=1.333
```

That has two failures. **Every scene gets the same stretch even when only one needs it**,
and the error **accumulates** — a constant ratio applied across a 45-minute film can end
seconds out of sync, and the stretch is audible throughout.

## What dubfit does instead

It works **scene by scene**, and per scene:

```
available = target_scene_end - output_so_far
speed     = clamp(source_scene_len / available, 0.90, 1.12)
out_len   = source_scene_len / speed
```

The key part is `output_so_far`. **The residual from each scene is carried into the next
scene's `available`**, so a scene that had to overrun is corrected by its neighbours
instead of pushing everything after it late. No single scene is ever stretched past the
window, and the final scene absorbs whatever remains so the file lands exactly on the
target length.

## Measured on real work

Three history documentaries, Spanish narration fitted to English picture. The scratch script
this was extracted from produced these, and `dubfit` reproduces **the same drift and the
same worst scene**:

| Film | Scenes | Length | Max drift | Worst scene |
|---|---|---|---|---|
| Al-Andalus | 53 | 43:52 | **-1.21s** | `s19_treaty` |
| Sefarad | 44 | 32:44 | **-0.82s** | `s_crescas` |
| Crusades | 59 | 45:50 | **+1.46s** | `s_after` |

Under a second and a half of drift across 45 minutes, with every scene inside the speed
window. That is the whole point.

## When a scene cannot be fitted

If one scene is far too long — a paragraph in the translation with no counterpart in the
original — it **cannot** fit inside the window. dubfit's contract in that case is:

1. **Clamp, do not rush.** The scene gets `max_speed`, not the 2.0x it "needed"
2. **Absorb in the remainder, do not compound.** The overrun is carried forward
3. **Say so.** `max_drift` and `worst_scene` name the scene and the size of the problem

```python
p = plan_fit(source, target, max_speed=1.12)
if abs(p.max_drift) > 3.0:
    print(f"cannot fit {p.worst_scene} ({p.max_drift:+.2f}s) -- consider re-recording it")
```

**Silent drift is the failure mode this avoids.** A tool that hides a 7-second overrun is
worse than one that refuses.

## Timings

Two files, one per cut. Ids must match exactly, in order — if they don't, the files describe
different cuts and `plan_fit` raises rather than producing plausible nonsense.

```json
[{"id": "s01", "start": 0.0, "end": 12.5}, {"id": "s02", "start": 12.5, "end": 30.0}]
```

Also accepted: `{"scenes": [...]}`, `{"s01": [0, 12.5], ...}`, a `dur` key instead of `end`,
and **SRT** (one span per cue, so you can work from subtitles without machine-readable
scene data).

## API

```python
from dubfit import load_timings, plan_fit
from dubfit.render import render, to_aac

source = load_timings("narration_es.json")   # the dub
target = load_timings("picture_en.json")     # the video being fitted to

plan = plan_fit(source, target, min_speed=0.90, max_speed=1.12)
print(plan.summary())

render("narration_es.wav", plan, "fitted.wav")
to_aac("fitted.wav", "upload.m4a")
```

`plan_fit` is **pure logic with no ffmpeg** — it returns `Slice`s with exact output sample
counts, so you can inspect, test and assert on the fit without rendering anything. The
`tests` run without ffmpeg for that reason, apart from three rendering tests.

## Two traps baked into the code

**`-ss`/`-to` must go BEFORE `-i`.** Placed after, they are *output* options and trim the
wrong timeline — which produced a 9-second file from a 27-second plan before it was caught
by a test. For audio there are no keyframes, so input seeking is sample-accurate.

**AAC overshoots peaks.** A source peaking at -4 dBFS can leave the encoder at -0.3 dBFS and
clip on some decoders. `to_aac()` applies -1.5 dB of headroom by default.

## Status

Alpha. The planner is exercised by 18 tests and validated against three real films. The
renderer is exercised by 3 tests with synthetic tones — **it has not been run on a large
real project since extraction**, though the scratch version it came from produced the
figures above.

## Roadmap

- **Spread the overrun instead of dumping it on the final scene.** Today an unfittable
  scene is absorbed at the end; distributing it across the remaining scenes would sound
  better. The clamp-and-report contract should not change.
- **Subtitle-aware splitting**, so a scene can be broken at a sentence boundary rather
  than only at scene boundaries.
- **`--dry-run` audio previews** — render one badly-fitted scene so you can hear the problem
  rather than reading a number.

Contributions welcome. Issues labelled `good first issue` are scoped to be self-contained.

## Licence

MIT.
