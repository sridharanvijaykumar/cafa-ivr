"""Illustrative Rasa reference adapter for CAFA-IVR.

Reference only. This file is intentionally NOT executed by the reference test
suite, and it makes no live calls unless you point it at your own Rasa
server. Never hard-code auth tokens here.

Rasa is the opposite shape from the other two vendor adapters: it is
NLU-only. Rasa ships no speech recognizer -- in voice deployments, an
external ASR feeds transcripts into Rasa through a voice channel connector
(Twilio voice channel, a custom connector, or a community voice interface).
So the pairing is:

  * Downstream side (this file): Rasa's NLU, reached over the HTTP API's
    POST /model/parse endpoint, on a Rasa server you trained and started
    yourself (`rasa train`, then `rasa run --enable-api`). The text control
    is your reference_text parsed by YOUR model; the audio side is your
    recognizer's transcript parsed by the same model.
  * ASR side (yours): any transcribe function, e.g. the Whisper hook
    below -- Rasa does not constrain this choice, and CAFA-IVR does not
    care which recognizer produced the transcript. A transcript that came
    in over a voice channel instead of a file is fine too: feed it through
    voice_transcript_to_trial() and skip the ASR side.

The counterfactual stays the same: does the task succeed on the reference
text (text_control_pass) and fail, or diverge in entities, on the
transcript (audio_task_success)? Rasa gives you intent name + confidence +
entities per parse, so the downstream adapter maps task_success to
(intent reached your NLU readiness test) -- intent name matches the
expected intent and confidence clears your threshold. See the caveats in
RasaDownstreamAdapter: "the NLU returned an intent" is not the same as
"the task succeeded."

Intended repo location: adapters/rasa_example.py (next to
adapter_contract.py), so `from adapter_contract import ...` resolves.
"""
import csv
import json
import os
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
# 1. Rasa NLU HTTP client (POST /model/parse)
# ---------------------------------------------------------------------------

