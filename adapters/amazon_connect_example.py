"""Illustrative Amazon Connect reference adapter for CAFA-IVR.

Reference only. This file is intentionally NOT executed by the reference test
suite, and it makes no live AWS calls unless you supply credentials through
boto3's standard credential chain. Never hard-code AWS secrets here.

An Amazon Connect voice contact gives an IVR team two audio/transcript
sources, and they map to different sides of the CAFA-IVR counterfactual
pairing:

  1. Call recordings (audio_path side). Amazon Connect stores call
     recordings as WAV files in an S3 bucket you configure (recording
     behavior is set in the contact flow or at the queue level). These are
     telephony-grade 8 kHz audio -- the same constrained-audio caveat as
     the pilot. They feed an ASR adapter: download the recording, run your
     recognizer over it, then run the transcript through your downstream
     NLU.
  2. Contact Lens analysis segments (transcript side). Post-call, Contact
     Lens writes analysis JSON segments to S3 under your configured prefix.
     Transcript segments carry the customer-side utterance text
     (ParticipantRole == "CUSTOMER") with millisecond offsets. If your
     flow relies on Connect's own transcript, the audio_task outcome comes
     from these segments, and the reference text is the prompt your flow
     played to the caller.

The pairing pattern below uses (1) for the ASR side and Amazon Lex V2
(what most Connect self-service IVRs already run behind) for the text
side, driven through paired_execute() from adapters/adapter_contract.py.
Every output row carries the columns the cafa-ivr scorer consumes:
asr_transcript, predicted_intent, predicted_entities_json,
text_control_pass, audio_task_success.

Intended repo location: adapters/amazon_connect_example.py (next to
adapter_contract.py), so `from adapter_contract import ...` resolves.
"""
import csv
import json
import os
import tempfile

try:
    from adapter_contract import (
        ASRAdapter,
        DownstreamAdapter,
        SemanticResult,
        paired_execute,
    )
except ImportError:  # file copied out of adapters/; wiring still runs duck-typed
    ASRAdapter = DownstreamAdapter = object  # type: ignore
    from dataclasses import dataclass

    @dataclass
    class SemanticResult:  # type: ignore
        predicted_intent: str
        predicted_entities_json: str = "{}"
        task_success: bool = False

    def paired_execute(test, asr, downstream):  # type: ignore
        text_result = downstream.evaluate_text(test["reference_text"])
        transcript = asr.transcribe(test["audio_path"])
        audio_result = downstream.evaluate_text(transcript)
        return {
            **test,
            "asr_transcript": transcript,
            "predicted_intent": audio_result.predicted_intent,
            "predicted_entities_json": audio_result.predicted_entities_json,
            "text_control_pass": text_result.task_success,
            "audio_task_success": audio_result.task_success,
        }


# ---------------------------------------------------------------------------
# 1. Connect call recording -> local audio file (ASR side)
# ---------------------------------------------------------------------------

class ConnectRecordingFetcher:
    """Download a Connect voice contact's call recording from S3.

    Credentials come from boto3's standard chain (env vars, ~/.aws, IAM
    role -- never hard-coded here). The S3 key layout depends on how your
    instance was configured; adapt key_template to your bucket layout.
    """

    def __init__(self, bucket=None, region=None, key_template=None):
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "Install boto3 to use this optional adapter"
            )
        self.bucket = bucket or os.environ.get("CONNECT_RECORDINGS_BUCKET")
        if not self.bucket:
            raise RuntimeError(
                "Set CONNECT_RECORDINGS_BUCKET (or pass bucket=); never "
                "hard-code bucket names in committed code."
            )
        self._s3 = boto3.client("s3", region_name=region)
        # Contact-ID-shaped default; adapt to your recording behavior's prefix.
        self.key_template = (
            key_template or "call-recordings/{contact_id}.wav"
        )

    def fetch(self, contact_id):
        """Return a local path to the .wav of a Connect contact's recording."""
        key = self.key_template.format(contact_id=contact_id)
        fd, path = tempfile.mkstemp(suffix="-%s.wav" % contact_id)
        os.close(fd)
        self._s3.download_file(self.bucket, key, path)
        return path


# ---------------------------------------------------------------------------
# 2. Contact Lens analysis segments -> trial dict (transcript side)
# ---------------------------------------------------------------------------

