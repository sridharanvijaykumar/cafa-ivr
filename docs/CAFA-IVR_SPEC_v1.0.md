# CAFA-IVR v1.0 Reference Specification

**Counterfactual ASR Failure Attribution for Conversational IVR**  
Status: Reference Specification v1.0  
Author: Vijay Kumar Sridharan  
IEEE Senior Member  
Frisco, TX, USA

## 1. Purpose

CAFA-IVR defines a portable method for testing whether the addition of an audio/ASR layer causes a conversational test to fail when the same semantic request succeeds through a reference-text control.

The framework is intentionally independent of ASR vendor, NLU vendor, contact-center platform, and dialogue architecture.

## 2. Normative language

The terms **MUST**, **SHOULD**, and **MAY** describe required, recommended, and optional implementation behavior.

## 3. Required paired execution

For every semantic case `i`, implementations MUST execute:

```text
T_i: reference_text -> downstream system -> outcome
A_i: audio -> ASR -> downstream system -> outcome
```

The downstream configuration SHOULD be frozen between `T_i` and `A_i`.

The audio and text cases MUST share the same expected semantic outcome.

## 4. Attribution states

| Text control | Audio path | CAFA-IVR state | Interpretation |
|---|---|---|---|
| Pass | Pass | `HEALTHY` | End-to-end semantic success |
| Pass | Fail | `SPEECH_ATTRIBUTABLE` | Failure appears after speech path is introduced |
| Fail | Fail | `DOWNSTREAM_OR_TEST` | Reference text already fails; do not blame ASR |
| Fail | Pass | `CONTEXT_OR_ORACLE` | Investigate nondeterminism, context, or test oracle |

A `SPEECH_ATTRIBUTABLE` state narrows the failure surface; it does not by itself prove a single acoustic root cause.

## 5. Required trial record

Every scored trial MUST retain:

| Field | Required | Description |
|---|---:|---|
| `test_id` | Yes | Stable semantic test identifier |
| `condition` | Yes | Clean / telephony / noise / rate / other |
| `reference_text` | Yes | Human-authored canonical transcript |
| `asr_transcript` | Yes | Transcript emitted by the tested speech engine |
| `expected_intent` | Yes* | Expected semantic goal or equivalent task oracle |
| `predicted_intent` | Yes* | Observed semantic goal |
| `text_control_pass` | Yes | Result when ASR is bypassed |
| `audio_task_success` | Yes | Result through audio -> ASR path |
| `expected_entities_json` | Recommended | Governed critical values |
| `predicted_entities_json` | Recommended | Resolved critical values |
| `risk_tier` | Recommended | Low / Medium / High or local equivalent |
| `impact_level` | Optional | L0-L4 consequence classification |
| ASR/NLU/agent version | Recommended | Reproducibility metadata |

`*` For generative/tool-using agents, a deterministic task-success oracle MAY replace intent labels.

## 6. Metrics

### 6.1 Word Error Rate

`WER = (S + D + I) / N`

WER MUST remain visible as the lexical diagnostic even when downstream task performance is the primary release criterion.

### 6.2 ASR-Attributable Intent Failure Rate (ASR-IFR)

For each trial:

```text
F_i = 1 when text_control_pass = true AND audio_task_success = false
      0 otherwise
```

Then:

`ASR-IFR = sum(F_i) / N`

Teams MAY additionally report a conditional IFR using only text-control-capable cases as the denominator.

### 6.3 Critical-Entity Error Rate (CEER)

CEER evaluates governed information such as:

- payment amounts
- dates
- negation
- account/card type
- lock/unlock/cancel/confirm actions
- authentication values
- fraud/dispute terminology

Entity normalization SHOULD happen before CEER scoring so equivalent representations such as `500` and `five hundred` are treated consistently.

For a result set, CEER is the total number of missing and spurious critical entities divided by the total number of reference critical entities. It is an unbounded normalized error count, not a probability, and MAY exceed 1.0 when spurious entities outnumber reference entities.

### 6.4 Conversational Impact Error Rate (CIER)

CIER is optional in v1.0. The reference implementation recognizes:

