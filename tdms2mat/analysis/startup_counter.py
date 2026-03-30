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

# Umbrales de histéresis y anti-rebote para el conteo de transiciones.
# La señal de velocidad está normalizada en 0-100, pero la referencia física
# es 0-72 rpm. Se considera parada por debajo de 1 rpm.
SPEED_MAX_RPM: float = 72.0
STOP_RPM_THRESHOLD: float = 1.0

# Encendida cuando velocidad >= STARTUP_ON_THRESHOLD.
# Apagada cuando velocidad <= SHUTDOWN_OFF_THRESHOLD.
STARTUP_ON_THRESHOLD: float = (STOP_RPM_THRESHOLD / SPEED_MAX_RPM) * 100.0
SHUTDOWN_OFF_THRESHOLD: float = STARTUP_ON_THRESHOLD

# Cantidad mínima de muestras consecutivas para confirmar transición.
# Si la transición queda pendiente al final de la serie, se confirma una vez.
STATE_CONFIRM_SAMPLES: int = 2

# Bloque mínimo (muestras) de filas totalmente en cero para considerar
# desconexión de adquisición cuando aparece en medio de dos tramos válidos.
DISCONNECTED_MIN_BLOCK_SAMPLES: int = 2


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
        disconnected_mask = detect_disconnected_rows(
            raw,
            min_block_samples=DISCONNECTED_MIN_BLOCK_SAMPLES,
        )
        speed_data: np.ndarray = raw[:, SPEED_CHANNEL_IDX]
    except (IndexError, KeyError):
        return 0, 0, "Desconocido", "Desconocido", np.array([])

    if speed_data.size < 2:
        estado = (
            "Encendida"
            if speed_data.size == 1 and speed_data[0] >= STARTUP_ON_THRESHOLD
            else "Apagada"
        )
        return 0, 0, estado, estado, speed_data

    startups, shutdowns, estado_inicial, estado_final = _count_with_hysteresis(
        speed_data,
        on_threshold=STARTUP_ON_THRESHOLD,
        off_threshold=SHUTDOWN_OFF_THRESHOLD,
        confirm_samples=STATE_CONFIRM_SAMPLES,
        disconnected_mask=disconnected_mask,
    )
    return startups, shutdowns, estado_inicial, estado_final, speed_data


def detect_disconnected_rows(
    raw_data: np.ndarray,
    min_block_samples: int = DISCONNECTED_MIN_BLOCK_SAMPLES,
) -> np.ndarray:
    """Detecta huecos de desconexión como bloques internos de filas en cero.

    Se marcan solo bloques **internos** (ni al inicio ni al final) para evitar
    confundir periodos reales de máquina apagada al arranque/cierre del archivo.
    """
    raw = np.asarray(raw_data, dtype=float)
    if raw.ndim != 2 or raw.shape[0] == 0:
        return np.zeros(raw.shape[0], dtype=bool)

    zero_rows = np.all(raw == 0.0, axis=1)
    if not np.any(zero_rows):
        return np.zeros(raw.shape[0], dtype=bool)

    min_len = max(1, int(min_block_samples))
    disconnected = np.zeros(raw.shape[0], dtype=bool)

    i = 0
    n = raw.shape[0]
    while i < n:
        if not zero_rows[i]:
            i += 1
            continue
        start = i
        while i < n and zero_rows[i]:
            i += 1
        end = i  # exclusivo

        is_internal = start > 0 and end < n
        if is_internal and (end - start) >= min_len:
            disconnected[start:end] = True

    return disconnected


