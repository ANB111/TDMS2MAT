"""Descompresión de archivos ZIP usando 7-Zip.

Correcciones respecto al original (decompress_utils.py):
- ``ProcessingError`` importada desde el módulo centralizado (no duplicada).
- ``log_callback`` usado en todos los mensajes (no ``print``).
- La limpieza de directorios vacíos corre una sola vez al terminar, no por cada ZIP.
- La función devuelve una lista de nombres de archivos fallidos para que el
  orquestador tenga visibilidad de los errores parciales.

Optimizaciones de rendimiento:
- **Extracción paralela**: cada ZIP se extrae a su propio subdirectorio temporal
  dentro de *output_folder*, luego se aplana todo de una vez.  Esto permite
  extraer múltiples ZIPs simultáneamente sin conflictos de nombre.
- Workers = min(4, cpu_count()) — limitado para no saturar disco en HDD.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

from tdms2mat.utils.exceptions import ProcessingError
from tdms2mat.utils.threading_utils import check_stop_event


def _extract_one(
    zip_path: str,
    zip_file: str,
    extract_dir: str,
) -> Tuple[str, int, str]:
    """Extrae un único ZIP a *extract_dir* (exclusivo para este ZIP).

    Returns:
        ``(zip_file, returncode, stderr)``
    """
    os.makedirs(extract_dir, exist_ok=True)
    result = subprocess.run(
        ["7z", "x", zip_path, f"-o{extract_dir}", "-y"],
        check=False,
        capture_output=True,
        text=True,
    )
    return zip_file, result.returncode, result.stderr.strip()


def decompress_zip_files(
    input_folder: str,
    output_folder: str,
    selected_files: List[str],
    stop_event: Optional[threading.Event] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Descomprime archivos ZIP seleccionados en *output_folder* en paralelo.

    Cada ZIP se extrae a un subdirectorio temporal ``<output_folder>/<stem>_xtmp/``
    para evitar conflictos de nombre entre ZIPs simultáneos.  Al finalizar
    todos los hilos, los archivos se aplanan a *output_folder*.

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

    # Verificar cancelación antes de comenzar
    check_stop_event(stop_event)

    # Filtrar archivos existentes
    valid_files: List[str] = []
    for zip_file in selected_files:
        zip_path = os.path.join(input_folder, zip_file)
        if not os.path.exists(zip_path):
            log(f"[Descompresión] ADVERTENCIA: Archivo no encontrado: {zip_path}")
            failed.append(zip_file)
        else:
            valid_files.append(zip_file)

    if not valid_files:
        return failed

    # Directorio temporal exclusivo por ZIP (evita conflictos de nombre en extracción paralela)
    extract_dirs: Dict[str, str] = {}
    for zip_file in valid_files:
        stem = os.path.splitext(zip_file)[0]
        extract_dirs[zip_file] = os.path.join(output_folder, f"{stem}_xtmp")

    cpu = os.cpu_count() or 2
    workers = min(4, cpu, len(valid_files))
    log(f"[Descompresión] Extrayendo {len(valid_files)} ZIP(s) con {workers} hilos paralelos...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(
                _extract_one,
                os.path.join(input_folder, zf),
                zf,
                extract_dirs[zf],
            ): zf
            for zf in valid_files
        }

        for fut in as_completed(futuros):
            # Verificar cancelación
            if stop_event and stop_event.is_set():
                log("[Descompresión] Proceso cancelado por el usuario.")
                # Limpiar dirs temporales ya creados
                for d in extract_dirs.values():
                    if os.path.exists(d):
                        shutil.rmtree(d, ignore_errors=True)
                raise ProcessingError("Cancelado por el usuario.")

            try:
                zip_file, rc, stderr = fut.result()
            except Exception as exc:
                zip_file = futuros[fut]
                log(f"[Descompresión] ERROR inesperado en '{zip_file}': {exc}")
                failed.append(zip_file)
                continue

            if rc != 0:
                log(f"[Descompresión] ERROR en '{zip_file}' (código {rc}): {stderr}")
                failed.append(zip_file)
                # Limpiar su directorio temporal
                d = extract_dirs[zip_file]
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)
            else:
                log(f"[Descompresión] Completado: {zip_file}")

    # Aplanar todos los directorios temporales → output_folder
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
