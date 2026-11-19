"""Conversión de CSV diarios a archivos MAT (scipy.io.savemat).

Correcciones respecto al original (mat_utils.py):
- Guarda los **nombres de columna** en ``channel_names`` dentro del .mat, de
  modo que el script MATLAB ya no depende de índices numéricos ciegos.
- ``decimal`` es consistente con el ``csv_processor`` (ambos usan ``.`` por
  defecto; configurable vía parámetro).
- Los CSV de días **completos** se eliminan tras la conversión.
- Los CSV ``_temp`` (días incompletos) se dejan intactos: el orquestador los
  mueve a la carpeta de estado persistente para el próximo run.

Optimizaciones de rendimiento:
- **ProcessPoolExecutor**: cada conversión CSV→MAT corre en un proceso
  separado con su propio GIL, logrando paralelismo CPU real.
  pd.read_csv, pd.to_datetime y savemat son CPU-bound; con hilos el GIL
  los serializa en la práctica.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.io import savemat  # type: ignore[import]

from tdms2mat.utils.threading_utils import cancelable_pool_map


def _convert_one(
    csv_file: str,
    input_folder: str,
    output_folder: str,
    unidad: str,
    decimal: str,
) -> Tuple[str, Optional[str]]:
    """Convierte un único CSV a MAT.

    Returns:
        ``(csv_file, error_msg)`` donde *error_msg* es ``None`` si fue exitoso.
    """
    output_name = csv_file.replace("_temp", "")
    input_path = os.path.join(input_folder, csv_file)
    date_part = os.path.splitext(output_name)[0].split("-")[0]
    output_path = os.path.join(output_folder, f"{date_part}-u{unidad}.mat")

    try:
        data = pd.read_csv(input_path, delimiter=";", decimal=decimal)

        if "Time" not in data.columns:
            return csv_file, f"omitido: falta columna 'Time'."

        data["Time"] = pd.to_datetime(data["Time"], errors="coerce")
        if data["Time"].isnull().all():
            return csv_file, "omitido: errores en conversión de fechas."

        # Convertir tiempo a epoch de manera vectorizada
        epoch_origin = pd.Timestamp("1970-01-01")
        data["Time_epoch"] = (data["Time"] - epoch_origin).dt.total_seconds()

        numeric_cols = [c for c in data.columns if c not in ("Time", "Time_epoch")]

        mat_data = {
            "time_epoch": data["Time_epoch"].to_numpy(dtype=np.float64),
            "data": data[numeric_cols].to_numpy(dtype=np.float64),
            "channel_names": np.array(numeric_cols, dtype="U100"),
        }

        savemat(output_path, mat_data)

        # Sólo eliminar CSVs de días completos.
        if "_temp" not in csv_file:
            os.remove(input_path)

        return csv_file, None

    except Exception as exc:
        return csv_file, str(exc)


def csv_to_mat(
    input_folder: str,
    output_folder: str,
    unidad: str = "05",
    procesar_incompleto: bool = False,
    decimal: str = ".",
    log_callback: Optional[Callable[[str], None]] = None,
    file_progress_callback: Optional[Callable[[int, int, str], None]] = None,
    num_workers: Optional[int] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Convierte todos los CSV diarios de *input_folder* a archivos MAT en paralelo.

    Formato del .mat generado:
    - ``time_epoch`` — vector float64 con el tiempo UNIX (segundos desde 1970).
    - ``data`` — matriz float64 con las columnas numéricas (sin la columna Time).
    - ``channel_names`` — array de strings con los nombres originales de las
      columnas numéricas (permite referenciarlas por nombre en MATLAB).

    Args:
        input_folder: Carpeta con los CSV generados por :mod:`csv_processor`.
        output_folder: Carpeta destino de los .mat.
        unidad: Sufijo de unidad para el nombre de archivo (ej. ``"05"``).
        procesar_incompleto: Si ``True`` incluye archivos ``_temp.csv``.
        decimal: Separador decimal de los CSV (debe coincidir con el usado al
            escribirlos; default ``"."``.
        log_callback: Función de logging.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    if not os.path.exists(input_folder):
        log(f"[CSV→MAT] La carpeta de entrada '{input_folder}' no existe.")
        return

    os.makedirs(output_folder, exist_ok=True)

    csv_files: List[str] = [
        f
        for f in os.listdir(input_folder)
        if f.endswith(".csv")
        and (procesar_incompleto or "_temp" not in f)
    ]

    if not csv_files:
        log(f"[CSV→MAT] No se encontraron CSV en '{input_folder}'.")
        return

    cpu = os.cpu_count() or 2
    workers = num_workers if num_workers else min(cpu, len(csv_files))
    log(f"[CSV→MAT] Convirtiendo {len(csv_files)} archivo(s) con {workers} procesos...")
    completados = 0
    total = len(csv_files)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(_convert_one, f, input_folder, output_folder, unidad, decimal): f
            for f in csv_files
        }

        def _on_result(fut, csv_f):  # type: ignore[misc]
            nonlocal completados
            csv_f_res, err = fut.result()
            completados += 1
            if err:
                log(f"[CSV→MAT] '{csv_f_res}': {err}")
            else:
                log(f"[CSV→MAT] {csv_f_res} → convertido.")
            if file_progress_callback:
                file_progress_callback(completados, total, csv_f_res)

        if not cancelable_pool_map(executor, futuros, stop_event, _on_result):
            log("[CSV→MAT] Cancelado por el usuario.")
