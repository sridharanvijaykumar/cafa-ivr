"""Minimal adapter contract for CAFA-IVR.

Replace the example methods with your platform-specific ASR/NLU calls.
The scorer itself remains vendor-neutral.
"""
from dataclasses import dataclass

@dataclass
class SemanticResult:
    predicted_intent: str
    predicted_entities_json: str = "{}"
    task_success: bool = False

class ASRAdapter:
    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError

class DownstreamAdapter:
    def evaluate_text(self, text: str) -> SemanticResult:
        raise NotImplementedError


def paired_execute(test, asr: ASRAdapter, downstream: DownstreamAdapter):
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
