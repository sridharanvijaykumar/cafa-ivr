# CAFA-IVR Release Checklist

Before publishing a CAFA-IVR release or paper artifact:

- [x] Reference scorer unit tests pass.
- [x] Scorer reproduces the included 360-trial empirical summary.
- [x] Paper distinguishes locally measured results from external human-source validation.
- [x] Paper states limitations of synthetic speech and closed-set neural decoding.
- [x] Specification avoids universal production thresholds.
- [x] Adoption log distinguishes independent organizational use from author-led testing.
- [x] Employer/platform references do not imply sponsorship or endorsement.
- [x] PDF paper and specification regenerated from the final LaTeX sources and visually checked.
- [x] Regenerated `RELEASE_MANIFEST.sha256` with `python scripts/generate_release_manifest.py` after all release edits.
- [x] Complete test suite passes after manifest regeneration, verifying every listed file and digest.
