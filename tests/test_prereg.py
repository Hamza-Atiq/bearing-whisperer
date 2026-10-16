from bearing import config, prereg


def test_frozen_prereg_passes_all_checks():
    assert prereg.check(prereg.load()) == []


def test_every_bearing_in_exactly_one_fold_and_one_healthy_per_fold():
    rules = prereg.load()
    seen = [b for fold in rules["folds"].values() for b in fold]
    assert sorted(seen) == sorted(config.ALL_BEARINGS)
    for fold in rules["folds"].values():
        assert sum(b in config.HEALTHY for b in fold) == 1


def test_check_catches_a_broken_fold():
    rules = prereg.load()
    rules["folds"]["1"] = rules["folds"]["1"][1:]          # drop K001
    assert any("K001" in p for p in prereg.check(rules))


def test_fingerprint_is_stable():
    assert prereg.fingerprint() == prereg.fingerprint()
    assert len(prereg.fingerprint()) == 64
