"""Conteo de arranques/paradas y cálculo de horas de operación desde archivos .mat.

Correcciones respecto al original (startup_shutdown_counter.py):
- Los índices de canal están declarados como constantes nombradas al inicio del
  módulo; ya no son "magic numbers" enterrados en el código.
- ``parse_fecha_string`` valida el rango de año (2000–2099).
- El heurístico de "24 h forzado" emite una advertencia explícita via
  ``log_callback``.
- Separación clara entre lógica de cálculo (puras, sin I/O) y la función
  orquestadora ``process_mat_folder``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.io import loadmat  # type: ignore[import]

# ---------------------------------------------------------------------------
# Constantes de canales (índices base-0 en la matriz ``data`` del .mat)
# ---------------------------------------------------------------------------
#: Velocidad de la turbina (rpm).  Usado para detectar arranques y paradas.
SPEED_CHANNEL_IDX: int = 13

#: Canal de contador de movimientos (por ej. posición de paletas).
MOVEMENT_COUNTER_IDX: int = 7


# ---------------------------------------------------------------------------
# Funciones de análisis (puras — sin I/O ni logging)
# ---------------------------------------------------------------------------


def extract_numeric_key(filename: str) -> Tuple[int, ...]:
    """Clave de ordenamiento numérico para nombres ``YY.M.D-uNN.mat``."""
    base = filename.split("-")[0]
    try:
        return tuple(int(p) for p in base.split("."))
    except Exception:
        return (0,)


def count_startups_shutdowns(
    mat_data: dict,
) -> Tuple[int, int, str, str, np.ndarray]:
    """Cuenta ciclos de arranque y parada usando :data:`SPEED_CHANNEL_IDX`.

    Returns:
        Tupla ``(arranques, paradas, estado_inicial, estado_final, speed_data)``.
    """
    try:
        raw = np.atleast_2d(mat_data["data"])
        if raw.ndim < 2 or raw.shape[0] == 0 or raw.shape[1] <= SPEED_CHANNEL_IDX:
            return 0, 0, "Desconocido", "Desconocido", np.array([])
        speed_data: np.ndarray = raw[:, SPEED_CHANNEL_IDX]
    except (IndexError, KeyError):
        return 0, 0, "Desconocido", "Desconocido", np.array([])

    if speed_data.size < 2:
        estado = "Encendida" if speed_data.size == 1 and speed_data[0] > 0 else "Apagada"
        return 0, 0, estado, estado, speed_data

    startups = shutdowns = 0
    for i in range(1, len(speed_data)):
        prev, curr = speed_data[i - 1], speed_data[i]
        if prev == 0 and curr > 0:
            startups += 1
        elif prev > 0 and curr == 0:
            shutdowns += 1

    estado_inicial = "Encendida" if speed_data[0] > 0 else "Apagada"
    estado_final = "Encendida" if speed_data[-1] > 0 else "Apagada"
    return startups, shutdowns, estado_inicial, estado_final, speed_data


def calculate_runtime_hours(
    speed_data: np.ndarray,
    time_epoch: Optional[np.ndarray],
    sample_rate_hint: float = 10.0,
) -> Tuple[float, float]:
    """Calcula las horas encendida y las horas totales disponibles.

    Usa diferencias del vector de tiempo cuando está disponible; si no, emplea
    ``1 / sample_rate_hint`` como tamaño de intervalo.

    Returns:
        ``(horas_encendida, horas_disponibles)``
    """
    speed_array = np.asarray(speed_data, dtype=float).flatten()
    if speed_array.size == 0:
        return 0.0, 0.0

    on_mask = speed_array > 0
    time_array: Optional[np.ndarray] = None

    if isinstance(time_epoch, np.ndarray) and time_epoch.size:
        time_array = np.asarray(time_epoch, dtype=float).squeeze()
        if time_array.ndim > 1:
            time_array = time_array.reshape(-1)

    if time_array is not None and time_array.size >= speed_array.size:
        time_array = time_array[: speed_array.size]
        diffs = np.diff(time_array)
        diffs = np.where(diffs > 0, diffs, 0.0)
        intervals = np.zeros(speed_array.size, dtype=float)
        intervals[:-1] = diffs
    else:
        sample_rate = float(sample_rate_hint) if sample_rate_hint else 10.0
        intervals = np.full(speed_array.size, 1.0 / sample_rate, dtype=float)
        if intervals.size:
            intervals[-1] = 0.0

    horas_disponibles = float(intervals.sum() / 3600.0)
    horas_encendida = float(intervals[on_mask].sum() / 3600.0)
    return horas_encendida, horas_disponibles


def calculate_movements_from_counter(counter_series: np.ndarray) -> Optional[int]:
    """Calcula movimientos acumulados incluso cuando el contador se reinicia."""
    try:
        arr = np.asarray(counter_series, dtype=float).flatten()
    except Exception:
        return None

    arr = arr[~np.isnan(arr)]
    if arr.size <= 1:
        return 0

    positive_diffs = np.diff(arr)
    positive_diffs = positive_diffs[positive_diffs > 0]
    return int(round(float(positive_diffs.sum()))) if positive_diffs.size else 0


def parse_fecha_string(fecha: str) -> Optional[datetime]:
    """Convierte ``'YY.M.D'`` a :class:`datetime`.

    Valida que el año esté en el rango 2000–2099.
    """
    if not fecha or not isinstance(fecha, str):
        return None
    try:
        parts = fecha.strip().split(".")
        if len(parts) != 3:
            return None
        year, month, day = map(int, parts)
        if not (0 <= year <= 99):
            return None
        full_year = 2000 + year
        return datetime(year=full_year, month=month, day=day)
    except Exception:
        return None


def format_fecha_string(date_obj: datetime) -> str:
    """Convierte :class:`datetime` → ``'YY.M.D'``."""
    return f"{date_obj.year - 2000}.{date_obj.month}.{date_obj.day}"


# ---------------------------------------------------------------------------
# Función orquestadora
# ---------------------------------------------------------------------------


def process_mat_folder(
    mat_folder: str,
    excel_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Procesa todos los .mat y actualiza/crea el Excel de arranques y paradas.

    - Solo procesa archivos nuevos (no presentes en el Excel existente).
    - Rellena días faltantes con ceros.
    - Ordena cronológicamente por fecha.

    Args:
        mat_folder: Carpeta con los archivos .mat.
        excel_path: Ruta del Excel de salida (se crea si no existe).
        log_callback: Función de logging.
    """
    import os

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    expected_columns = [
        "Fecha", "Arranques", "Paradas", "Total",
        "Horas Encendida", "Movimientos",
        "Estado Inicial", "Estado Final", "Archivo",
        "Total Acumulado", "Movimientos Acumulados",
    ]

    # Cargar Excel existente o crear vacío
    if os.path.exists(excel_path):
        df_excel = pd.read_excel(excel_path)
        for col in expected_columns:
            if col not in df_excel.columns:
                df_excel[col] = None
        # Leer solo las columnas base (sin acumuladas) para no contaminar el recálculo
        base_columns = [c for c in expected_columns if c not in ("Total Acumulado", "Movimientos Acumulados")]
        df_excel = df_excel[base_columns]
        processed_files: set = set(df_excel["Archivo"].dropna())
    else:
        base_columns = [c for c in expected_columns if c not in ("Total Acumulado", "Movimientos Acumulados")]
        df_excel = pd.DataFrame(columns=base_columns)
        processed_files = set()

    # Listar y ordenar archivos .mat
    mat_files = sorted(
        [f for f in os.listdir(mat_folder) if f.endswith(".mat")],
        key=extract_numeric_key,
    )

    for mat_file in mat_files:
        if mat_file in processed_files:
            log(f"Saltando (ya procesado): {mat_file}")
            continue

        mat_path = os.path.join(mat_folder, mat_file)
        try:
            mat_data = loadmat(mat_path)
            date_str = mat_file.split("-")[0]

            # Validar que el archivo tenga datos suficientes para análisis
            raw_data = np.atleast_2d(mat_data.get("data", np.empty((0, 0))))
            n_samples = raw_data.shape[0]
            if n_samples < 2:
                log(f"ADVERTENCIA: '{mat_file}' tiene solo {n_samples} muestra(s); se omite el análisis.")
                new_row = {
                    "Fecha": date_str,
                    "Arranques": 0,
                    "Paradas": 0,
                    "Total": 0,
                    "Horas Encendida": 0.0,
                    "Movimientos": None,
                    "Estado Inicial": "Desconocido",
                    "Estado Final": "Desconocido",
                    "Archivo": mat_file,
                }
                df_excel = pd.concat(
                    [df_excel, pd.DataFrame([new_row])], ignore_index=True
                )
                processed_files.add(mat_file)
                continue

            startups, shutdowns, est_ini, est_fin, speed_data = count_startups_shutdowns(
                mat_data
            )
            total = startups + shutdowns

            try:
                raw = np.atleast_2d(mat_data["data"])
                if raw.ndim >= 2 and raw.shape[1] > MOVEMENT_COUNTER_IDX:
                    movimientos = calculate_movements_from_counter(
                        raw[:, MOVEMENT_COUNTER_IDX]
                    )
                else:
                    movimientos = None
            except Exception:
                movimientos = None

            time_epoch = mat_data.get("time_epoch")
            horas_enc, horas_disp = calculate_runtime_hours(speed_data, time_epoch)

            # Heurístico de día completo con máquina siempre encendida
            if (
                horas_disp >= 23.9
                and speed_data.size > 0
                and speed_data[0] > 0
                and shutdowns == 0
            ):
                log(
                    f"ADVERTENCIA: '{mat_file}' tiene datos de ~24 h sin paradas y "
                    "máquina encendida desde el inicio. Forzando horas_encendida = 24."
                )
                horas_enc = 24.0

            horas_enc = round(horas_enc, 2)

            new_row = {
                "Fecha": date_str,
                "Arranques": startups,
                "Paradas": shutdowns,
                "Total": total,
                "Horas Encendida": horas_enc,
                "Movimientos": movimientos,
                "Estado Inicial": est_ini,
                "Estado Final": est_fin,
                "Archivo": mat_file,
            }
            df_excel = pd.concat(
                [df_excel, pd.DataFrame([new_row])], ignore_index=True
            )
            processed_files.add(mat_file)

        except Exception as exc:
            log(f"Error procesando '{mat_file}': {exc}")

    # Rellenar días faltantes con ceros
    parsed_dates = df_excel["Fecha"].apply(parse_fecha_string)
    valid_dates = parsed_dates.dropna()

    if not valid_dates.empty:
        min_date = valid_dates.min()
        max_date = valid_dates.max()
        existing_dates = {dt.date() for dt in valid_dates}

        missing_rows = []
        for current in pd.date_range(min_date, max_date, freq="D"):
            if current.date() in existing_dates:
                continue
            missing_rows.append(
                {
                    "Fecha": format_fecha_string(current.to_pydatetime()),
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
            df_excel = pd.concat(
                [df_excel, pd.DataFrame(missing_rows)], ignore_index=True
            )
            parsed_dates = df_excel["Fecha"].apply(parse_fecha_string)

        df_excel["__fecha_dt"] = pd.to_datetime(parsed_dates)
        df_excel = df_excel.sort_values(
            "__fecha_dt", kind="mergesort", na_position="last"
        )
        df_excel["Fecha"] = df_excel["__fecha_dt"].apply(
            lambda dt: format_fecha_string(dt.to_pydatetime()) if pd.notna(dt) else ""
        )
        df_excel = df_excel.drop(columns=["__fecha_dt"]).reset_index(drop=True)

    # Calcular columnas acumuladas (sobre el DataFrame ya ordenado)
    df_excel["Total Acumulado"] = pd.to_numeric(
        df_excel["Total"], errors="coerce"
    ).fillna(0).cumsum().astype(int)

    df_excel["Movimientos Acumulados"] = pd.to_numeric(
        df_excel["Movimientos"], errors="coerce"
    ).fillna(0).cumsum().astype(int)

    df_excel.to_excel(excel_path, index=False)
    log(f"Resultados guardados en: {excel_path}")
