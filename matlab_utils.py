import os
import subprocess
from config_utils import load_config
from tqdm import tqdm

def run_matlab_script(name, config):
    """
    Ejecuta un script de MATLAB con los parámetros proporcionados en el archivo de configuración.
    
    Parámetros:
    - name (str): Nombre del archivo MAT a procesar.
    - config (dict): Diccionario con la configuración cargada desde el archivo JSON.
    
    Retorna:
    - None
    """
    # Extraer parámetros del archivo de configuración
    matlab_path = config.get("matlab_path", r"C:\Program Files\Polyspace\R2021a\bin\matlab.exe")
    ruta_matlab_script = config.get("ruta_matlab_script", "")
    FS = config.get("FS", 10)
    escritura = config.get("escritura", True)
    n_channels = config.get("n_channels", 16)
    mat_folder = config.get("output_folder", "")
    excel_folder = config.get("excel_output_folder", "")

    # Crear la carpeta de salida para Excel si no existe
    os.makedirs(excel_folder, exist_ok=True)

    # Construir el comando para ejecutar MATLAB
    command = [
        matlab_path,
        "-batch",
        f"cd('{ruta_matlab_script}'); matlab_script('{name}', {str(escritura).lower()}, {FS}, {n_channels}, '{mat_folder}', '{excel_folder}')"
    ]

    try:
        # Ejecutar el comando
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        print(e.stderr)

def process_mat_files(output_folder, config):
    """
    Procesa todos los archivos MAT en la carpeta de salida usando MATLAB.
    """
    mat_files = [f for f in os.listdir(output_folder) if f.endswith('.mat')]
    for mat_file in tqdm(mat_files, desc="Procesando archivos MAT", unit="archivo"):
        mat_file_path = os.path.join(output_folder, mat_file)
        name = os.path.splitext(mat_file)[0]  # Extraer el nombre del archivo sin extensión
        run_matlab_script(name, config)