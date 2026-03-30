"""
Tests for tdms2mat.analysis.startup_counter.

Exercises the pure calculation functions with synthetic numpy data so there
is no dependency on real .mat files.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat


# ---------------------------------------------------------------------------
# count_startups_shutdowns
# ---------------------------------------------------------------------------


class TestCountStartupsShutdowns:
    def test_basic_cycle(self) -> None:
        """One off→on transition = 1 startup; one on→off = 1 shutdown."""
        from tdms2mat.analysis.startup_counter import (
            SPEED_CHANNEL_IDX,
            count_startups_shutdowns,
        )

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data_matrix = np.zeros((10, n_cols))
        # Samples 0–4 off; samples 5–9 on
        data_matrix[5:, SPEED_CHANNEL_IDX] = 120.0
        mat = {"data": data_matrix}
        starts, stops, est_ini, est_fin, _ = count_startups_shutdowns(mat)
        assert starts == 1
        assert stops == 0  # still on at end
        assert est_ini == "Apagada"
        assert est_fin == "Encendida"

    def test_multiple_cycles(self) -> None:
        from tdms2mat.analysis.startup_counter import (
            SPEED_CHANNEL_IDX,
            count_startups_shutdowns,
        )

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data_matrix = np.zeros((14, n_cols))
        # Tres ciclos completos con estados estables (sin casos borde de 1 muestra).
        speed = np.array(
            [0, 0, 120, 120, 0, 0, 120, 120, 0, 0, 120, 120, 0, 0],
            dtype=float,
        )
        data_matrix[:, SPEED_CHANNEL_IDX] = speed
        mat = {"data": data_matrix}
        starts, stops, _, _, _ = count_startups_shutdowns(mat)
        assert starts == 3
        assert stops == 3

    def test_rebound_noise_does_not_create_extra_cycle(self) -> None:
        """Un rebote corto no debe sumar una parada+arranque extra."""
        from tdms2mat.analysis.startup_counter import (
            SPEED_CHANNEL_IDX,
            count_startups_shutdowns,
        )

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data_matrix = np.zeros((9, n_cols))
        # Ciclo real: off->on ... on->off, con un dip de 1 muestra en medio.
        speed = np.array([0, 0, 120, 120, 0, 120, 120, 0, 0], dtype=float)
        data_matrix[:, SPEED_CHANNEL_IDX] = speed
        mat = {"data": data_matrix}

        starts, stops, est_ini, est_fin, _ = count_startups_shutdowns(mat)
        assert starts == 1
        assert stops == 1
        assert est_ini == "Apagada"
        assert est_fin == "Apagada"

    def test_always_off_gives_zero_counts(self) -> None:
        from tdms2mat.analysis.startup_counter import (
            SPEED_CHANNEL_IDX,
            count_startups_shutdowns,
        )

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data_matrix = np.zeros((20, n_cols))
        mat = {"data": data_matrix}
        starts, stops, est_ini, est_fin, _ = count_startups_shutdowns(mat)
        assert starts == 0
        assert stops == 0
        assert est_ini == "Apagada"
        assert est_fin == "Apagada"

    def test_always_on_gives_zero_counts(self) -> None:
        from tdms2mat.analysis.startup_counter import (
            SPEED_CHANNEL_IDX,
            count_startups_shutdowns,
        )

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data_matrix = np.ones((20, n_cols)) * 100
        mat = {"data": data_matrix}
        starts, stops, est_ini, est_fin, _ = count_startups_shutdowns(mat)
        assert starts == 0
        assert stops == 0
        assert est_ini == "Encendida"
        assert est_fin == "Encendida"

    def test_missing_data_key_returns_zeros(self) -> None:
        from tdms2mat.analysis.startup_counter import count_startups_shutdowns

        starts, stops, est_ini, est_fin, spd = count_startups_shutdowns({})
        assert starts == 0
        assert stops == 0
        assert spd.size == 0


# ---------------------------------------------------------------------------
# calculate_runtime_hours
# ---------------------------------------------------------------------------


class TestCalculateRuntimeHours:
    def test_half_on_half_off_with_epoch(self) -> None:
        """3600-sample signal: first 1800 on, second 1800 off → ~0.5 h on."""
        from tdms2mat.analysis.startup_counter import calculate_runtime_hours

        n = 3600
        speed = np.concatenate([np.ones(1800) * 100, np.zeros(1800)])
        time_epoch = np.arange(n, dtype=float)  # 1 sample per second
        h_on, h_total = calculate_runtime_hours(speed, time_epoch, sample_rate_hint=1.0)
        assert abs(h_on - 0.5) < 0.01, f"Expected ~0.5 h on, got {h_on}"
        assert abs(h_total - 1.0) < 0.02, f"Expected ~1.0 h total, got {h_total}"

    def test_all_on_equals_total(self) -> None:
        from tdms2mat.analysis.startup_counter import calculate_runtime_hours

        speed = np.ones(100) * 50
        time_epoch = np.arange(100, dtype=float)
        h_on, h_total = calculate_runtime_hours(speed, time_epoch)
        assert abs(h_on - h_total) < 1e-6

    def test_empty_speed_returns_zeros(self) -> None:
        from tdms2mat.analysis.startup_counter import calculate_runtime_hours

        h_on, h_total = calculate_runtime_hours(np.array([]), None)
        assert h_on == 0.0
        assert h_total == 0.0


# ---------------------------------------------------------------------------
# parse_fecha_string
# ---------------------------------------------------------------------------


class TestParseFechaString:
    def test_valid_date(self) -> None:
        from tdms2mat.analysis.startup_counter import parse_fecha_string

        dt = parse_fecha_string("25.7.10")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 7
        assert dt.day == 10

    def test_invalid_year_out_of_range(self) -> None:
        """Year component > 99 must return None."""
        from tdms2mat.analysis.startup_counter import parse_fecha_string

        assert parse_fecha_string("125.7.10") is None

    def test_empty_string_returns_none(self) -> None:
        from tdms2mat.analysis.startup_counter import parse_fecha_string

        assert parse_fecha_string("") is None
        assert parse_fecha_string(None) is None  # type: ignore[arg-type]

    def test_malformed_string_returns_none(self) -> None:
        from tdms2mat.analysis.startup_counter import parse_fecha_string

        assert parse_fecha_string("2025-07-10") is None  # wrong separator
        assert parse_fecha_string("not_a_date") is None


# ---------------------------------------------------------------------------
# process_mat_folder (integration)
# ---------------------------------------------------------------------------


class TestProcessMatFolder:
    def _make_mat(self, path: Path, n: int = 100, n_on: int = 50) -> None:
        """Create a minimal synthetic .mat file with a speed channel."""
        from tdms2mat.analysis.startup_counter import SPEED_CHANNEL_IDX

        n_cols = max(SPEED_CHANNEL_IDX + 1, 16)
        data = np.zeros((n, n_cols))
        data[:n_on, SPEED_CHANNEL_IDX] = 120.0
        time_epoch = np.arange(n, dtype=float)
        savemat(str(path), {"data": data, "time_epoch": time_epoch})

    def test_creates_excel_output(self, tmp_dir: Path) -> None:
        from tdms2mat.analysis.startup_counter import process_mat_folder

        mat_dir = tmp_dir / "mat"
        mat_dir.mkdir()
        self._make_mat(mat_dir / "25.7.10-u05.mat")

        excel_path = str(tmp_dir / "output.xlsx")
        process_mat_folder(str(mat_dir), excel_path)
        assert Path(excel_path).exists()

    def test_excel_contains_expected_columns(self, tmp_dir: Path) -> None:
        import pandas as pd
        from tdms2mat.analysis.startup_counter import process_mat_folder

        mat_dir = tmp_dir / "mat"
        mat_dir.mkdir()
        self._make_mat(mat_dir / "25.7.10-u05.mat")

        excel_path = str(tmp_dir / "output.xlsx")
        process_mat_folder(str(mat_dir), excel_path)
        df = pd.read_excel(excel_path)
        for col in ("Fecha", "Arranques", "Paradas", "Horas Encendida"):
            assert col in df.columns, f"Missing column: {col}"

    def test_no_duplicate_when_rerun(self, tmp_dir: Path) -> None:
        """Running process_mat_folder twice must not produce duplicate rows."""
        import pandas as pd
        from tdms2mat.analysis.startup_counter import process_mat_folder

        mat_dir = tmp_dir / "mat"
        mat_dir.mkdir()
        self._make_mat(mat_dir / "25.7.10-u05.mat")

        excel_path = str(tmp_dir / "output.xlsx")
        process_mat_folder(str(mat_dir), excel_path)
        process_mat_folder(str(mat_dir), excel_path)  # second run

        df = pd.read_excel(excel_path)
        count = (df["Archivo"] == "25.7.10-u05.mat").sum()
        assert count == 1, f"Expected 1 row, got {count} (duplicate detected)"

    def test_skips_files_older_than_last_excel_date(self, tmp_dir: Path) -> None:
        """Con Excel previo, no debe procesar .mat anteriores a la última fecha."""
        import pandas as pd
        from tdms2mat.analysis.startup_counter import process_mat_folder

        mat_dir = tmp_dir / "mat"
        mat_dir.mkdir()
        self._make_mat(mat_dir / "25.7.9-u05.mat")
        self._make_mat(mat_dir / "25.7.11-u05.mat")

        excel_path = str(tmp_dir / "output.xlsx")
        df_existing = pd.DataFrame(
            [
                {
                    "Fecha": "25.7.10",
                    "Arranques": 0,
                    "Paradas": 0,
                    "Total": 0,
                    "Horas Encendida": 0.0,
                    "Movimientos": 0,
                    "Estado Inicial": "Apagada",
                    "Estado Final": "Apagada",
                    "Archivo": "25.7.10-u05.mat",
                }
            ]
        )
        df_existing.to_excel(excel_path, index=False)

        process_mat_folder(str(mat_dir), excel_path)

        df = pd.read_excel(excel_path)
        archivos = set(df["Archivo"].dropna())
        assert "25.7.9-u05.mat" not in archivos
        assert "25.7.11-u05.mat" in archivos

    def test_skips_files_on_same_last_excel_date(self, tmp_dir: Path) -> None:
        """Con Excel previo, no debe reprocesar archivos del mismo último día."""
        import pandas as pd
        from tdms2mat.analysis.startup_counter import process_mat_folder

        mat_dir = tmp_dir / "mat"
        mat_dir.mkdir()
        self._make_mat(mat_dir / "25.7.10-u99.mat")
        self._make_mat(mat_dir / "25.7.11-u05.mat")

        excel_path = str(tmp_dir / "output.xlsx")
        df_existing = pd.DataFrame(
            [
                {
                    "Fecha": "25.7.10",
                    "Arranques": 1,
                    "Paradas": 1,
                    "Total": 2,
                    "Horas Encendida": 1.0,
                    "Movimientos": 0,
                    "Estado Inicial": "Apagada",
                    "Estado Final": "Apagada",
                    "Archivo": "25.7.10-u05.mat",
                }
            ]
        )
        df_existing.to_excel(excel_path, index=False)

        process_mat_folder(str(mat_dir), excel_path)

        df = pd.read_excel(excel_path)
        archivos = set(df["Archivo"].dropna())
        assert "25.7.10-u99.mat" not in archivos
        assert "25.7.11-u05.mat" in archivos
