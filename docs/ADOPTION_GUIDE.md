# CAFA-IVR Adoption Guide

## Goal

Get from an existing voicebot regression suite to a paired CAFA-IVR run with minimal architectural change.

## Step 1 - Select semantic tests

Start with 20-50 existing intents/tasks. Include low-risk inquiries and high-risk actions. Each test needs a canonical reference text and deterministic expected outcome.

## Step 2 - Establish the text control

Execute the reference text directly against the same downstream NLU/agent used by the voice path. Do not continue to ASR attribution for a case without recording whether this control passes.

## Step 3 - Execute audio

Use recorded human speech, approved synthetic speech, or both. Preserve the raw audio and ASR transcript.

## Step 4 - Score

Populate the CAFA-IVR CSV and run:

```bash
cafa-ivr score --input trials.csv --out cafa_out
```

## Step 5 - Triage by attribution

- `SPEECH_ATTRIBUTABLE`: speech/ASR/channel investigation
- `DOWNSTREAM_OR_TEST`: NLU/agent/oracle investigation
- `CONTEXT_OR_ORACLE`: nondeterminism/context investigation
- `HEALTHY`: no semantic regression

## Step 6 - Add critical entities

Mark amounts, dates, negation and high-risk actions. Normalize entities before CEER scoring.

## Step 7 - Put CAFA in CI/CD

Store the approved baseline summary. On a new release, run the same fixed corpus and compare the candidate summary. Treat example thresholds in the reference CLI as placeholders until governance approves local gates.

## Step 8 - Preserve adoption evidence

Record the version used, date, independent evaluator, test scope, decision and resulting engineering change. Use `ADOPTION_EVIDENCE_LOG.md`.
