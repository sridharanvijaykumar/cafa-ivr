from __future__ import annotations

import argparse
import json
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
    for r in rows:
        if str(r.get("condition", r.get("group", ""))).upper() == "OVERALL":
            return r
    return rows[-1]


def cmd_compare(args):
    b = _overall(args.baseline)
    c = _overall(args.candidate)
    rules = [
        ("asr_ifr", args.max_asr_ifr_delta),
        ("ceer", args.max_ceer_delta),
        ("wer", args.max_wer_delta),
    ]
    failed = []
    for metric, limit in rules:
        if limit is None:
            continue
        try:
            delta = float(c[metric]) - float(b[metric])
        except (KeyError, ValueError, TypeError):
            continue
        print(f"{metric}: baseline={b[metric]} candidate={c[metric]} delta={delta:.4f} limit={limit:.4f}")
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
    c.add_argument("--max-wer-delta", type=float, default=None)
    c.set_defaults(func=cmd_compare)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)
