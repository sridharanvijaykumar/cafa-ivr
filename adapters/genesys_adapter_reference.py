"""Illustrative Genesys Cloud CX reference adapter for CAFA-IVR.

Reference only. This file is intentionally NOT executed by the reference test
suite, and it makes no live Genesys calls unless you supply an OAuth client
via environment variables. Never hard-code client secrets here.

Genesys Cloud gives an IVR call two audio/transcript sources, and they map to
different sides of the CAFA-IVR counterfactual pairing:

  1. Conversation recordings (audio_path side). Call-leg audio on the
     Conversations / Recording API, fetched over REST with an OAuth bearer
     token (client-credentials grant). These feed an ASR adapter: transcribe
     the recorded caller audio, then run the transcript through your
     downstream NLU.
  2. Speech and Text Analytics transcripts (transcript side). Genesys Cloud's
     own speech-to-text for the conversation, reached through the
     transcripturl endpoint -- a signed download URL, returned per
     (conversationId, communicationId) pair. If your flow already uses
     Genesys transcription, the audio_task outcome comes from this payload,
     and the reference text is the script your Architect flow played to the
     caller.

The pairing pattern below uses (1) for the ASR side and a pluggable
downstream NLU for the text side, driven through paired_execute() from
adapters/adapter_contract.py. Every output row carries the columns the
cafa-ivr scorer consumes: asr_transcript, predicted_intent,
predicted_entities_json, text_control_pass, audio_task_success.

About the downstream side: unlike Rasa, Genesys Cloud exposes no stateless
NLU-eval HTTP endpoint (Architect bot flows delegate intent recognition to
the connected bot -- typically Google Dialogflow CX/ES or Amazon Lex V2 via
a Genesys integration -- and evaluate inside the flow). So the downstream
side here is the NLU behind YOUR Architect bot flow, reached through that
platform's API -- the Connect and Rasa references in this folder already show
the wrapper shape for Lex V2 and Rasa. The Genesys adapter below supplies
the two Genesys-side sources; pair them with whichever downstream adapter
matches your flow's NLU. The offline demo uses the same demo-only keyword
NLU as the Twilio reference so the wiring is verifiable without
infrastructure.

Intended repo location: adapters/genesys_example.py (next to
adapter_contract.py), so `from adapter_contract import ...` resolves.
"""
import base64
import csv
import json
import os
import tempfile
import urllib.parse
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
# 1. Genesys Cloud API client (OAuth client-credentials, urllib only)
# ---------------------------------------------------------------------------

