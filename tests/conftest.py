import numpy as np
import pandas as pd
import pytest

from bearing import config


def fake_features(n_rec: int = 6, separation: float = 2.0, seed: int = 0) -> pd.DataFrame:
    """A small fake feature table: band_00 and tone_outer_minus carry the label, the rest is noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for b in config.ALL_BEARINGS:
        y = config.label(b)
        for cond in config.CONDITIONS:
            rpm, torque = config.drive_setting(cond)
            for r in range(1, n_rec + 1):
                rows.append({"bearing": b, "condition": cond, "rec": r, "setting": "lab", "rpm": rpm,
                             "torque": torque, "label": y, "origin": config.damage_origin(b),
                             "usable": True, "error": "", "n_clipped": 0, "fe_hz": rpm / 15,
                             "residual_db": rng.normal(), "band_00": rng.normal(separation * y, 1.0),
                             "band_01": rng.normal(), "tone_outer_minus": rng.normal(separation * y, 1.0),
                             "tone_outer_ring": rng.normal()})
    return pd.DataFrame(rows)


@pytest.fixture
def fake_df():
    return fake_features()
