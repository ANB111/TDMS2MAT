import os
import shutil
import pandas as pd
from tqdm import tqdm

def ordenar_y_agrupado_por_dia(input_folder, procesar_incompleto=False):
    script_folder = os.path.dirname(os.path.abspath(__file__))
    temp_folder = os.path.join(script_folder, 'temp')

    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    for temp_file_name in os.listdir(temp_folder):
        temp_file_path = os.path.join(temp_folder, temp_file_name)
        if os.path.exists(temp_file_path):
            shutil.move(temp_file_path, os.path.join(input_folder, temp_file_name))

    csv_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(input_folder)
        for file in files if file.endswith(".csv")
    ]

    if not csv_files:
        print("No se encontraron archivos CSV en la carpeta especificada.")
        return

    datos_por_dia = {}

    for file in csv_files:
        for chunk in pd.read_csv(file, delimiter=";", decimal=",", parse_dates=['Time'], chunksize=10000):
            chunk.sort_values(by='Time', inplace=True)
            chunk['Date'] = chunk['Time'].dt.date

            for date, group in chunk.groupby('Date'):
                if date not in datos_por_dia:
                    datos_por_dia[date] = []
                datos_por_dia[date].append(group)

    for date, groups in tqdm(datos_por_dia.items(), desc="Concatenando archivos por día", unit="día"):
        daily_data = pd.concat(groups, ignore_index=True)
        daily_data.drop('Date', axis=1, inplace=True)
        output_file = os.path.join(input_folder, f"{date}.csv")
        daily_data.to_csv(output_file, sep=";", decimal=",", index=False)

        last_time = daily_data['Time'].max()
        if last_time.hour != 23 or last_time.minute != 59 or last_time.second != 59:
            temp_file = os.path.join(temp_folder, f"{date}_temp.csv")
            shutil.copy(output_file, temp_file)
            if not procesar_incompleto:
                os.remove(output_file)

    eliminar_archivos_csv(csv_files)

def eliminar_archivos_csv(csv_files):
    for file in csv_files:
        if os.path.exists(file):
            os.remove(file)