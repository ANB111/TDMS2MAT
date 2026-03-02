"""Ordenamiento y agrupación de archivos CSV por día calendario.

Correcciones críticas respecto al original (csv_utils.py):
- **Bug crítico corregido**: ``datos_por_dia`` y ``datos_lock`` son ahora
  variables **locales** a ``ordenar_y_agrupado_por_dia()``, no globales.
  En la versión original, llamar a esta función dos veces en el mismo proceso
  provocaba que los datos del primer run se mezclaran con los del segundo.
- ``COLUMN_ORDER`` se puede pasar como parámetro (``column_order``), con la
  lista hardcodeada como valor por defecto retrocompatible.
- Workers por defecto = ``min(8, cpu_count())`` en lugar de 14 fijo.
"""
from __future__ import annotations

import glob
import os
import shutil
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

import pandas as pd

# Columnas conocidas de los TDMS de la turbina hidráulica.
# Se puede sobreescribir pasando ``column_order`` a ``ordenar_y_agrupado_por_dia``.
DEFAULT_COLUMN_ORDER: List[str] = [
    "Time", "Potencia", "Paletas", "Alabes", "Pres_Abr_Pal", "Pres_Cerr_Pal",
    "Pres_Abr_Alab", "Pres_Cerr_Alab", "Cont_Potencia", "Consigna_Pal",
    "Consigna_Pot", "Consigna_Alab", "Salto_Reg", "Velocidad", "Frecuencia",
    "ModoPotCon", "FaseDiv2",
]


def _default_workers() -> int:
    cpu = os.cpu_count() or 4
    return min(8, cpu)


def _procesar_csv_individual(
    file: str,
    datos_por_dia: Dict,
    datos_lock: threading.Lock,
    decimal: str,
) -> None:
    """Lee un CSV en chunks y acumula filas en *datos_por_dia* (thread-safe)."""
    try:
        for chunk in pd.read_csv(
            file,
            delimiter=";",
            decimal=decimal,
            parse_dates=["Time"],
            chunksize=10_000,
        ):
            chunk.sort_values(by="Time", inplace=True)
            chunk["Date"] = chunk["Time"].dt.date
            with datos_lock:
                for date, group in chunk.groupby("Date"):
                    datos_por_dia[date].append(group)
    except Exception as exc:
        # No podemos usar log_callback aquí sin overhead extra de locking;
        # el error quedará como excepción en el Future.
        raise RuntimeError(f"Error procesando '{os.path.basename(file)}': {exc}") from exc


def ordenar_y_agrupado_por_dia(
    input_folder: str,
    num_workers: Optional[int] = None,
    column_order: Optional[List[str]] = None,
    decimal: str = ".",
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Lee todos los CSV de *input_folder*, los agrupa por día y los reescribe.

    Para cada día calendario detectado genera:
    - ``YY.M.D.csv`` — datos del día ordenados cronológicamente.
    - ``YY.M.D_temp.csv`` — copia cuando el día está incompleto (última muestra
      antes de las 23:59:59).

    Los CSV originales son eliminados al finalizar.

    Args:
        input_folder: Carpeta con los CSV generados por :mod:`tdms_reader`.
        num_workers: Hilos para lectura paralela.  Default: ``min(8, cpu_count())``.
        column_order: Lista de columnas en el orden deseado.  Default:
            :data:`DEFAULT_COLUMN_ORDER`.
        decimal: Separador decimal de los CSV (``"."`` por defecto).
        log_callback: Función de logging.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    csv_files = glob.glob(os.path.join(input_folder, "*.csv"))
    if not csv_files:
        log("[CSV] No se encontraron archivos CSV en la carpeta especificada.")
        return

    col_order = column_order or DEFAULT_COLUMN_ORDER

    # Estado LOCAL por invocación — no hay global state.
    datos_por_dia: Dict = defaultdict(list)
    datos_lock = threading.Lock()

    workers = num_workers or _default_workers()
    log(f"[CSV] Leyendo {len(csv_files)} CSV con {workers} hilos...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(
                _procesar_csv_individual,
                f,
                datos_por_dia,
                datos_lock,
                decimal,
            ): f
            for f in csv_files
        }
        for fut in futuros:
            try:
                fut.result()
            except Exception as exc:
                log(f"[CSV] ADVERTENCIA: {exc}")

    if not datos_por_dia:
        log("[CSV] No se pudo extraer ningún dato de los CSV.")
        return

    log(f"[CSV] Agrupando en {len(datos_por_dia)} día(s)...")

    for date, groups in datos_por_dia.items():
        daily_data = pd.concat(groups, ignore_index=True)
        daily_data.sort_values(by="Time", inplace=True)
        daily_data.drop(columns=["Date"], inplace=True)

        # Reordenar columnas
        current_cols = list(daily_data.columns)
        if current_cols != col_order:
            missing = [c for c in col_order if c not in current_cols]
            if missing:
                log(f"[CSV] ADVERTENCIA: columnas faltantes en {date}: {missing}")
            ordered = [c for c in col_order if c in current_cols]
            remaining = [c for c in current_cols if c not in ordered]
            daily_data = daily_data[ordered + remaining]

        date_str = f"{str(date.year)[-2:]}.{date.month}.{date.day}"
        output_file = os.path.join(input_folder, f"{date_str}.csv")
        daily_data.to_csv(output_file, sep=";", decimal=decimal, index=False)

        # Crear/eliminar _temp.csv según completitud del día.
        # Un día se considera completo si la última muestra cae después de las
        # 23:59:30, tolerando frecuencias de muestreo de hasta 1/30 Hz.
        last_time = daily_data["Time"].max()
        temp_file = os.path.join(input_folder, f"{date_str}_temp.csv")
        day_end_threshold = pd.Timestamp(date) + pd.Timedelta(hours=23, minutes=59, seconds=30)
        if pd.notnull(last_time) and last_time >= day_end_threshold:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        else:
            shutil.copy(output_file, temp_file)

    _eliminar_archivos_csv(csv_files, log)
    log("[CSV] Agrupación por día completada.")


def _eliminar_archivos_csv(
    csv_files: List[str],
    log: Callable[[str], None],
) -> None:
    """Elimina los CSV originales (no los _temp.csv generados)."""
    for f in csv_files:
        if os.path.exists(f) and "_temp.csv" not in f:
            try:
                os.remove(f)
            except OSError as exc:
                log(f"[CSV] No se pudo eliminar '{f}': {exc}")
