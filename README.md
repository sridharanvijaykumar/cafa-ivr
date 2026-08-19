# CAFA-IVR v1.0

[![CAFA-IVR CI](https://github.com/sridharanvijaykumar/cafa-ivr/actions/workflows/cafa-regression.yml/badge.svg)](https://github.com/sridharanvijaykumar/cafa-ivr/actions/workflows/cafa-regression.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Counterfactual ASR Failure Attribution for Conversational IVR**

CAFA-IVR is a vendor-neutral testing framework for answering a practical question that Word Error Rate (WER) cannot answer by itself:

> Did adding the speech/ASR path cause an otherwise valid conversational test to fail?

## Core idea

Run every semantic test through two paths:

```text
TEXT CONTROL:  reference text -> NLU / agent -> task outcome
AUDIO PATH:    audio -> ASR -> NLU / agent -> task outcome
```

CAFA-IVR then distinguishes:

| Text control | Audio path | Attribution |
|---|---|---|
| Pass | Pass | HEALTHY |
| Pass | Fail | SPEECH_ATTRIBUTABLE |
| Fail | Fail | DOWNSTREAM_OR_TEST |
| Fail | Pass | CONTEXT_OR_ORACLE |

The primary metric is **ASR-IFR (ASR-Attributable Intent Failure Rate)**: the fraction of the full paired suite where the text control passes but the audio path fails.

CAFA-IVR also supports:

- **WER** - lexical transcription fidelity
- **CEER** - Critical-Entity Error Rate for amounts, dates, negation, actions, etc.
- **CIER** - optional severity-weighted consequence score
- condition-level summaries for clean, telephony, noise and speaking-rate tests
- baseline-vs-candidate regression gates for CI/CD

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . --no-build-isolation

cafa-ivr score \
  --input examples/demo_results.csv \
  --out demo_out
```

Outputs:

```text
demo_out/
  scored_trials.csv
  summary.csv
  summary.json
  report.md
```

The demo file is **illustrative only** and must not be cited as empirical evidence.

To reproduce scoring on the measured 360-trial Conformer-CTC pilot included with this release:

```bash
cafa-ivr score \
  --input empirical/conformer_360_cafa_input.csv \
  --out measured_out
```

## CI/CD gate

```bash
cafa-ivr compare \
  --baseline baseline/summary.csv \
  --candidate candidate/summary.csv \
  --max-asr-ifr-delta 0.02 \
  --max-ceer-delta 0.01
```

The default numeric gates are examples for tooling demonstration, not universal acceptance criteria. Production teams should govern their own thresholds by risk tier and historical baseline.

## Integration contract

CAFA-IVR does not require a specific ASR, NLU, contact-center platform, or agent architecture. An adapter only needs to populate the trial-result fields described in `docs/CAFA-IVR_SPEC_v1.0.md`.

Possible integrations include:

- cloud or on-prem ASR
- intent classifiers
- LLM voice agents
- contact-center test harnesses
- deterministic dialogue managers
- tool-calling agents with task-success oracles

## Evidence included in this release

`empirical/` contains the locally measured controlled Conformer-CTC results used in the research manuscript plus public-human-source validation metadata. Synthetic-speech measurements and public-human source validation are deliberately kept separate.

### Evidence boundary

CAFA-IVR is a testing and attribution framework, not an ASR model. The included 360-trial neural pilot uses controlled synthetic speech and a constrained in-domain recognizer; it should **not** be interpreted as a production-ASR benchmark. Public human-banking material is retained as source/provenance validation and is not mixed with locally executed measurements.

## Adoption

Organizations adopting the framework should record the exact CAFA-IVR version, test scope, engines, thresholds, and change-management decision. `docs/ADOPTION_EVIDENCE_LOG.md` provides a neutral template so independent use is reproducible and auditable.

## Research paper

See `paper/CAFA-IVR_ICASSP2027.pdf` and the LaTeX source in the same folder.

## License

Reference implementation: Apache-2.0. Dataset/audio licensing remains governed by the source dataset or organization that owns the test material.

## Author

Vijay Kumar Sridharan  
IEEE Senior Member  
Frisco, TX, USA

## Repository adoption workflow

CAFA-IVR is designed to be forked or wrapped rather than requiring teams to replace their ASR/NLU stack. A typical adoption is:

```text
existing test audio ──> existing ASR ──> existing NLU/agent ──> result adapter
         │
reference text ─────────────────────────> same NLU/agent ────> text control
                                                              │
                                                              v
                                                         CAFA-IVR scorer
```

Teams can add an adapter under `adapters/`, generate the required trial CSV, run `cafa-ivr score`, and optionally place `cafa-ivr compare` in CI/CD. Independent evaluations are welcome through the adoption-report issue template.

