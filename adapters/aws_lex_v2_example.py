"""Illustrative Amazon Lex V2 downstream adapter.

This file is intentionally not executed by the reference test suite.
It uses boto3's standard credential chain; never hard-code AWS secrets here.
Adapt locale_id, bot_id, bot_alias_id and session handling to your environment.
"""
import uuid

try:
    import boto3
except ImportError:  # optional dependency
    boto3 = None


def recognize_text(reference_text: str, *, bot_id: str, bot_alias_id: str, locale_id: str = "en_US"):
    if boto3 is None:
        raise RuntimeError("Install boto3 to use this optional adapter")
    client = boto3.client("lexv2-runtime")
    response = client.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=locale_id,
        sessionId=str(uuid.uuid4()),
        text=reference_text,
    )
    interpretations = response.get("interpretations", [])
    top = interpretations[0] if interpretations else {}
    intent = top.get("intent", {})
    return {
        "predicted_intent": intent.get("name", ""),
        "predicted_entities_json": intent.get("slots", {}),
        "raw": response,
    }
