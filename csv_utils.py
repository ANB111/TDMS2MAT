import os
import shutil
import pandas as pd
from tqdm import tqdm
import glob

def ordenar_y_agrupado_por_dia(input_folder):
    # Obtener lista de archivos CSV en la carpeta de entrada
    csv_files = glob.glob(os.path.join(input_folder, "*.csv"))

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
        daily_data.drop(columns=['Date'], inplace=True)
        output_file = os.path.join(input_folder, f"{date}.csv")
        
        daily_data.to_csv(output_file, sep=";", decimal=",", index=False)

        # Verificar si el archivo del día está completo
        last_time = daily_data['Time'].max()
        temp_file = os.path.join(input_folder, f"{date}_temp.csv")

        if last_time.hour == 23 and last_time.minute == 59 and last_time.second == 59:
            # Si el día está completo, eliminamos el archivo _temp.csv si existe
            if os.path.exists(temp_file):
                os.remove(temp_file)
        else:
            # Si el día no está completo, aseguramos que _temp.csv se mantenga
            shutil.copy(output_file, temp_file)

    eliminar_archivos_csv(csv_files)

def eliminar_archivos_csv(csv_files):
    """Elimina los archivos CSV procesados (excepto los _temp.csv)."""
    for file in csv_files:
        if os.path.exists(file) and not file.endswith("_temp.csv"):
            os.remove(file)