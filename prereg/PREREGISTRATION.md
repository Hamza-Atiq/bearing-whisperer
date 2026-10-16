# Pre-registration (frozen before any experiment)

Written 2026-10-15, spec v9. Machine-readable copy: `prereg.json`. Its SHA-256 is stamped into every result.

1. **Test groups (HR-4, HR-9, HR-17).** Six fixed groups, each with one healthy bearing and both lab-made and
   real damage where possible. Every bearing is tested once, by a model that never saw it.
2. **Detectors (HR-6, HR-12, HR-15).** "shape" (headline; 32 pitch bands), "tones" (classic bearing pitches only;
   the physics check), "loudness" (one number), "setting_only" (speed and load setting only; must be about 0.5),
   "always_damaged" (0.5 by definition). All are reported.
3. **Drive-like quality (FR-004).** lab; 32 kHz/12 bit; 16 kHz/12 bit; 8 kHz/12 bit (stress); 16 kHz/10 bit
   (stress). Full scale plus or minus 10 A. Clipping is counted. A 12-bit converter has 4,096 steps, from
   -10 A up to one step below +10 A.
4. **Headline:** "shape" at lab quality. **Plant view:** "shape" at 16 kHz/12 bit, condition N15_M07_F10,
   motor verdict from the median of its recordings, at least 10 usable recordings or "ask a person".
5. **Line (HR-19):** highest balanced accuracy on inner out-of-fold scores of the training groups.
   **Band (HR-11):** the 20% of those scores closest to the line. **How sure:** "low" inside the band,
   "medium" up to the 50% closest, "high" beyond. **Percentages** only if calibration error on unseen
   recordings is at most 0.10.
6. **Urgency (FR-008):** check bearing + high: this week. Check bearing + medium, or ask a person: next routine
   visit, with a manual check.
7. **Expected result of the quality test, written before seeing it (FR-017):** the strongest bearing trace sits
   below about 1 kHz, so "tones" should lose almost nothing from lab to 8 kHz. If "shape" loses a lot when the
   sample rate drops, it was leaning on content above 4 kHz (switching noise or higher-order traces). This is a
   flag, not a proof, and a small drop does not prove the detector heard the bearing (the 25 Hz shaft grid
   sits in the same low band). **"A lot" means a drop of 0.10 balanced accuracy or more** from lab to 8 kHz.
8. **Load test (FR-011, HR-13):** train at N15_M07_F10, test at N15_M01_F10, and the reverse, same groups.
9. **Dataset authors' split (FR-020, Should): not run.** Lessmeier 2016 Table 8 trains on K002, KA01, KA05, KA07,
   KI01, KI05, KI07 and tests on K001, KA04, KA15, KA16, KA22, KA30, KI14, KI16, KI17, KI18, KI21. It has only
   one healthy training bearing, so the line and band cannot be set on held-out healthy training bearings
   (HR-11, HR-19), and the authors report 3-class accuracy, which is not comparable with balanced accuracy.
   Decided before any result was seen (`research/lessmeier-table8-2026-10-16.txt`).
10. **Shortcut check size (HR-15):** "shape" scoring **0.10 balanced accuracy or more above "tones"** at lab
   quality is reported as "may be hearing more than the classic bearing pitches". The same 0.10 is the size of
   gap between the honest and seen numbers that the results page calls a real difference.
