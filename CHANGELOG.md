# Changelog

## Unreleased

- Made baseline/candidate comparison fail closed for missing, nonnumeric, nonfinite, or empty enabled metrics, with an explicit opt-out for datasets where optional CEER is not annotated.
- Corrected summary CEER aggregation to match the published corpus-level equation.
- Defined CIER as a realized-consequence score and corrected successful audio-path tasks to contribute zero.
- Added regression coverage and automated release-manifest verification.
- Clarified CEER's range and the exact reproducibility boundary of the released artifact.
- Repaired release-manifest generation so cache files cannot be included, and pinned repository text files to LF for cross-platform digest stability.
- Renamed the technical manuscript artifacts to venue-neutral filenames for reusable adoption outside any single conference.

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
