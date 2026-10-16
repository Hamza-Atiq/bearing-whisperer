"""Round 2 features: listen for what damage makes, not for each bearing's own fingerprint.

"Sticks out" (contrast): how far each bearing line rises above the noise right next to it. A bearing's fingerprint
(mounting, run-in) changes the broad level of the spectrum; a contrast against the local neighbourhood cancels most of
that, while a narrow damage line still stands out.
"Clicks": how spiky the current is once the main tone and its multiples are removed. A ball rolling over a dent makes
short knocks (time-domain statistics, as used for phase currents by Wagner and Sommer, PHME 2021).
"""
import numpy as np
from scipy.stats import kurtosis, skew

from .config import BPFI_FACTOR, BPFO_FACTOR, POLE_PAIRS
from .features import find_fundamental, spectrum

PEAK_HALF_WIDTH_HZ = 0.3        # the line itself: bins within 0.3 Hz
NEIGHBOUR_HZ = 8.0              # the local noise: up to 8 Hz away ...
NEIGHBOUR_GAP_HZ = 1.5          # ... but not closer than 1.5 Hz to the line
GRID_EXCLUDE_HZ = 1.0           # and never within 1 Hz of a shaft-grid line (multiples of the shaft speed)
HARMONIC_NOTCH_HZ = 3.0
HF_CUT_HZ = 1_000.0
TINY = 1e-30


def contrast_lines(fe_hz: float) -> dict[str, float]:
    """Bearing pitches and their traces around the main tone, orders 1 to 3. fe - i1 equals o1 - fe in size
    (o + i = 2 fe), so 'fe_minus_i1' would repeat 'fe_minus_o1' and is left out."""
    shaft = fe_hz / POLE_PAIRS
    o, i = shaft * BPFO_FACTOR, shaft * BPFI_FACTOR
    lines = {}
    for k in (1, 2, 3):
        lines[f"o{k}"], lines[f"i{k}"] = k * o, k * i
        lines[f"fe_minus_o{k}"], lines[f"fe_plus_o{k}"] = abs(fe_hz - k * o), fe_hz + k * o
        if k > 1:
            lines[f"fe_minus_i{k}"] = abs(fe_hz - k * i)
        lines[f"fe_plus_i{k}"] = fe_hz + k * i
    return lines


def _contrast(f, p, hz, shaft):
    d = np.abs(f - hz)
    peak = p[d <= PEAK_HALF_WIDTH_HZ]
    near_grid = np.abs(((f + shaft / 2) % shaft) - shaft / 2) < GRID_EXCLUDE_HZ
    neighbours = p[(d <= NEIGHBOUR_HZ) & (d > NEIGHBOUR_GAP_HZ) & ~near_grid]
    if not len(peak) or not len(neighbours):
        return None
    return float(10 * np.log10(peak.max() / (np.median(neighbours) + TINY) + TINY))


def _residual(x, fs, fe, low_cut):
    """The current with the main tone, its multiples and everything below `low_cut` removed."""
    x = np.asarray(x, dtype=float)
    spec = np.fft.rfft(x - x.mean())
    f = np.fft.rfftfreq(len(x), 1 / fs)
    nearest = np.round(f / fe) * fe
    spec[(f < low_cut) | (np.abs(f - nearest) <= HARMONIC_NOTCH_HZ)] = 0
    return np.fft.irfft(spec, len(x))


def _spikiness(r):
    rms = float(np.sqrt(np.mean(r ** 2))) + TINY
    return float(kurtosis(r)), float(np.max(np.abs(r)) / rms), float(skew(r))


def recording_features2(i1: np.ndarray, i2: np.ndarray, fs: int, rpm: int) -> dict[str, float]:
    f, p1 = spectrum(i1, fs)
    _, p2 = spectrum(i2, fs)
    p = (p1 + p2) / 2
    fe, _ = find_fundamental(f, p, expected_hz=rpm / 60 * POLE_PAIRS)
    shaft = fe / POLE_PAIRS
    out = {"fe_hz": fe}
    for name, hz in contrast_lines(fe).items():
        if hz + NEIGHBOUR_HZ < 0.45 * fs:
            c = _contrast(f, p, hz, shaft)
            if c is not None:
                out[f"contrast_{name}"] = c
    for prefix, low_cut in (("click", 10.0), ("click_hf", HF_CUT_HZ)):
        if low_cut < 0.45 * fs:
            stats = np.mean([_spikiness(_residual(x, fs, fe, low_cut)) for x in (i1, i2)], axis=0)
            suffix = "" if prefix == "click" else "_hf"
            out[f"click_kurt{suffix}"], out[f"click_crest{suffix}"], out[f"click_skew{suffix}"] = map(float, stats)
    return out
