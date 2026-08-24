from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .core import cafa_score_row, grouped_summaries, read_csv, write_csv


def _fmt(v):
    if v in (None, ""):
        return "-"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def cmd_score(args):
    rows = read_csv(args.input)
    scored = [cafa_score_row(r) for r in rows]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    write_csv(outdir / "scored_trials.csv", scored)
    summary = grouped_summaries(scored, args.group_by)
    write_csv(outdir / "summary.csv", summary)
    overall = summary[-1]
    (outdir / "summary.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    report = [
        "# CAFA-IVR Results",
        "",
        f"Trials: **{overall['n']}**",
        f"Mean WER: **{_fmt(overall.get('wer'))}**",
        f"Intent/task accuracy: **{_fmt(overall.get('intent_accuracy'))}**",
        f"Text-control accuracy: **{_fmt(overall.get('text_control_accuracy'))}**",
        f"ASR-IFR: **{_fmt(overall.get('asr_ifr'))}**",
        f"CEER: **{_fmt(overall.get('ceer'))}**",
        f"CIER: **{_fmt(overall.get('cier'))}**",
        "",
        "ASR-IFR counts trials where the reference-text control passes but the audio-path task fails.",
    ]
    (outdir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(overall, indent=2))


def _overall(path):
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"{path}: summary contains no data rows")
    for r in rows:
        if str(r.get("condition", r.get("group", ""))).upper() == "OVERALL":
            return r
    return rows[-1]


def _metric_value(row, metric, source):
    raw = row.get(metric)
    if raw in (None, ""):
        raise ValueError(f"{source}: required metric '{metric}' is missing")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source}: required metric '{metric}' is not numeric: {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{source}: required metric '{metric}' must be finite: {raw!r}")
    return value


def cmd_compare(args):
    try:
        b = _overall(args.baseline)
        c = _overall(args.candidate)
    except (OSError, UnicodeError, ValueError) as exc:
        print("CAFA-IVR release gate: FAIL")
        print(f" - invalid summary input: {exc}")
        raise SystemExit(2) from exc

    rules = [
        ("asr_ifr", args.max_asr_ifr_delta),
        ("ceer", None if getattr(args, "no_ceer_gate", False) else args.max_ceer_delta),
        ("wer", args.max_wer_delta),
    ]
    checks = []
    invalid = []
    for metric, limit in rules:
        if limit is None:
            continue
        try:
            baseline_value = _metric_value(b, metric, args.baseline)
            candidate_value = _metric_value(c, metric, args.candidate)
        except ValueError as exc:
            invalid.append(str(exc))
            continue
        checks.append((metric, baseline_value, candidate_value, limit))

    if invalid:
        print("CAFA-IVR release gate: FAIL")
        for error in invalid:
            print(f" - invalid summary input: {error}")
        raise SystemExit(2)

    failed = []
    for metric, baseline_value, candidate_value, limit in checks:
        delta = candidate_value - baseline_value
        print(
            f"{metric}: baseline={baseline_value} candidate={candidate_value} "
            f"delta={delta:.4f} limit={limit:.4f}"
        )
        if delta > limit:
            failed.append((metric, delta, limit))
    if failed:
        print("CAFA-IVR release gate: FAIL")
        for metric, delta, limit in failed:
            print(f" - {metric} regressed by {delta:.4f} > {limit:.4f}")
        raise SystemExit(2)
    print("CAFA-IVR release gate: PASS")


def build_parser():
    p = argparse.ArgumentParser(prog="cafa-ivr", description="CAFA-IVR reference scorer")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("score", help="score trial-level ASR/NLU results")
    s.add_argument("--input", required=True, help="CSV containing reference and observed outputs")
    s.add_argument("--out", default="cafa_out")
    s.add_argument("--group-by", default="condition")
    s.set_defaults(func=cmd_score)

    c = sub.add_parser("compare", help="apply simple regression gates to two CAFA summary CSVs")
    c.add_argument("--baseline", required=True)
    c.add_argument("--candidate", required=True)
    c.add_argument("--max-asr-ifr-delta", type=float, default=0.02)
    c.add_argument("--max-ceer-delta", type=float, default=0.01)
    c.add_argument(
        "--no-ceer-gate",
        action="store_true",
        help="explicitly disable CEER comparison for a dataset without critical-entity annotations",
    )
    c.add_argument("--max-wer-delta", type=float, default=None)
    c.set_defaults(func=cmd_compare)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)
