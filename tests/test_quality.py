import numpy as np
import pytest

from bearing.config import FS_LAB
from bearing.quality import simulate

T = np.arange(int(FS_LAB * 0.5)) / FS_LAB


def power(x):
    return float(np.mean(x ** 2))


def test_content_above_new_nyquist_is_removed_not_folded():
    x = np.sin(2 * np.pi * 20_000 * T)             # would alias to 4 kHz if not filtered
    y, _ = simulate(x, 16_000, None, 10.0)
    assert power(y[200:-200]) < 1e-3 * power(x)


def test_low_tones_survive():
    x = np.sin(2 * np.pi * 100 * T)
    y, _ = simulate(x, 8_000, None, 10.0)
    assert 0.95 < power(y[200:-200]) / power(x) < 1.05


def test_quantisation_and_clipping():
    x = np.array([0.0, 0.001, 3.0, 12.0, -15.0] * 2)
    y, n_clipped = simulate(x, FS_LAB, 12, 10.0)
    step = 20.0 / 2 ** 12
    assert n_clipped == 4
    assert np.allclose(y / step, np.round(y / step))
    assert y.max() <= 10.0 and y.min() >= -10.0


def test_lab_setting_is_untouched():
    x = np.random.default_rng(0).normal(size=1000)
    y, n = simulate(x, FS_LAB, None, 10.0)
    assert n == 0 and np.array_equal(x, y)


def test_rejects_rate_that_does_not_divide():
    with pytest.raises(ValueError):
        simulate(np.zeros(100), 30_000, 12, 10.0)
