# CAFA-IVR v1.0.0

First public release of **CAFA-IVR - Counterfactual ASR Failure Attribution for Conversational IVR**.

## Highlights

- Paired reference-text and audio-path counterfactual testing.
- Four-state failure attribution: `HEALTHY`, `SPEECH_ATTRIBUTABLE`, `DOWNSTREAM_OR_TEST`, and `CONTEXT_OR_ORACLE`.
- WER, ASR-IFR, CEER, and optional CIER scoring.
- `cafa-ivr score` CLI for trial-level scoring and summaries.
- `cafa-ivr compare` CLI for baseline/candidate regression gates.
- Vendor-neutral adapter contract and Amazon Lex V2 adapter example.
- Self-contained GitHub Actions CI that runs tests and smoke-tests the measured 360-trial scoring path.
- Empirical reproduction test that verifies the included Conformer-CTC CAFA summary: 360 trials, 142 speech-attributable failures, 0.648429 mean WER, 0.411111 intent/task accuracy, 0.800000 text-control accuracy, and 0.394444 ASR-IFR.
- CAFA-IVR v1.0 specification, implementation checklist, adoption guide, and evidence-log template.
- Research manuscript and reproducibility artifacts.

## Evidence boundary

CAFA-IVR is a testing and attribution framework, not an ASR model. The included neural pilot uses controlled synthetic speech and a constrained in-domain recognizer. Public human-banking artifacts are source/provenance validation and are not mixed with locally executed measurements.

## License

Apache-2.0 for the reference implementation. External datasets and audio retain their source licenses.
