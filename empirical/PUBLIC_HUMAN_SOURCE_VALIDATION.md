# Public human-speech external validation

## Evidence boundary

This add-on does **not** claim that the local Conformer, PocketSphinx, Whisper, or Wav2Vec2 models were run on the HarperValleyBank audio in this runtime.

The paper now separates three evidence layers:

1. **Locally measured legacy ASR:** 180 actual PocketSphinx decodes on controlled eSpeak audio.
2. **Locally measured neural ASR:** 360 actual Conformer-CTC decodes on controlled eSpeak audio.
3. **External public human-speech source validation:** a six-intent metadata sample from SLUE-HVB / HarperValleyBank, plus published HarperValleyBank neural baseline results clearly attributed to the corpus authors.

## HarperValleyBank source facts

- Public consumer-banking spoken-dialog corpus.
- 23.7 hours, 1,446 conversations, 25,730 utterances, 59 speakers, 8 task classes.
- Speaker-separated 8-kHz telephony audio.
- Eight tasks: order checks, check balance, replace card, reset password, get branch hours, pay bill, schedule appointment, transfer money.
- Original repository transcript JSON schema contains both corrected `human_transcript` and machine-generated `transcript`.
- License: CC-BY-4.0.

Primary sources:
- https://arxiv.org/abs/2010.13929
- https://github.com/cricketclub/gridspace-stanford-harper-valley
- https://huggingface.co/datasets/asapp/slue-phase-2/viewer/hvb/train

## Published baseline context

The HarperValleyBank paper reports, on its speaker-split test set:
- CTC: CER 14.43%, caller-intent accuracy 45.47%.
- LAS: CER 47.45%, caller-intent accuracy 34.96%.
- MTL: CER 38.59%, caller-intent accuracy 42.28%.

These are **published corpus-author results, not measurements produced by our experiment** and are not directly comparable to the closed-set Conformer results.

## Online sample selection

`hvb_online_human_sample_manifest.csv` contains six caller problem-description segments, one each for:
- replace card
- check balance
- transfer money
- schedule appointment
- get branch hours
- reset password

Selection rule: first browser-visible caller problem-description segment for a distinct intent, selected before examining ASR quality.

## Single audited corpus-ASR segment

For issue `0002f70f7386445b`, the original HarperValleyBank transcript JSON shows that the caller's lost-card problem segment has an exact match between the corrected human transcript and the corpus-provided machine transcript, giving segment WER 0. This is one sanity-check segment, not a corpus-level estimate.
