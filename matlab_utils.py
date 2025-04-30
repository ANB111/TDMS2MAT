import os
import subprocess
import logging
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tdms2mat.matlab_runner")

class MatlabExecutionError(Exception):
    """Excepción personalizada para errores de ejecución de MATLAB."""


def log(msg: str, level: str = "info", log_callback: Optional[Callable] = None):
    if log_callback:
        prefix = f"[{level.upper()}] "
        log_callback(prefix + msg)
    else:
        getattr(logger, level)(msg)


def construir_comando_matlab(
    matlab_path: str,
    script_path: str,
    mat_file: str,
    excel_folder: str,
    graficos: bool,
    escritura: bool,
    fs: int,
    n_channels: int,
) -> list:
    script_dir = Path(script_path).as_posix()
    mat_file_posix = Path(mat_file).as_posix()
    excel_posix = Path(excel_folder).as_posix()

    opts = ["-nosplash"]
    if platform.system() != "Windows":
        opts.append("-nodisplay")
    opts.append("-nodesktop")

    batch_cmd = (
        f"addpath('{script_dir}');"
        f"try, "
            f"procesar_matlab('{mat_file_posix}',"
                             f"'{excel_posix}',"
                             f"{str(graficos).lower()},"
                             f"{str(escritura).lower()},"
                             f"{fs},"
                             f"{n_channels});"
        f"catch e, "
            f"disp(getReport(e,'extended')); "
            f"exit(1);"
        f"end; "
        f"exit(0);"
    )

    return [matlab_path] + opts + ["-batch", batch_cmd]


def run_matlab_script(name: str, config: Dict[str, Any], show_output: bool = False, log_callback: Optional[Callable] = None) -> None:
    matlab_path = config.get("matlab_path")
    script_path = obtener_script_path(config, log_callback)
    fs = config.get("FS", 10)
    escritura = config.get("escritura", True)
    mat_folder = config.get("output_folder", "")
    excel_folder = config.get("excel_output_folder", "")
    graficos_matlab = config.get("graficos_matlab", False)
    n_channels = config.get("n_channels", 16)

    Path(excel_folder).mkdir(parents=True, exist_ok=True)

    mat_file = Path(mat_folder) / f"{name}.mat"
    if not mat_file.exists():
        raise FileNotFoundError(f"MATLAB .mat no encontrado: {mat_file}")

    cmd = construir_comando_matlab(
        matlab_path=matlab_path,
        script_path=script_path,
        mat_file=str(mat_file),
        excel_folder=excel_folder,
        graficos=graficos_matlab,
        escritura=escritura,
        fs=fs,
        n_channels=n_channels,
    )

    log(f"[MATLAB] Ejecutando '{name}'", "info", log_callback)

    if show_output:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            log(line.rstrip(), "info", log_callback)
        code = proc.wait()
    else:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        code = result.returncode
        if result.stdout:
            log(result.stdout.strip(), "debug", log_callback)
        if result.stderr:
            log(result.stderr.strip(), "error", log_callback)

    if code != 0:
        raise MatlabExecutionError(f"MATLAB terminó con código {code}")


def process_mat_files(output_folder: str, config: Dict[str, Any], log_callback: Optional[Callable] = None) -> None:
    if not os.path.isdir(output_folder):
        raise FileNotFoundError(f"Carpeta de salida no existe: {output_folder}")

    files = [f for f in os.listdir(output_folder) if f.lower().endswith(".mat")]
    if not files:
        log(f"No se encontraron archivos .mat en {output_folder}", "warning", log_callback)
        return

    log(f"Procesando {len(files)} archivos MAT con MATLAB...", "info", log_callback)
    failed = []
    show_output = config.get("mostrar_salida_matlab", False)

    for mat_file in files:
        name = Path(mat_file).stem
        expected_excel = Path(config["excel_output_folder"]) / f"{name}.xlsx"

        if expected_excel.exists():
            log(f"[MATLAB] Saltando '{name}': Excel ya existe.", "info", log_callback)
            continue

        log(f"[MATLAB] Procesando '{name}'...", "info", log_callback)
        try:
            run_matlab_script(name, config, show_output, log_callback)
        except Exception as e:
            log(f"Error en '{name}': {e}", "error", log_callback)
            failed.append(name)

    if failed:
        log(f"{len(failed)} archivo(s) fallaron al procesar: {failed}", "warning", log_callback)
    else:
        log("Todos los archivos .mat fueron procesados correctamente.", "info", log_callback)


def obtener_script_path(config: Dict[str, Any], log_callback: Optional[Callable] = None) -> str:
    matlab_script_name = "procesar_matlab.m"
    config_path = config.get("ruta_matlab_script")

    if config_path:
        config_path = os.path.abspath(config_path)
        script_en_config = os.path.join(config_path, matlab_script_name)
        if os.path.isdir(config_path) and os.path.isfile(script_en_config):
            log(f"Usando script MATLAB desde: {config_path}", "info", log_callback)
            return config_path
        else:
            log(f"No se encontró '{matlab_script_name}' en ruta proporcionada: {config_path}", "warning", log_callback)

    default_path = os.path.abspath(os.path.dirname(__file__))
    script_en_default = os.path.join(default_path, matlab_script_name)

    if os.path.isfile(script_en_default):
        log(f"Usando script MATLAB desde ruta por defecto: {default_path}", "info", log_callback)
        return default_path

    log(f"ERROR: No se encontró '{matlab_script_name}' ni en la ruta proporcionada ni en la ruta por defecto.", "error", log_callback)
    raise FileNotFoundError(f"No se encuentra '{matlab_script_name}' para ejecutar MATLAB.")
