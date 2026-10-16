import numpy as np
import pytest

from bearing import config, features

FS = 64_000
T = np.arange(4 * FS) / FS


def motor_current(fe=100.0, amp=3.0, extra=()):
    x = amp * np.sin(2 * np.pi * fe * T)
    for f, a in extra:
        x = x + a * np.sin(2 * np.pi * f * T)
    return x


def test_finds_main_tone_from_the_current_itself():
    f, p = features.spectrum(motor_current(fe=100.5), FS)
    fe, _ = features.find_fundamental(f, p, expected_hz=100.0)
    assert abs(fe - 100.5) <= 0.25


def test_noise_only_is_unusable():
    x = np.random.default_rng(1).normal(size=4 * FS)
    f, p = features.spectrum(x, FS)
    with pytest.raises(features.UnusableRecording):
        features.find_fundamental(f, p, expected_hz=100.0)


def test_tone_lines_at_1500_rpm():
    lines = features.tone_lines(100.0)
    assert abs(lines["outer_ring"] - 76.4) < 0.5
    assert abs(lines["inner_ring"] - 123.6) < 0.5
    assert abs(lines["outer_minus"] - 23.6) < 0.5      # also equals inner_ring - 100 Hz
    assert abs(lines["outer_plus"] - 176.4) < 0.5
    assert abs(lines["inner_plus"] - 223.6) < 0.5


def test_tone_windows_stay_clear_of_the_25_hz_shaft_grid():
    for hz in features.tone_lines(100.0).values():
        nearest_grid = round(hz / 25.0) * 25.0
        assert abs(hz - nearest_grid) > features.TONE_HALF_WIDTH_HZ + 0.25


def test_bearing_trace_shows_in_tone_feature():
    trace_hz = features.tone_lines(100.0)["outer_minus"]
    with_trace = features.recording_features(motor_current(extra=[(trace_hz, 0.01)]),
                                             motor_current(extra=[(trace_hz, 0.01)]), FS, rpm=1500)
    without = features.recording_features(motor_current(), motor_current(), FS, rpm=1500)
    expected_db = 20 * np.log10(0.01 / 3.0)
    assert abs(with_trace["tone_outer_minus"] - expected_db) < 1.5
    assert without["tone_outer_minus"] < expected_db - 30


def test_band_count_depends_on_sample_rate():
    lab = features.recording_features(motor_current(), motor_current(), FS, rpm=1500)
    x8 = motor_current()[::8]
    low = features.recording_features(x8, x8, 8_000, rpm=1500)
    n_lab = sum(k.startswith("band_") for k in lab)
    n_low = sum(k.startswith("band_") for k in low)
    assert n_lab == 32 and 0 < n_low < n_lab
    assert set(k for k in low if k.startswith("band_")) <= set(lab)


def test_900_rpm_uses_60_hz_main_tone():
    x = motor_current(fe=60.0)
    out = features.recording_features(x, x, FS, rpm=900)
    assert abs(out["fe_hz"] - 60.0) <= 0.25
