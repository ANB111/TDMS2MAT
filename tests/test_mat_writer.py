"""
Tests for tdms2mat.pipeline.mat_writer (csv_to_mat).

Verifies that:
- ``channel_names`` is stored in the .mat output.
- ``time_epoch`` is a float64 vector.
- ``data`` matrix has the right shape.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.io import loadmat


def _write_pipeline_csv(path: Path, n_rows: int = 30) -> None:
    """Write a synthetic daily CSV in the format produced by csv_processor."""
    rows = []
    base = pd.Timestamp("2025-07-15 08:00:00")
    for i in range(n_rows):
        t = base + pd.Timedelta(seconds=i * 0.1)
        rows.append(
            {
                "Time": t.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Potencia": float(i),
                "Velocidad": float(100 + i),
                "Frecuencia": 50.0,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(path, sep=";", index=False)


class TestCsvToMat:
    def test_creates_mat_file(self, tmp_dir: Path) -> None:
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        _write_pipeline_csv(in_dir / "25.7.15.csv")
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")

        mat_files = list(out_dir.glob("*.mat"))
        assert len(mat_files) == 1, f"Expected 1 .mat, found {mat_files}"

    def test_mat_contains_channel_names(self, tmp_dir: Path) -> None:
        """channel_names must be present and non-empty in the .mat."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        _write_pipeline_csv(in_dir / "25.7.15.csv")
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")

        mat_file = next(out_dir.glob("*.mat"))
        data = loadmat(str(mat_file))
        assert "channel_names" in data, (
            "channel_names must be saved to allow MATLAB to reference columns by name"
        )
        ch_names = data["channel_names"]
        # Flatten and decode
        names = [str(n).strip() for n in ch_names.flatten()]
        assert "Potencia" in names, f"Expected 'Potencia' in channel_names: {names}"
        assert "Velocidad" in names

    def test_mat_contains_time_epoch(self, tmp_dir: Path) -> None:
        """time_epoch must be a float64 vector."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        _write_pipeline_csv(in_dir / "25.7.15.csv", n_rows=30)
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")

        mat_file = next(out_dir.glob("*.mat"))
        data = loadmat(str(mat_file))
        assert "time_epoch" in data
        assert data["time_epoch"].dtype == np.float64

    def test_mat_data_shape(self, tmp_dir: Path) -> None:
        """data matrix rows must equal the number of CSV rows."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        n_rows = 25
        _write_pipeline_csv(in_dir / "25.7.15.csv", n_rows=n_rows)
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")

        mat_file = next(out_dir.glob("*.mat"))
        data = loadmat(str(mat_file))
        assert data["data"].shape[0] == n_rows, (
            f"Expected {n_rows} rows, got {data['data'].shape[0]}"
        )

    def test_time_colname_format_in_output(self, tmp_dir: Path) -> None:
        """'Time' column itself must not appear in channel_names (it's time_epoch)."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        _write_pipeline_csv(in_dir / "25.7.15.csv")
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")

        mat_file = next(out_dir.glob("*.mat"))
        data = loadmat(str(mat_file))
        names = [str(n).strip() for n in data["channel_names"].flatten()]
        assert "Time" not in names, (
            "The 'Time' column should be in time_epoch, not in channel_names"
        )

    def test_original_csv_deleted(self, tmp_dir: Path) -> None:
        """Non-temp CSV must be removed after successful .mat generation."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        in_dir = tmp_dir / "in"
        out_dir = tmp_dir / "out"
        in_dir.mkdir()

        csv_path = in_dir / "25.7.15.csv"
        _write_pipeline_csv(csv_path)
        csv_to_mat(str(in_dir), str(out_dir), unidad="05")
        assert not csv_path.exists(), "Original CSV should be deleted after .mat creation"

    def test_missing_input_folder_logs_and_returns(self, tmp_dir: Path) -> None:
        """Should not raise when input folder does not exist."""
        from tdms2mat.pipeline.mat_writer import csv_to_mat

        messages: list = []
        csv_to_mat(
            str(tmp_dir / "does_not_exist"),
            str(tmp_dir / "out"),
            log_callback=messages.append,
        )
        assert any("no existe" in m.lower() for m in messages)
