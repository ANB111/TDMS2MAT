import os
import shutil
import pandas as pd
from tqdm import tqdm
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading

COLUMN_ORDER = [
    "Time", "Potencia", "Paletas", "Alabes", "Pres_Abr_Pal", "Pres_Cerr_Pal",
    "Pres_Abr_Alab", "Pres_Cerr_Alab", "Cont_Potencia", "Consigna_Pal",
    "Consigna_Pot", "Consigna_Alab", "Salto_Reg", "Velocidad", "Frecuencia",
    "ModoPotCon", "FaseDiv2"
]

# Diccionario compartido para acumular los datos por día (protegido con lock)
datos_por_dia = defaultdict(list)
datos_lock = threading.Lock()

def procesar_csv_individual(file):
    try:
        for chunk in pd.read_csv(file, delimiter=";", decimal=",", parse_dates=['Time'], chunksize=10000):
            chunk.sort_values(by='Time', inplace=True)
            chunk['Date'] = chunk['Time'].dt.date

            with datos_lock:
                for date, group in chunk.groupby('Date'):
                    datos_por_dia[date].append(group)
    except Exception as e:
        print(f"Error procesando {file}: {e}")

def ordenar_y_agrupado_por_dia(input_folder, num_workers=14):
    csv_files = glob.glob(os.path.join(input_folder, "*.csv"))

    if not csv_files:
        print("No se encontraron archivos CSV en la carpeta especificada.")
        return

    # Procesar archivos CSV en paralelo
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        list(tqdm(executor.map(procesar_csv_individual, csv_files), total=len(csv_files), desc="Leyendo archivos CSV", unit="archivo"))

    # Combinar y guardar resultados por día
    for date, groups in tqdm(datos_por_dia.items(), desc="Concatenando archivos por día", unit="día"):
        daily_data = pd.concat(groups, ignore_index=True)
        daily_data.drop(columns=['Date'], inplace=True)

        # Reordenar columnas
        current_columns = list(daily_data.columns)
        if current_columns != COLUMN_ORDER:
            missing_cols = [col for col in COLUMN_ORDER if col not in current_columns]
            if missing_cols:
                print(f"Advertencia: faltan columnas en {date}.csv: {missing_cols}")
            ordered_cols = [col for col in COLUMN_ORDER if col in current_columns]
            remaining_cols = [col for col in current_columns if col not in ordered_cols]
            daily_data = daily_data[ordered_cols + remaining_cols]

        output_file = os.path.join(input_folder, f"{date}.csv")
        daily_data.to_csv(output_file, sep=";", decimal=",", index=False)

        # Verificación para crear _temp.csv si el día está incompleto
        last_time = daily_data['Time'].max()
        temp_file = os.path.join(input_folder, f"{date}_temp.csv")

        if pd.notnull(last_time) and last_time.hour == 23 and last_time.minute == 59 and last_time.second == 59:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        else:
            shutil.copy(output_file, temp_file)

    eliminar_archivos_csv(csv_files)

def eliminar_archivos_csv(csv_files):
    for file in csv_files:
        if os.path.exists(file) and not file.endswith("_temp.csv"):
            os.remove(file)
