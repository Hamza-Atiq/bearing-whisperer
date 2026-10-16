"""Drive-like measurement quality, simulated from the 64 kHz lab current (FR-004).

Lower sample rate: an anti-alias filter, then keep every n-th sample, so no content above the new
half-sample-rate survives. Fewer bits: clip to the full-scale range, then round to the nearest step.
"""
import numpy as np
from scipy.signal import resample_poly

from .config import FS_LAB


def simulate(x: np.ndarray, target_fs: int, bits: int | None, full_scale_a: float) -> tuple[np.ndarray, int]:
    if FS_LAB % target_fs:
        raise ValueError(f"{target_fs} Hz does not divide {FS_LAB} Hz")
    down = FS_LAB // target_fs
    y = resample_poly(x, 1, down) if down > 1 else np.array(x, dtype=float, copy=True)
    if bits is None:
        return y, 0
    n_clipped = int(np.count_nonzero(np.abs(y) > full_scale_a))
    step = 2 * full_scale_a / 2 ** bits
    # A signed converter has codes -2^(bits-1) .. 2^(bits-1)-1, so the top code is one step below full scale.
    codes = np.clip(np.round(y / step), -2 ** (bits - 1), 2 ** (bits - 1) - 1)
    return codes * step, n_clipped
