"""Fixed facts about the Paderborn bearing data and its test rig.

Source: Lessmeier et al., PHME 2016. Nothing in this file is learned from data.
"""

HEALTHY = ["K001", "K002", "K003", "K004", "K005", "K006"]
ARTIFICIAL = ["KA01", "KA03", "KA05", "KA06", "KA07", "KA08", "KA09",
              "KI01", "KI03", "KI05", "KI07", "KI08"]
REAL = ["KA04", "KA15", "KA16", "KA22", "KA30", "KB23", "KB24", "KB27",
        "KI04", "KI14", "KI16", "KI17", "KI18", "KI21"]
ALL_BEARINGS = HEALTHY + ARTIFICIAL + REAL

CONDITIONS = ["N15_M07_F10", "N09_M07_F10", "N15_M01_F10", "N15_M07_F04"]
LOW_LOAD_CONDITION = "N15_M01_F10"
PLANT_CONDITION = "N15_M07_F10"

FS_LAB = 64_000            # Hz, lab recording rate of the current
POLE_PAIRS = 4             # 425 W permanent-magnet motor
NOMINAL_CURRENT_A = 2.3

# Bearing type 6203: 8 balls, ball diameter 6.75 mm, pitch diameter 28.55 mm, contact angle 0.
N_BALLS = 8
BALL_D_MM = 6.75
PITCH_D_MM = 28.55
BPFO_FACTOR = N_BALLS / 2 * (1 - BALL_D_MM / PITCH_D_MM)   # outer-ring tone, times shaft frequency
BPFI_FACTOR = N_BALLS / 2 * (1 + BALL_D_MM / PITCH_D_MM)   # inner-ring tone, times shaft frequency

DOWNLOAD_URL = "https://groups.uni-paderborn.de/kat/BearingDataCenter/{bearing}.rar"


def label(bearing: str) -> int:
    """1 means damaged, 0 means healthy."""
    return 0 if bearing in HEALTHY else 1


def damage_origin(bearing: str) -> str:
    if bearing in HEALTHY:
        return "healthy"
    return "artificial" if bearing in ARTIFICIAL else "real"


def drive_setting(condition: str) -> tuple[int, float]:
    """What a drive knows: speed in rpm and load torque in Nm. The force part is dropped (FR-002)."""
    speed, torque, _force = condition.split("_")
    return int(speed[1:]) * 100, int(torque[1:]) / 10