```text
L0 = 0.00   healthy
L1 = 0.00   benign lexical error
L2 = 0.25   semantic/entity error
L3 = 0.65   task/dialogue failure
L4 = 1.00   critical consequence
```

These weights are illustrative policy parameters and MUST NOT be represented as universal industry thresholds.

CIER measures realized consequence. Let `I` be the set of trials carrying a recognized impact level. For each `i` in `I`, let `A_i = 1` when the audio-path task succeeds and `0` when it fails, and let `w(L_i)` be the selected impact-level weight. Then:

`CIER = sum((1 - A_i) * w(L_i) for i in I) / |I|`

A successful audio-path task MUST contribute `0` rather than being excluded, so CIER is a severity-weighted failure rate over the impact-labelled population rather than an average severity of failures. A failed task contributes its L0-L4 weight; a trial without a recognized impact level is excluded.

CIER counts realized audio-path task failures regardless of attribution, including trials whose text control also failed. It is not restricted to `SPEECH_ATTRIBUTABLE` failures. An ASR-attributable consequence analysis SHOULD filter to `attribution = SPEECH_ATTRIBUTABLE` before summarizing CIER.

## 7. Minimum acoustic test matrix

A production test suite SHOULD include the following when relevant:

| Dimension | Minimum examples |
|---|---|
| Baseline | clean/wideband |
| Telephony | 8-kHz narrowband or actual codec path |
| Noise | moderate and severe controlled SNR |
| Speaking rate | normal plus bounded fast/slow condition |
| Speakers | multiple representative human speakers |
| Critical semantics | amounts, dates, negation, high-risk actions |

Synthetic speech MAY expand coverage but SHOULD NOT be the only evidence used to claim human-speech robustness.

## 8. Risk-aware release gates

CAFA-IVR does not mandate universal numeric thresholds. A team SHOULD compare a candidate against its last approved baseline and SHOULD define stronger gates for high-consequence intents.

Recommended policy pattern:

1. No unexplained statistically meaningful increase in ASR-IFR.
2. No new governed critical-entity failures for high-risk journeys without explicit approval.
3. WER regressions are investigated, but WER alone does not determine release approval.
4. Text-control regressions are routed to NLU/agent/test owners rather than ASR owners.
5. Every failed release gate retains audio, transcript, expected outcome, observed outcome, and version metadata.

## 9. CI/CD lifecycle

```text
Freeze versions
   |
Run text controls --------------------+
   |                                  |
Run clean + stressed audio            |
   |                                  |
Score WER / CEER / ASR-IFR            |
   |                                  |
Compare to approved baseline <--------+
   |
PASS -> release candidate
FAIL -> attributed investigation -> rerun
```

## 10. Vendor adapter contract

An adapter MAY call any ASR/NLU/agent. It MUST return the CAFA-IVR trial record. Secrets and credentials SHOULD remain in the platform's standard credential mechanism and MUST NOT be committed to a CAFA results package.

## 11. Reproducibility

A publishable or independently auditable CAFA-IVR run SHOULD freeze:

- audio files or immutable source identifiers
- perturbation parameters and random seeds
- ASR model/engine version
- NLU/agent version
- prompts and tool schemas if generative models are used
- locale and endpoint configuration
- test oracle version
- CAFA-IVR specification version

The v1.0 reference release recomputes scores from supplied decoded outputs. It does not include the audio-generation, ASR-decoding, perturbation, or bootstrap-resampling pipelines and therefore does not reproduce the reported decode-level and bootstrap results end to end.

The included 360-trial pilot contains no critical-entity annotations or impact labels. It exercises WER and ASR-IFR; it does not empirically exercise CEER or CIER.

## 12. Adoption statement

An organization can accurately describe implementation with wording such as:

> We evaluated conversational voice regressions using CAFA-IVR v1.0 paired reference-text and audio-path testing and incorporated ASR-IFR into our failure-triage workflow.

The organization should only make such a statement if the paired procedure was actually used.

## 13. Non-endorsement

CAFA-IVR is a technical reference framework. Listing an employer, vendor, dataset, or platform does not imply sponsorship or endorsement. Production thresholds and risk decisions remain the responsibility of the adopting organization.
