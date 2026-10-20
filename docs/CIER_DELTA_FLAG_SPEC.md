# CIER delta flag spec for the `compare` gate — Cycle C1

**Status:** review-ready proposal. Nothing committed, no repo changes, no version bump claimed.
All CLI output below is verbatim from real `v1.1.0` and patched-sandbox runs (Oct 13, 2026).
The patch was applied only to a `/tmp` sandbox copy; the cloned repo is untouched.

## 1. The gap

CIER (conversational impact error rate) is computed and reported by `cafa-ivr score`
since v1.1.0, but the `compare` release gate has no CIER delta check. The current gate
rules (`src/cafa_ivr/cli.py`, `cmd_compare`) are `asr_ifr` → `ceer` → `wer`, so a
candidate that breaks the same number of tasks but at far higher consequence can
still pass. This gap is on the record twice in Cycle B (the CIER deep-dive notes
"the flag is a small change"; the benchmark procedure documents the compare gate's
missing CIER delta flag), and this spec closes it.

What CIER measures, from `src/cafa_ivr/core.py` (v1.1.0, unchanged by this proposal):

- `cier_contrib = CIER_WEIGHTS[impact_level] × (1 if audio-path task failed else 0)`,
  with `CIER_WEIGHTS = {"L0": 0.0, "L1": 0.0, "L2": 0.25, "L3": 0.65, "L4": 1.0}`.
- Summary CIER is the mean of per-trial contributions over impact-labelled trials;
  unlabelled trials are excluded (null, not zero — same honesty rule as CEER).
- CIER ∈ [0, 1]: a severity-weighted task-failure rate, the operations number
  ("what did callers experience, weighted by consequence"), not the blame number.
  It counts realized failures regardless of attribution — including
  `DOWNSTREAM_OR_TEST` trials. Teams wanting ASR-attributable consequence gating
  should filter to `SPEECH_ATTRIBUTABLE` before summarizing; unfiltered CIER is the
  fleet-wide number.

## 2. Design decisions

**D1 — Gate on by default (fail-closed).** Mirrors CEER: the framework's release
story is fail-closed (cf. the fail-closed gate design), and silently dropping the
consequence gate on unlabelled data would repeat the exact failure mode the
WER-vs-task writing warns about. WER is the deliberate exception (its gate defaults
off because WER is not a task metric); CIER *is* a task metric, so it defaults on.

**D2 — Default `--max-cier-delta 0.02`.** Rationale, not convention: CIER is a
per-trial mean bounded in [0,1], failure-frequency-shaped like ASR-IFR (unlike
CEER, which is unbounded and denominated in errors per reference entity). 0.02
speaks the same units as the ASR-IFR default: 2 percentage points of L4-weighted
failures, 8 points of L2-weighted failures, per 100 trials. The asymmetry is the
point — consequence-weighting means low-tier regressions are tolerated more than
high-tier ones. Teams govern their own thresholds by risk tier (README §CI/CD).

**D3 — `--no-cier-gate` opt-out, mirroring `--no-ceer-gate`.** Datasets without
`impact_level` annotations get `cier: null` in the summary, and the enabled gate
fails closed with `invalid summary input: <file>: required metric 'cier' is
missing` (one line per metric, naming the first summary that lacks it —
demonstrated verbatim in A1 below). The 360-trial pilot itself is such a dataset.

**D4 — Annotation-drift fairness rule.** A CIER delta cannot separate model
change from re-labelling: identical trials, identical behavior, different tier
annotations produce a binding FAIL (demonstrated verbatim in B2 below). The spec
therefore requires baseline and candidate to be labelled with the same tier
taxonomy and procedure. Operationally: re-annotate both suites from the same
procedure on every comparison run. Recording a taxonomy version in summary
provenance is recommended future work, not part of this diff.

**D5 — Scope discipline.** This diff touches the gate only. No scorer changes, no
weight changes, no new metrics. The weights remain the v1.1.0 illustrative
consequence judgments — they are not calibrated loss values and the gate does not
measure money.

