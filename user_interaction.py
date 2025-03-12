import os
import json

def solicitar_ruta(mensaje, config_key, config, default=None):
    """
    Solicita una ruta al usuario si no está definida en la configuración.
    """
    if config_key not in config or not config[config_key]:
        ruta = input(f"{mensaje} ").strip().replace('"', '')
        config[config_key] = os.path.normpath(ruta) if ruta else default
    return config[config_key]

def solicitar_parametro(mensaje, config_key, config, tipo=str, default=None):
    """
    Solicita un parámetro al usuario si no está definido en la configuración.
    """
    if config_key not in config or not config[config_key]:
        valor = input(f"{mensaje} ").strip()
        config[config_key] = tipo(valor) if valor else default
    return config[config_key]

def get_folders_from_user(config):
    """
    Solicita las carpetas de entrada, salida y otros parámetros al usuario si no están definidos.
    """
    solicitar_ruta("Ingrese la carpeta de entrada:", "input_folder", config)
    solicitar_ruta("Ingrese la carpeta de salida para archivos .mat:", "output_folder", config)
    solicitar_ruta("Ingrese la carpeta de salida para archivos Excel:", "excel_output_folder", config)
    solicitar_ruta("Ingrese la ruta del script de MATLAB:", "ruta_matlab_script", config)

    default_matlab_path = r"C:\Program Files\Polyspace\R2021a\bin\matlab.exe"
    solicitar_ruta(f"Ingrese la ruta del ejecutable de MATLAB (predeterminado: {default_matlab_path}):", 
                   "matlab_path", config, default=default_matlab_path)

    solicitar_parametro("Ingrese la frecuencia de muestreo (FS, predeterminado: 10):", "FS", config, int, default=10)
    solicitar_parametro("¿Habilitar escritura en MATLAB? (s/n, predeterminado: s):", "escritura", config, 
                        lambda x: x.lower() in ['s', 'si', 'y', 'yes'], default=True)
    solicitar_parametro("Ingrese el número de canales (predeterminado: 16):", "n_channels", config, int, default=16)

    return config

def mostrar_archivos_disponibles(zip_files):
    """
    Muestra una lista numerada de los archivos disponibles.
    """
    print("\nArchivos disponibles:")
    for idx, f in enumerate(zip_files, start=1):
        print(f"{idx}. {f}")

def seleccionar_archivos(zip_files, config):
    """
    Permite al usuario seleccionar cómo procesar los archivos (último procesado, uno específico o un rango).
    """
    while True:
        print("\nSeleccione una opción:")
        print("1. Procesar a partir del último archivo procesado")
        print("2. Procesar un archivo específico")
        print("3. Procesar un rango de archivos")
        print("4. Salir")

        option = input("Ingrese el número de su elección: ").strip()
        last_processed_file = config.get('last_processed_file', None)

        if option == "1":
            if last_processed_file and last_processed_file in zip_files:
                start_index = zip_files.index(last_processed_file) + 1
                files_to_process = zip_files[start_index:]
            else:
                print("No hay registro de un último archivo procesado.")
                files_to_process = None
        elif option == "2":
            mostrar_archivos_disponibles(zip_files)
            try:
                file_index = int(input("Ingrese el número del archivo a procesar: ")) - 1
                files_to_process = [zip_files[file_index]] if 0 <= file_index < len(zip_files) else None
            except ValueError:
                files_to_process = None
        elif option == "3":
            mostrar_archivos_disponibles(zip_files)
            try:
                start_index = int(input("Ingrese el número del primer archivo del rango: ")) - 1
                end_index = int(input("Ingrese el número del último archivo del rango: ")) - 1
                files_to_process = zip_files[start_index:end_index + 1] if 0 <= start_index <= end_index < len(zip_files) else None
            except ValueError:
                files_to_process = None
        elif option == "4":
            print("Saliendo del programa.")
            return None, None, None, False
        else:
            print("Opción no válida. Intente de nuevo.")
            continue

        if files_to_process:
            break
        else:
            print("Selección no válida. Intente de nuevo.")

    return files_to_process

def select_processing_option(input_folder, config):
    """
    Permite seleccionar los archivos a procesar y las opciones de procesamiento.
    """
    zip_files = sorted([f for f in os.listdir(input_folder) if f.endswith('.zip')])

    if not zip_files:
        print("No se encontraron archivos ZIP en la carpeta de entrada.")
        return None, None, None, False

    files_to_process = seleccionar_archivos(zip_files, config)
    if not files_to_process:
        return None, None, None, False

    unidad = input("Indique la unidad que se va a procesar: ").strip()
    procesar_incompleto = input("¿Desea procesar el último archivo del día aunque esté incompleto? (s/n): ").strip().lower() == "s"
    realizar_conteo = input("¿Desea realizar el conteo de ciclos de arranque y parada? (s/n): ").strip().lower() in ['s', 'si', 'y', 'yes']

    config['last_processed_file'] = files_to_process[-1]
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

    return files_to_process, procesar_incompleto, unidad, realizar_conteo
