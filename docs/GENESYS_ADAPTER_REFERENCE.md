# Genesys adapter reference implementation

Companion code: `adapters/genesys_example.py`.

## What this is

The fourth of four vendor adapter references (Twilio → Amazon Connect → Rasa → Genesys),
each written against `adapters/adapter_contract.py`. It shows a Genesys Cloud CX team
how to feed CAFA-IVR's counterfactual pairing — text control vs. audio-path task
outcome — using the two audio/transcript sources a Genesys voice call actually
provides:

1. **Conversation recordings** — call-leg audio on the Conversations / Recording API
   (`GET /api/v2/conversations/{conversationId}/recordings`; per-recording `mediaUris`
   map holds signed download URIs). `GenesysRecordingFetcher` downloads the caller
   recording — one recording per participant, external/caller preferred, WAV then
   MP3. OAuth client-credentials via `https://login.{environment}/oauth/token`, urllib
   only, secrets in `GENESYS_CLIENT_ID` / `GENESYS_CLIENT_SECRET` (never hard-coded).
   Telephony-grade 8 kHz audio — the same constrained-audio caveat as the pilot; the
   default trial condition is `telephony_8khz`.
2. **Speech and Text Analytics transcripts** — Genesys Cloud's own transcription, via
   `GET /api/v2/speechandtextanalytics/conversations/{conversationId}/communications/{communicationId}/transcripturl`
   (signed download URL, requires `speechAndTextAnalytics:data:view` +
   `recording:recording:view`). `genesys_customer_transcript()` keeps only
   customer/caller-side phrases in order and fails loudly if the transcript document's
   labeling doesn't match — the same customer-only filtering as the Connect reference's
   Contact Lens walker. `transcript_to_trial()` maps it to a trial dict. The attribution
   framing mirrors the other references: a transcript-side trial answers "did Genesys's
   own transcription break the task?" — pair it with the recording side (1) to
   attribute against your own ASR instead.

Both paths funnel through `paired_execute()`, so output rows carry exactly the
columns the scorer consumes (including `impact_level` and `evidence_type`), via
`run_paired_from_manifest()` + `write_scorer_csv()`. Manifest rows accept
`genesys:<conversationId>[:communicationId]` in `audio_path` for recording fetch, or
an empty `audio_path` with a pre-filled `asr_transcript` for the transcript-side shape.

## How to use it

```bash
export GENESYS_CLIENT_ID=... GENESYS_CLIENT_SECRET=...   # never hard-code secrets
export GENESYS_ENVIRONMENT=mypurecloud.com               # region of your org
python adapters/genesys_example.py  # offline wiring demo, no Genesys org needed
```

For a real run: build a manifest in the layout of `examples/manifest_schema_example.csv`
using `genesys:<conversationId>` audio refs, resolve the voice communication's
communication ID from the conversation detail
(`GET /api/v2/conversations/{conversationId}`), and point `run_paired_from_manifest()`
at it.

## The honest downstream decision

Unlike Rasa, Genesys Cloud exposes no stateless NLU-eval HTTP endpoint. An Architect
bot flow delegates intent recognition to the connected bot — typically Google
Dialogflow CX/ES or Amazon Lex V2 via a Genesys integration — and evaluates inside the
flow. So the reference does **not** invent a Genesys `/model/parse`; the downstream
side is the NLU behind *your* Architect bot flow, reached through that platform's API
(the Connect and Rasa references in this folder already show the wrapper shape for
Lex V2 and Rasa — reuse one). The offline demo uses the same demo-only keyword NLU
as the Twilio reference so the wiring is verifiable without infrastructure.

## What the offline demo proves (and what it doesn't)

`_offline_demo()` runs with no Genesys org and no network. Three checks:

1. `genesys_customer_transcript()` on a transcripturl-shaped document: the IVR prompt
   phrase is excluded, only the caller phrase is kept (`phrase_count: 1`).
2. The audio-side pairing with a fake transcribe function substituting "fifteen" for
   "fifty": the text control passes, and the demo's keyword NLU also "passes" the audio
   task — even though the $50 entity became $15. The deliberate CEER lesson, same as
   the Twilio reference: **intent-task accuracy is blind to entity substitution**.
3. The transcript-side trial (no audio file): same attribution from the stored Genesys
   transcript directly.

## Limitations stated plainly in the code

- Classes are illustrative and not executed by the reference test suite; OAuth classes
  raise clear errors when secrets are missing.
- Endpoint paths and the `mediaUris`/transcript-document field names follow the public
  Genesys Cloud API Explorer and third-party tooling built against it — verify against
  your region's explorer if they differ.
- The OAuth client role needs `recording:recording:view`/`download` and
  `speechAndTextAnalytics:data:view` — check the role, don't guess.
- **Licensing caveat**: transcripts require the Speech and Text Analytics add-on;
  recordings require recording enabled on the queue/flow. No transcript URL exists
  without both.
- **Post-call only**: recordings and analytics transcripts are post-call — regression
  testing, not real-time gating.
- **Retention caveat**: recording retention policies expire audio; a trial built after
  expiry has no recording to fetch. Keep the audio and the transcript paired by age.
- The demo NLU is labeled "OFFLINE DEMO ONLY — replace with your Architect flow's real
  NLU"; keyword matching is never presented as how intent quality should be judged.

## Review status

- Offline demo verified: all three checks pass; the module compiles clean.
- Review-ready; commit + push awaits Vijay (no commits under his name from the engine).
- Next in queue C4: v1.2.0 roadmap revision folding in C1–C3 — the repo story becomes
  "found our own gap, fixed it."
