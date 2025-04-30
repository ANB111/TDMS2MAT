import os
import pandas as pd
from scipy.io import savemat
from tqdm import tqdm


def csv_to_mat(input_folder, output_folder, unidad="05", procesar_incompleto=False, log_callback=None):
    """
    Convierte archivos CSV en archivos MAT.
    
    Parámetros:
        input_folder (str): Carpeta de entrada con archivos CSV.
        output_folder (str): Carpeta de salida para archivos MAT.
        unidad (str): Unidad a procesar (por defecto "05").
        procesar_incompleto (bool): Indica si se deben procesar archivos incompletos (_temp).
        log_callback (function): Función de callback para registrar mensajes.
    """
    def log(message):
        """Registra un mensaje usando log_callback si está definido."""
        if log_callback:
            log_callback(message)

    # Verificar si la carpeta de entrada existe
    if not os.path.exists(input_folder):
        log(f"La carpeta de entrada '{input_folder}' no existe.")
        return

    # Crear la carpeta de salida si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Obtener archivos CSV (excluir los que contienen _temp si procesar_incompleto=False)
    if procesar_incompleto:
        csv_files = [f for f in os.listdir(input_folder) if f.endswith('.csv')]
    else:
        csv_files = [f for f in os.listdir(input_folder) if f.endswith('.csv') and "_temp" not in f]

    if not csv_files:
        log(f"No se encontraron archivos CSV en la carpeta '{input_folder}'.")
        return

    # Procesar cada archivo CSV
    for csv_file in tqdm(csv_files, desc="Convirtiendo archivos", unit="archivo"):
        # Ignorar archivos con _temp si no se deben procesar
        if "_temp.csv" in csv_file and not procesar_incompleto:
            continue

        # Construcción del nombre de salida eliminando _temp si está presente
        output_name = csv_file.replace("_temp", "")
        input_file = os.path.join(input_folder, csv_file)
        output_file = os.path.join(
            output_folder,
            f"{os.path.splitext(output_name)[0].replace('-', '.')}-u{unidad}.mat"
        )

        try:
            # Leer el archivo CSV
            data = pd.read_csv(input_file, delimiter=";", decimal=".")

            # Verificar si tiene la columna 'Time'
            if "Time" not in data.columns:
                log(f"Archivo '{csv_file}' omitido: no tiene columna 'Time'.")
                continue

            # Convertir la columna de tiempo
            data["Time"] = pd.to_datetime(data["Time"], errors='coerce')
            if data["Time"].isnull().all():
                log(f"Archivo '{csv_file}' omitido: errores en la conversión de fechas.")
                continue

            # Calcular epoch time
            data["Time_epoch"] = (data["Time"] - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s")

            # Crear diccionario para guardar en .mat
            mat_data = {
                "time_epoch": data["Time_epoch"].values,
                "data": data.drop(columns=["Time", "Time_epoch"]).values
            }

            # Guardar en formato MAT
            savemat(output_file, mat_data)

            # Eliminar solo si no es un archivo _temp
            if "_temp.csv" not in csv_file:
                os.remove(input_file)

        except Exception as e:
            log(f"Error procesando '{csv_file}': {e}")