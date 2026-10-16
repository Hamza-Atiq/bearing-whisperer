from pathlib import Path

import numpy as np

from bearing import extract, prereg


def test_parse_name():
    assert extract.parse_name("N15_M07_F10_K001_1") == ("N15_M07_F10", "K001", 1)
    assert extract.parse_name("N09_M07_F10_KB23_20") == ("N09_M07_F10", "KB23", 20)


def test_unreadable_file_becomes_unusable_row(tmp_path: Path):
    bad = tmp_path / "N15_M07_F10_KA08_2.mat"
    bad.write_bytes(b"not a mat file")
    rows = extract.rows_for_file(bad, prereg.load())
    assert len(rows) == len(prereg.load()["quality_settings"])
    assert all(r["usable"] is False and r["error"] for r in rows)
    assert {r["bearing"] for r in rows} == {"KA08"}


def test_rows_for_good_signal(monkeypatch, tmp_path: Path):
    fs = 64_000
    t = np.arange(4 * fs) / fs
    x = 3 * np.sin(2 * np.pi * 100 * t)
    monkeypatch.setattr(extract, "read_currents", lambda path: (x, x))
    rows = extract.rows_for_file(tmp_path / "N15_M07_F10_K001_3.mat", prereg.load())
    assert all(r["usable"] for r in rows)
    assert {r["setting"] for r in rows} == set(prereg.load()["quality_settings"])
    lab = next(r for r in rows if r["setting"] == "lab")
    assert lab["rpm"] == 1500 and lab["torque"] == 0.7 and lab["label"] == 0 and lab["rec"] == 3
    assert "force" not in " ".join(lab)


def test_unpack_uses_unrar_or_falls_back_to_7zip(monkeypatch, tmp_path: Path):
    rar, folder = tmp_path / "K001.rar", tmp_path / "K001"
    monkeypatch.setattr(extract.shutil, "which", lambda name: "/usr/bin/unrar" if name == "unrar" else None)
    assert extract.unpack_command(rar, folder)[0] == "/usr/bin/unrar"
    monkeypatch.setattr(extract.shutil, "which", lambda name: None)
    monkeypatch.setattr(extract, "SEVEN_ZIP", tmp_path / "7z.exe")
    (tmp_path / "7z.exe").write_bytes(b"")
    cmd = extract.unpack_command(rar, folder)
    assert cmd[0] == str(tmp_path / "7z.exe") and cmd[1] == "x" and f"-o{folder}" in cmd


def test_unpack_falls_back_to_bsdtar(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(extract.shutil, "which", lambda name: "/usr/bin/bsdtar" if name == "bsdtar" else None)
    monkeypatch.setattr(extract, "SEVEN_ZIP", tmp_path / "missing.exe")
    cmd = extract.unpack_command(tmp_path / "K001.rar", tmp_path / "K001")
    assert cmd[0] == "/usr/bin/bsdtar" and "-C" in cmd


def test_rows_for_file_can_use_another_feature_recipe(monkeypatch, tmp_path: Path):
    fs = 64_000
    x = 3 * np.sin(2 * np.pi * 100 * np.arange(4 * fs) / fs)
    monkeypatch.setattr(extract, "read_currents", lambda path: (x, x))
    rows = extract.rows_for_file(tmp_path / "N15_M07_F10_K001_3.mat", prereg.load(),
                                 features_fn=lambda i1, i2, fs, rpm: {"special": float(fs)})
    assert {r["special"] for r in rows} == {64000.0, 32000.0, 16000.0, 8000.0}
    assert all(r["usable"] for r in rows)
