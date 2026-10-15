"""Command line:  python -m dubfit plan|fit <source timings> <target timings>"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from .plan import plan_fit
from .render import render, to_aac
from .timings import load_timings


def _load(a):
    src = load_timings(a.source_timings)
    tgt = load_timings(a.target_timings)
    return plan_fit(src, tgt, sample_rate=a.sample_rate,
                    min_speed=a.min_speed, max_speed=a.max_speed)


def cmd_plan(a):
    plan = _load(a)
    print(plan.summary())
    if a.json:
        print(json.dumps({"target_total": plan.target_total,
                          "slices": [vars(s) for s in plan.slices]}, indent=1))
    else:
        for d, sid in plan.drift[:10]:
            print(f"  {sid:<14} drift {d:+.3f}s")
    return 0 if abs(plan.max_drift) <= a.tolerance else 1


def cmd_fit(a):
    plan = _load(a)
    print(plan.summary())
    res = render(a.audio, plan, a.out)
    print(f"  wrote {res['output']}  {res['seconds']}s  delta {res['delta']:+.3f}s")
    if a.aac:
        to_aac(a.out, a.aac)
        print(f"  encoded {a.aac}")
    return 0 if res["ok"] and abs(plan.max_drift) <= a.tolerance else 1


def build_parser():
    p = argparse.ArgumentParser(prog="dubfit", description=__doc__)
    p.add_argument("--sample-rate", type=int, default=48000)
    p.add_argument("--min-speed", type=float, default=0.90,
                   help="slowest allowed atempo (default 0.90)")
    p.add_argument("--max-speed", type=float, default=1.12,
                   help="fastest allowed atempo before the final scene (default 1.12)")
    p.add_argument("--tolerance", type=float, default=3.0,
                   help="max acceptable per-scene drift in seconds (default 3.0)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("plan", help="show the fit without rendering")
    s.add_argument("source_timings"); s.add_argument("target_timings")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("fit", help="render the fitted audio")
    s.add_argument("source_timings"); s.add_argument("target_timings")
    s.add_argument("audio", help="the source narration to cut up")
    s.add_argument("out", help="output wav")
    s.add_argument("--aac", help="also encode an upload-ready m4a here")
    s.set_defaults(func=cmd_fit)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