def _count_with_hysteresis(
    speed_data: np.ndarray,
    on_threshold: float,
    off_threshold: float,
    confirm_samples: int,
    disconnected_mask: Optional[np.ndarray] = None,
) -> Tuple[int, int, str, str]:
    """Cuenta transiciones con histéresis y confirmación de estado.

    Esta lógica evita falsos conteos por ruido/rebote cerca de cero.
    """
    arr = np.asarray(speed_data, dtype=float).flatten()
    if arr.size == 0:
        return 0, 0, "Desconocido", "Desconocido"

    if disconnected_mask is None:
        disconnected = np.zeros(arr.size, dtype=bool)
    else:
        disconnected = np.asarray(disconnected_mask, dtype=bool).flatten()
        if disconnected.size < arr.size:
            padded = np.zeros(arr.size, dtype=bool)
            padded[: disconnected.size] = disconnected
            disconnected = padded
        elif disconnected.size > arr.size:
            disconnected = disconnected[: arr.size]

    connected_idx = np.flatnonzero(~disconnected)
    if connected_idx.size == 0:
        return 0, 0, "Desconocido", "Desconocido"

    # Separar tramos conectados contiguos e ignorar transiciones entre tramos.
    split_at = np.where(np.diff(connected_idx) > 1)[0]
    seg_starts = np.r_[0, split_at + 1]
    seg_ends = np.r_[split_at, connected_idx.size - 1]

    startups = 0
    shutdowns = 0
    estado_inicial = "Desconocido"
    estado_final = "Desconocido"

    for seg_i, (s_idx, e_idx) in enumerate(zip(seg_starts, seg_ends)):
        idx_slice = connected_idx[s_idx : e_idx + 1]
        seg = arr[idx_slice]
        (
            seg_startups,
            seg_shutdowns,
            seg_estado_ini,
            seg_estado_fin,
        ) = _count_contiguous_segment(
            seg,
            on_threshold=on_threshold,
            off_threshold=off_threshold,
            confirm_samples=confirm_samples,
        )

        startups += seg_startups
        shutdowns += seg_shutdowns
        if seg_i == 0:
            estado_inicial = seg_estado_ini
        estado_final = seg_estado_fin

    return startups, shutdowns, estado_inicial, estado_final


def _count_contiguous_segment(
    arr: np.ndarray,
    on_threshold: float,
    off_threshold: float,
    confirm_samples: int,
) -> Tuple[int, int, str, str]:
    """Cuenta transiciones en un tramo sin desconexiones."""
    if arr.size == 0:
        return 0, 0, "Desconocido", "Desconocido"

    # Estado inicial con histéresis: por defecto, un valor intermedio se toma
    # como apagada para minimizar falsos arranques.
    is_on = bool(arr[0] >= on_threshold)
    estado_inicial = "Encendida" if is_on else "Apagada"

    startups = 0
    shutdowns = 0
    required = max(1, int(confirm_samples))
    pending_state: Optional[bool] = None
    pending_count = 0

    for value in arr[1:]:
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

    # Si la serie termina durante una transición pendiente, se confirma una vez.
    if pending_state is not None and pending_state != is_on and pending_count > 0:
        if pending_state:
            startups += 1
        else:
            shutdowns += 1
        is_on = pending_state

    estado_final = "Encendida" if is_on else "Apagada"
    return startups, shutdowns, estado_inicial, estado_final