class GenesysCloudClient:
    """Minimal Genesys Cloud REST client.

    Auth: POST https://login.{environment}/oauth/token with
    grant_type=client_credentials (HTTP Basic with client_id:client_secret).
    Credentials come from GENESYS_CLIENT_ID / GENESYS_CLIENT_SECRET (or the
    constructor args); GENESYS_ENVIRONMENT defaults to "mypurecloud.com"
    (override per region, e.g. "usw2.pure.cloud", "mypurecloud.de"). API
    base becomes https://api.{environment}.

    The OAuth client needs a role with, at minimum:
      * recording:recording:view and recording:recording:download (audio),
      * speechAndTextAnalytics:data:view (transcripts),
    plus analytics:conversationDetail:view if you read the conversation
    detail to resolve communication IDs. Check the role, don't guess.
    """

    def __init__(self, client_id=None, client_secret=None, environment=None):
        self.client_id = client_id or os.environ.get("GENESYS_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("GENESYS_CLIENT_SECRET")
        self.environment = (environment
                            or os.environ.get("GENESYS_ENVIRONMENT")
                            or "mypurecloud.com")
        if not (self.client_id and self.client_secret):
            raise RuntimeError(
                "Set GENESYS_CLIENT_ID and GENESYS_CLIENT_SECRET environment "
                "variables (never hard-code client secrets)."
            )
        self._token = None

    @property
    def api_base(self):
        return "https://api.%s/api/v2" % self.environment

    def _get_token(self):
        if self._token is not None:
            return self._token
        url = "https://login.%s/oauth/token" % self.environment
        basic = base64.b64encode(
            ("%s:%s" % (self.client_id, self.client_secret)).encode("utf-8")
        ).decode("ascii")
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(
                {"grant_type": "client_credentials"}).encode("utf-8"),
            headers={"Authorization": "Basic " + basic,
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        token = payload.get("access_token")
        if not token:
            raise RuntimeError(
                "Genesys OAuth token exchange failed; check client id/secret "
                "and that the environment (%s) matches your region."
                % self.environment)
        self._token = token
        return token

    def get(self, path, params=None):
        """GET a /api/v2 path; returns the decoded JSON payload."""
        url = self.api_base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"Authorization": "Bearer " + self._get_token()},
            method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# 2. Conversation recordings -> local audio file (ASR side)
# ---------------------------------------------------------------------------

class GenesysRecordingFetcher:
    """Download IVR call-leg audio from the Conversations / Recording API.

    GET /api/v2/conversations/{conversationId}/recordings returns the
    conversation's recordings; each entity carries a mediaUris map with
    signed download URIs. Prefer the external (caller) recording -- Genesys
    Cloud records one recording per participant -- then WAV, else MP3.
    Recordings are telephony-grade 8 kHz: set the trial condition to
    "telephony_8khz" (the same constrained-audio caveat as the pilot).
    Endpoint and field names follow the Genesys Cloud API Explorer's
    Recording API; verify against your region's explorer if they differ.
    """

    def __init__(self, client=None):
        self.client = client or GenesysCloudClient()

    def fetch(self, conversation_id, communication_id=None):
        """Return a local path to the caller's recording WAV/MP3."""
        payload = self.client.get(
            "/conversations/%s/recordings" % conversation_id)
        entities = payload.get("entities") or []
        if not entities:
            raise RuntimeError(
                "No recordings found for conversation %s (recording may be "
                "disabled on the queue/flow, or the recording retention "
                "period has elapsed)." % conversation_id)
        entities = self._prefer_external(entities, communication_id)
        for rec in entities:
            media_uris = rec.get("mediaUris") or {}
            uri = self._pick_uri(media_uris)
            if uri:
                return self._download(uri, rec.get("id", "recording"))
        raise RuntimeError(
            "Recordings exist for conversation %s but none carried a "
            "downloadable mediaUri." % conversation_id)

    @staticmethod
    def _prefer_external(entities, communication_id):
        if communication_id:
            for rec in entities:
                if rec.get("communicationId") == communication_id:
                    return [rec] + [e for e in entities if e is not rec]
        external = [e for e in entities if e.get("isExternal", False)]
        return external + [e for e in entities if not e.get("isExternal", False)]

    @staticmethod
    def _pick_uri(media_uris):
        for key in ("WAV", "WAV_128", "MP3", "OGG"):
            entry = media_uris.get(key) or {}
            if entry.get("mediaUri"):
                return entry["mediaUri"]
        for entry in media_uris.values():
            if (entry or {}).get("mediaUri"):
                return entry["mediaUri"]
        return None

    def _download(self, uri, recording_id):
        fd, path = tempfile.mkstemp(suffix="-genesys-%s.wav" % recording_id)
        req = urllib.request.Request(
            uri, headers={"Authorization": "Bearer " + self.client._get_token()},
            method="GET")
        with os.fdopen(fd, "wb") as fh, urllib.request.urlopen(req,
                                                               timeout=300) as resp:
            fh.write(resp.read())
        return path


# ---------------------------------------------------------------------------
# 3. Speech and Text Analytics transcript -> trial dict (transcript side)
# ---------------------------------------------------------------------------

def genesys_customer_transcript(transcript_json):
    """Extract the caller-side transcript from a transcripturl download.

    The transcripturl payload is a JSON transcript document; phrases are
    listed in order. This keeps entries whose speaker maps to the caller/
    customer participant and joins them in order -- the same customer-only
    filtering as the Connect reference's Contact Lens walker. The exact
    document shape is the transcript format your org receives from the
    /speechandtextanalytics/.../transcripturl endpoint; verify field names
    against it. Phrases are matched against common speaker-label
    spellings so the function degrades loudly (ValueError) rather than
    silently scoring empty text.
    """
    participants = {}
    for p in transcript_json.get("participants") or []:
        participants[p.get("id")] = (p.get("purpose") or p.get("name") or "").lower()
    customer_texts = []
    phrases = transcript_json.get("phrases") or []
    for ph in phrases:
        pid = ph.get("participantId") or ph.get("participant_id")
        label = participants.get(pid, "")
        text = (ph.get("text") or "").strip()
        if not text:
            continue
        if pid is None or "customer" in label or "external" in label \
                or "caller" in label:
            customer_texts.append(text)
    if not customer_texts and phrases:
        raise ValueError(
            "No customer-side phrases found in the transcript document; "
            "check the participant labeling of your transcript format.")
    return {
        "transcript": " ".join(customer_texts),
        "phrase_count": len(customer_texts),
    }


class GenesysTranscriptFetcher:
    """Fetch a conversation's Genesys transcription (post-call).

    GET /api/v2/speechandtextanalytics/conversations/{conversationId}/
    communications/{communicationId}/transcripturl returns a signed
    download URL. Needs speechAndTextAnalytics:data:view (+
    recording:recording:view). Resolve communicationId from the
    conversation detail (GET /api/v2/conversations/{conversationId} ->
    participants' communication records).

    Transcripts are POST-CALL: this reference is for regression testing,
    not real-time gating. Also note the attribution framing: a trial built
    from this transcript answers "did Genesys's own transcription break the
    task?" -- pair it with the recording side (2) if you want to attribute
    against your own ASR instead.
    """

    def __init__(self, client=None):
        self.client = client or GenesysCloudClient()

    def fetch(self, conversation_id, communication_id):
        payload = self.client.get(
            "/speechandtextanalytics/conversations/%s/communications/%s/transcripturl"
            % (conversation_id, communication_id))
        url = payload.get("url")
        if not url:
            raise RuntimeError(
                "transcripturl returned no URL for %s/%s (Speech and Text "
                "Analytics may not be licensed for this org, or no "
                "transcript exists for that communication)."
                % (conversation_id, communication_id))
        with urllib.request.urlopen(url, timeout=120) as resp:
            document = json.loads(resp.read().decode("utf-8"))
        return genesys_customer_transcript(document)


def transcript_to_trial(customer_transcript, *, reference_text, test_id,
                        conversation_id, communication_id="",
                        condition="telephony_8khz",
                        expected_intent="", expected_entities_json="{}",
                        risk_tier="Medium"):
    """Map a Genesys customer transcript to a CAFA trial dict.

    reference_text is the script the Architect flow played / the prompt the
    caller was answering -- the text control the transcript is compared
    against.
    """
    return {
        "test_id": test_id,
        "condition": condition,
        "reference_text": reference_text,
        "expected_intent": expected_intent,
        "expected_entities_json": expected_entities_json,
        "risk_tier": risk_tier,
        "genesys_conversation_id": conversation_id,
        "genesys_communication_id": communication_id,
        "asr_transcript": customer_transcript,
        "audio_path": "",
    }


# ---------------------------------------------------------------------------
# 4. ASR side: wrap any transcribe function; Whisper hook left to the user
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
# 5. Downstream side: illustrative keyword NLU (OFFLINE DEMO ONLY)
#
# Genesys Cloud has no stateless NLU-eval endpoint, so production use plugs
# in the NLU behind your Architect bot flow (Dialogflow CX/ES or Amazon Lex
# V2 reached through that platform's API -- see the Rasa/Connect references
# for the wrapper shape). Keyword matching is NOT how intent quality should
# be judged; it exists so the pairing wiring runs offline.
# ---------------------------------------------------------------------------

class KeywordDownstreamAdapter(DownstreamAdapter):
    """Demo-only keyword NLU. Replace with your Architect flow's real NLU."""

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
# 6. Manifest -> scorer-ready rows
# ---------------------------------------------------------------------------

def run_paired_from_manifest(manifest_csv, asr, downstream, audio_resolver=None,
                             transcript_resolver=None):
    """Run the counterfactual pairing over every manifest row.

    manifest_csv columns follow examples/manifest_schema_example.csv.
    Two row shapes are supported:
      * audio rows: audio_path holds a local file, or "genesys:<conversationId>"
        (optionally "genesys:<conversationId>:<communicationId>") to fetch
        the caller recording -- the default audio_resolver.
      * transcript rows: audio_path is empty and asr_transcript is already set
        (e.g. from transcript_to_trial()); only the downstream pairing runs.
    Pass audio_resolver/transcript_resolver to change either behavior.
    """
    rows = []
    with open(manifest_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            audio_ref = row.get("audio_path") or ""
            if transcript_resolver is not None:
                rows.append(transcript_resolver(row, downstream))
            elif not audio_ref and row.get("asr_transcript"):
                trial = dict(row)
                rows.append(_paired_transcript_trial(trial, downstream))
                continue
            else:
                if audio_resolver is not None:
                    local_audio = audio_resolver(row)
                elif audio_ref.startswith("genesys:"):
                    parts = audio_ref.split(":")
                    local_audio = GenesysRecordingFetcher().fetch(
                        parts[1], parts[2] if len(parts) > 2 else None)
                else:
                    local_audio = audio_ref
                trial = dict(row, audio_path=local_audio)
                rows.append(paired_execute(trial, asr, downstream))
    return rows


def _paired_transcript_trial(trial, downstream):
    """Pairing for a trial whose transcript is already known (transcript-
    side shape): run the reference text and the stored Genesys transcript
    through the same downstream NLU."""
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
# Offline demo: verifies the wiring with no Genesys org and no network.
# ---------------------------------------------------------------------------

_FAKE_TRANSCRIPT_DOC = {
    "participants": [
        {"id": "p-caller", "purpose": "customer"},
        {"id": "p-flow", "purpose": "ivr"},
    ],
    "phrases": [
        {"participantId": "p-flow", "text": "How much would you like to send?"},
        {"participantId": "p-caller", "text": "send fifteen dollars to john smith"},
        {"participantId": "p-flow", "text": "Confirming transfer."},
    ],
}


def _offline_demo():
    # Check 1: customer-side transcript extraction on a transcripturl-shaped
    # document -- the IVR prompt is excluded, only the caller phrase kept.
    extracted = genesys_customer_transcript(_FAKE_TRANSCRIPT_DOC)
    assert extracted["transcript"] == "send fifteen dollars to john smith", extracted
    assert extracted["phrase_count"] == 1, extracted
    print(json.dumps(extracted, indent=2))

    # Check 2: the audio-side pairing. Pretend the ASR misheard "fifty" as
    # "fifteen" -- the classic entity-substitution shape CEER exists to
    # catch.
    def fake_transcribe(_path):
        return "send fifteen dollars to john smith"

    asr = ExternalAsrAdapter(fake_transcribe)
    downstream = KeywordDownstreamAdapter()
    trial = {
        "test_id": "G-DEMO-01",
        "condition": "telephony_8khz",
        "reference_text": "send fifty dollars to john smith",
        "expected_intent": "transfer_money",
        "expected_entities_json": '{"amount": 50, "recipient": "john smith"}',
        "risk_tier": "High",
        "audio_path": "/tmp/demo-genesys-call-leg.wav",
    }
    row = paired_execute(trial, asr, downstream)
    print(json.dumps({k: row[k] for k in (
        "test_id", "asr_transcript", "predicted_intent",
        "predicted_entities_json",
        "text_control_pass", "audio_task_success")}, indent=2))
    print("-> text control passes AND the audio task passes (the demo NLU "
          "still sees transfer_money at high confidence) -- even though the "
          "$50 entity became $15. That blind spot is exactly what CEER exists "
          "to catch: intent-task accuracy says fine, while an entity-aware "
          "check says a High-risk substitution just corrupted the "
          "transaction.")

    # Check 3: the transcript-side trial (no audio file needed) -- the
    # pairing the transcripturl fetch feeds.
    t_trial = transcript_to_trial(
        extracted["transcript"],
        reference_text="send fifty dollars to john smith",
        test_id="G-DEMO-02",
        conversation_id="00000000-0000-0000-0000-000000000000",
        expected_intent="transfer_money",
        expected_entities_json='{"amount": 50, "recipient": "john smith"}',
        risk_tier="High",
    )
    t_row = _paired_transcript_trial(t_trial, downstream)
    print(json.dumps({k: t_row[k] for k in (
        "test_id", "asr_transcript", "predicted_intent",
        "text_control_pass", "audio_task_success")}, indent=2))
    print("-> same attribution without any audio file: the transcript-side "
          "trial carries asr_transcript directly.")


if __name__ == "__main__":
    _offline_demo()
