"""Turn one 4-second recording of two phase currents into a row of numbers.

Everything is measured relative to the main tone found in the current itself, so load does not look like damage.
"""
import numpy as np

from .config import BPFI_FACTOR, BPFO_FACTOR, POLE_PAIRS

BAND_EDGES = np.geomspace(10.0, 25_000.0, 33)     # 32 "shape" bands
TONE_HALF_WIDTH_HZ = 0.5                           # 1 Hz windows; the shaft grid is 1.36 Hz away at 1,500 rpm
                                                   # but only 0.81 Hz at 900 rpm, where a wobbling grid line can leak in
MAIN_TONE_SEARCH_HZ = 3.0
MAIN_TONE_EXCLUDE_HZ = 3.0
MIN_MAIN_TONE_SNR_DB = 20.0
TINY = 1e-20


class UnusableRecording(ValueError):
    """No clear main tone: the recording is skipped and counted, never guessed."""


def spectrum(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    return np.fft.rfftfreq(len(x), 1 / fs), p


def _band(f, p, lo, hi):
    return float(p[(f >= lo) & (f < hi)].sum())


def find_fundamental(f: np.ndarray, p: np.ndarray, expected_hz: float) -> tuple[float, float]:
    near = (f >= expected_hz - MAIN_TONE_SEARCH_HZ) & (f <= expected_hz + MAIN_TONE_SEARCH_HZ)
    if not near.any():
        raise UnusableRecording("main tone outside the spectrum")
    i = int(np.argmax(np.where(near, p, -1.0)))
    floor = float(np.median(p[(f > expected_hz - 50) & (f < expected_hz + 50)])) + TINY
    if 10 * np.log10(p[i] / floor + TINY) < MIN_MAIN_TONE_SNR_DB:
        raise UnusableRecording("no clear main tone")
    fe = float(f[i])
    return fe, _band(f, p, fe - TONE_HALF_WIDTH_HZ, fe + TONE_HALF_WIDTH_HZ + 1e-9)


def tone_lines(fe_hz: float) -> dict[str, float]:
    """Classic bearing pitches and their traces in the current. inner_ring - fe equals fe - outer_ring
    exactly (outer + inner = 8 x shaft = 2 x fe), so that line appears once, as outer_minus."""
    shaft = fe_hz / POLE_PAIRS
    o, i = shaft * BPFO_FACTOR, shaft * BPFI_FACTOR
    return {
        "outer_ring": o, "inner_ring": i,
        "outer_minus": abs(fe_hz - o), "outer_plus": fe_hz + o, "inner_plus": fe_hz + i,
        "outer_minus2": abs(fe_hz - 2 * o), "outer_plus2": fe_hz + 2 * o,
        "inner_minus2": abs(fe_hz - 2 * i), "inner_plus2": fe_hz + 2 * i,
    }


def recording_features(i1: np.ndarray, i2: np.ndarray, fs: int, rpm: int) -> dict[str, float]:
    f, p1 = spectrum(i1, fs)
    _, p2 = spectrum(i2, fs)
    p = (p1 + p2) / 2
    fe, p_fund = find_fundamental(f, p, expected_hz=rpm / 60 * POLE_PAIRS)
    out = {"fe_hz": fe}
    keep = np.abs(f - fe) > MAIN_TONE_EXCLUDE_HZ
    residual = float(p[keep & (f >= BAND_EDGES[0])].sum())
    out["residual_db"] = 10 * np.log10(residual / p_fund + TINY)
    for name, hz in tone_lines(fe).items():
        if hz < 0.45 * fs:
            power = _band(f, p, hz - TONE_HALF_WIDTH_HZ, hz + TONE_HALF_WIDTH_HZ + 1e-9)
            out[f"tone_{name}"] = 10 * np.log10(power / p_fund + TINY)
    for k in range(len(BAND_EDGES) - 1):
        lo, hi = BAND_EDGES[k], BAND_EDGES[k + 1]
        if hi > 0.45 * fs:
            break
        power = float(p[keep & (f >= lo) & (f < hi)].sum())
        out[f"band_{k:02d}"] = 10 * np.log10(power / p_fund + TINY)
    return out
