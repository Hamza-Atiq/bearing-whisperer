# Bearing Whisperer

Can the motor current a drive already measures tell a damaged bearing from a healthy one, when it is tested
honestly on bearings it has never seen? This project measures that on public lab data, and wraps the answer in a
small app that tells a technician which motor to check first, how sure it is, and when to call a person.

Entry for the AMD Developer Hackathon ACT III, Track 1 "Intelligent Industry".

**App:** _link added after deployment_

## The honest result

All numbers come from `results/summary.json` (pre-registration fingerprint `383402e7d27e...`).

| | Balanced accuracy |
| --- | --- |
| **Honest: bearings the detector never saw** ("shape" detector, lab quality) | **0.51** (95% range over bearings 0.40 to 0.63) |
| Inflated: the same bearings in training and testing (the common way) | 0.71 |

On bearings it never saw, a current-only detector is about as good as a coin toss here. Its main weakness is
false alarms: it flags 0.75 of healthy recordings and misses 0.23 of damaged ones. The 0.71 you get by testing
on bearings it already saw is the trap many published results fall into. A strict published audit found the
same pattern for motor current (Cekic and Akan, Energies 2026).

**It does not beat the simple baselines** (lab quality): always "damaged" 0.50, one loudness number 0.43, speed
and load setting only 0.49 (at chance, so the setting does not leak the answer). The physics check "tones" (only
the classic bearing pitches) scores 0.42, with its whole 95% range (0.35 to 0.48) below chance.

**Why:** each bearing carries its own fingerprint in the current (mounting, run-in time), and it is louder than
the damage. A simple model can tell which of the 32 bearings a recording came from 77% of the time
(a one-off diagnostic, 16 Oct). With only six healthy bearings, a detector learns the healthy
bearings' fingerprints instead of "healthy".

**Drive-like quality (simulated):** "shape" drops from 0.51 at lab quality to 0.38 at 8 kHz / 12 bit. That loss
of 0.13 is above the 0.10 flag fixed in advance, which suggests it leaned on high-pitch content. It is a flag, not
a proof. "tones" barely changes (0.42 to 0.43).

**Per motor (round 1 at 16 kHz / 12 bit, one operating condition):** flags 65% of 26 damaged motors and 83% of 6
healthy motors; the motor it would list first is a healthy bearing.

**Load test:** trained at normal load and tested at low load, it scores 0.50; the reverse scores 0.58.

### Round 2: a second, separately sealed attempt

Round 2 was designed after seeing round 1, and its rules were sealed (fingerprint `c3f518734dac...`) before it ran.
It tried six combinations of listening set and model, and chose among them **using training bearings only**, so the
test bearings judged the whole procedure once. Every combination's own score is in `results/summary.json`.

| Round 2 (selected: the same 32 pitch bands, with a random forest instead of a straight-line model) | Balanced accuracy |
| --- | --- |
| **Honest: bearings it never saw**, lab quality | **0.82** (95% range 0.68 to 0.92) |
| Inflated: bearings it had seen (computed after round 2) | 0.94 |
| Drive-like 16 kHz / 12 bit | 0.80 (0.64 to 0.92) |
| Drive-like 8 kHz / 12 bit | 0.75 (0.58 to 0.90) |

False alarms on healthy recordings drop from 0.75 to 0.15. Round 2 beats the simple baselines: its whole range is
above the best one (0.50). Because its whole range at 16 kHz / 12 bit is above 0.5, a rule sealed before round 2
ran switched the app's plant view to round 2: per motor it now flags 69% of 26 damaged motors and 1 of 6 healthy
motors.

**Checks run after round 2 to test this surprise** (exploratory, not sealed; `results/round2_checks.json`):

- **Null test:** in each group a random bearing was called "healthy" instead, 20 times. The same method scored 0.49
  on average; none reached 0.82, but the best reached 0.79. The real healthy bearings do stand out, but the
  evidence is moderate, not strong.
- **No leak from the setting:** the same forest given only speed and load scores 0.50.
- **It is not hearing the bearing pitches (HR-15 flag):** the same forest given only the classic bearing pitches
  scores 0.42. One pitch range at a time: up to 1 kHz 0.62, 1 to 4.5 kHz 0.79, above 4.5 kHz 0.84. The difference
  sits in the broad noise above 1 kHz.
- **It does not carry over to a new load:** trained at normal load and tested at low load it scores 0.51 (reverse
  0.50), while trained and tested at one single load, with the same amount of data, it scores 0.80 and 0.81.
- **Run-in time may be part of it:** the healthy bearing with the shortest run-in before the test (K003, 1 hour;
  Lessmeier 2016 Table 7) is the one round 2 flags most (71% of its recordings); the others (5 to over 50 hours)
  are flagged 0% to 21%.

