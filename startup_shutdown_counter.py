import os
from datetime import datetime
import numpy as np
import pandas as pd
from scipy.io import loadmat

def extract_numeric_key(filename):
    """
    Extrae una clave numérica de un nombre de archivo con formato '25.2.11-u05.mat'.
    Devuelve una tupla de enteros para ordenar correctamente.
    """
    # Tomar la parte antes del primer '-'
    base = filename.split('-')[0]
    # Separar por '.' y convertir a enteros
    try:
        parts = tuple(int(p) for p in base.split('.'))
    except Exception:
        parts = (0,)
    return parts

def count_startups_shutdowns(mat_data):
    """Cuenta los arranques y paradas usando el canal 13 (velocidad de turbina).

    Retorna una tupla con (arranques, paradas, estado_inicial, estado_final, speed_data).
    """

    try:
        speed_data = mat_data["data"][:, 13]
    except (IndexError, KeyError):
        print("El archivo .mat no tiene datos en el canal 13.")
        return 0, 0, "Desconocido", "Desconocido", np.array([])

    startups = 0
    shutdowns = 0

    for i in range(1, len(speed_data)):
        if speed_data[i - 1] == 0 and speed_data[i] > 0:
            startups += 1
        elif speed_data[i - 1] > 0 and speed_data[i] == 0:
            shutdowns += 1

    estado_inicial = "Encendida" if speed_data[0] > 0 else "Apagada"
    estado_final = "Encendida" if speed_data[-1] > 0 else "Apagada"

    return startups, shutdowns, estado_inicial, estado_final, speed_data


def calculate_runtime_hours(speed_data, time_epoch, sample_rate_hint: float = 10.0):
    """Calcula las horas que la máquina estuvo encendida y el total de horas con datos."""

    speed_array = np.asarray(speed_data, dtype=float).flatten()
    if speed_array.size == 0:
        return 0.0, 0.0

    on_mask = speed_array > 0

    time_array = None
    if isinstance(time_epoch, np.ndarray) and time_epoch.size:
        time_array = np.asarray(time_epoch, dtype=float).squeeze()
        if time_array.ndim > 1:
            time_array = time_array.reshape(-1)

    if time_array is not None and time_array.size >= speed_array.size:
        time_array = time_array[: speed_array.size]
        diffs = np.diff(time_array)
        if diffs.size:
            diffs = np.where(diffs > 0, diffs, 0.0)
            intervals = np.zeros(speed_array.size, dtype=float)
            intervals[:-1] = diffs
        else:
            intervals = np.zeros(speed_array.size, dtype=float)
    else:
        # Fallback a una frecuencia de muestreo estimada cuando no hay vector de tiempo.
        sample_rate = float(sample_rate_hint) if sample_rate_hint else 10.0
        interval = 1.0 / sample_rate
        intervals = np.full(speed_array.size, interval, dtype=float)
        if intervals.size:
            intervals[-1] = 0.0

    horas_disponibles = intervals.sum() / 3600.0
    horas_encendida = intervals[on_mask].sum() / 3600.0

    return horas_encendida, horas_disponibles


def calculate_movements_from_counter(counter_series):
    """Calcula los movimientos acumulados incluso cuando el contador se reinicia."""

    try:
        counter_array = np.asarray(counter_series, dtype=float).flatten()
    except Exception:
        return None

    if counter_array.size == 0:
        return None

    counter_array = counter_array[~np.isnan(counter_array)]
    if counter_array.size == 0:
        return None

    if counter_array.size == 1:
        return 0

    diffs = np.diff(counter_array)
    if diffs.size == 0:
        return 0

    positive_diffs = diffs[diffs > 0]
    if positive_diffs.size == 0:
        return 0

    total_movements = float(positive_diffs.sum())
    return int(round(total_movements))


def parse_fecha_string(fecha: str):
    if not fecha or not isinstance(fecha, str):
        return None
    try:
        parts = fecha.strip().split(".")
        if len(parts) != 3:
            return None
        year, month, day = map(int, parts)
        return datetime(year=2000 + year, month=month, day=day)
    except Exception:  # pylint: disable=broad-except
        return None


def format_fecha_string(date_obj: datetime) -> str:
    return f"{date_obj.year - 2000}.{date_obj.month}.{date_obj.day}"


