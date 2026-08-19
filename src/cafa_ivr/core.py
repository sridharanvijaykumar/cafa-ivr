from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CIER_WEIGHTS = {"L0": 0.0, "L1": 0.0, "L2": 0.25, "L3": 0.65, "L4": 1.0}


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "pass", "passed"}


def normalize_text(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def word_error_rate(reference: Any, hypothesis: Any) -> float:
    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else float(len(hyp))
    return _edit_distance(ref, hyp) / len(ref)


def _norm_entity_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    return normalize_text(v)


def _entity_multiset(raw: Any) -> Counter[tuple[str, str]]:
    if raw is None or raw == "" or (isinstance(raw, float) and math.isnan(raw)):
        return Counter()
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return Counter()
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return Counter({("value", _norm_entity_value(raw)): 1})
    if not isinstance(raw, dict):
        return Counter({("value", _norm_entity_value(raw)): 1})
    out: Counter[tuple[str, str]] = Counter()
    for key, values in raw.items():
        if not isinstance(values, list):
            values = [values]
        for value in values:
            out[(normalize_text(key), _norm_entity_value(value))] += 1
    return out


def critical_entity_error_rate(expected: Any, observed: Any) -> float | None:
    exp = _entity_multiset(expected)
    obs = _entity_multiset(observed)
    if not exp:
        return None
    missing = sum((exp - obs).values())
    extra = sum((obs - exp).values())
    return (missing + extra) / sum(exp.values())


def attribution(text_control_pass: Any, audio_task_success: Any) -> str:
    t = _bool(text_control_pass)
    a = _bool(audio_task_success)
    if t and a:
        return "HEALTHY"
    if t and not a:
        return "SPEECH_ATTRIBUTABLE"
    if not t and not a:
        return "DOWNSTREAM_OR_TEST"
    return "CONTEXT_OR_ORACLE"


def cafa_score_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    ref = row.get("reference_text", "")
    hyp = row.get("asr_transcript", "")
    out["wer"] = word_error_rate(ref, hyp)

    audio_success = row.get("audio_task_success")
    if audio_success in (None, ""):
        if row.get("intent_correct") not in (None, ""):
            audio_success = row.get("intent_correct")
        else:
            audio_success = normalize_text(row.get("expected_intent")) == normalize_text(row.get("predicted_intent"))
    out["audio_task_success"] = int(_bool(audio_success))
    out["text_control_pass"] = int(_bool(row.get("text_control_pass")))
    out["attribution"] = attribution(out["text_control_pass"], out["audio_task_success"])
    out["asr_ifr_contrib"] = int(out["attribution"] == "SPEECH_ATTRIBUTABLE")

    ceer = critical_entity_error_rate(row.get("expected_entities_json"), row.get("predicted_entities_json"))
    out["ceer"] = "" if ceer is None else ceer

    impact = str(row.get("impact_level", "")).strip().upper()
    out["cier_contrib"] = CIER_WEIGHTS.get(impact, "")
    return out


def mean(values: Iterable[float]) -> float | None:
    vals = [float(x) for x in values if x not in (None, "") and not (isinstance(x, float) and math.isnan(x))]
    return sum(vals) / len(vals) if vals else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0}
    intent_acc = mean(float(r["audio_task_success"]) for r in rows)
    text_acc = mean(float(r["text_control_pass"]) for r in rows)
    return {
        "n": n,
        "wer": mean(r.get("wer") for r in rows),
        "intent_accuracy": intent_acc,
        "text_control_accuracy": text_acc,
        "asr_ifr": mean(r.get("asr_ifr_contrib") for r in rows),
        "ceer": mean(r.get("ceer") for r in rows),
        "cier": mean(r.get("cier_contrib") for r in rows),
        "speech_attributable_count": sum(int(r.get("asr_ifr_contrib", 0)) for r in rows),
    }


def grouped_summaries(rows: list[dict[str, Any]], key: str = "condition") -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "UNSPECIFIED"))].append(row)
    out = []
    for name in sorted(groups):
        s = summarize(groups[name])
        s[key] = name
        out.append(s)
    overall = summarize(rows)
    overall[key] = "OVERALL"
    out.append(overall)
    return out


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
