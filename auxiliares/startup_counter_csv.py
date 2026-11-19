"""Conteo diario de arranques/paradas para un CSV externo (no MAT).

Caso objetivo:
- Entrada: ``U05 diciembre 2025 copy.csv`` en la carpeta ``auxiliares``.
- Salida: Excel ``arranque_paradas_csv.xlsx`` en la carpeta ``auxiliares``.

Reglas acordadas para este caso:
- Máquina encendida si ``Velocidad_rpm >= 1``.
- Una fila por día con acumulados.
- Columnas de movimientos en cero (no existe contador en el CSV).
- Fecha de salida en formato ``DD/MM/YYYY``.

Robustez adicional:
- Histéresis de velocidad para evitar rebote: encendida con umbral de entrada
    y apagada con umbral de salida.
- Confirmación por muestras consecutivas para filtrar picos espurios.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd


# Nombres exactos esperados para este CSV (6 columnas útiles).
EXPECTED_COLUMNS = [
    "Time",
    "Velocidad_rpm",
    "PosicionDistribuidor_%",
    "PosicionRodete%",
    "PotenciaActiva_Mw",
    "SaltoRegulador_m",
]


OUTPUT_COLUMNS = [
    "Fecha",
    "Arranques",
    "Paradas",
    "Total",
    "Horas Encendida",
    "Movimientos",
    "Estado Inicial",
    "Estado Final",
    "Archivo",
    "Total Acumulado",
    "Movimientos Acumulados",
]


SPEED_MAX_RPM = 72.0
STOP_RPM_THRESHOLD = 1.0

DEFAULT_ON_THRESHOLD = (STOP_RPM_THRESHOLD / SPEED_MAX_RPM) * 100.0
DEFAULT_OFF_THRESHOLD = DEFAULT_ON_THRESHOLD
DEFAULT_CONFIRM_SAMPLES = 2


@dataclass(frozen=True)
class DailyStats:
    date: pd.Timestamp
    startups: int
    shutdowns: int
    total: int
    runtime_hours: float
    estado_inicial: str
    estado_final: str


def _default_paths() -> tuple[Path, Path]:
    base = Path(__file__).resolve().parent
    return base / "U05 diciembre 2025 copy.csv", base / "arranque_paradas_csv.xlsx"


def _normalize_ampm(values: pd.Series) -> pd.Series:
    as_str = values.astype(str).str.strip()
    as_str = as_str.str.replace("a.m.", "AM", regex=False)
    as_str = as_str.str.replace("p.m.", "PM", regex=False)
    return as_str


def _read_and_validate_csv(csv_path: Path, log: Callable[[str], None]) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el CSV de entrada: {csv_path}")

    df = pd.read_csv(csv_path, sep=";", decimal=",")

    # Muchos exportadores dejan un delimitador ';' final y crean una columna
    # adicional vacía (por ejemplo "Unnamed: 6"). Se elimina aquí.
    empty_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if empty_cols:
        df = df.drop(columns=empty_cols)

    all_nan_cols = [c for c in df.columns if df[c].isna().all()]
    if all_nan_cols:
        df = df.drop(columns=all_nan_cols)

    actual_cols = list(df.columns)
    log(f"Columnas detectadas ({len(actual_cols)}): {actual_cols}")

    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Faltan columnas esperadas en el CSV: "
            f"{missing}. Columnas detectadas: {actual_cols}"
        )

    if len(actual_cols) != 6:
        log(
            "ADVERTENCIA: tras limpieza no hay exactamente 6 columnas. "
            f"Se continuará usando las esperadas: {EXPECTED_COLUMNS}"
        )

    return df[EXPECTED_COLUMNS].copy()


def _parse_time_column(df: pd.DataFrame, log: Callable[[str], None]) -> pd.DataFrame:
    normalized_time = _normalize_ampm(df["Time"])
    parsed = pd.to_datetime(
        normalized_time,
        format="%d/%m/%Y %I:%M:%S %p",
        errors="coerce",
    )

    invalid_count = int(parsed.isna().sum())
    if invalid_count:
        log(f"ADVERTENCIA: se descartarán {invalid_count} fila(s) por fecha inválida.")

    work = df.copy()
    work["Time"] = parsed
    work["Velocidad_rpm"] = pd.to_numeric(work["Velocidad_rpm"], errors="coerce")

    # Sin tiempo o sin velocidad no se puede contar transiciones correctamente.
    before = len(work)
    work = work.dropna(subset=["Time", "Velocidad_rpm"]).copy()
    removed = before - len(work)
    if removed:
        log(f"ADVERTENCIA: se eliminaron {removed} fila(s) con Time/Velocidad nulos.")

    work = work.sort_values("Time", kind="mergesort").reset_index(drop=True)
    return work


def _compute_runtime_hours(speed: np.ndarray, ts: np.ndarray, threshold: float) -> float:
    if speed.size == 0:
        return 0.0

    on_mask = speed >= threshold
    intervals = np.zeros(speed.size, dtype=float)

    if ts.size >= 2:
        diffs = np.diff(ts).astype("timedelta64[ns]").astype(np.int64) / 1_000_000_000.0
        diffs = np.where(diffs > 0, diffs, 0.0)
        intervals[:-1] = diffs

    hours = float(intervals[on_mask].sum() / 3600.0)
    return round(hours, 2)


def _count_with_hysteresis(
    speed: np.ndarray,
    on_threshold: float,
    off_threshold: float,
    confirm_samples: int,
) -> tuple[int, int, str, str]:
    if speed.size == 0:
        return 0, 0, "Desconocido", "Desconocido"

    is_on = bool(speed[0] >= on_threshold)
    estado_inicial = "Encendida" if is_on else "Apagada"

    startups = 0
    shutdowns = 0
    required = max(1, int(confirm_samples))
    pending_state: Optional[bool] = None
    pending_count = 0

    for value in speed[1:]:
        if is_on:
            target_on = not (value <= off_threshold)
        else:
            target_on = bool(value >= on_threshold)

        if target_on == is_on:
            pending_state = None
            pending_count = 0
            continue

        if pending_state is None or pending_state != target_on:
            pending_state = target_on
            pending_count = 1
        else:
            pending_count += 1

        if pending_count >= required:
            if pending_state:
                startups += 1
            else:
                shutdowns += 1
            is_on = pending_state
            pending_state = None
            pending_count = 0

    if pending_state is not None and pending_state != is_on and pending_count > 0:
        if pending_state:
            startups += 1
        else:
            shutdowns += 1
        is_on = pending_state

    estado_final = "Encendida" if is_on else "Apagada"
    return startups, shutdowns, estado_inicial, estado_final


def _compute_daily_stats(
    day_df: pd.DataFrame,
    on_threshold: float,
    off_threshold: float,
    confirm_samples: int,
) -> DailyStats:
    speed = day_df["Velocidad_rpm"].to_numpy(dtype=float)
    ts = day_df["Time"].to_numpy(dtype="datetime64[ns]")

    if speed.size == 0:
        date = pd.Timestamp(day_df["Time"].iloc[0]).normalize()
        return DailyStats(
            date=date,
            startups=0,
            shutdowns=0,
            total=0,
            runtime_hours=0.0,
            estado_inicial="Desconocido",
            estado_final="Desconocido",
        )

    startups, shutdowns, estado_inicial, estado_final = _count_with_hysteresis(
        speed,
        on_threshold=on_threshold,
        off_threshold=off_threshold,
        confirm_samples=confirm_samples,
    )
    runtime_hours = _compute_runtime_hours(speed, ts, on_threshold)

    return DailyStats(
        date=pd.Timestamp(day_df["Time"].iloc[0]).normalize(),
        startups=startups,
        shutdowns=shutdowns,
        total=startups + shutdowns,
        runtime_hours=runtime_hours,
        estado_inicial=estado_inicial,
        estado_final=estado_final,
    )


def _build_daily_rows(
    df: pd.DataFrame,
    source_name: str,
    on_threshold: float,
    off_threshold: float,
    confirm_samples: int,
    log: Callable[[str], None],
) -> pd.DataFrame:
    if df.empty:
        raise ValueError("No quedaron filas válidas después de parsear y limpiar el CSV.")

    by_day = []
    grouped = df.groupby(df["Time"].dt.date, sort=True)
    for _, day_df in grouped:
        stats = _compute_daily_stats(
            day_df,
            on_threshold=on_threshold,
            off_threshold=off_threshold,
            confirm_samples=confirm_samples,
        )
        by_day.append(
            {
                "_fecha_dt": stats.date,
                "Fecha": stats.date.strftime("%d/%m/%Y"),
                "Arranques": stats.startups,
                "Paradas": stats.shutdowns,
                "Total": stats.total,
                "Horas Encendida": stats.runtime_hours,
                "Movimientos": 0,
                "Estado Inicial": stats.estado_inicial,
                "Estado Final": stats.estado_final,
                "Archivo": source_name,
            }
        )

    out = pd.DataFrame(by_day)
    out = out.sort_values("_fecha_dt", kind="mergesort").reset_index(drop=True)

    min_date = out["_fecha_dt"].min()
    max_date = out["_fecha_dt"].max()

    existing = {d.date() for d in out["_fecha_dt"]}
    missing_rows = []
    for current in pd.date_range(min_date, max_date, freq="D"):
        if current.date() in existing:
            continue
        missing_rows.append(
            {
                "_fecha_dt": current.normalize(),
                "Fecha": current.strftime("%d/%m/%Y"),
                "Arranques": 0,
                "Paradas": 0,
                "Total": 0,
                "Horas Encendida": 0.0,
                "Movimientos": 0,
                "Estado Inicial": "",
                "Estado Final": "",
                "Archivo": "",
            }
        )

    if missing_rows:
        log(f"Se agregaron {len(missing_rows)} día(s) faltante(s) con ceros.")
        out = pd.concat([out, pd.DataFrame(missing_rows)], ignore_index=True)
        out = out.sort_values("_fecha_dt", kind="mergesort").reset_index(drop=True)

    out["Total Acumulado"] = (
        pd.to_numeric(out["Total"], errors="coerce").fillna(0).cumsum().astype(int)
    )
    out["Movimientos Acumulados"] = (
        pd.to_numeric(out["Movimientos"], errors="coerce").fillna(0).cumsum().astype(int)
    )

    out = out.drop(columns=["_fecha_dt"])
    return out[OUTPUT_COLUMNS]


def process_csv_file(
    csv_path: Path,
    excel_path: Path,
    speed_on_threshold: float = DEFAULT_ON_THRESHOLD,
    speed_off_threshold: float = DEFAULT_OFF_THRESHOLD,
    confirm_samples: int = DEFAULT_CONFIRM_SAMPLES,
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    log(f"Procesando CSV: {csv_path}")
    raw = _read_and_validate_csv(csv_path, log)
    prepared = _parse_time_column(raw, log)

    if prepared.empty:
        raise ValueError("No hay datos válidos para procesar después de la limpieza.")

    date_min = prepared["Time"].min()
    date_max = prepared["Time"].max()
    log(
        "Rango temporal válido: "
        f"{date_min.strftime('%d/%m/%Y %H:%M:%S')} -> {date_max.strftime('%d/%m/%Y %H:%M:%S')}"
    )

    out = _build_daily_rows(
        prepared,
        source_name=csv_path.name,
        on_threshold=float(speed_on_threshold),
        off_threshold=float(speed_off_threshold),
        confirm_samples=int(confirm_samples),
        log=log,
    )

    excel_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_excel(excel_path, index=False)

    total_arr = int(out["Arranques"].sum())
    total_par = int(out["Paradas"].sum())
    log(f"Filas en salida (días): {len(out)}")
    log(f"Totales: arranques={total_arr}, paradas={total_par}")
    log(f"Excel generado en: {excel_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    default_csv, default_excel = _default_paths()

    parser = argparse.ArgumentParser(
        description=(
            "Analiza un CSV de velocidad para contar arranques/paradas por día "
            "y generar un Excel con acumulados."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=f"Ruta CSV de entrada (default: {default_csv})",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=default_excel,
        help=f"Ruta Excel de salida (default: {default_excel})",
    )
    parser.add_argument(
        "--speed-threshold",
        type=float,
        default=None,
        help=(
            "Umbral único de velocidad (retrocompatible). "
            "Si se usa, se aplica como umbral de encendido."
        ),
    )
    parser.add_argument(
        "--speed-on-threshold",
        type=float,
        default=DEFAULT_ON_THRESHOLD,
        help=(
            "Umbral de entrada en la escala de la señal (0-100). "
            "Default equivale a 1 rpm con base 72 rpm."
        ),
    )
    parser.add_argument(
        "--speed-off-threshold",
        type=float,
        default=DEFAULT_OFF_THRESHOLD,
        help=(
            "Umbral de salida en la escala de la señal (0-100). "
            "Default equivale a 1 rpm con base 72 rpm."
        ),
    )
    parser.add_argument(
        "--confirm-samples",
        type=int,
        default=DEFAULT_CONFIRM_SAMPLES,
        help="Muestras consecutivas para confirmar transición (default: 2).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    on_threshold = (
        float(args.speed_threshold)
        if args.speed_threshold is not None
        else float(args.speed_on_threshold)
    )
    off_threshold = float(args.speed_off_threshold)
    if off_threshold > on_threshold:
        raise ValueError(
            "speed-off-threshold no puede ser mayor que speed-on-threshold."
        )

    process_csv_file(
        args.csv,
        args.excel,
        speed_on_threshold=on_threshold,
        speed_off_threshold=off_threshold,
        confirm_samples=max(1, int(args.confirm_samples)),
    )


if __name__ == "__main__":
    main()
