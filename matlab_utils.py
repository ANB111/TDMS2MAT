import os
import subprocess
import logging
import platform
from pathlib import Path
from typing import Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tdms2mat.matlab_runner")

class MatlabExecutionError(Exception):
    """Excepción personalizada para errores de ejecución de MATLAB."""


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
    """
    Construye un comando MATLAB via '-batch'.  
    - Añade script_path al MATLAB path.  
    - Llama a otra función (procesar_matlab) y sale con 0/1 según éxito.
    """
    # Rutas POSIX para MATLAB
    script_dir = Path(script_path).as_posix()
    mat_file_posix = Path(mat_file).as_posix()
    excel_posix   = Path(excel_folder).as_posix()

    # Opciones de inicio comunes
    opts = ["-nosplash"]
    # Windows no reconoce -nodisplay, Linux sí
    if platform.system() != "Windows":
        opts.append("-nodisplay")
    opts.append("-nodesktop")

    # Comando batch: addpath y luego try/catch
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


def run_matlab_script(name: str, config: Dict[str, Any], show_output: bool = False) -> None:
    """
    Ejecuta la función MATLAB 'procesar_matlab' para un archivo .mat concreto.
    """
    # Obtener parámetros de config
    matlab_path        = config.get("matlab_path")
    script_path = obtener_script_path(config, logger)
    fs                 = config.get("FS", 10)
    escritura          = config.get("escritura", True)
    mat_folder         = config.get("output_folder", "")
    excel_folder       = config.get("excel_output_folder", "")
    graficos_matlab    = config.get("graficos_matlab", False)
    n_channels         = config.get("n_channels", 16)

    # Asegurar folder de Excel
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

    logger.info(f"[MATLAB] Ejecutando '{name}'")
    logger.debug("Comando: " + " ".join(cmd))

    # Ejecutar y capturar el output
    if show_output:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            logger.info(line.rstrip())
        code = proc.wait()
    else:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        code = result.returncode
        if result.stdout:
            logger.debug(result.stdout)
        if result.stderr:
            logger.error(result.stderr)

    if code != 0:
        raise MatlabExecutionError(f"MATLAB terminó con código {code}")


def process_mat_files(output_folder: str, config: Dict[str, Any]) -> None:
    """
    Procesa en serie todos los .mat de la carpeta con MATLAB.
    Cada archivo .mat será procesado individualmente y el resultado (Excel)
    se guardará en la carpeta indicada en 'excel_output_folder'.
    """
    if not os.path.isdir(output_folder):
        raise FileNotFoundError(f"Carpeta de salida no existe: {output_folder}")

    files = [f for f in os.listdir(output_folder) if f.lower().endswith(".mat")]
    if not files:
        logger.warning(f"No se encontraron archivos .mat en {output_folder}")
        return

    logger.info(f"Procesando {len(files)} archivos MAT con MATLAB...")
    failed = []
    show_output = config.get("mostrar_salida_matlab", False)

    for mat_file in files:
        name = Path(mat_file).stem
        expected_excel = Path(config["excel_output_folder"]) / f"{name}.xlsx"

        if expected_excel.exists():
            logger.info(f"[MATLAB] Saltando '{name}': Excel ya existe.")
            continue

        logger.info(f"[MATLAB] Procesando '{name}'...")
        try:
            run_matlab_script(name, config, show_output)
        except Exception as e:
            logger.error(f"Error en '{name}': {e}")
            failed.append(name)


    if failed:
        logger.warning(f"{len(failed)} archivo(s) fallaron al procesar: {failed}")
    else:
        logger.info("Todos los archivos .mat fueron procesados correctamente.")

def obtener_script_path(config: Dict[str, Any], logger: logging.Logger) -> str:
    """
    Verifica si existe procesar_matlab.m en la ruta proporcionada.
    Si no existe, busca en una ruta por defecto. Si aún no está, lanza error.
    """
    # Nombre del script MATLAB esperado
    matlab_script_name = "procesar_matlab.m"

    # Ruta desde config
    config_path = config.get("ruta_matlab_script")
    if config_path:
        config_path = os.path.abspath(config_path)
        script_en_config = os.path.join(config_path, matlab_script_name)
        if os.path.isdir(config_path) and os.path.isfile(script_en_config):
            logger.info(f"Usando script MATLAB desde: {config_path}")
            return config_path
        else:
            logger.warning(f"No se encontró '{matlab_script_name}' en ruta proporcionada: {config_path}")

    # Ruta por defecto: mismo directorio que este script .py
    default_path = os.path.abspath(os.path.dirname(__file__))
    script_en_default = os.path.join(default_path, matlab_script_name)

    if os.path.isfile(script_en_default):
        logger.info(f"Usando script MATLAB desde ruta por defecto: {default_path}")
        return default_path

    # Si no se encuentra en ninguna ruta
    logger.error(f"ERROR: No se encontró '{matlab_script_name}' ni en la ruta proporcionada ni en la ruta por defecto.")
    raise FileNotFoundError(f"No se encuentra '{matlab_script_name}' para ejecutar MATLAB.")
