# Amazon Connect adapter reference implementation

Companion code: `adapters/amazon_connect_example.py`.

## What this is

The second of three vendor adapter references (Twilio → Amazon Connect → Rasa),
each written against `adapters/adapter_contract.py`. It shows a Connect IVR team
how to feed CAFA-IVR's counterfactual pairing — text control vs. audio-path task
outcome — using the two audio/transcript sources a Connect voice contact actually
provides:

1. **Call recordings** — WAV files in the S3 bucket you configure (recording
   behavior is set in the contact flow or queue). Telephony-grade 8 kHz audio —
   the same constrained-audio caveat as the pilot. `ConnectRecordingFetcher`
   downloads by contact ID via boto3's standard credential chain; the S3 key
   layout is configurable per instance and the default template is explicitly
   marked "adapt to your bucket layout."
2. **Contact Lens analysis segments** — post-call, Contact Lens writes analysis
   JSON segments to S3 under your configured prefix. `contact_lens_customer_transcript()`
   walks them, keeps only `ParticipantRole == "CUSTOMER"` transcript entries, joins
   them in order, and counts redacted segments. `contact_lens_to_trial()` maps that
   to a trial dict. Note the attribution framing: this trial answers "did Connect's
   own transcription break the task?" — pair it with the recording side (1) if you
   want to attribute against your own ASR instead.

Both paths funnel through `paired_execute()`, so output rows carry exactly the
columns the scorer consumes (including `impact_level` and `evidence_type`, which
the v1.1.0 scorer schema expects), via `run_paired_from_manifest()` +
`write_scorer_csv()`.

## How to use it

```bash
export CONNECT_RECORDINGS_BUCKET=my-contact-recordings  # never hard-code creds
python adapters/amazon_connect_example.py  # offline wiring demo, no AWS needed
```

For a real run: put your Lex V2 bot IDs behind the env var or constructor, build
a manifest in the layout of `examples/manifest_schema_example.csv` using
`s3:bucket/key` in the `audio_path` column for recordings to fetch, and point
`run_paired_from_manifest()` at it. Credentials flow through boto3's standard
chain — the same pattern as the repo's existing `aws_lex_v2_example.py`.

## What the offline demo proves (and what it doesn't)

`_offline_demo()` runs with no AWS account and no network. Two checks:

1. A fake transcribe function substitutes "fifteen" for "fifty". The text control
   passes, and the demo's keyword NLU also "passes" the audio task — even though
   the $50 entity became $15. The deliberate CEER lesson, same as the Twilio
   reference: **intent-task accuracy is blind to entity substitution**.
2. `contact_lens_customer_transcript()` is exercised on synthetic segments: the
   agent-side utterance is correctly excluded, the customer utterances join in
   order, and the `[redacted]` segment is skipped and counted
   (`"redacted_segments": 1`).

The demo NLU is explicitly labeled "OFFLINE DEMO ONLY — replace with Lex V2 (4a)
or your real NLU"; keyword matching is never presented as how intent quality
should be judged. The Lex V2 downstream class derives `task_success` from the
intent reaching `Fulfilled` — with an explicit warning that "the NLU returned an
intent" is not the same as "the task succeeded."

## Limitations stated plainly in the code

- Connect/Lex V2 classes are illustrative and not executed by the test suite.
  Optional `boto3` raises a clear `RuntimeError` with an install hint.
- S3 key layout is instance-configurable — the default template must be adapted;
  Contact Lens segment field names follow the published output format and may
  vary across releases.
- **Redaction caveat**: sensitive-data redaction replaces content with
  `[redacted]` — exactly the entities CEER measures. A heavily redacted contact
  is a weak trial for entity-level attribution; the walker flags this rather
  than silently scoring hollow transcripts.
- Connect telephony audio is 8 kHz — no accuracy claim is made for any real
  deployment; the default trial condition is `connect_8khz`.
- Contact Lens post-call analysis is post-call: this reference is for regression
  testing, not real-time gating.

## Why Connect second

The adapter order follows platform shape, not preference: Twilio was the "audio
is already there" case. Connect is the "transcript is already there" case — the
team's Lex V2 bot and Contact Lens segments exist whether or not anyone is
testing. The reference is therefore mostly *mapping*: S3 artifacts and Lex
session states onto the pairing's columns. Rasa closes the trio with the opposite
shape — NLU-only, bring-your-own ASR.