def process_mat_folder(mat_folder, excel_path, log_callback=None):
    """
    Procesa todos los archivos .mat en la carpeta especificada y actualiza el archivo Excel.
    Solo procesa archivos que no han sido contabilizados previamente.
    
    Parámetros:
    - mat_folder (str): Ruta de la carpeta que contiene los archivos .mat.
    - excel_path (str): Ruta del archivo Excel donde se guardarán los resultados.
    - log_callback (function): Función de callback para registrar mensajes en el log.
    """
    # Función de registro
    def log(message):
        if log_callback:
            log_callback(message)
        else:
            print(message)

    expected_columns = [
        "Fecha",
        "Arranques",
        "Paradas",
        "Total",
        "Horas Encendida",
        "Movimientos",
        "Estado Inicial",
        "Estado Final",
        "Archivo",
    ]

    # Verificar si el archivo Excel ya existe
    if os.path.exists(excel_path):
        df_excel = pd.read_excel(excel_path)
        for column in expected_columns:
            if column not in df_excel.columns:
                df_excel[column] = None
        df_excel = df_excel[expected_columns]
        processed_files = set(df_excel["Archivo"])  # Conjunto de archivos ya procesados
    else:
        # Crear un DataFrame vacío si el archivo no existe
        df_excel = pd.DataFrame(columns=expected_columns)
        processed_files = set()

    # Obtener y ordenar archivos .mat de forma numérica
    mat_files = [f for f in os.listdir(mat_folder) if f.endswith('.mat')]
    mat_files.sort(key=extract_numeric_key)

    # Procesar cada archivo .mat en la carpeta
    for mat_file in mat_files:
        # Verificar si el archivo ya fue procesado
        if mat_file in processed_files:
            log(f"El archivo {mat_file} ya fue procesado. Saltando...")
            continue

        mat_path = os.path.join(mat_folder, mat_file)

        try:
            # Cargar los datos del archivo .mat
            mat_data = loadmat(mat_path)
            # Extraer la fecha del nombre del archivo
            date_str = mat_file.split('-')[0]

            # Contar arranques, paradas y obtener estados inicial y final
            startups, shutdowns, estado_inicial, estado_final, speed_data = count_startups_shutdowns(mat_data)
            total = startups + shutdowns

            # Calcular movimientos del día considerando reinicios del contador (canal 8, índice 8)
            try:
                movimientos = calculate_movements_from_counter(mat_data['data'][:, 7])
            except Exception:
                movimientos = None

            time_epoch = mat_data.get("time_epoch")
            horas_encendida, horas_disponibles = calculate_runtime_hours(speed_data, time_epoch)

            if (
                horas_disponibles >= 23.9
                and speed_data.size > 0
                and speed_data[0] > 0
                and shutdowns == 0
            ):
                horas_encendida = 24.0
            horas_encendida = round(horas_encendida, 2)

            # Agregar nueva fila al DataFrame
            new_row = {
                "Fecha": date_str,
                "Arranques": startups,
                "Paradas": shutdowns,
                "Total": total,
                "Horas Encendida": horas_encendida,
                "Movimientos": movimientos,
                "Estado Inicial": estado_inicial,
                "Estado Final": estado_final,
                "Archivo": mat_file  # Registrar el nombre del archivo procesado
            }
            df_excel = pd.concat([df_excel, pd.DataFrame([new_row])], ignore_index=True)

            # Agregar el archivo al conjunto de archivos procesados
            processed_files.add(mat_file)

        except Exception as e:
            log(f"Error procesando {mat_file}: {e}")

    parsed_dates = df_excel["Fecha"].apply(parse_fecha_string)
    valid_dates = parsed_dates.dropna()

    if not valid_dates.empty:
        min_date = valid_dates.min()
        max_date = valid_dates.max()
        existing_dates = {dt.date() for dt in valid_dates}

        missing_rows = []
        for current_date in pd.date_range(min_date, max_date, freq="D"):
            if current_date.date() in existing_dates:
                continue
            missing_rows.append(
                {
                    "Fecha": format_fecha_string(current_date.to_pydatetime()),
                    "Arranques": 0,
                    "Paradas": 0,
                    "Total": 0,
                    "Horas Encendida": 0.0,
                    "Movimientos": 0,
                    "Estado Inicial": "",
                    "Estado Final": "",
                    "Archivo": "",
                }
            )

        if missing_rows:
            df_excel = pd.concat([df_excel, pd.DataFrame(missing_rows)], ignore_index=True)
            parsed_dates = df_excel["Fecha"].apply(parse_fecha_string)

        df_excel["__fecha_dt"] = pd.to_datetime(parsed_dates)
        df_excel = df_excel.sort_values("__fecha_dt", kind="mergesort", na_position="last")
        df_excel["Fecha"] = df_excel["__fecha_dt"].apply(
            lambda dt: format_fecha_string(dt.to_pydatetime()) if pd.notna(dt) else ""
        )
        df_excel = df_excel.drop(columns=["__fecha_dt"]).reset_index(drop=True)

    # Guardar el archivo Excel actualizado
    df_excel.to_excel(excel_path, index=False)
    log(f"Resultados guardados en {excel_path}")