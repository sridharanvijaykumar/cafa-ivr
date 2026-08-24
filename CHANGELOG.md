# Changelog

## 1.1.0 - 2026-08-24

### Behaviour changes

- Baseline/candidate comparison now fails closed for missing, nonnumeric, nonfinite, or empty enabled metrics. Pipelines that previously passed malformed input now exit with status 2; datasets without critical-entity annotations can explicitly opt out with `--no-ceer-gate`.
- CIER is now a realized-consequence score. Successful known-impact audio-path tasks contribute zero, so values change on existing impact-labelled data.
- Corpus CEER now uses the published micro-average, so values change on existing entity-annotated data.
- Technical manuscript artifacts moved to venue-neutral `paper/CAFA-IVR.pdf` and `paper/CAFA-IVR.tex` paths; the old `paper/CAFA-IVR_ICASSP2027.*` paths no longer resolve on this release tree.

### Fixes and additions

- Repaired release-manifest generation so cache files cannot be included and added automated manifest verification.
- Pinned repository text files to LF for cross-platform digest stability.
- Clarified CEER's unbounded range and the released artifact's exact reproducibility boundary.
- Added regression coverage for the corrected gate and metric behavior; the standard-library suite now contains 14 tests.

## 1.0.0 - 2026-08-18

- Named CAFA-IVR framework and portable attribution states.
- Added reference scorer for WER, ASR-IFR, CEER and optional CIER.
- Added condition-level summaries and baseline/candidate release-gate comparison.
- Added v1.0 reference specification and adoption guide.
- Included measured 360-trial controlled Conformer-CTC evidence package.
- Included public-human-source validation metadata as a separate evidence layer.

### CI/reproducibility cleanup - 2026-08-19

- Replaced the adopter-only GitHub Actions template with self-contained repository CI.
- Added an empirical reproduction test for the included 360-trial Conformer-CTC result set.
- Added repository metadata and CI/license badges.
- Removed pre-publication GitHub publishing scaffolding.
