import os
import pandas as pd
from scipy.io import savemat


def csv_to_mat(input_folder, output_folder, unidad="05", procesar_incompleto=False, log_callback=None):
    """
    Convierte archivos CSV en archivos MAT.

    Parámetros:
        input_folder (str): Carpeta de entrada con archivos CSV.
        output_folder (str): Carpeta de salida para archivos MAT.
        unidad (str): Unidad a procesar (por defecto "05").
        procesar_incompleto (bool): Indica si se deben procesar archivos incompletos (_temp).
        log_callback (function): Función de callback para registrar mensajes (por ejemplo, mostrar en GUI).
    """
    def log(message):
        """Registra un mensaje usando log_callback si está definido."""
        if log_callback:
            log_callback(message)

    # Verificar si la carpeta de entrada existe
    if not os.path.exists(input_folder):
        log(f"[CSV2MAT] La carpeta de entrada '{input_folder}' no existe.")
        return

    # Crear la carpeta de salida si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Obtener archivos CSV
    csv_files = [
        f for f in os.listdir(input_folder)
        if f.endswith('.csv') and (procesar_incompleto or "_temp" not in f)
    ]

    if not csv_files:
        log(f"[CSV2MAT] No se encontraron archivos CSV en la carpeta '{input_folder}'.")
        return

    log(f"[CSV2MAT] Procesando {len(csv_files)} archivo(s)...")

    for csv_file in csv_files:
        output_name = csv_file.replace("_temp", "")
        input_file = os.path.join(input_folder, csv_file)
        # Extraer solo la parte de la fecha (ej: 25.2.11 de 25.2.11.csv o 25.2.11-u05.csv)
        base_name = os.path.splitext(output_name)[0]
        # Si el nombre es tipo 25.2.11-u05, tomar solo la parte antes del primer guion
        date_part = base_name.split('-')[0]
        output_file = os.path.join(
            output_folder,
            f"{date_part}-u{unidad}.mat"
        )

        try:
            data = pd.read_csv(input_file, delimiter=";", decimal=".")

            if "Time" not in data.columns:
                log(f"[CSV2MAT] '{csv_file}' omitido: no tiene columna 'Time'.")
                continue

            data["Time"] = pd.to_datetime(data["Time"], errors='coerce')
            if data["Time"].isnull().all():
                log(f"[CSV2MAT] '{csv_file}' omitido: errores en la conversión de fechas.")
                continue

            data["Time_epoch"] = (data["Time"] - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s")

            mat_data = {
                "time_epoch": data["Time_epoch"].values,
                "data": data.drop(columns=["Time", "Time_epoch"]).values
            }

            savemat(output_file, mat_data)
            log(f"[CSV2MAT] Archivo convertido: {csv_file} -> {os.path.basename(output_file)}")

            if "_temp.csv" not in csv_file:
                os.remove(input_file)
                log(f"[CSV2MAT] Archivo original eliminado: {csv_file}")

        except Exception as e:
            log(f"[CSV2MAT] Error procesando '{csv_file}': {e}")
