# CAFA-IVR v1.1.0

CAFA-IVR v1.1.0 changes observable release-gate and metric behavior to align the implementation with the documented safety and scoring contracts. Adopters should review the migration notes before updating.

## Behaviour changes

- Baseline/candidate comparisons now fail closed when an enabled metric is missing, nonnumeric, nonfinite, or has no comparable rows. Pipelines that previously passed malformed input now exit with status 2.
- `cafa-ivr compare --no-ceer-gate` explicitly disables the optional CEER gate for datasets without critical-entity annotations.
- CIER now represents realized consequence: successful known-impact audio-path tasks contribute zero, failures contribute their impact weight, and unknown-impact rows are excluded. Values therefore change on existing impact-labelled data.
- Summary CEER now uses corpus-level micro-aggregation, matching the published equation. Values therefore change on existing entity-annotated data.
- Manuscript artifacts now use venue-neutral `paper/CAFA-IVR.pdf` and `paper/CAFA-IVR.tex` paths. The old `paper/CAFA-IVR_ICASSP2027.*` paths do not exist in this release tree.

## Fixes and additions

- Added regression coverage for the corrected comparison, CEER, and CIER behavior; the standard-library suite contains 14 tests.
- Added deterministic release-manifest generation and verification, excluding cache/build artifacts and pinning repository text files to LF.
- Clarified CEER's unbounded range and the released artifact's reproducibility boundary: supplied decoded outputs reproduce scoring, but the release does not regenerate audio, ASR decodes, perturbations, or bootstrap samples end to end.

## Compatibility and migration

- Package APIs remain within the v1 specification series, but gate outcomes and CEER/CIER values can change as described above.
- Users who intentionally compare datasets without CEER annotations must pass `--no-ceer-gate`; other enabled gates remain fail closed.
- Update any links or automation that reference the former venue-specific manuscript paths.

## Verification

- The complete 14-test standard-library suite passes.
- The included 360-trial Conformer-CTC scoring reproduction remains exact: 360 trials, 142 speech-attributable failures, 0.648429 mean WER, 0.411111 intent/task accuracy, 0.800000 text-control accuracy, and 0.394444 ASR-IFR.
- `RELEASE_MANIFEST.sha256` is regenerated from and verified against the v1.1.0 release tree.

## License

Apache-2.0 for the reference implementation. External datasets and audio retain their source licenses.
