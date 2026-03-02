"""Descompresión de archivos ZIP usando 7-Zip.

Correcciones respecto al original (decompress_utils.py):
- ``ProcessingError`` importada desde el módulo centralizado (no duplicada).
- ``log_callback`` usado en todos los mensajes (no ``print``).
- La limpieza de directorios vacíos corre una sola vez al terminar, no por cada ZIP.
- La función devuelve una lista de nombres de archivos fallidos para que el
  orquestador tenga visibilidad de los errores parciales.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from typing import Callable, List, Optional

from tdms2mat.utils.exceptions import ProcessingError
from tdms2mat.utils.threading_utils import check_stop_event


def decompress_zip_files(
    input_folder: str,
    output_folder: str,
    selected_files: List[str],
    stop_event: Optional[threading.Event] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Descomprime archivos ZIP seleccionados en *output_folder*.

    Aplana cualquier subdirectorio creado por 7z y renombra conflictos
    automáticamente.

    Args:
        input_folder: Carpeta con los archivos .zip de origen.
        output_folder: Carpeta destino (aplanada).
        selected_files: Nombres de archivo (solo el basename, sin ruta).
        stop_event: Evento de cancelación cooperativa.
        log_callback: Función para registrar mensajes en la GUI / CLI.

    Returns:
        Lista de nombres de archivos que fallaron (vacía si todo fue bien).

    Raises:
        :class:`EnvironmentError`: Si ``7z`` no está instalado o en el PATH.
        :class:`ProcessingError`: Si el usuario canceló el proceso.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    if shutil.which("7z") is None:
        raise EnvironmentError(
            "El programa '7z' no está instalado o no está en el PATH. "
            "Instálelo desde https://www.7-zip.org/"
        )

    os.makedirs(output_folder, exist_ok=True)
    failed: List[str] = []

    for zip_file in selected_files:
        check_stop_event(stop_event)

        zip_path = os.path.join(input_folder, zip_file)
        log(f"[Descompresión] Procesando: {zip_file}")

        if not os.path.exists(zip_path):
            log(f"[Descompresión] ADVERTENCIA: Archivo no encontrado: {zip_path}")
            failed.append(zip_file)
            continue

        try:
            result = subprocess.run(
                ["7z", "x", zip_path, f"-o{output_folder}", "-y"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log(
                    f"[Descompresión] ERROR en '{zip_file}' (código {result.returncode}): "
                    f"{result.stderr.strip()}"
                )
                failed.append(zip_file)
                continue

            log(f"[Descompresión] Completado: {zip_file}")

        except Exception as exc:  # pragma: no cover
            log(f"[Descompresión] ERROR inesperado en '{zip_file}': {exc}")
            failed.append(zip_file)

    # Aplanar subdirectorios creados por 7z — una pasada al terminar todos los ZIPs
    # (O(archivos) en vez de O(archivos × ZIPs))
    _flatten_output_folder(output_folder, log)

    _remove_empty_dirs(output_folder, log)

    if failed:
        log(
            f"[Descompresión] {len(failed)} archivo(s) fallaron: "
            + ", ".join(failed)
        )

    return failed


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _flatten_output_folder(
    base: str, log: Callable[[str], None]
) -> None:
    """Mueve todos los archivos de subdirectorios a *base* (un nivel plano).

    Resuelve conflictos de nombre añadiendo un sufijo ``_N``.
    Se llama una sola vez al finalizar la extracción de todos los ZIPs.
    """
    for root, _, files in os.walk(base, topdown=False):
        if root == base:
            continue
        for file in files:
            src = os.path.join(root, file)
            dst = os.path.join(base, file)
            if os.path.exists(dst):
                stem, ext = os.path.splitext(file)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(base, f"{stem}_{counter}{ext}")
                    counter += 1
            shutil.move(src, dst)


def _remove_empty_dirs(
    base: str, log: Callable[[str], None]
) -> None:
    """Elimina recursivamente directorios vacíos bajo *base*."""
    for root, dirs, files in os.walk(base, topdown=False):
        if root == base:
            continue  # No eliminar la carpeta raíz
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass
