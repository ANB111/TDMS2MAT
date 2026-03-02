"""
Shared pytest fixtures for the tdms2mat test suite.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Tempdir that is automatically removed after each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def minimal_config_dict() -> dict:
    """Minimal valid raw dict for AppConfig."""
    return {
        "input_folder": "/tmp/in",
        "output_folder": "/tmp/out",
        "excel_output_folder": "/tmp/excel",
    }


@pytest.fixture
def sample_csv_file(tmp_dir: Path) -> Path:
    """
    Creates a small synthetic CSV in the tdms2mat pipeline format.

    Format expected by csv_processor:
    - Delimiter: ;
    - Decimal: .
    - Has a 'Time' column in ISO-format
    """
    rows = []
    base = pd.Timestamp("2025-07-10 08:00:00")
    for i in range(20):
        t = base + pd.Timedelta(seconds=i * 6)  # 10 Hz → 1 sample / 0.1 s
        rows.append(
            {
                "Time": t.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Potencia": float(i),
                "Velocidad": float(100 + i),
                "Frecuencia": float(50.0),
            }
        )
    df = pd.DataFrame(rows)
    csv_path = tmp_dir / "sample.csv"
    df.to_csv(csv_path, sep=";", index=False)
    return csv_path


@pytest.fixture
def sample_mat_data() -> dict:
    """
    Synthetic MAT-compatible dict that mimics a day's processed .mat file,
    with the fields expected by startup_counter.
    """
    n = 3600  # 1 hour at 1 Hz
    time_epoch = np.linspace(0, 3600, n)
    # Channel 13 (index) → Velocidad
    velocidad = np.concatenate(
        [
            np.zeros(100),         # off
            np.ones(200) * 120.0,  # running
            np.zeros(100),         # off
            np.ones(200) * 120.0,  # running
            np.zeros(400),         # rest
        ]
    )
    # Channel 7 (index) → generic counter
    counter_ch = np.zeros(n)

    data = {
        "time_epoch": time_epoch,
    }
    # Build a matrix: shape (n, 16) — matches DEFAULT_COLUMN_ORDER count
    matrix = np.zeros((n, 17))
    matrix[:, 13] = velocidad
    matrix[:, 7] = counter_ch
    data["data"] = matrix
    data["channel_names"] = np.array(
        [
            "Time", "Potencia", "Paletas", "Alabes", "Pres_Abr_Pal",
            "Pres_Cerr_Pal", "Pres_Abr_Alab", "Pres_Cerr_Alab",
            "Cont_Potencia", "Consigna_Pal", "Consigna_Pot", "Consigna_Alab",
            "Salto_Reg", "Velocidad", "Frecuencia", "ModoPotCon", "FaseDiv2",
        ],
        dtype="U100",
    )
    return data