def contact_lens_customer_transcript(analysis_segments):
    """Rebuild the customer-side transcript from Contact Lens segments.

    analysis_segments is the parsed JSON of a Contact Lens output file
    (the segments written to S3 post-call). Returns (transcript_text,
    redacted_count). Segments whose content is redacted are skipped and
    counted -- see the caveats in the module docstring: redaction hides
    exactly the entities CEER needs, so a heavily redacted contact is a
    weak trial for entity-level attribution.
    """
    utterances = []
    redacted = 0
    for segment in analysis_segments:
        transcript = segment.get("Transcript", {})
        if not transcript:
            continue
        if transcript.get("ParticipantRole") != "CUSTOMER":
            continue
        content = (transcript.get("Content") or "").strip()
        if not content or content == "[redacted]":
            redacted += 1
            continue
        utterances.append(content)
    return " ".join(utterances), redacted


def list_contact_lens_segments(bucket, prefix, *, region=None):
    """Yield parsed Contact Lens analysis JSON docs under an S3 prefix.

    Adapt bucket/prefix to your Contact Lens output location; the segment
    field names below follow the published Contact Lens output format and
    may vary across releases. Credentials via boto3's standard chain.
    """
    try:
        import boto3
    except ImportError:
        raise RuntimeError("Install boto3 to use this optional adapter")
    s3 = boto3.client("s3", region_name=region)
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                continue
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            yield json.loads(body)


def contact_lens_to_trial(contact_id, analysis_segments, *, reference_text,
                          test_id, condition="connect_8khz",
                          expected_intent="", expected_entities_json="{}",
                          risk_tier="Medium"):
    """Map a Contact Lens customer transcript to a CAFA trial dict.

    reference_text is the prompt your Connect flow played to the caller --
    it is the text control the transcript is compared against. Note the
    ASR side here is Connect/Contact Lens itself: this trial answers
    "did Connect's own transcription break the task?" rather than "did
    recognizer X break the task?" Pair it with the recording side (1)
    above if you want to attribute against your own ASR instead.
    """
    transcript, redacted = contact_lens_customer_transcript(analysis_segments)
    return {
        "test_id": test_id,
        "condition": condition,
        "reference_text": reference_text,
        "expected_intent": expected_intent,
        "expected_entities_json": expected_entities_json,
        "risk_tier": risk_tier,
        "connect_contact_id": contact_id,
        "connect_customer_transcript": transcript,
        "connect_redacted_segments": redacted,
    }


# ---------------------------------------------------------------------------
# 3. ASR side: wrap any transcribe function; Whisper hook left to the user
# ---------------------------------------------------------------------------

class ExternalAsrAdapter(ASRAdapter):
    """ASRAdapter that delegates to a caller-supplied transcribe function."""

    def __init__(self, transcribe_fn):
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_path: str) -> str:
        return self._transcribe_fn(audio_path)


def whisper_local_factory(model="base"):
    """Build a transcribe_fn around a local Whisper install (optional dep)."""
    try:
        import whisper  # openai-whisper
    except ImportError:
        raise RuntimeError(
            "Install openai-whisper (or your ASR of choice) to use this "
            "factory; the reference does not depend on it."
        )
    model_obj = whisper.load_model(model)

    def transcribe(audio_path):
        return model_obj.transcribe(audio_path)["text"].strip()

    return transcribe


# ---------------------------------------------------------------------------
# 4a. Downstream side: Amazon Lex V2 (what Connect IVRs typically run)
# ---------------------------------------------------------------------------

class LexV2DownstreamAdapter(DownstreamAdapter):
    """Downstream NLU backed by an Amazon Lex V2 bot, via boto3.

    Mirrors adapters/aws_lex_v2_example.py. task_success is derived from
    whether the recognized intent's session state reached Fulfilled --
    adapt the readiness test to your bot's dialog design; "the NLU
    returned an intent" is not the same as "the task succeeded."
    """

    def __init__(self, bot_id, bot_alias_id, locale_id="en_US", region=None,
                 session_id=None):
        try:
            import boto3
        except ImportError:
            raise RuntimeError("Install boto3 to use this optional adapter")
        import uuid

        self.client = boto3.client("lexv2-runtime", region_name=region)
        self.bot_id = bot_id
        self.bot_alias_id = bot_alias_id
        self.locale_id = locale_id
        self.session_id = session_id or str(uuid.uuid4())

    def evaluate_text(self, text: str) -> SemanticResult:
        response = self.client.recognize_text(
            botId=self.bot_id,
            botAliasId=self.bot_alias_id,
            localeId=self.locale_id,
            sessionId=self.session_id,
            text=text,
        )
        interpretations = response.get("interpretations", [])
        top = interpretations[0] if interpretations else {}
        intent = top.get("intent", {})
        state = intent.get("state", "")
        return SemanticResult(
            predicted_intent=intent.get("name", ""),
            predicted_entities_json=json.dumps(intent.get("slots", {})),
            task_success=state == "Fulfilled",
        )


# ---------------------------------------------------------------------------
# 4b. Downstream side: illustrative keyword NLU (OFFLINE DEMO ONLY)
# ---------------------------------------------------------------------------