## 3. Reference implementation diff (against v1.1.0 `src/cafa_ivr/cli.py`)

```diff
--- src/cafa_ivr/cli.py (v1.1.0)
+++ src/cafa_ivr/cli.py (proposed)
@@ -78,6 +78,7 @@
     rules = [
         ("asr_ifr", args.max_asr_ifr_delta),
         ("ceer", None if getattr(args, "no_ceer_gate", False) else args.max_ceer_delta),
+        ("cier", None if getattr(args, "no_cier_gate", False) else args.max_cier_delta),
         ("wer", args.max_wer_delta),
     ]
     checks = []
@@ -136,6 +137,17 @@
         action="store_true",
         help="explicitly disable CEER comparison for a dataset without critical-entity annotations",
     )
+    c.add_argument(
+        "--max-cier-delta",
+        type=float,
+        default=0.02,
+        help="max allowed candidate-minus-baseline delta in impact-weighted task-error rate",
+    )
+    c.add_argument(
+        "--no-cier-gate",
+        action="store_true",
+        help="explicitly disable CIER comparison for a dataset without impact-level annotations",
+    )
     c.add_argument("--max-wer-delta", type=float, default=None)
     c.set_defaults(func=cmd_compare)
     return p
```

Twelve lines. The metric prints in the existing per-metric line format
(`cier: baseline=… candidate=… delta=… limit=…`), in the order
asr_ifr → ceer → **cier** → wer (blame → entity → consequence).

## 4. Verbatim before/after CLI output

All runs used a fresh v1.1.0 install from the public repo and a separately
installed patched copy; summaries were produced by the real scorer. The
alpha/beta pair is the 10-trial synthetic comparison set from the
benchmark-comparison procedure (verified there: near-identical WER 0.1226 vs
0.1143, intent accuracy 0.50 vs 1.00, ASR-IFR 0.50 vs 0.00, CEER 1.20 vs 0.20).

### BEFORE — v1.1.0 `compare`, beta (baseline) vs alpha (candidate)

```
asr_ifr: baseline=0.0 candidate=0.5 delta=0.5000 limit=0.0200
ceer: baseline=0.2 candidate=1.2 delta=1.0000 limit=0.0100
CAFA-IVR release gate: FAIL
 - asr_ifr regressed by 0.5000 > 0.0200
 - ceer regressed by 1.0000 > 0.0100
```
(exit 2). No `cier` line — the gap. Both summaries carry `cier: null` because the
alpha/beta CSVs have no `impact_level` column.

### AFTER — patched `compare`

**A1. Unlabelled alpha/beta (missing-data behavior — fail-closed):**

```
CAFA-IVR release gate: FAIL
 - invalid summary input: /tmp/gate_demo/before/beta_scored/summary.csv: required metric 'cier' is missing
```
(exit 2). The CIER gate fires on absent annotations exactly like the CEER gate
does — the migration path for existing pipelines is explicit, not silent.

**A2. Same, with `--no-cier-gate` (v1.1.0-identical behavior restored):**

```
asr_ifr: baseline=0.0 candidate=0.5 delta=0.5000 limit=0.0200
ceer: baseline=0.2 candidate=1.2 delta=1.0000 limit=0.0100
CAFA-IVR release gate: FAIL
 - asr_ifr regressed by 0.5000 > 0.0200
 - ceer regressed by 1.0000 > 0.0100
```
(exit 2). Byte-identical semantics to v1.1.0 for teams without impact labels.

**B1–B4. Impact-labelled variants** (same alpha transcripts/task outcomes, plus an
illustrative `impact_level` column labelled
`illustrative_synthetic_not_empirical`; the five failing trials annotated L2 in
variant A → CIER 0.125, L4 in variant B → CIER 0.50; demo inputs archived at
`hidden_files/cier_gate_demo/`):

B1 — identical annotations, `compare A vs A`:

```
asr_ifr: baseline=0.5 candidate=0.5 delta=0.0000 limit=0.0200
ceer: baseline=1.2 candidate=1.2 delta=0.0000 limit=0.0100
cier: baseline=0.125 candidate=0.125 delta=0.0000 limit=0.0200
CAFA-IVR release gate: PASS
```
(exit 0). The `cier` line appears; zero deltas pass.

B2 — annotation drift, `compare A(L2) vs B(L4)` — **identical trials, identical
model behavior, only the tier annotations differ**:

```
asr_ifr: baseline=0.5 candidate=0.5 delta=0.0000 limit=0.0200
ceer: baseline=1.2 candidate=1.2 delta=0.0000 limit=0.0100
cier: baseline=0.125 candidate=0.5 delta=0.3750 limit=0.0200
CAFA-IVR release gate: FAIL
 - cier regressed by 0.3750 > 0.0200
```
(exit 2). The CIER gate is the *only* failing line — binding on its own — and
this run is the evidence behind fairness rule D4.

B3 — same drift with `--max-cier-delta 0.5`:

```
asr_ifr: baseline=0.5 candidate=0.5 delta=0.0000 limit=0.0200
ceer: baseline=1.2 candidate=1.2 delta=0.0000 limit=0.0100
cier: baseline=0.125 candidate=0.5 delta=0.3750 limit=0.5000
CAFA-IVR release gate: PASS
```
(exit 0). Limit configurability works.

B4 — improvement direction, `compare A(L2) vs beta-labelled` (beta: no failures,
CIER 0.0):

```
asr_ifr: baseline=0.5 candidate=0.0 delta=-0.5000 limit=0.0200
ceer: baseline=1.2 candidate=0.2 delta=-1.0000 limit=0.0100
cier: baseline=0.125 candidate=0.0 delta=-0.1250 limit=0.0200
CAFA-IVR release gate: PASS
```
(exit 0). Negative deltas (consequence improvement) pass — the gate is
one-sided by design.

## 5. Migration and release notes (proposed, not claimed)

- **Breaking change → v1.2.0 candidacy.** Any existing `compare` invocation on
  summaries without CIER will now fail closed instead of silently skipping
  consequence gating. Migration is one flag (`--no-cier-gate`) or one annotation
  column (`impact_level`). Demonstrated: A2 restores exact v1.1.0 output.
- **README §CI/CD** gains the flag and a sentence sibling to the existing one:
  "Datasets without impact-level annotations must explicitly disable that gate
  with `--no-cier-gate`." The example command gains `--max-cier-delta 0.02`.
- **CHANGELOG:** gate addition, default-on rationale, migration note.
- **No scorer changes.** `score`, `summary.csv`/`summary.json` schema, and
  `report.md` are untouched — CIER was already reported.
- Suggested tests: default-on CIER regression → FAIL; `--no-cier-gate` skips;
  missing `cier` in either summary → fail-closed with the missing-metric message;
  custom `--max-cier-delta`; negative delta passes; non-finite `cier` rejected.

## 6. Anti-overclaim checklist

- [x] No repo changes made — the patch exists only in the `/tmp` sandbox; the
      fresh clone is untouched and no commit was authored under anyone's name.
- [x] No version bump claimed — "v1.2.0 candidacy" is a proposal for Vijay's call.
- [x] Demo tier annotations are illustrative annotator judgment, labelled
      `illustrative_synthetic_not_empirical` in the CSVs; they are not field data.
- [x] CIER weights are illustrative consequence judgments, not calibrated dollar
      losses; the gate does not measure money and the spec never says it does.
- [x] The 360-trial pilot carries `cier: null` (no impact labels) — stated, not hidden.
- [x] CIER deltas cannot separate annotation change from model change (B2 proves
      it) — fairness rule D4 is in the spec, not a footnote.
- [x] Every number in §4 came from the real scorer/gate binaries, not hand computation.