def parse_with_rasa(text, *, base_url=None, token=None, timeout=30):
    """Parse text with a Rasa server's /model/parse endpoint.

    base_url defaults to the RASA_SERVER_URL env var or the conventional
    local default http://localhost:5005 (server started with
    `rasa run --enable-api`, a trained model loaded). token is optional;
    RASA_TOKEN env var works too. urllib only -- no extra dependencies.
    """
    base = (base_url or os.environ.get("RASA_SERVER_URL")
            or "http://localhost:5005").rstrip("/")
    token = token or os.environ.get("RASA_TOKEN")
    url = base + "/model/parse"
    if token:
        url += "?token=" + token
    req = urllib.request.Request(
        url,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except OSError as exc:
        raise RuntimeError(
            "Could not reach the Rasa server at %s: %s. Train a model "
            "(`rasa train`) and start it with `rasa run --enable-api`."
            % (base, exc)
        )


# ---------------------------------------------------------------------------
# 2. Downstream side: Rasa NLU via /model/parse
# ---------------------------------------------------------------------------

class RasaDownstreamAdapter(DownstreamAdapter):
    """Downstream NLU backed by a Rasa server, via /model/parse.

    task_success is a readiness test you own:
      * the parsed intent name matches expected_intent (when given), and
      * the intent confidence clears confidence_threshold.

    Two explicit caveats. First, if your pipeline uses Rasa's
    FallbackClassifier, a parse that Rasa itself refused to trust arrives
    as intent name "nlu_fallback" -- that is an NLU refusal, not a task
    outcome; it fails the readiness test, which is correct, but don't read
    it as "the task ran and failed." Second, keep confidence_threshold
    consistent with the FallbackClassifier threshold in your config.yml;
    a parse can return an intent name at low confidence, and "the NLU
    returned an intent" is not the same as "the task succeeded."
    """

    def __init__(self, confidence_threshold=0.7, expected_intent=None,
                 base_url=None, token=None):
        self.confidence_threshold = confidence_threshold
        self.expected_intent = expected_intent
        self.base_url = base_url
        self.token = token

    def evaluate_text(self, text: str) -> SemanticResult:
        parse = parse_with_rasa(text, base_url=self.base_url, token=self.token)
        intent = parse.get("intent") or {}
        intent_name = intent.get("name") or ""
        confidence = float(intent.get("confidence") or 0.0)
        entities = {}
        for ent in parse.get("entities") or []:
            name = ent.get("entity")
            if name is None:
                continue
            entities.setdefault(name, []).append(ent.get("value"))
        intent_ok = (
            intent_name and intent_name != "nlu_fallback"
            and confidence >= self.confidence_threshold
        )
        return SemanticResult(
            predicted_intent=intent_name,
            predicted_entities_json=json.dumps(entities),
            task_success=bool(
                intent_ok
                and (self.expected_intent is None
                     or intent_name == self.expected_intent)
            ),
        )


# ---------------------------------------------------------------------------
# 3. Voice-channel transcript -> trial dict (when the ASR side is already
#    a transcript, not a file)
# ---------------------------------------------------------------------------

def voice_transcript_to_trial(transcript, *, reference_text, test_id,
                             condition="custom_asr",
                             expected_intent="", expected_entities_json="{}",
                             risk_tier="Medium"):
    """Map a voice-channel transcript to a CAFA trial dict.

    Use this when your recognizer's output arrives as text (a Rasa voice
    channel webhook, a channel log, a transcript file) rather than an
    audio file -- the ASR side of the pairing is then already resolved,
    and only the reference_text -> transcript counterfactual matters.
    The downstream Rasa adapter parses both sides; set the transcript as
    the trial's asr_transcript directly.
    """
    return {
        "test_id": test_id,
        "condition": condition,
        "reference_text": reference_text,
        "expected_intent": expected_intent,
        "expected_entities_json": expected_entities_json,
        "risk_tier": risk_tier,
        "asr_transcript": transcript,
        "audio_path": "",
    }


# ---------------------------------------------------------------------------
# 4. ASR side: wrap any transcribe function; Whisper hook left to the user
# ---------------------------------------------------------------------------

class ExternalAsrAdapter(ASRAdapter):
    """ASRAdapter that delegates to a caller-supplied transcribe function.

    Rasa does not ship an ASR, so this side is entirely yours: a cloud
    recognizer, a local Whisper install, the recognizer behind your voice
    channel -- CAFA-IVR is agnostic. Set the trial condition to whatever
    describes your audio pipeline (e.g. "telephony_8khz" if that's what
    feeds your recognizer).
    """

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
# 5. Manifest -> scorer-ready rows
# ---------------------------------------------------------------------------

def run_paired_from_manifest(manifest_csv, asr, downstream, audio_resolver=None):
    """Run the counterfactual pairing over every manifest row.

    manifest_csv columns follow examples/manifest_schema_example.csv.
    audio_resolver maps a row's audio_path to a local file; the default
    treats an empty audio_path as "transcript already in the row" (the
    voice-channel shape from voice_transcript_to_trial()) and anything
    else as an already-local path.
    """
    rows = []
    with open(manifest_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            audio_ref = row["audio_path"]
            if audio_resolver is not None:
                local_audio = audio_resolver(row)
            elif not audio_ref:
                trial = dict(row, asr_transcript=row.get("asr_transcript", ""))
                rows.append(paired_execute_voice_trial(trial, downstream))
                continue
            else:
                local_audio = audio_ref
            trial = dict(row, audio_path=local_audio)
            rows.append(paired_execute(trial, asr, downstream))
    return rows


def paired_execute_voice_trial(trial, downstream):
    """Pairing for a trial whose transcript is already known (voice-channel
    shape): parse the reference text and the stored transcript through
    the same downstream NLU."""
    text_result = downstream.evaluate_text(trial["reference_text"])
    audio_result = downstream.evaluate_text(trial["asr_transcript"])
    return {
        **trial,
        "predicted_intent": audio_result.predicted_intent,
        "predicted_entities_json": audio_result.predicted_entities_json,
        "text_control_pass": text_result.task_success,
        "audio_task_success": audio_result.task_success,
    }


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
# Offline demo: verifies the wiring with no Rasa server and no network.
# ---------------------------------------------------------------------------

class _FakeRasaDownstream(DownstreamAdapter):
    """Stands in for RasaDownstreamAdapter in the offline demo: canned
    /model/parse-shaped results, so the pairing wiring is exercised with
    zero infrastructure."""

    PARSES = {
        "send fifty dollars to john smith": {
            "intent": {"name": "transfer_money", "confidence": 0.94},
            "entities": [
                {"entity": "amount", "value": "50"},
                {"entity": "recipient", "value": "john smith"},
            ],
        },
        "send fifteen dollars to john smith": {
            "intent": {"name": "transfer_money", "confidence": 0.93},
            "entities": [
                {"entity": "amount", "value": "15"},
                {"entity": "recipient", "value": "john smith"},
            ],
        },
    }

    def evaluate_text(self, text: str) -> SemanticResult:
        parse = self.PARSES[text]
        entities = {}
        for ent in parse["entities"]:
            entities.setdefault(ent["entity"], []).append(ent["value"])
        intent_name = parse["intent"]["name"]
        confidence = parse["intent"]["confidence"]
        return SemanticResult(
            predicted_intent=intent_name,
            predicted_entities_json=json.dumps(entities),
            task_success=bool(intent_name == "transfer_money"
                              and confidence >= 0.7),
        )


def _offline_demo():
    # Pretend the ASR misheard "fifty" as "fifteen" -- the classic
    # entity-substitution shape CEER exists to catch.
    def fake_transcribe(_path):
        return "send fifteen dollars to john smith"

    asr = ExternalAsrAdapter(fake_transcribe)
    downstream = _FakeRasaDownstream()
    trial = {
        "test_id": "R-DEMO-01",
        "condition": "custom_asr",
        "reference_text": "send fifty dollars to john smith",
        "expected_intent": "transfer_money",
        "expected_entities_json": '{"amount": [50], "recipient": ["john smith"]}',
        "risk_tier": "High",
        "audio_path": "/tmp/demo-rasa-utterance.wav",
    }
    row = paired_execute(trial, asr, downstream)
    print(json.dumps({k: row[k] for k in (
        "test_id", "asr_transcript", "predicted_intent",
        "predicted_entities_json",
        "text_control_pass", "audio_task_success")}, indent=2))
    print("-> text control passes AND the audio task passes (Rasa still "
          "classifies transfer_money at 0.93) -- even though the $50 entity "
          "became $15. That blind spot is exactly what CEER exists to "
          "catch: intent-task accuracy says fine, while an entity-aware "
          "check says a High-risk substitution just corrupted the "
          "transaction.")
    # The voice-channel shape: transcript already known, no audio file.
    voice_trial = voice_transcript_to_trial(
        "send fifteen dollars to john smith",
        reference_text="send fifty dollars to john smith",
        test_id="R-DEMO-02",
        expected_intent="transfer_money",
        expected_entities_json='{"amount": [50], "recipient": ["john smith"]}',
        risk_tier="High",
    )
    voice_row = paired_execute_voice_trial(voice_trial, downstream)
    print(json.dumps({k: voice_row[k] for k in (
        "test_id", "asr_transcript", "predicted_intent",
        "predicted_entities_json",
        "text_control_pass", "audio_task_success")}, indent=2))
    print("-> same attribution without any audio file: the "
          "voice-channel trial carries asr_transcript directly.")


if __name__ == "__main__":
    _offline_demo()
