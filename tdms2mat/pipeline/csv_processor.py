"""Ordenamiento y agrupación de archivos CSV por día calendario.

Correcciones críticas respecto al original (csv_utils.py):
- **Bug crítico corregido**: ``datos_por_dia`` y ``datos_lock`` son ahora
  variables **locales** a ``ordenar_y_agrupado_por_dia()``, no globales.
  En la versión original, llamar a esta función dos veces en el mismo proceso
  provocaba que los datos del primer run se mezclaran con los del segundo.
- ``COLUMN_ORDER`` se puede pasar como parámetro (``column_order``), con la
  lista hardcodeada como valor por defecto retrocompatible.
- Workers por defecto = ``min(8, cpu_count())`` en lugar de 14 fijo.

Optimizaciones de rendimiento:
- **Sin lock contention**: cada hilo acumula en su propio dict local; la
  fusión ocurre en el hilo principal tras completar todos los futuros.
  Elimina la contención extrema de la versión anterior donde el lock se
  adquiría en cada chunk por cada fecha.
- **Chunk size 50 k** → reduce el número de iteraciones y overhead de groupby.
- **parse_dates diferido**: pd.read_csv lee Time como string y se convierte
  con pd.to_datetime sólo una vez por chunk (más rápido que parse_dates=).
- **sort=False en groupby**: evita un sort innecesario (ya se ordena al final).
- **Operaciones in-place**: evitan copias de DataFrame intermedias.
"""
from __future__ import annotations

import glob
import os
import shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    decimal: str,
) -> Dict:
    """Lee un CSV en chunks y retorna datos agrupados por día — sin locks.

    Cada hilo acumula en su propio dict local.  La fusión con el dict global
    ocurre en el hilo principal tras completar todos los futuros, eliminando
    completamente la contención de locks.

    Mejoras respecto a la versión anterior:
    - Sin threading.Lock → cero contención entre hilos.
    - Chunk size 50 k → menos iteraciones y overhead de groupby.
    - parse_dates diferido: pd.read_csv lee Time como str, se convierte una
      sola vez por chunk con pd.to_datetime (más rápido que parse_dates=).
    - sort=False en groupby → evita sort redundante (se ordena al final).
    """
    local: Dict = defaultdict(list)
    try:
        for chunk in pd.read_csv(
            file,
            delimiter=";",
            decimal=decimal,
            chunksize=50_000,
        ):
            # Parsear fechas una vez por chunk (más rápido que parse_dates=)
            chunk["Time"] = pd.to_datetime(chunk["Time"], errors="coerce")
            chunk.dropna(subset=["Time"], inplace=True)
            if chunk.empty:
                continue
            chunk["Date"] = chunk["Time"].dt.date
            for date, group in chunk.groupby("Date", sort=False):
                local[date].append(group)
    except Exception as exc:
        raise RuntimeError(f"Error procesando '{os.path.basename(file)}': {exc}") from exc
    return local


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
    # Sin lock: cada hilo acumula en su propio dict, se fusiona aquí al final.
    datos_por_dia: Dict = defaultdict(list)

    workers = num_workers or _default_workers()
    log(f"[CSV] Leyendo {len(csv_files)} CSV con {workers} hilos...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(
                _procesar_csv_individual,
                f,
                decimal,
            ): f
            for f in csv_files
        }
        for fut in as_completed(futuros):
            try:
                local = fut.result()
                # Fusión en el hilo principal — sin contención
                for date, groups in local.items():
                    datos_por_dia[date].extend(groups)
            except Exception as exc:
                log(f"[CSV] ADVERTENCIA: {exc}")

    if not datos_por_dia:
        log("[CSV] No se pudo extraer ningún dato de los CSV.")
        return

    log(f"[CSV] Agrupando en {len(datos_por_dia)} día(s)...")

    total_dias = len(datos_por_dia)
    dias_procesados = 0
    for date, groups in datos_por_dia.items():
        # Concatenar de una vez — más rápido que concat progresivo
        daily_data = pd.concat(groups, ignore_index=True, copy=False)
        # Ordenar una sola vez al final (mergesort = estable, rápido sobre nearly-sorted)
        daily_data.sort_values(by="Time", inplace=True, kind="mergesort", ignore_index=True)
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
        daily_data.to_csv(output_file, sep=";", decimal=decimal, index=False, lineterminator="\n")

        # Progreso por día
        dias_procesados += 1
        if file_progress_callback:
            file_progress_callback(dias_procesados, total_dias, date_str)

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
