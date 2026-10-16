import numpy as np

from bearing import features2

FS = 64_000
T = np.arange(4 * FS) / FS
RNG = np.random.default_rng(3)


def current(fe=100.0, extra=(), noise=0.003, impulses=0.0):
    x = 3.0 * np.sin(2 * np.pi * fe * T) + noise * RNG.normal(size=len(T))
    for f, a in extra:
        x = x + a * np.sin(2 * np.pi * f * T)
    if impulses:
        x[:: FS // 76] += impulses                     # a click about 76 times a second
    return x


def test_lines_are_clear_of_the_shaft_grid_at_both_speeds():
    for fe in (100.0, 60.0):
        shaft = fe / 4
        for hz in features2.contrast_lines(fe).values():
            grid = round(hz / shaft) * shaft
            assert abs(hz - grid) > features2.PEAK_HALF_WIDTH_HZ + 0.25, (fe, hz)


def test_no_duplicate_lines():
    lines = features2.contrast_lines(100.0)
    values = sorted(lines.values())
    assert min(np.diff(values)) > 1.0


def test_a_line_that_sticks_out_has_high_contrast():
    hz = features2.contrast_lines(100.0)["fe_minus_o1"]
    out = features2.recording_features2(current(extra=[(hz, 0.01)]), current(extra=[(hz, 0.01)]), FS, rpm=1500)
    assert out["contrast_fe_minus_o1"] > 15
    assert out["contrast_i2"] < 8


def test_contrast_ignores_the_overall_noise_level():
    noise = np.random.default_rng(7).normal(size=len(T))
    base = 3.0 * np.sin(2 * np.pi * 100.0 * T)
    quiet = features2.recording_features2(base + 0.003 * noise, base + 0.003 * noise, FS, rpm=1500)
    loud = features2.recording_features2(base + 0.03 * noise, base + 0.03 * noise, FS, rpm=1500)
    for k in ("contrast_o1", "contrast_fe_plus_i2", "contrast_i3"):
        assert abs(quiet[k] - loud[k]) < 0.5, k


def test_a_strong_shaft_grid_tone_does_not_count_as_a_bearing_line():
    grid = features2.recording_features2(current(extra=[(75.0, 0.05)]), current(extra=[(75.0, 0.05)]), FS, rpm=1500)
    assert grid["contrast_o1"] < 8                  # o1 = 76.4 Hz sits 1.4 Hz from the 75 Hz grid line


def test_clicks_raise_spikiness():
    calm = features2.recording_features2(current(), current(), FS, rpm=1500)
    clicky = features2.recording_features2(current(impulses=0.5), current(impulses=0.5), FS, rpm=1500)
    assert clicky["click_kurt"] > calm["click_kurt"] + 5
    assert clicky["click_crest"] > calm["click_crest"]
    assert clicky["click_kurt_hf"] > calm["click_kurt_hf"] + 5


def test_works_at_8_khz_and_900_rpm():
    x = current(fe=60.0)[::8]
    out = features2.recording_features2(x, x, 8_000, rpm=900)
    assert abs(out["fe_hz"] - 60.0) <= 0.25
    assert all(np.isfinite(v) for v in out.values())
    assert "click_kurt_hf" in out
