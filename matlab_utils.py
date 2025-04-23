import os
import subprocess
from config_utils import load_config
from tqdm import tqdm

def run_matlab_script(name, config):
    """
    Ejecuta la función MATLAB 'procesar_matlab' con los parámetros desde el archivo de configuración.
    """
    matlab_path = config.get("matlab_path", r"C:\Program Files\Polyspace\R2021a\bin\matlab.exe")
    ruta_matlab_script = config.get("ruta_matlab_script", "")
    FS = config.get("FS", 10)
    escritura = config.get("escritura", True)
    mat_folder = config.get("output_folder", "")
    excel_folder = config.get("excel_output_folder", "")
    graficos_matlab = config.get("graficos_matlab", False)

    os.makedirs(excel_folder, exist_ok=True)

    # Ruta completa al archivo .mat
    mat_file_path = os.path.join(mat_folder, f"{name}.mat")

    # Comando para ejecutar la función MATLAB
    command = [
        matlab_path,
        "-nosplash",
        "-nodesktop" if not graficos_matlab else "",
        "-r",
        (
            f"cd('{ruta_matlab_script}'); "
            f"procesar_matlab('{mat_file_path}', '{excel_folder}', {str(graficos_matlab).lower()}, "
            f"{str(escritura).lower()}, {FS}); exit;"
        )
    ]

    command = [arg for arg in command if arg]  # Filtrar vacíos

    try:
        if graficos_matlab:
            print(f"Ejecutando MATLAB en modo interactivo para el archivo: {name}")
            subprocess.run(command, check=True)
        else:
            print(f"Ejecutando MATLAB en segundo plano para el archivo: {name}")
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar MATLAB para el archivo {name}: {e.stderr}")


def process_mat_files(output_folder, config):
    """
    Procesa todos los archivos MAT en la carpeta de salida usando MATLAB.
    """
    mat_files = [f for f in os.listdir(output_folder) if f.endswith('.mat')]
    for mat_file in tqdm(mat_files, desc="Procesando archivos MAT", unit="archivo"):
        mat_file_path = os.path.join(output_folder, mat_file)
        name = os.path.splitext(mat_file)[0]  # Extraer el nombre del archivo sin extensión
        run_matlab_script(name, config)