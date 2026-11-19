"""Ejecución de MATLAB para el análisis de rainflow (procesar_matlab.m).

Correcciones respecto al original (matlab_utils.py):
- ``logging.basicConfig`` eliminado de la importación del módulo; el logging
  se configura una sola vez en ``tdms2mat.utils.logging_utils``.
- Las comillas simples en rutas se escapan antes de construir la cadena
  ``-batch`` para evitar roturas silenciosas en MATLAB.
- Se agrega lógica de **skip**: si el .xlsx ya existe para un .mat, no relanza
  MATLAB (procesamiento idempotente).
- La variable ``expected_excel`` (dead code) ha sido eliminada.
- ``resource_path`` consolidado aquí para uso con PyInstaller.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tdms2mat.utils.logging_utils import get_logger

logger = get_logger("matlab_runner")


# ---------------------------------------------------------------------------
# Helpers de rutas
# ---------------------------------------------------------------------------


def resource_path(relative_path: str) -> str:
    """Resuelve una ruta relativa compatible con PyInstaller (``_MEIPASS``)."""
    base: str
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def _escape_matlab_str(s: str) -> str:
    """Escapa comillas simples en una cadena para uso en un comando MATLAB.

    MATLAB usa ``''`` para representar una comilla simple literal dentro de
    una cadena delimitada por comillas simples.
    """
    return s.replace("'", "''")


# ---------------------------------------------------------------------------
# Construcción del comando MATLAB
# ---------------------------------------------------------------------------


def construir_comando_matlab(
    matlab_path: str,
    script_path: str,
    mat_file: str,
    excel_folder: str,
    graficos: bool,
    escritura: bool,
    fs: int,
    n_channels: int,
    ruta_guardado_graficos: str,
) -> List[str]:
    """Construye la lista de argumentos para llamar a MATLAB con ``-batch``.

    Todas las rutas son convertidas a POSIX (``/``) para compatibilidad con la
    sintaxis MATLAB multi-plataforma, y las comillas simples son escapadas.
    """
    script_dir = _escape_matlab_str(Path(script_path).as_posix())
    mat_posix = _escape_matlab_str(Path(mat_file).as_posix())
    excel_posix = _escape_matlab_str(Path(excel_folder).as_posix())
    graficos_posix = _escape_matlab_str(Path(ruta_guardado_graficos).as_posix())

    opts = ["-nosplash"]
    if platform.system() != "Windows":
        opts.append("-nodisplay")
    opts.append("-nodesktop")

    batch_cmd = (
        f"addpath('{script_dir}');"
        f"try, "
        f"procesar_matlab('{mat_posix}',"
        f"'{excel_posix}',"
        f"{str(graficos).lower()},"
        f"{str(escritura).lower()},"
        f"{fs},"
        f"{n_channels},"
        f"'{graficos_posix}');"
        f"catch e, "
        f"disp(getReport(e,'extended')); "
        f"exit(1);"
        f"end; "
        f"exit(0);"
    )

    return [matlab_path] + opts + ["-batch", batch_cmd]


# ---------------------------------------------------------------------------
# Ejecución por archivo
# ---------------------------------------------------------------------------


class MatlabExecutionError(Exception):
    """MATLAB terminó con código de salida distinto de 0."""


def run_matlab_script(
    name: str,
    config: Dict[str, Any],
    show_output: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Ejecuta ``procesar_matlab.m`` para **un** archivo .mat.

    Args:
        name: Stem del archivo .mat (sin extensión ni carpeta).
        config: Configuración de la aplicación (dict o AppConfig serializado).
        show_output: Si ``True`` transmite stdout de MATLAB línea a línea al log.
        log_callback: Función de logging.
    """

    def log(msg: str, level: str = "info") -> None:
        if log_callback:
            log_callback(f"[MATLAB] {msg}")
        else:
            getattr(logger, level)(msg)

    matlab_path: str = config.get("matlab_path", "")
    if not matlab_path:
        raise MatlabExecutionError(
            "No se ha configurado la ruta a matlab.exe ('matlab_path')."
        )

    script_path = obtener_script_path(config, log_callback)
    mat_folder: str = config.get("output_folder", "")
    excel_folder: str = config.get("excel_output_folder", "")
    fs: int = int(config.get("FS", 10))
    n_channels: int = int(config.get("n_channels", 16))
    escritura: bool = bool(config.get("escritura", True))
    graficos: bool = bool(config.get("graficos_matlab", False))
    ruta_graficos: str = config.get("ruta_guardado_graficos", "") or ""

    Path(excel_folder).mkdir(parents=True, exist_ok=True)

    mat_file = Path(mat_folder) / f"{name}.mat"
    if not mat_file.exists():
        raise FileNotFoundError(f"Archivo .mat no encontrado: {mat_file}")

    cmd = construir_comando_matlab(
        matlab_path=matlab_path,
        script_path=script_path,
        mat_file=str(mat_file),
        excel_folder=excel_folder,
        graficos=graficos,
        escritura=escritura,
        fs=fs,
        n_channels=n_channels,
        ruta_guardado_graficos=ruta_graficos,
    )

    if show_output:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            log(line.rstrip())
        code = proc.wait()
    else:
        result = subprocess.run(
            cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        code = result.returncode
        if result.stdout:
            log(result.stdout.strip(), "debug")
        if result.stderr:
            log(result.stderr.strip(), "error")

    if code != 0:
        raise MatlabExecutionError(f"MATLAB terminó con código {code} para '{name}'")


# ---------------------------------------------------------------------------
# Procesamiento en lote
# ---------------------------------------------------------------------------


def process_mat_files(
    output_folder: str,
    config: Dict[str, Any],
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Ejecuta MATLAB sobre todos los .mat de *output_folder*.

    Archivos para los que ya existe un .xlsx en ``excel_output_folder`` son
    omitidos (idempotente).

    Args:
        output_folder: Carpeta con los .mat a procesar.
        config: Configuración de la aplicación.
        log_callback: Función de logging.
    """

    def log(msg: str, level: str = "info") -> None:
        if log_callback:
            log_callback(f"[MATLAB] {msg}")
        else:
            getattr(logger, level)(msg)

    if not os.path.isdir(output_folder):
        raise FileNotFoundError(f"Carpeta de salida no existe: {output_folder}")

    files = [f for f in os.listdir(output_folder) if f.lower().endswith(".mat")]
    if not files:
        log(f"No se encontraron archivos .mat en {output_folder}", "warning")
        return

    excel_folder: str = config.get("excel_output_folder", "")
    show_output: bool = bool(config.get("mostrar_salida_matlab", False))
    failed: List[str] = []

    for mat_file in files:
        name = Path(mat_file).stem

        # Skip si el excel ya existe (idempotente)
        if excel_folder:
            expected_xlsx = Path(excel_folder) / f"{name}.xlsx"
            if expected_xlsx.exists():
                log(f"Omitido (excel ya existe): {name}")
                continue

        try:
            run_matlab_script(name, config, show_output, log_callback)
            log(f"Procesado: {name}")
        except Exception as exc:
            log(f"Error en '{name}': {exc}", "error")
            failed.append(name)

    if failed:
        log(
            f"{len(failed)} archivo(s) fallaron: {failed}",
            "warning",
        )
    else:
        log("Todos los archivos .mat fueron procesados correctamente.")


# ---------------------------------------------------------------------------
# Localización del script MATLAB
# ---------------------------------------------------------------------------


def obtener_script_path(
    config: Dict[str, Any],
    log_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Resuelve la ruta del directorio que contiene ``procesar_matlab.m``.

    Estrategia (en orden de prioridad):
    1. ``config["ruta_matlab_script"]`` si apunta a un directorio con el .m.
    2. Directorio del bundle PyInstaller (``_MEIPASS``).
    3. Directorio de trabajo actual.

    Raises:
        :class:`FileNotFoundError`: Si no se encuentra ``procesar_matlab.m``.
    """

    def log(msg: str, level: str = "info") -> None:
        if log_callback:
            log_callback(f"[MATLAB] {msg}")
        else:
            getattr(logger, level)(msg)

    script_name = "procesar_matlab.m"
    config_path: str = config.get("ruta_matlab_script", "") or ""

    if config_path:
        config_path = os.path.abspath(config_path)
        if os.path.isdir(config_path) and os.path.isfile(
            os.path.join(config_path, script_name)
        ):
            return config_path
        log(
            f"No se encontró '{script_name}' en la ruta configurada: {config_path}",
            "warning",
        )

    for candidate in (resource_path("."), os.path.abspath(".")):
        if os.path.isfile(os.path.join(candidate, script_name)):
            log(f"Usando script desde: {candidate}")
            return candidate

    raise FileNotFoundError(
        f"No se encontró '{script_name}'. "
        "Configure 'ruta_matlab_script' o coloque el archivo junto al ejecutable."
    )
