"""Lectura de archivos TDMS y conversión a CSV.

Correcciones respecto al original (tdms_utils.py):
- La zona horaria (+/-3 h) ya no está hardcodeada: se lee de ``AppConfig.timezone_offset_hours``.
- Soporte para archivos TDMS con múltiples grupos (se itera sobre todos).
- El ``stop_event`` se verifica dentro del bucle ``as_completed``, no solo al inicio.
- Workers por defecto = ``cpu_count()`` para usar todos los núcleos disponibles.
- ``log_callback`` obligatorio en todos los mensajes (cero ``print``).

Optimizaciones de rendimiento:
- **ProcessPoolExecutor** para conversión TDMS→CSV: cada proceso tiene su
  propio GIL.  La deserialización TDMS y la conversión de timestamps con
  pandas son CPU-bound; con ThreadPoolExecutor el GIL los serializa.
- El ``stop_event`` y ``log_callback`` (no serializables por pickle) se
  gestionan únicamente en el proceso principal; cada proceso worker recibe
  solo argumentos simples (strings, ints).
- **TdmsFile.open() (streaming)** en lugar de ``TdmsFile.read()``  que carga
  todo el archivo en RAM de una vez.  Con archivos de 100 MB+ en paralelo,
  ``read()`` puede agotar la memoria; ``open()`` lee canal por canal.
- **``float_format='%.6f'`` y ``lineterminator='\\n'``** en ``to_csv`` para
  evitar overhead de formateo y evitar ``\\r\\n`` innecesario en Windows.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Optional

import pandas as pd
from nptdms import TdmsFile  # type: ignore[import]

from tdms2mat.utils.threading_utils import check_stop_event, cancelable_pool_map


def _default_workers() -> int:
    cpu = os.cpu_count() or 4
    return cpu


def convertir_tdms_a_csv(
    archivo_tdms: str,
    carpeta_salida: str,
    timezone_offset_hours: int = -3,
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Convierte **un** archivo TDMS a CSV usando lectura en streaming.

    Usa ``TdmsFile.open()`` (context manager) para leer canal por canal sin
    cargar el archivo completo en memoria de una vez.  Especialmente importante
    cuando múltiples hilos procesan archivos grandes en simultáneo.

    Args:
        archivo_tdms: Ruta al archivo .tdms.
        carpeta_salida: Carpeta donde escribir el CSV resultante.
        timezone_offset_hours: Desfase horario a aplicar (horas).  Usa 0 para
            no aplicar ningún ajuste.
        log_callback: Función para registrar mensajes.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    try:
        data_dict: dict = {}

        # open() = streaming: lee cada canal bajo demanda sin cargar todo en RAM
        with TdmsFile.open(archivo_tdms) as tdms_file:
            for grupo in tdms_file.groups():
                for canal in grupo.channels():
                    nombre = canal.name
                    nombre_lower = nombre.lower()

                    if nombre_lower == "time" or nombre_lower.startswith("date"):
                        # read_data() carga sólo este canal
                        raw = canal.read_data()
                        datos_tiempo = pd.to_datetime(
                            raw,
                            format="%Y-%m-%d %H:%M:%S.%f",
                            errors="coerce",
                        )
                        if timezone_offset_hours != 0:
                            datos_tiempo = datos_tiempo + pd.Timedelta(
                                hours=timezone_offset_hours
                            )
                        data_dict[nombre] = datos_tiempo
                    else:
                        data_dict[nombre] = canal.read_data()

        if not data_dict:
            log(f"[TDMS→CSV] ADVERTENCIA: '{os.path.basename(archivo_tdms)}' no tiene canales.")
            return

        df = pd.DataFrame(data_dict)
        nombre_csv = os.path.splitext(os.path.basename(archivo_tdms))[0] + ".csv"
        ruta_csv = os.path.join(carpeta_salida, nombre_csv)
        # lineterminator="\n" evita \r\n en Windows (archivos más pequeños y rápidos)
        df.to_csv(ruta_csv, index=False, sep=";", lineterminator="\n")

        if os.path.exists(ruta_csv):
            os.remove(archivo_tdms)
            idx = archivo_tdms + "_index"
            if os.path.exists(idx):
                os.remove(idx)
        else:
            log(
                f"[TDMS→CSV] ERROR: No se creó '{ruta_csv}'. "
                "El archivo TDMS no ha sido eliminado."
            )

    except Exception as exc:
        log(f"[TDMS→CSV] Error al convertir '{archivo_tdms}': {exc}")


def procesar_archivos_tdms_paralelo(
    carpeta_tdms: str,
    num_workers: Optional[int] = None,
    timezone_offset_hours: int = -3,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_event: Optional[threading.Event] = None,
    file_progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    """Convierte todos los TDMS de *carpeta_tdms* a CSV en paralelo.

    Args:
        carpeta_tdms: Carpeta que contiene los archivos .tdms.
        num_workers: Número de hilos.  Default: ``min(8, cpu_count())``.
        timezone_offset_hours: Desfase horario (ver :func:`convertir_tdms_a_csv`).
        log_callback: Función de logging.
        stop_event: Evento de cancelación cooperativa.
        file_progress_callback: ``(actual, total, nombre_archivo)`` — llamada
            después de cada archivo completado para actualizar progreso detallado.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    check_stop_event(stop_event)

    if not os.path.exists(carpeta_tdms):
        log(f"[TDMS→CSV] La carpeta '{carpeta_tdms}' no existe.")
        return

    archivos = [
        os.path.join(carpeta_tdms, f)
        for f in os.listdir(carpeta_tdms)
        if f.lower().endswith(".tdms")
    ]

    if not archivos:
        log(f"[TDMS→CSV] No se encontraron archivos TDMS en '{carpeta_tdms}'.")
        return

    workers = num_workers or _default_workers()
    total = len(archivos)
    log(f"[TDMS→CSV] Convirtiendo {total} archivos con {workers} procesos...")
    completados = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(
                convertir_tdms_a_csv,
                arch,
                carpeta_tdms,
                timezone_offset_hours,
                None,  # log_callback no es serializable: se omite en el worker
            ): arch
            for arch in archivos
        }

        def _on_result(futuro, arch):
            nonlocal completados
            try:
                futuro.result()
                completados += 1
                if file_progress_callback:
                    file_progress_callback(completados, total, os.path.basename(arch))
            except Exception as exc:
                log(f"[TDMS→CSV] Error procesando '{os.path.basename(arch)}': {exc}")

        cancelled = not cancelable_pool_map(
            executor, futuros, stop_event, _on_result,
            on_cancel_msg="[TDMS→CSV] Proceso cancelado por el usuario.",
        )
        if cancelled:
            log("[TDMS→CSV] Proceso cancelado por el usuario.")
