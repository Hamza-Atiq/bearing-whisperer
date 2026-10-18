# Bearing Whisperer

Can the motor current a drive already measures tell a damaged bearing from a healthy one, when it is tested
honestly on bearings it has never seen, and at a load it was not trained on? This project measures that on public
lab data, and wraps the answer in a web app that tells a technician which motor to check first, how sure it is, and
when to call a person. An open model on AMD GPUs does all the explaining and planning, and every word it writes is
fact-checked before it is shown.

Entry for the AMD Developer Hackathon ACT III, Track 1 "Intelligent Industry".

**App:** https://bearing-whisperer.vercel.app/ (opens in any browser, no install)

## The honest result in one table

Balanced accuracy on bearings the detector never saw (0.50 = coin flip). 95% ranges come from resampling whole
bearings. Every number is in `results/summary.json`, `results/round3.json` and `results/round4.json`.

| | Same load, lab quality | **New load** (trained at one load, tested at the other) | **Each condition left out** (the published test) | Inflated (bearings seen) |
| --- | --- | --- | --- | --- |
| Round 1 (sealed first) | 0.51 (0.40 to 0.63) | 0.50 and 0.58 | not run | 0.71 |
| Round 2 (sealed separately) | 0.82 (0.68 to 0.92) | 0.51 and 0.50 (checked after round 2) | not run | 0.94 |
| Round 3 (sealed separately) | 0.83 (0.69 to 0.94) | 0.79 and 0.83 | not run | 0.95 |
| **Round 4 (sealed; runs the app)** | **0.81 (0.66 to 0.93)** | **0.80 (0.65 to 0.93) and 0.84 (0.73 to 0.93)** | **mean 0.78** (0.77 to 0.82 per condition) | 0.95 |

At the drive-like quality the app uses (16 kHz, 12 bit, simulated), round 4 scores 0.82 at the same load, 0.77 and
0.78 at a new load, and a mean of 0.81 with each condition left out. At the same load and lab quality it raises false
alarms on 17% of healthy recordings and misses 20% of damaged ones; it decides 81% of recordings and scores 0.86 on
those.

**Round 4 exists because our own audit found two problems in round 3** (both stated; round 3 stays reported):
round 3 compared each motor with the fleet "at the same condition", and the condition name includes the side force on
the bearing, which a drive cannot know (removing it: lab 0.83 to 0.81, 16 kHz 0.82 to 0.82); and round 3 did not run
the test the published audit uses.

## Against published work, like for like

Cekic and Akan (Energies 2026, doi 10.3390/en19163884) tested motor current on this dataset with unseen bearings and
each operating condition left out in turn, using deep networks on time-frequency images. Round 4 ran the same kind of
test (lab quality):

| Target | Theirs (from their abstract) | Ours, round 4 |
| --- | --- | --- |
| Healthy vs real (aged) damage | 0.736, the best of eight models | 0.86 (0.71 to 0.99), real wear on one ring |
| Healthy vs all damage types | about 0.50 (0.503 for a matched model), with about 85 to 90% false alarms | 0.78 (0.62 to 0.93), with 26% false alarms |

This is not a head-to-head: different models, splits and seeds. Our "compare with the fleet" step uses other motors'
unlabelled recordings at the test condition, which theirs did not; without that step our score in the same test is
0.72. On the dataset authors' own split (Lessmeier 2016, three answers) we are at about guessing (below).

**Per motor in the app** (round 4, 16 kHz / 12 bit, one condition): it marks "check bearing" on 69% of 26 damaged
motors and on none of the 6 healthy ones; it hands 2 of the 6 healthy motors and 4 of the 26 damaged ones to a person.

## How we got there (four sealed rounds)

Each round's rules were written down and fingerprinted (SHA-256) before it touched the test bearings, and every
round stays reported, including the ones that failed.

1. **Round 1** (`prereg/prereg.json`): 32 pitch slices of the current's "hiss" and a straight-line model. Near
   chance: each bearing has its own fingerprint (mounting, run-in) that is louder than the damage.
2. **Round 2** (`prereg/ROUND2.md`): six combinations, chosen fairly on training bearings only. A random forest on the
   same 32 slices reached 0.82, but fell to chance at a new load.
3. **Round 3** (`prereg/ROUND3.md`): the same forest, but each recording is first compared with the fleet at the
   same condition (minus the fleet's middle, divided by its spread). The fleet is the training bearings, used
   **without their labels**, which is what a drive could know: how its other motors sound at this load, not which
   are damaged.
4. **Round 4** (`prereg/ROUND4.md`): round 3 with the fleet grouped by speed and load only (never the side force), and
   the published test added: each of the four operating conditions left out in turn. A control without the fleet step
   is run the same way and shown.

## What round 4 still cannot do (said as loudly as the good news)

- **It does not hear the bearing's own notes.** Checks run after round 3 (`results/round3_checks.json`, same method,
  one pitch range at a time): classic bearing notes only 0.45; pitches up to 1 kHz 0.57; 1 to 4.5 kHz 0.80; above
  4.5 kHz 0.83. The result comes from the broad hiss above 1 kHz.
