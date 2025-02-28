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
    graficos_matlab = config.get("graficos_matlab", False)  # Verificar si los gráficos están activados

    # Crear la carpeta de salida para Excel si no existe
    os.makedirs(excel_folder, exist_ok=True)

    # Construir el comando base para ejecutar MATLAB
    command = [
        matlab_path,
        "-nosplash",  # Oculta la pantalla de inicio de MATLAB
        "-nodesktop" if not graficos_matlab else "",  # Modo sin interfaz gráfica si graficos_matlab es False
        "-r",  # Ejecutar un comando
        f"cd('{ruta_matlab_script}'); matlab_script('{name}', {str(escritura).lower()}, {FS}, {n_channels}, '{mat_folder}', '{excel_folder}'); exit;"  # Comando MATLAB
    ]

    # Filtrar elementos vacíos del comando
    command = [arg for arg in command if arg]

    try:
        # Ejecutar el comando
        if graficos_matlab:
            print(f"Ejecutando MATLAB en modo interactivo para el archivo: {name}")
            subprocess.run(command, check=True)  # No capturamos stdout/stderr en modo interactivo
        else:
            print(f"Ejecutando MATLAB en segundo plano para el archivo: {name}")
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(result.stdout)  # Mostrar la salida estándar
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