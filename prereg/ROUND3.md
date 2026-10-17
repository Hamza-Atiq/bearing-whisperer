# Round 3 rules (sealed before any round-3 result; machine copy `round3.json`)

Written 2026-10-17, after round 2 (fingerprint c3f51873...) scored 0.82 on unseen bearings but about 0.51 at a new
load. Hamza's go-ahead 17 Oct. Rounds 1 and 2 are not changed and stay reported.

1. **Why:** a load change shifts the whole "hiss picture" of the current, so a detector trained at one load reads the
   new load as different. A drive knows its load setting and how its other motors sound at that load.
2. **One detector, fixed now (no choosing):** `shape_fleet+rf` = round 2's listener (32 pitch slices, random forest),
   but every recording is first compared with the fleet at the same condition: minus the fleet median, divided by
   the fleet spread. The fleet = the training bearings, used without labels. Four other variants are run and shown,
   never chosen.
3. **Two honest tests:** same load (as round 2) and new load (trained at 0.7 Nm, tested at 0.1 Nm, and back).
   At a new load, only the training bearings' recordings at that load may be used, and only without labels.
4. **Which ring (FR-003):** outer vs inner, damaged bearings only, both-ring bearings never scored. The product names
   a ring only if that score's whole 95% range is above 0.5 at 16 kHz / 12 bit.
5. **Damage size (FR-014):** detection per damage level 1 to 3 (Lessmeier Tables 4 and 5).
6. **Authors' split (FR-020):** their bearings, their 3 classes, their metric, next to their 26.8% to 60.9%.
7. **Plant switch:** round 3 only if its whole 95% range is above 0.5 at the same load and at both new-load
   directions (16 kHz / 12 bit). Otherwise the plant view stays on round 2.