- **The null test is a real warning.** When a made-up group of six bearings is called "healthy" (10 tries, round 3),
  the method scores 0.49 on average, but one try scored 0.84, as high as the real result (that group held two real
  healthy bearings and four with lab-made damage). So the evidence that it hears "healthy" itself is weak.
- **Lab-made damage is caught too** (77% of recordings, real wear 83%), so it is not only hearing a bearing's
  life-test history. It almost never flags KB23 and KB24 (real wear on both rings) or KI01.
- **Bigger damage is not flagged more.** Share of damaged recordings flagged (lab): size level 1, 90% (15 bearings);
  level 2, 72% (9); level 3, 44% (2). If it heard damage size, this should rise. A warning sign.
- **It cannot tell which ring is damaged:** 0.61 (0.46 to 0.77). The range reaches chance, so the app says "which
  ring: cannot tell" (rule sealed in advance).
- **On the dataset authors' own split** (learn on lab-made damage, test on real wear, three answers) it scores 36%
  accuracy, about guessing (33%) and inside the authors' own motor-current range (27% to 61%, ensemble 46%). That
  split has one healthy training bearing; the detector never calls the healthy test bearing healthy.
- **Run-in may be part of it:** the healthy bearing with the shortest run-in (K003, 1 hour; Lessmeier 2016 Table 7)
  is the one flagged most (85% of its recordings). The app hands it to a person rather than calling it damaged.
- **Only six healthy bearings exist.** Every result is exploratory.
- The tested bearing sits in a separate module on the shaft line, not inside the motor. The current was measured by
  lab sensors between drive and motor; drive-like quality is simulated, not a real drive's sensor.
- **Not claimed:** days until failure, bearings inside a motor, any drive brand's sensor.

## What the app does

- **Plant:** 32 motors on one screen, colour-coded (check bearing, ask a person, healthy), each with a tiny picture of
  its current. The motor to check first is highlighted.
- **Motor:** where the detector put it (a bar from healthy to check bearing, in words, never a percentage), and the
  motor's "hiss picture" (how much louder or quieter than the healthy bearings, at each pitch), with the bearing
  notes, where the detector listens, and this motor's top two signs marked. A technician's note, questions in plain words, a draft
  work order that a person approves.
- **Plan my shift:** say how much time you have; the AMD assistant asks the plant for what it needs (fleet list,
  motor facts) using tool calls, and returns an ordered visit list with work orders.
- **Explain this chart:** a vision model on AMD reads the exact chart the trainee sees and explains it.
- **Proof:** every round, every honest check, the failures included, as charts.
- **Value:** an illustrative yearly value you can change with sliders (assumptions are labelled as such).

## What runs on AMD, and how it is kept honest

All the language and vision work runs on open models served on AMD GPUs through AMD Token Factory (Gemma-4-31B-IT,
with Qwen3.8-27B as backup): the notes, the follow-up answers, the shift plan (native tool calls) and the chart
explainer (image input). The detector itself is small and does not need a GPU.

Every answer is checked in code before it is shown (`bearing/notes.py`, `bearing/copilot.py`): a note or explanation
may only use numbers that are in the detector's facts, may not contradict the verdict, and may not predict days to
failure; a shift plan may only name motors the tools returned, never a healthy motor, never more visits than the time
allows. If a check fails, the service is down, or the answer would take longer than 45 seconds, a fixed template or rule
answers instead, and the page says so. The
key lives only in the server's environment, never in the browser or this repository.

Assistant test (`results/assistant_questions.json`): 10 fixed questions written before testing, on 3 motors, 30
answers: 30 passed the automatic check; all 9 trick questions (days until failure, which ring, the brand) were
declined; 29 of 30 were right when read by Claude. A person's read is pending.

## Run it

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q                 # tests
.venv/Scripts/python -m bearing.export_web        # results/ -> web/public/data/app.json (needs data/ features)
.venv/Scripts/python -m bearing.sync_web          # copies the tested assistant code into web/api/_bearing
.venv/Scripts/python web/dev_api.py               # local server functions on :8787 (reads AMD_KEY)
cd web && npm install && npx vite                 # app on :5173
```

Deploy: `web/` is a Vercel project (Vite build plus Python functions in `web/api/`). Set `AMD_KEY` in the project's
environment variables. Without it, the app still works with template notes and the rule-based plan.

**To remake the results:** features were extracted on Kaggle (`kaggle/`, or `colab/RUN_IN_COLAB.md`), which
downloads each bearing from Paderborn University, reads it and deletes it. Then `python -m bearing.evaluate`
(round 1), `python -m bearing.round2`, `python -m bearing.round3`, `python -m bearing.round4`, and the checks `python -m bearing.round3_checks`.
The earlier Streamlit app (`app/`) is kept for reference only.

## Data and licence

Paderborn University bearing data: C. Lessmeier, J. K. Kimotho, D. Zimmer, W. Sextro, "Condition Monitoring of
Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark
Data Set for Data-Driven Classification", PHME 2016. Licence CC BY-NC 4.0. The raw data is not in this repository;
it is downloaded from its source. The files in `results/` and `web/public/data/` are derived from it and shared
under the same licence.

Our code: MIT (`LICENSE`).
