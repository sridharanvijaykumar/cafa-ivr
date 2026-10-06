# Twilio adapter reference implementation

Companion code: `adapters/twilio_example.py`.

## What this is

The first of three vendor adapter references (Twilio → Amazon Connect → Rasa), each
written against `adapters/adapter_contract.py`. It shows a Twilio IVR team how to feed
CAFA-IVR's counterfactual pairing — text control vs. audio-path task outcome — using
the two audio/transcript sources a Twilio call leg actually provides:

1. **Recordings** — caller audio on the Recording resource, fetched over REST with
   basic auth (Account SID + Auth Token). These feed the ASR side:
   `TwilioRecordingFetcher.fetch(recording_sid)` downloads the `.wav` to a temp path,
   `ExternalAsrAdapter` runs any `transcribe_fn` over it (a local-Whisper factory is
   provided; bring your own recognizer).
2. **`<Gather input="speech">`** — Twilio's own speech recognition, delivered as the
   `SpeechResult` / `Confidence` webhook parameters, *not* a REST transcription API.
   `gather_to_trial()` maps that webhook to a trial dict. Note the doc's explicit
   warning: Gather confidence is a recognizer score, not task success — the
   attribution needs your downstream NLU's verdict on the text control.

Both paths funnel through `paired_execute()`, so output rows carry exactly the
columns the scorer consumes (`asr_transcript`, `predicted_intent`,
`predicted_entities_json`, `text_control_pass`, `audio_task_success`), via
`run_paired_from_manifest()` + `write_scorer_csv()`.

## How to use it

```bash
export TWILIO_ACCOUNT_SID=ACxxxx   # never hard-code credentials
export TWILIO_AUTH_TOKEN=xxxx
python adapters/twilio_example.py  # offline wiring demo, no account needed
```

For a real run: build a manifest in the layout of
`examples/manifest_schema_example.csv`, using `twilio:RExxxx` in the `audio_path`
column for call legs you want fetched, and point your real NLU at
`DownstreamAdapter`. Credentials are read from the environment; the fetch uses
plain `urllib` so the reference adds zero dependencies.

## What the offline demo proves (and what it doesn't)

`_offline_demo()` runs with no Twilio account and no network: a fake transcribe
function substitutes "fifteen" for "fifty" ("send fifteen dollars to john smith").
Result: the text control passes, and the demo's keyword NLU also "passes" the audio
task — even though the $50 entity became $15. That is deliberately the CEER lesson
from blog post #2: **intent-task accuracy is blind to entity substitution**, and the
print statement says so in plain words. The demo NLU is explicitly labeled
"OFFLINE DEMO ONLY — replace with your IVR's real NLU"; keyword matching is never
presented as how intent quality should be judged.

## Limitations stated plainly in the code

- The `KeywordDownstreamAdapter` is wiring-verification scaffolding, not an NLU.
- Gather confidence ≠ task success (docstring says it twice, in two places).
- Twilio telephony audio is 8 kHz — the same "constrained recognizer" caveat as the
  pilot; the default trial condition is `telephony_8khz`, and no accuracy claim is
  made for any real deployment.
- Like `aws_lex_v2_example.py`, this file is illustrative and not executed by the
  test suite. Optional dependencies (Whisper) raise a clear `RuntimeError` with an
  install hint instead of failing silently.

## Why Twilio first

The three planned adapters follow the contract's shape, but Twilio is the most
common "audio is already there" IVR platform: teams already have Recordings and
Gather webhooks, so the reference is mostly mapping concepts to columns rather than
new infrastructure. Amazon Connect (Contact Lens / real-time streams) and Rasa
(NLU-only, bring-your-own ASR) cover the other two shapes — one per run.
