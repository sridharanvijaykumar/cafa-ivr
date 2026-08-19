import json
from pathlib import Path

from cafa_ivr.core import cafa_score_row, grouped_summaries, read_csv


def test_conformer_360_reproduces_published_cafa_summary():
    repo = Path(__file__).resolve().parents[1]
    rows = read_csv(repo / "empirical" / "conformer_360_cafa_input.csv")
    scored = [cafa_score_row(row) for row in rows]
    actual = grouped_summaries(scored, "condition")[-1]
    expected = json.loads(
        (repo / "empirical" / "cafa_reproduced_overall_360.json").read_text(encoding="utf-8")
    )

    assert actual["n"] == expected["n"] == 360
    assert actual["speech_attributable_count"] == expected["speech_attributable_count"] == 142
    assert actual["condition"] == expected["condition"] == "OVERALL"

    for key in ("wer", "intent_accuracy", "text_control_accuracy", "asr_ifr"):
        assert abs(float(actual[key]) - float(expected[key])) < 1e-12

    assert actual["ceer"] is None
    assert actual["cier"] is None
