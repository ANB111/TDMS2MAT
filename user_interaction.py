import os

def get_folders_from_user(config):
    """
    Solicita las carpetas de entrada y salida al usuario si no están definidas en la configuración.
    También permite ingresar otros parámetros necesarios.
    """
    # Solicitar carpeta de entrada
    if 'input_folder' not in config or not config['input_folder']:
        config['input_folder'] = input("Ingrese la carpeta de entrada: ").strip().replace('"', '')

    # Solicitar carpeta de salida para archivos .mat
    if 'output_folder' not in config or not config['output_folder']:
        config['output_folder'] = input("Ingrese la carpeta de salida para archivos .mat: ").strip().replace('"', '')

    # Solicitar carpeta de salida para archivos Excel
    if 'excel_output_folder' not in config or not config['excel_output_folder']:
        config['excel_output_folder'] = input("Ingrese la carpeta de salida para archivos Excel: ").strip().replace('"', '')

    # Solicitar ruta del script de MATLAB
    if 'ruta_matlab_script' not in config or not config['ruta_matlab_script']:
        config['ruta_matlab_script'] = input("Ingrese la ruta del script de MATLAB: ").strip().replace('"', '')

    # Solicitar ruta del ejecutable de MATLAB
    if 'matlab_path' not in config or not config['matlab_path']:
        default_matlab_path = r"C:\Program Files\Polyspace\R2021a\bin\matlab.exe"
        config['matlab_path'] = input(f"Ingrese la ruta del ejecutable de MATLAB (predeterminado: {default_matlab_path}): ").strip().replace('"', '')
        if not config['matlab_path']:
            config['matlab_path'] = default_matlab_path

    # Solicitar otros parámetros opcionales
    if 'FS' not in config or not config['FS']:
        config['FS'] = int(input("Ingrese la frecuencia de muestreo (FS, predeterminado: 10): ").strip() or "10")

    if 'escritura' not in config or not config['escritura']:
        config['escritura'] = input("¿Habilitar escritura en MATLAB? (s/n, predeterminado: s): ").strip().lower() in ['s', 'si', 'y', 'yes']
    
    if 'n_channels' not in config or not config['n_channels']:
        config['n_channels'] = int(input("Ingrese el número de canales (predeterminado: 16): ").strip() or "16")

    return config

def select_processing_option(input_folder, config):
    """
    Muestra las opciones al usuario para seleccionar cómo procesar los archivos.
    Solicita si se desea procesar el último archivo incompleto y permite corregir errores.
    También pregunta si se desea realizar el conteo de ciclos de arranque y parada.
    """
    while True:
        print("\nSeleccione una opción:")
        print("1. Procesar a partir del último archivo procesado")
        print("2. Procesar un archivo específico")
        print("3. Procesar un rango de archivos")
        print("4. Salir")
        option = input("Ingrese el número de su elección: ").strip()
        
        # Obtener la lista de archivos ZIP en la carpeta de entrada
        zip_files = sorted([f for f in os.listdir(input_folder) if f.endswith('.zip')])
        last_processed_file = config.get('last_processed_file', None)
        if option == "1":
            if last_processed_file:
                start_index = zip_files.index(last_processed_file) + 1
                files_to_process = zip_files[start_index:]
            else:
                print("No hay registro de un último archivo procesado. Se procesarán todos los archivos.")
                files_to_process = zip_files
        elif option == "2":
            print("\nArchivos disponibles:")
            for idx, f in enumerate(zip_files, start=1):
                print(f"{idx}. {f}")
            try:
                file_index = int(input("Ingrese el número del archivo a procesar: ")) - 1
                if 0 <= file_index < len(zip_files):
                    files_to_process = [zip_files[file_index]]
                else:
                    print("Número fuera de rango. Intente de nuevo.")
                    continue
            except ValueError:
                print("Entrada no válida. Intente de nuevo.")
                continue
        elif option == "3":
            print("\nArchivos disponibles:")
            for idx, f in enumerate(zip_files, start=1):
                print(f"{idx}. {f}")
            try:
                start_index = int(input("Ingrese el número del primer archivo del rango: ")) - 1
                end_index = int(input("Ingrese el número del último archivo del rango: ")) - 1
                if 0 <= start_index <= end_index < len(zip_files):
                    files_to_process = zip_files[start_index:end_index + 1]
                else:
                    print("Rango no válido. Intente de nuevo.")
                    continue
            except ValueError:
                print("Entrada no válida. Intente de nuevo.")
                continue
        elif option == "4":
            print("Saliendo del programa.")
            return None, None, None, False  # Indica que no se seleccionó nada y no se realizará el conteo
        else:
            print("Opción no válida. Intente de nuevo.")
            continue
        
        # Solicitar la unidad a procesar
        unidad = input("Indique la unidad que se va a procesar: ").strip()
        
        # Preguntar si procesar el último archivo incompleto
        procesar_incompleto = input(
            "¿Desea procesar el último archivo del día aunque esté incompleto? (s/n): "
        ).strip().lower() == "s"
        
        # Preguntar si se desea realizar el conteo de ciclos de arranque y parada
        realizar_conteo = input(
            "¿Desea realizar el conteo de ciclos de arranque y parada? (s/n): "
        ).strip().lower() in ['s', 'si', 'y', 'yes']
        
        return files_to_process, procesar_incompleto, unidad, realizar_conteo