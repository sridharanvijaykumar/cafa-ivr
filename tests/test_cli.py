import io
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

from cafa_ivr.cli import cmd_compare


class CompareTests(unittest.TestCase):
    def _run_compare(self, baseline_row, candidate_row, *, max_wer_delta=None, no_ceer_gate=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.csv"
            candidate = root / "candidate.csv"
            baseline.write_text(baseline_row, encoding="utf-8")
            candidate.write_text(candidate_row, encoding="utf-8")
            args = Namespace(
                baseline=str(baseline),
                candidate=str(candidate),
                max_asr_ifr_delta=0.02,
                max_ceer_delta=0.01,
                max_wer_delta=max_wer_delta,
                no_ceer_gate=no_ceer_gate,
            )
            output = io.StringIO()
            with redirect_stdout(output):
                cmd_compare(args)
            return output.getvalue()

    def test_valid_candidate_passes(self):
        row = "condition,asr_ifr,ceer,wer\nOVERALL,0.10,0.02,0.20\n"
        output = self._run_compare(row, row, max_wer_delta=0.01)
        self.assertIn("CAFA-IVR release gate: PASS", output)

    def test_regression_fails(self):
        baseline = "condition,asr_ifr,ceer\nOVERALL,0.10,0.02\n"
        candidate = "condition,asr_ifr,ceer\nOVERALL,0.15,0.02\n"
        with self.assertRaises(SystemExit) as raised:
            self._run_compare(baseline, candidate)
        self.assertEqual(raised.exception.code, 2)

    def test_missing_enabled_metric_fails_closed(self):
        baseline = "condition,asr_ifr,ceer\nOVERALL,0.10,0.02\n"
        candidate = "condition,asr_ifr\nOVERALL,0.10\n"
        with self.assertRaises(SystemExit) as raised:
            self._run_compare(baseline, candidate)
        self.assertEqual(raised.exception.code, 2)

    def test_missing_ceer_can_be_explicitly_disabled(self):
        row = "condition,asr_ifr\nOVERALL,0.10\n"
        output = self._run_compare(row, row, no_ceer_gate=True)
        self.assertIn("CAFA-IVR release gate: PASS", output)

    def test_nonnumeric_enabled_metric_fails_closed(self):
        baseline = "condition,asr_ifr,ceer\nOVERALL,0.10,0.02\n"
        candidate = "condition,asr_ifr,ceer\nOVERALL,not-a-number,0.02\n"
        with self.assertRaises(SystemExit) as raised:
            self._run_compare(baseline, candidate)
        self.assertEqual(raised.exception.code, 2)

    def test_nonfinite_enabled_metric_fails_closed(self):
        baseline = "condition,asr_ifr,ceer\nOVERALL,0.10,0.02\n"
        candidate = "condition,asr_ifr,ceer\nOVERALL,nan,0.02\n"
        with self.assertRaises(SystemExit) as raised:
            self._run_compare(baseline, candidate)
        self.assertEqual(raised.exception.code, 2)

    def test_empty_summary_fails_closed(self):
        baseline = "condition,asr_ifr,ceer\nOVERALL,0.10,0.02\n"
        candidate = "condition,asr_ifr,ceer\n"
        with self.assertRaises(SystemExit) as raised:
            self._run_compare(baseline, candidate)
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
