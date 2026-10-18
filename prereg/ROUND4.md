# Round 4 rules (sealed before any round-4 result; machine copy `round4.json`)

Written 2026-10-18 at 04:15 Pakistan time, after a strict audit of round 3 (fingerprint 85a1fc60...).
`round4.json` SHA-256: `e49358b0f505ffb36814b286589f59703c701050abe651e54af66c2f727f2626`.
Rounds 1 to 3 are not changed and stay reported.

1. **Why.** Two audit findings. (a) Round 3 compared each recording with the fleet "at the same condition", and the
   condition name includes the radial force on the bearing, which a drive cannot know (FR-002). (b) The published
   test we compare with (Cekic and Akan, Energies 2026) leaves each operating condition out in turn; round 3 only
   swapped two loads.
2. **One detector, fixed now:** round 3's `shape_fleet+rf`, with the fleet grouped by speed and torque only.
3. **Already seen before this seal (stated, not hidden):** the audit ran this detector's same-load test once to size
   the force problem: lab 0.8138, 16 kHz / 12 bit 0.8202 (`research` log of 18 Oct). Nothing below was chosen from it.
4. **Tests:** same load (five qualities), new load (as round 3), and **leave one condition out**: for each of the four
   conditions, labels only from training bearings at the other three, unseen bearings scored at the held-out one.
   Reported per condition and as the mean over the four (their kind of number), at lab and 16 kHz / 12 bit.
5. **Like for like:** from the same predictions, healthy against real wear on one ring (closest to their aged-only
   target), all real wear, lab-made damage, and all damage (closest to their all-damage target).
6. **Fairness bar:** `shape+rf`, which never looks at other motors at the test condition, is run the same way and shown.
7. **Plant view:** moves to round 4 whatever its score, because round 3 breaks FR-002.
