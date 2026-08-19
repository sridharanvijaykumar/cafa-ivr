# Reference scorer validation

The CAFA-IVR v1.0 reference scorer was run against the included 360-trial measured Conformer-CTC result file.

Reproduced overall values:

- N = 360
- WER = 0.6484292328
- intent/task accuracy = 0.4111111111
- text-control accuracy = 0.8000000000
- ASR-IFR = 0.3944444444
- speech-attributable trials = 142

These match the rounded empirical paper values (64.8% WER, 41.1% intent accuracy, 39.4% ASR-IFR).
