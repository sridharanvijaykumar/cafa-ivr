# Rasa adapter reference implementation

Companion code: `adapters/rasa_example.py`.

## What this is

The third and last of the three vendor adapter references (Twilio → Amazon
Connect → Rasa), each written against `adapters/adapter_contract.py`. It shows
a Rasa IVR/voice-assistant team how to feed CAFA-IVR's counterfactual pairing —
text control vs. audio-path task outcome — using Rasa as it actually exists in
production:

1. **Rasa NLU as the downstream side** — `parse_with_rasa()` posts to the
   `/model/parse` endpoint on a server you trained and started yourself
   (`rasa train`, then `rasa run --enable-api`). `RasaDownstreamAdapter`
   maps the parse result (intent name + confidence + entities) to a task
   readiness test: the intent name must match the expected intent and the
   confidence must clear your threshold. Auth is optional via `RASA_TOKEN`;
   the client is urllib-only with no extra dependencies.
2. **Your recognizer as the ASR side** — Rasa ships no speech recognizer, so
   this side is entirely pluggable: `ExternalAsrAdapter` wraps any transcribe
   function (a cloud recognizer, a local Whisper install, the recognizer
   behind your voice channel). When the transcript already arrives as text —
   a voice-channel webhook, a channel log — `voice_transcript_to_trial()`
   carries `asr_transcript` directly in the trial dict with no audio file,
   and `paired_execute_voice_trial()` runs the pairing without an ASR at all.

Both paths funnel through the same scorer columns (including `impact_level`
and `evidence_type`, which the v1.1.0 scorer schema expects), via
`run_paired_from_manifest()` + `write_scorer_csv()`.

## How to use it

```bash
python adapters/rasa_example.py  # offline wiring demo, no Rasa server needed
```

For a real run: point `RASA_SERVER_URL` at your server (default is the
conventional local `http://localhost:5005`), build a manifest in the layout
of `examples/manifest_schema_example.csv`, and point
`run_paired_from_manifest()` at it. Rows whose `audio_path` is empty are
treated as voice-channel trials with the transcript already in the row;
rows with a path go through your ASR via `paired_execute()`.

## What the offline demo proves (and what it doesn't)

`_offline_demo()` runs with no Rasa server and no network. Two checks:

1. A fake transcribe function substitutes "fifteen" for "fifty". Canned
   parse results (in the `/model/parse` shape: intent + confidence +
   entity/value pairs) show the text control passing and the audio task
   passing — Rasa still classifies `transfer_money` at 0.93 confidence — even
   though the $50 entity became $15. The deliberate CEER lesson, same as the
   Twilio and Connect references: **intent-task accuracy is blind to entity
   substitution**.
2. The voice-channel shape is exercised end to end: a trial with the
   transcript already in the row produces the same attribution with no audio
   file involved.

The fake downstream is explicitly labeled as a stand-in for the real
`RasaDownstreamAdapter`; nothing in the demo claims a real Rasa server was
involved. The real adapter's `task_success` rule — intent name matches the
expected intent AND confidence clears the threshold — is reproduced exactly
in the fake's readiness test.

## Limitations stated plainly in the code

- The Rasa classes are illustrative and not executed by the test suite. No
  live calls happen unless you point the client at your own server.
- `task_success` is a readiness test you own, not Rasa's verdict: if your
  pipeline uses Rasa's FallbackClassifier, a parse Rasa refused to trust
  arrives as intent name `nlu_fallback` — that is an NLU refusal, not a task
  outcome. Keep `confidence_threshold` consistent with the fallback
  threshold in your `config.yml`; "the NLU returned an intent" is not the
  same as "the task succeeded."
- Rasa ships no ASR — the ASR side is entirely the team's choice, so set the
  trial condition to whatever describes your actual audio pipeline (e.g.
  `telephony_8khz` if that's what feeds your recognizer). No accuracy claim
  is made for any real deployment.
- Entity values flow into `predicted_entities_json` as dict-of-lists, which
  is the layout the scorer's entity multiset already handles.
- The `/model/parse` field names used here (`intent.name`,
  `intent.confidence`, `entities[].entity`/`entities[].value`) follow Rasa
  Open Source's published HTTP API shape; verify against your Rasa version
  if your server is much older or newer than 3.x.

## Why Rasa last

The adapter order follows platform shape, not preference: Twilio was the
"audio is already there" case, Connect the "transcript is already there"
case. Rasa closes the trio with the opposite shape — **NLU-only,
bring-your-own ASR** — which is also the cleanest illustration of the
framework's vendor-neutrality: the counterfactual pairing is identical
whether the downstream is Twilio, Lex V2, or your own trained Rasa model.