class KeywordDownstreamAdapter(DownstreamAdapter):
    """Demo-only keyword NLU so the pairing wiring runs without credentials.

    Replace with Lex V2 (4a) or your real NLU in production use; keyword
    matching is NOT how intent quality should be judged. It exists here
    so the end-to-end pairing can be verified offline.
    """

    RULES = [
        (("balance",), "check_balance"),
        (("pay", "bill"), "pay_bill"),
        (("transfer", "send"), "transfer_money"),
        (("cancel", "card", "lost", "stolen"), "report_card_issue"),
    ]

    def evaluate_text(self, text: str) -> SemanticResult:
        lowered = (text or "").lower()
        for keywords, intent in self.RULES:
            if any(k in lowered for k in keywords):
                return SemanticResult(
                    predicted_intent=intent,
                    predicted_entities_json=json.dumps({"amount": 50})
                    if "fifty" in lowered or "50" in lowered else "{}",
                    task_success=True,
                )
        return SemanticResult(predicted_intent="unknown", task_success=False)


# ---------------------------------------------------------------------------
# 5. Manifest -> scorer-ready rows
# ---------------------------------------------------------------------------

def run_paired_from_manifest(manifest_csv, asr, downstream, audio_resolver=None):
    """Run the counterfactual pairing over every manifest row.

    manifest_csv columns follow examples/manifest_schema_example.csv.
    audio_resolver maps a row's audio_path to a local file; the default
    resolver treats an 's3:bucket/key' audio_path as an S3 object to
    download, and anything else as an already-local path.
    """
    try:
        import boto3
    except ImportError:
        boto3 = None

    rows = []
    with open(manifest_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            audio_ref = row["audio_path"]
            if audio_resolver is not None:
                local_audio = audio_resolver(row)
            elif audio_ref.startswith("s3:") and boto3 is not None:
                bucket, _, key = audio_ref[3:].partition("/")
                fd, local_audio = tempfile.mkstemp(suffix="-" + key.rsplit("/", 1)[-1])
                os.close(fd)
                boto3.client("s3").download_file(bucket, key, local_audio)
            else:
                local_audio = audio_ref
            trial = dict(row, audio_path=local_audio)
            rows.append(paired_execute(trial, asr, downstream))
    return rows


def write_scorer_csv(rows, out_path):
    """Write paired rows in the column layout the cafa-ivr scorer reads."""
    cols = [
        "test_id", "condition", "reference_text", "asr_transcript",
        "expected_intent", "predicted_intent",
        "text_control_pass", "audio_task_success",
        "expected_entities_json", "predicted_entities_json",
        "impact_level", "risk_tier", "evidence_type",
    ]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Offline demo: verifies the wiring with no AWS account and no network.
# ---------------------------------------------------------------------------

def _offline_demo():
    # Pretend the ASR misheard "fifty" as "fifteen" -- the classic
    # entity-substitution shape CEER exists to catch.
    def fake_transcribe(_path):
        return "send fifteen dollars to john smith"

    asr = ExternalAsrAdapter(fake_transcribe)
    downstream = KeywordDownstreamAdapter()
    trial = {
        "test_id": "C-DEMO-01",
        "condition": "connect_8khz",
        "reference_text": "send fifty dollars to john smith",
        "expected_intent": "transfer_money",
        "expected_entities_json": '{"amount": 50, "recipient": "john smith"}',
        "risk_tier": "High",
        "audio_path": "/tmp/demo-connect-recording.wav",
    }
    row = paired_execute(trial, asr, downstream)
    print(json.dumps({k: row[k] for k in (
        "test_id", "asr_transcript", "predicted_intent",
        "text_control_pass", "audio_task_success")}, indent=2))
    print("-> text control passes; this toy intent-only NLU also 'passes' the "
          "audio task -- even though the $50 entity became $15. That blind "
          "spot is exactly what CEER exists to catch: intent-task accuracy "
          "says fine, while an entity-aware check says a High-risk "
          "substitution just corrupted the transaction.")
    # Show the Contact Lens segment walker on synthetic segments, too.
    segments = [
        {"Transcript": {"ParticipantRole": "CUSTOMER", "Content": "I want to send fifty dollars"}},
        {"Transcript": {"ParticipantRole": "AGENT", "Content": "Confirming the amount"}},
        {"Transcript": {"ParticipantRole": "CUSTOMER", "Content": "[redacted]"}},
    ]
    text, redacted = contact_lens_customer_transcript(segments)
    print(json.dumps({"customer_transcript": text, "redacted_segments": redacted},
                     indent=2))


if __name__ == "__main__":
    _offline_demo()
