# Worked example: CEER and CIER, scored with the real framework

The 360-trial pilot exercises WER and ASR-IFR only — it carries no critical-entity annotations or impact labels, so CEER and CIER were implemented-but-unexercised until this example. This closes that gap with a small, fully **synthetic** dataset: 24 trials in 3 conditions of 8, every row tagged `evidence_type = illustrative_synthetic_not_empirical`. Nothing here is empirical; everything is scored by the actual v1.1.0 scorer, and every number below is real output.

Companion dataset: `../examples/ceer_cier_worked_example/ceer_cier_worked_example.csv`.

## Reproduce it

From the repo root:

```bash
pip install cafa-ivr==1.1.0   # or pip install from the repo
cafa-ivr score --input examples/ceer_cier_worked_example/ceer_cier_worked_example.csv --out ceer_demo --group-by condition
```

The input follows the repo's own demo vocabulary (`reference_text`, `asr_transcript`, `expected_intent`, `predicted_intent`, `text_control_pass`, `audio_task_success`, `expected_entities_json`, `predicted_entities_json`, `impact_level`, `risk_tier`, `evidence_type`).

## The three conditions

- **clean (8 trials):** routine IVR requests ("check balance on my savings account", "lock my debit card immediately"). Transcripts exact, entities correct, task succeeds. Impact L0.
- **entity_swap (8 trials):** the money trials. Exactly one word changes in each transcript — "five hundred" → "five thousand", account digits "4271" → "4276", "savings" → "checking", "card" → "car". The reference-text control routes correctly (text_control_pass = 1) but the audio path fails (audio_task_success = 0), so every trial attributes **SPEECH_ATTRIBUTABLE** and contributes to ASR-IFR. Impact L4 for money-moving amounts, L3 for dates/accounts.
- **benign_noise (8 trials):** filler-word noise — "uh", "please", "sir" — scattered through transcripts. Higher WER than entity_swap, but nothing task-critical changes. Impact L1.

## Results (real scorer output, grouped by condition)

| condition | WER | task accuracy | text-control accuracy | ASR-IFR | CEER | CIER |
|---|---|---|---|---|---|---|
| clean | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| entity_swap | 0.1240 | **0.0000** | 1.0000 | 1.0000 | 1.1538 | 0.8250 |
| benign_noise | 0.4250 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| OVERALL (n=24) | 0.1830 | 0.6667 | 1.0000 | 0.3333 | 0.6000 | 0.2750 |

Read that table the wrong way and it breaks your release gate. The condition with the **lowest** non-zero WER (entity_swap, 0.1240) has **zero** task accuracy — every one of its 8 trials is a speech-attributable failure. The condition with the **highest** WER (benign_noise, 0.4250) has perfect task accuracy and is entirely HEALTHY. A WER-only gate would have passed the catastrophic recognizer change and flagged the harmless one. This is the framework's core claim, now with an empirical vignette behind it.

## What CEER shows that WER cannot

CEER (spec §6.3) is a micro-average: total missing + spurious critical entities divided by total reference critical entities across the scored set. Three properties show up in the output:

1. **Substitution counts double.** Trial E-09 ("five hundred" → "five thousand"): 2 errors over 2 references — the expected `amount: 500` is missing *and* `amount: 5000` is spurious. Per-trial CEER = 1.0 on a single-word change with WER 0.1429.
2. **CEER is unbounded — it exceeds 1.0.** Trials E-12 (account "4271" → "4276"), E-13 (June 15 → June 50), and E-16 (card → car) each carry one annotated reference entity and produce 2 errors: per-trial CEER = 2.0. The condition-level CEER of 1.1538 is a legitimate value, not a bug — "not a probability," per the spec.
3. **WER can be exactly zero and CEER still fires.** Trial E-15: the transcript is word-for-word identical to the reference (WER 0.0000), but the NLU emitted a `currency: USD` the reference never had — a spurious entity CEER catches (0.5) and WER structurally cannot. This trial exists to make one point: entity-level evaluation and transcript-level evaluation measure different things.

Caveat, stated plainly: in a real pipeline `predicted_entities_json` comes from your NLU's output on the ASR text. Here it is authored to match each substituted transcript, because the dataset is illustrative. The metric mechanics are real; the trial content is synthetic.

## What CIER adds

CIER weights each failed trial by its annotated impact level (L2 = 0.25, L3 = 0.65, L4 = 1.0; L0/L1 = 0). The entity_swap condition — 4 trials at L4, 4 at L3, all failing — scores CIER 0.8250, versus overall 0.2750. The money-moving failures dominate exactly as the annotation intends.

Honest limitation: **the v1.1.0 `compare` gate has no CIER delta flag.** I verified this directly: a candidate dataset identical except that four L3 trials were re-annotated L4 (CIER 0.2750 → 0.3333, all other metrics unchanged) passes the gate:

```
asr_ifr: baseline=0.3333 candidate=0.3333 delta=0.0000 limit=0.0200
ceer: baseline=0.6000 candidate=0.6000 delta=0.0000 limit=0.0100
CAFA-IVR release gate: PASS
```

A pure consequence-severity regression does not fail the release gate in v1.1.0. That is a documented roadmap item, not a hidden flaw — file it under v1.3.0 candidate work.

## The gate firing on CEER, verbatim

A second candidate — the baseline plus two extra entity-swap failures (a new recognizer build regressing on amounts) — fails fail-closed, exit code 2:

```
asr_ifr: baseline=0.3333 candidate=0.3846 delta=0.0513 limit=0.0200
ceer: baseline=0.6000 candidate=0.6552 delta=0.0552 limit=0.0100
CAFA-IVR release gate: FAIL
 - asr_ifr regressed by 0.0513 > 0.0200
 - ceer regressed by 0.0552 > 0.0100
```

Same story as the blog-series finale (the framework's own pilot fails its own CEER gate without `--no-ceer-gate`), now with the entity-metric vignette behind it.

## Boundaries of this example

- **Synthetic, labeled, illustrative.** 24 hand-written trials; not a production corpus, not a recognizer benchmark, not evidence that any real ASR behaves this way. It exercises metric mechanics, not field behavior.
- **The pilot boundary is unchanged.** The 360-trial Conformer-CTC reproduction remains synthetic-speech + constrained recognizer; this dataset doesn't retroactively upgrade it.
- **Entity annotations are the expensive part.** CEER/CIER only exist where someone annotated expected entities and impact levels. The framework scores them; it can't create them.

## What this unlocks

This is the worked example the Show HN draft and the blog series both promised. It gives the campaign a concrete, reproducible artifact: "clone the CSV, run one command, watch WER rank the conditions backwards." The CSV lives at `examples/ceer_cier_worked_example/`; this walkthrough lives in `docs/`.