def calculate_runtime_hours(
    speed_data: np.ndarray,
    time_epoch: Optional[np.ndarray],
    sample_rate_hint: float = 10.0,
    disconnected_mask: Optional[np.ndarray] = None,
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

    if disconnected_mask is None:
        disconnected = np.zeros(speed_array.size, dtype=bool)
    else:
        disconnected = np.asarray(disconnected_mask, dtype=bool).flatten()
        if disconnected.size < speed_array.size:
            padded = np.zeros(speed_array.size, dtype=bool)
            padded[: disconnected.size] = disconnected
            disconnected = padded
        elif disconnected.size > speed_array.size:
            disconnected = disconnected[: speed_array.size]

    on_mask = (speed_array >= STARTUP_ON_THRESHOLD) & (~disconnected)
    time_array: Optional[np.ndarray] = None

    if isinstance(time_epoch, np.ndarray) and time_epoch.size:
        time_array = np.asarray(time_epoch, dtype=float).squeeze()
        if time_array.ndim > 1:
            time_array = time_array.reshape(-1)

    if time_array is not None and time_array.size >= speed_array.size:
        time_array = time_array[: speed_array.size]
        diffs = np.diff(time_array)
        valid_pair = (~disconnected[:-1]) & (~disconnected[1:])
        diffs = np.where((diffs > 0) & valid_pair, diffs, 0.0)
        intervals = np.zeros(speed_array.size, dtype=float)
        intervals[:-1] = diffs
    else:
        sample_rate = float(sample_rate_hint) if sample_rate_hint else 10.0
        intervals = np.full(speed_array.size, 1.0 / sample_rate, dtype=float)
        valid_pair = (~disconnected[:-1]) & (~disconnected[1:])
        intervals[:-1] = np.where(valid_pair, intervals[:-1], 0.0)
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

    - Si existe Excel previo, procesa desde la última fecha registrada en adelante.
    - Además, solo procesa archivos nuevos (no presentes por nombre en el Excel).
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
    last_recorded_date: Optional[datetime] = None
    last_known_state_date: Optional[datetime] = None
    last_known_state: Optional[str] = None

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

        parsed_existing_dates = df_excel["Fecha"].apply(parse_fecha_string)
        valid_existing_dates = parsed_existing_dates.dropna()
        if not valid_existing_dates.empty:
            last_recorded_date = valid_existing_dates.max()
            log(
                "Modo incremental por fecha habilitado. "
                f"Última fecha en Excel: {format_fecha_string(last_recorded_date)}"
            )

        # Último estado confiable para inferir transición al reconectar
        state_rows = df_excel.copy()
        state_rows["__fecha_dt"] = parsed_existing_dates
        state_rows = state_rows[
            state_rows["__fecha_dt"].notna()
            & state_rows["Estado Final"].isin(["Encendida", "Apagada"])
            & state_rows["Archivo"].notna()
            & (state_rows["Archivo"].astype(str).str.strip() != "")
        ]
        if not state_rows.empty:
            state_rows = state_rows.sort_values("__fecha_dt", kind="mergesort")
            last_state_row = state_rows.iloc[-1]
            last_known_state_date = last_state_row["__fecha_dt"]
            last_known_state = str(last_state_row["Estado Final"])
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

        file_date = parse_fecha_string(mat_file.split("-")[0])
        if (
            last_recorded_date is not None
            and file_date is not None
            and file_date.date() <= last_recorded_date.date()
        ):
            log(
                "Saltando (anterior o igual al último registro en Excel): "
                f"{mat_file}"
            )
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

            disconnected_mask = detect_disconnected_rows(
                raw_data,
                min_block_samples=DISCONNECTED_MIN_BLOCK_SAMPLES,
            )
            n_disconnected = int(disconnected_mask.sum())
            if n_disconnected > 0:
                log(
                    f"ADVERTENCIA: '{mat_file}' contiene {n_disconnected} muestra(s) "
                    "de desconexión (filas en cero internas). Se ignoran para conteo."
                )

            startups, shutdowns, est_ini, est_fin, speed_data = count_startups_shutdowns(
                mat_data
            )

            if (
                last_known_state_date is not None
                and last_known_state in ("Encendida", "Apagada")
                and file_date is not None
                and est_ini in ("Encendida", "Apagada")
            ):
                gap_days = (file_date.date() - last_known_state_date.date()).days
                if gap_days > 1 and est_ini != last_known_state:
                    if last_known_state == "Apagada" and est_ini == "Encendida":
                        startups += 1
                        log(
                            "Transición inferida por reconexión: "
                            f"+1 arranque en '{mat_file}' "
                            f"(gap {gap_days} días, estado previo: {last_known_state}, "
                            f"estado inicial: {est_ini})."
                        )
                    elif last_known_state == "Encendida" and est_ini == "Apagada":
                        shutdowns += 1
                        log(
                            "Transición inferida por reconexión: "
                            f"+1 parada en '{mat_file}' "
                            f"(gap {gap_days} días, estado previo: {last_known_state}, "
                            f"estado inicial: {est_ini})."
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
            horas_enc, horas_disp = calculate_runtime_hours(
                speed_data,
                time_epoch,
                disconnected_mask=disconnected_mask,
            )

            # Heurístico de día completo con máquina siempre encendida
            if (
                horas_disp >= 23.9
                and speed_data.size > 0
                and speed_data[0] >= STARTUP_ON_THRESHOLD
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

            if file_date is not None and est_fin in ("Encendida", "Apagada"):
                last_known_state_date = file_date
                last_known_state = est_fin

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
