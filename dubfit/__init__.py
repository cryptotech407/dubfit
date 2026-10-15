"""dubfit -- fit dubbed narration to a video scene by scene.

The problem: a translation is never the same length as the original. Stretch the whole
track by one constant ratio and the error accumulates -- by the end of a 45-minute film
you are seconds out of sync, and the stretch is audible.

dubfit fits per scene instead, capping the speed ratio and carrying the residual drift
forward, so no single scene is ever squeezed into sounding rushed and the accumulated
error never compounds.
"""
from .plan import FitPlan, SceneSpan, plan_fit
from .timings import load_timings, parse_srt

__version__ = "0.1.0"
__all__ = ["FitPlan", "SceneSpan", "plan_fit", "load_timings", "parse_srt"]
