# Contributing to CAFA-IVR

Thanks for helping improve CAFA-IVR.

## Good contribution areas

- ASR/NLU/contact-center adapters
- additional deterministic scoring tests
- entity normalizers for amounts, dates, negation, account types, and actions
- CI/CD integrations
- reproducible public benchmarks
- documentation corrections and implementation examples

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -e . --no-build-isolation
python -m unittest discover -s tests -v
```

## Evidence rules

Do not submit fabricated or estimated empirical results as measurements. Any benchmark contribution must identify the source corpus, license, ASR/NLU configuration, frozen model/version, and scoring procedure.

Synthetic speech is welcome for controlled testing but must be labeled as synthetic. Human-speech results must preserve dataset provenance and applicable consent/license terms.

## Pull requests

Please keep changes focused, add tests for scoring changes, and describe whether the change affects metric definitions or backward compatibility.
