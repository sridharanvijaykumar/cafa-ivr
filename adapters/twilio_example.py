"""Illustrative Twilio reference adapter for CAFA-IVR.

Reference only. This file is intentionally NOT executed by the reference test
suite, and it makes no live Twilio calls unless you supply credentials via
environment variables. Never hard-code account credentials here.

Twilio gives an IVR call leg two audio/transcript sources, and they map to
different sides of the CAFA-IVR counterfactual pairing:

  1. Recordings (audio_path side). Audio files on the Recording resource,
     fetched over REST with basic auth (Account SID + Auth Token). These feed
     an ASR adapter: transcribe the recorded caller audio, then run the
     transcript through your downstream NLU.
  2. <Gather input="speech"> (transcript side). Twilio's own speech
     recognition, delivered as the SpeechResult webhook parameter on the
     call -- NOT a REST transcription API. If your flow uses Gather, the
     audio_task outcome comes from the webhook payload, and the reference
     text is the script your IVR played to the caller.

The pairing pattern below uses (1) for the ASR side and a pluggable
downstream NLU for the text side, driven through paired_execute() from
adapters/adapter_contract.py. Every output row carries the columns the
cafa-ivr scorer consumes: asr_transcript, predicted_intent,
predicted_entities_json, text_control_pass, audio_task_success.

Intended repo location: adapters/twilio_example.py (next to
adapter_contract.py), so `from adapter_contract import ...` resolves.
"""
import csv
import json
import os
import tempfile
import urllib.request

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
# 1. Twilio Recording -> local audio file (ASR side)
# ---------------------------------------------------------------------------

class TwilioRecordingFetcher:
    """Download IVR call-leg audio from the Twilio Recording resource.

    Credentials come from TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN (or the
    constructor args); the file is written to a temp dir the caller owns.
    """

    def __init__(self, account_sid=None, auth_token=None):
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN")
        if not (self.account_sid and self.auth_token):
            raise RuntimeError(
                "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment "
                "variables (never hard-code credentials)."
            )

    def fetch(self, recording_sid):
        """Return a local path to the .wav of recording RE...."""
        url = (
            "https://api.twilio.com/2010-04-01/Accounts/%s/Recordings/%s.wav"
            % (self.account_sid, recording_sid)
        )
        mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, self.account_sid, self.auth_token)
        opener = urllib.request.build_opener(
            urllib.request.HTTPBasicAuthHandler(mgr)
        )
        fd, path = tempfile.mkstemp(suffix="-%s.wav" % recording_sid)
        with os.fdopen(fd, "wb") as fh, opener.open(url) as resp:
            fh.write(resp.read())
        return path


# ---------------------------------------------------------------------------
# 2. <Gather> webhook -> trial dict (transcript side)
# ---------------------------------------------------------------------------

def gather_to_trial(webhook_form, *, reference_text, test_id, condition="telephony_8khz",
                    expected_intent="", expected_entities_json="{}",
                    risk_tier="Medium"):
    """Map a Twilio <Gather input="speech"> webhook to a CAFA trial dict.

    webhook_form is the parsed POST body: SpeechResult (transcript) and
    Confidence (0..1) are the documented parameters. Note: Gather
    confidence is a recognizer score, NOT task success -- the attribution
    needs your downstream NLU's verdict on the text control, which the
    pairing below provides. Keep reference_text as the script your IVR
    played; it is the text control the transcript is compared against.
    """
    return {
        "test_id": test_id,
        "condition": condition,
        "reference_text": reference_text,
        "expected_intent": expected_intent,
        "expected_entities_json": expected_entities_json,
        "risk_tier": risk_tier,
        "gather_speech_result": webhook_form.get("SpeechResult", ""),
        "gather_confidence": webhook_form.get("Confidence", ""),
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
# 4. Downstream side: illustrative keyword NLU (OFFLINE DEMO ONLY)
# ---------------------------------------------------------------------------

class KeywordDownstreamAdapter(DownstreamAdapter):
    """Demo-only keyword NLU so the pairing wiring runs without credentials.

    Replace with your IVR's real NLU in production use; keyword matching is
    NOT how intent quality should be judged. It exists here so the
    end-to-end pairing can be verified offline.
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
    resolver treats a 'twilio:RExxxx' audio_path as a Recording SID to
    fetch, and anything else as an already-local path.
    """
    rows = []
    with open(manifest_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            audio_ref = row["audio_path"]
            if audio_resolver is not None:
                local_audio = audio_resolver(row)
            elif audio_ref.startswith("twilio:"):
                local_audio = TwilioRecordingFetcher().fetch(audio_ref.split(":", 1)[1])
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
        "risk_tier", "audio_path",
    ]
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Offline demo: verifies the wiring with no Twilio account and no network.
# ---------------------------------------------------------------------------

def _offline_demo():
    # Pretend the ASR misheard "fifty" as "fifteen" -- the classic
    # entity-substitution shape CEER exists to catch.
    def fake_transcribe(_path):
        return "send fifteen dollars to john smith"

    asr = ExternalAsrAdapter(fake_transcribe)
    downstream = KeywordDownstreamAdapter()
    trial = {
        "test_id": "T-DEMO-01",
        "condition": "telephony_8khz",
        "reference_text": "send fifty dollars to john smith",
        "expected_intent": "transfer_money",
        "expected_entities_json": '{"amount": 50, "recipient": "john smith"}',
        "risk_tier": "High",
        "audio_path": "/tmp/demo-call-leg.wav",
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


if __name__ == "__main__":
    _offline_demo()