**What this means:** with a model that can say "given this speed and load", motor current does separate these six
healthy bearings from the damaged ones on bearings it never saw. But the separating sound is broad noise, not the
bearing's own pitches, it only works at loads it was trained on, and it may partly be how long a bearing was run
in. With six healthy bearings, this project cannot tell damage apart from these other differences.

So the story is: here is how far current alone gets on unseen bearings, here is what an honest check of a good
number looks like, and here is when to call a person.

## What the app does

- **Plant:** 32 motors (each one lab bearing), marked healthy, check bearing or ask a person, with how sure the
  detector is. Check-bearing motors come first.
- **Motor:** a short technician's note, written by an open model on AMD Token Factory and then checked against
  the detector's facts, shown beside a plain template note built from the same facts. A draft work order that a
  person must approve, and follow-up questions.
- **Results:** every number above, per bearing, per condition, per quality, and every run, not only the best.
- **Business value:** an illustrative example built from the measured rates plus assumptions you can change.

## What runs on AMD

The assistant that turns each verdict into a technician's note, answers follow-up questions and drafts work
orders runs on an open model (Gemma-4-31B-IT, with Qwen3.8-27B as backup) served on AMD GPUs through AMD Token
Factory. Every note is checked before it is shown: it must name the motor, its status, how sure, the evidence and
the urgency, it may not add a number, and it must say to confirm with a vibration or ultrasound check. If the
model fails the check or is offline, the app shows the template note and says so. The detector itself is a small
model (round 1: logistic regression; round 2, used in the plant view: a random forest of 300 trees) that runs
anywhere.

**How the assistant was tested** (`results/assistant_questions.json`): 10 fixed questions
written before testing, asked about 3 motors (one per status), 30 answers in all, all from Gemma. 30 of 30 passed the
automatic check, and all 9 questions it had to refuse (days until failure, which ring is damaged, the brand) were
refused. Read by hand, 29 of 30 were right; once it refused to explain "how sure: medium" although it had the
meaning. On 3 motors, the AMD notes and the template notes both matched the detector's facts with nothing invented;
the AMD notes are shorter and plainer but carry the same facts, so the assistant's clearer value is answering
follow-up questions.

## How the test was kept honest

- The 32 bearings were split into 6 fixed groups, each with one healthy bearing, written down before any result
  (`prereg/prereg.json`, plain words in `prereg/PREREGISTRATION.md`). Each verdict comes from a model that never
  saw that bearing.
- The line between healthy and damaged, and the "ask a person" band, are set only on training bearings, each
  scored by a model that never saw it.
- The detector, the quality settings, the plant view, the size of a "large" change (0.10) and the expected outcome
  were all sealed by SHA-256 fingerprint before any test result. Every run is logged in `results/runs.jsonl`.
- Round 2 was designed after round 1, and its rules were sealed separately before it ran (`prereg/ROUND2.md`).

## What this cannot rule out

- Healthy bearings differ from damaged ones in run-in time and mounting, not only damage.
- Shaft-wobble tones sit about 1.4 Hz from every bearing tone at 1,500 rpm and about 0.8 Hz at 900 rpm, where a
  wobbling shaft tone can spill 1 to 5% of its power into the bearing-tone window (measured by simulation).
- Only six healthy bearings exist, so the results are exploratory, and the "ask a person" band moves between groups.
- The tested bearing sits in a separate module on the shaft line, outside the motor. The current was measured by
  lab sensors between drive and motor; drive-like quality is simulated, not a real drive's sensor.
- **Not claimed:** days until failure, results for bearings inside a motor, or any drive brand's sensor.

## Run it

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/streamlit run app/streamlit_app.py
```

The app reads `results/`. For the AI notes, put `AMD_KEY` in the environment or in Streamlit secrets; without it
the app still works with template notes.

**To remake the results:** the features were extracted on Kaggle (`kaggle/`, or the Colab cells in
`colab/RUN_IN_COLAB.md`), which downloads each bearing from Paderborn University, reads it and deletes it. Then
`python -m bearing.evaluate` (round 1) and `python -m bearing.round2` (round 2). Tests: `python -m pytest -q`.

## Data and licence

Paderborn University bearing data: C. Lessmeier, J. K. Kimotho, D. Zimmer, W. Sextro, "Condition Monitoring of
Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark
Data Set for Data-Driven Classification", PHME 2016. Licence CC BY-NC 4.0. The raw data is not in this repository;
it is downloaded from its source. The files in `results/` are derived from it and shared under the same licence.

Our code: MIT (`LICENSE`).
