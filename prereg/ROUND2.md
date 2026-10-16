# Round 2 rules (sealed before any round-2 result; machine copy `round2.json`)

Written 2026-10-16, after round 1 (sealed, fingerprint 383402e7...) scored near chance, with Hamza's go-ahead.
Round 1 is not changed and stays reported as the result sealed first.

1. **Why:** each bearing has its own fingerprint in the current (mounting, run-in) that is louder than damage
   (`research/why-near-chance-2026-10-16.md`).
2. **New listening sets:** "contrast" = how far each bearing line (orders 1 to 3, and their traces around the main
   tone) sticks out of the noise right next to it, never counting shaft-grid lines; "clicks" = how spiky the current
   is once the main tone and its multiples are removed (all of it, and above 1 kHz).
3. **Six combinations, in this order:** shape+lr, contrast+lr, contrast_clicks+lr, shape+rf, contrast+rf,
   contrast_clicks+rf (lr = round 1's model; rf = a random forest of 300 trees). Speed and load setting always added.
4. **Fair choice:** inside each test group's training bearings, each combination is scored on the training groups
   it did not learn from (the same scores that set the line and band); the best is chosen, ties to the earlier one.
   The test bearings never take part in the choice. Every combination's own score is also shown.
5. **Everything else as round 1:** groups, line, band, how sure, urgency, plant condition, median of recordings,
   bootstrap, the 0.10 flag size, all five quality settings.
6. **When the app switches to round 2:** only if, at 16 kHz / 12 bit, the whole 95% range of round 2's honest score
   is above 0.5. Otherwise the plant view stays on round 1.
