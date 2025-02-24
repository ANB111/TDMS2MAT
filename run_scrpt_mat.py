import os
from config_utils import load_config
from matlab_utils import process_mat_files

def main():
    # Ruta del archivo de configuración
    config_path = "config.json"

    # Cargar la configuración desde el archivo JSON
    config = load_config(config_path)

    # Verificar que los parámetros necesarios estén presentes en la configuración
    required_keys = ["output_folder", "excel_output_folder", "ruta_matlab_script", "matlab_path"]
    if not all(key in config for key in required_keys):
        print("Error: Faltan parámetros obligatorios en el archivo de configuración.")
        return

    # Carpeta de salida donde se encuentran los archivos .mat
    output_folder = config["output_folder"]

    # Verificar si la carpeta de salida existe
    if not os.path.exists(output_folder):
        print(f"La carpeta de salida no existe: {output_folder}")
        return

    # Procesar todos los archivos .mat en la carpeta de salida usando MATLAB
    print("Iniciando el procesamiento de archivos MAT con MATLAB...")
    process_mat_files(output_folder, config)
    print("Procesamiento completado.")

if __name__ == "__main__":
    main()