"""
Tests for tdms2mat.pipeline.csv_processor.

Key regression test: verifies the global-state bug fix — calling
``ordenar_y_agrupado_por_dia`` twice must NOT contaminate results.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest


def _write_day_csv(folder: Path, date_str: str, n_rows: int, potencia: float) -> None:
    """Helper: write a synthetic daily CSV in pipeline format."""
    rows = []
    base = pd.Timestamp(date_str + " 08:00:00")
    for i in range(n_rows):
        t = base + pd.Timedelta(seconds=i * 6)
        rows.append(
            {
                "Time": t.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Potencia": potencia,
                "Velocidad": 100.0,
                "Frecuencia": 50.0,
            }
        )
    df = pd.DataFrame(rows)
    csv_path = folder / f"raw_{date_str.replace('-', '')}.csv"
    df.to_csv(csv_path, sep=";", index=False)


class TestOrdenarYAgrupadoPorDia:
    """Functional tests for ordenar_y_agrupado_por_dia."""

    def test_produces_day_files(self, tmp_dir: Path) -> None:
        """Function must produce one dated CSV per day found in input CSVs."""
        from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia

        _write_day_csv(tmp_dir, "2025-07-10", n_rows=20, potencia=50.0)
        ordenar_y_agrupado_por_dia(str(tmp_dir))

        day_files = [f for f in os.listdir(str(tmp_dir)) if f.endswith(".csv")]
        assert any("25.7.10" in f for f in day_files), (
            f"Expected a day file 25.7.10*.csv but found: {day_files}"
        )

    def test_original_csv_deleted_after_processing(self, tmp_dir: Path) -> None:
        """Original raw CSV files must be removed after grouping."""
        from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia

        _write_day_csv(tmp_dir, "2025-07-10", n_rows=20, potencia=50.0)
        raw_path = list(tmp_dir.glob("raw_*.csv"))
        assert len(raw_path) == 1
        original_name = raw_path[0].name

        ordenar_y_agrupado_por_dia(str(tmp_dir))
        assert not (tmp_dir / original_name).exists(), (
            "Original raw CSV should have been deleted"
        )

    def test_no_global_state_contamination(self, tmp_dir: Path) -> None:
        """
        REGRESSION TEST: calling the function twice must not mix data.

        This is the critical bug that was present in csv_utils.py:
        ``datos_por_dia`` was a module-level global dict, so a second call
        would see data from the first call.
        """
        from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia

        folder_a = tmp_dir / "run_a"
        folder_b = tmp_dir / "run_b"
        folder_a.mkdir()
        folder_b.mkdir()

        # Run A: day 2025-07-10, Potencia = 11.0
        _write_day_csv(folder_a, "2025-07-10", n_rows=20, potencia=11.0)
        ordenar_y_agrupado_por_dia(str(folder_a))

        # Run B: day 2025-08-01, Potencia = 99.0 (completely different data)
        _write_day_csv(folder_b, "2025-08-01", n_rows=20, potencia=99.0)
        ordenar_y_agrupado_por_dia(str(folder_b))

        # Run B's output must contain ONLY day 25.8.1, NOT 25.7.10
        b_files = [f for f in os.listdir(str(folder_b)) if f.endswith(".csv")]
        assert not any("25.7.10" in f for f in b_files), (
            f"Run B should not contain run A's day file. Found: {b_files}"
        )
        # Verify the data values are only from run B
        mat_csv = next((f for f in b_files if "25.8.1" in f and "_temp" not in f), None)
        assert mat_csv is not None, f"Expected 25.8.1.csv in {b_files}"

        df = pd.read_csv(str(folder_b / mat_csv), delimiter=";")
        assert (df["Potencia"] == 99.0).all(), (
            "Run B values should be 99.0, not contaminated by run A's 11.0"
        )

    def test_log_callback_receives_messages(self, tmp_dir: Path) -> None:
        """log_callback must be called at least once during processing."""
        from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia

        _write_day_csv(tmp_dir, "2025-07-10", n_rows=5, potencia=10.0)
        messages: list = []
        ordenar_y_agrupado_por_dia(str(tmp_dir), log_callback=messages.append)
        assert len(messages) > 0

    def test_empty_folder_logs_warning(self, tmp_dir: Path) -> None:
        """Empty folder should log a warning and not raise."""
        from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia

        messages: list = []
        # Should not raise, should log a warning
        ordenar_y_agrupado_por_dia(str(tmp_dir), log_callback=messages.append)
        assert any("no se encontraron" in m.lower() for m in messages), (
            f"Expected no-CSV warning, got: {messages}"
        )
