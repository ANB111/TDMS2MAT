"""Lectura de archivos TDMS y conversión a CSV.

Correcciones respecto al original (tdms_utils.py):
- La zona horaria (+/-3 h) ya no está hardcodeada: se lee de ``AppConfig.timezone_offset_hours``.
- Soporte para archivos TDMS con múltiples grupos (se itera sobre todos).
- El ``stop_event`` se verifica dentro del bucle ``as_completed``, no solo al inicio.
- Workers por defecto = ``min(8, cpu_count())`` en lugar de 14 fijo.
- ``log_callback`` obligatorio en todos los mensajes (cero ``print``).
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import pandas as pd
from nptdms import TdmsFile  # type: ignore[import]

from tdms2mat.utils.threading_utils import check_stop_event


def _default_workers() -> int:
    cpu = os.cpu_count() or 4
    return min(8, cpu)


def convertir_tdms_a_csv(
    archivo_tdms: str,
    carpeta_salida: str,
    timezone_offset_hours: int = -3,
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Convierte **un** archivo TDMS a CSV.

    Itera sobre **todos** los grupos del TDMS (no solo el primero).
    Cuando un canal se llama "time" o empieza con "date" aplica la corrección
    de zona horaria indicada.

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
        tdms_file = TdmsFile.read(archivo_tdms)
        data_dict: dict = {}

        for grupo in tdms_file.groups():
            for canal in grupo.channels():
                nombre = canal.name
                nombre_lower = nombre.lower()

                if nombre_lower == "time" or nombre_lower.startswith("date"):
                    datos_tiempo = pd.to_datetime(
                        canal.data,
                        format="%Y-%m-%d %H:%M:%S.%f",
                        errors="coerce",
                    )
                    if timezone_offset_hours != 0:
                        datos_tiempo = datos_tiempo + pd.Timedelta(
                            hours=timezone_offset_hours
                        )
                    data_dict[nombre] = datos_tiempo
                else:
                    data_dict[nombre] = canal.data

        if not data_dict:
            log(f"[TDMS→CSV] ADVERTENCIA: '{os.path.basename(archivo_tdms)}' no tiene canales.")
            return

        df = pd.DataFrame(data_dict)
        nombre_csv = os.path.splitext(os.path.basename(archivo_tdms))[0] + ".csv"
        ruta_csv = os.path.join(carpeta_salida, nombre_csv)
        df.to_csv(ruta_csv, index=False, sep=";")

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
) -> None:
    """Convierte todos los TDMS de *carpeta_tdms* a CSV en paralelo.

    Args:
        carpeta_tdms: Carpeta que contiene los archivos .tdms.
        num_workers: Número de hilos.  Default: ``min(8, cpu_count())``.
        timezone_offset_hours: Desfase horario (ver :func:`convertir_tdms_a_csv`).
        log_callback: Función de logging.
        stop_event: Evento de cancelación cooperativa.
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
    log(f"[TDMS→CSV] Convirtiendo {len(archivos)} archivos con {workers} hilos...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(
                convertir_tdms_a_csv,
                arch,
                carpeta_tdms,
                timezone_offset_hours,
                log_callback,
            ): arch
            for arch in archivos
        }

        for futuro in as_completed(futuros):
            # Verificar cancelación dentro del bucle
            if stop_event and stop_event.is_set():
                log("[TDMS→CSV] Proceso cancelado por el usuario.")
                break

            arch = futuros[futuro]
            try:
                futuro.result()
            except Exception as exc:
                log(f"[TDMS→CSV] Error procesando '{os.path.basename(arch)}': {exc}")
