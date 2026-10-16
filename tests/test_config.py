from bearing import config


def test_bearing_counts_match_the_paper():
    assert len(config.HEALTHY) == 6
    assert len(config.ARTIFICIAL) == 12
    assert len(config.REAL) == 14
    assert len(set(config.ALL_BEARINGS)) == 32


def test_bearing_tones_at_1500_rpm_match_spec():
    shaft = 25.0
    assert abs(shaft * config.BPFO_FACTOR - 76.4) < 0.5
    assert abs(shaft * config.BPFI_FACTOR - 123.6) < 0.5


def test_drive_setting_drops_the_force():
    assert config.drive_setting("N15_M07_F10") == (1500, 0.7)
    assert config.drive_setting("N09_M07_F10") == (900, 0.7)
    assert config.drive_setting("N15_M01_F10") == (1500, 0.1)
    assert config.drive_setting("N15_M07_F04") == (1500, 0.7)


def test_labels_and_origin():
    assert config.label("K003") == 0 and config.damage_origin("K003") == "healthy"
    assert config.label("KA01") == 1 and config.damage_origin("KA01") == "artificial"
    assert config.label("KB23") == 1 and config.damage_origin("KB23") == "real"
