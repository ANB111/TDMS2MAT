import os
import shutil
import pandas as pd
import glob

COLUMNS_ORDER = [
    "Time", "Potencia", "Paletas", "Alabes", "Pres_Abr_Pal", "Pres_Cerr_Pal",
    "Pres_Abr_Alab", "Pres_Cerr_Alab", "Cont_Potencia", "Consigna_Pal",
    "Consigna_Pot", "Consigna_Alab", "Salto_Reg", "Velocidad",
    "Frecuencia", "ModoPotCon", "FaseDiv2"
]

def ordenar_y_agrupado_por_dia(input_folder, log_callback=print):
    csv_files = glob.glob(os.path.join(input_folder, "*.csv"))

    if not csv_files:
        log_callback("No se encontraron archivos CSV en la carpeta especificada.")
        return

    datos_por_dia = {}

    for file in csv_files:
        for chunk in pd.read_csv(file, delimiter=";", decimal=",", parse_dates=['Time'], chunksize=10000):
            chunk.sort_values(by='Time', inplace=True)
            chunk['Date'] = chunk['Time'].dt.date

            for date, group in chunk.groupby('Date'):
                # Verifica y reordena columnas
                if set(COLUMNS_ORDER).issubset(group.columns):
                    if list(group.columns) != COLUMNS_ORDER:
                        log_callback(f"[INFO] Reordenando columnas en archivo: {file}")
                        group = group[COLUMNS_ORDER]
                else:
                    missing = list(set(COLUMNS_ORDER) - set(group.columns))
                    log_callback(f"[WARNING] Faltan columnas en {file}: {missing}")
                    group = group[[col for col in COLUMNS_ORDER if col in group.columns]]

                if date not in datos_por_dia:
                    datos_por_dia[date] = []
                datos_por_dia[date].append(group)

    for date, groups in datos_por_dia.items():
        daily_data = pd.concat(groups, ignore_index=True)
        daily_data.drop(columns=['Date'], inplace=True, errors='ignore')
        output_file = os.path.join(input_folder, f"{date}.csv")
        daily_data.to_csv(output_file, sep=";", decimal=",", index=False)

        last_time = daily_data['Time'].max()
        temp_file = os.path.join(input_folder, f"{date}_temp.csv")

        if last_time.hour == 23 and last_time.minute == 59 and last_time.second == 59:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                log_callback(f"[INFO] Día completo para {date}, eliminando {temp_file}")
        else:
            shutil.copy(output_file, temp_file)
            log_callback(f"[INFO] Día incompleto para {date}, guardando también como {temp_file}")

    eliminar_archivos_csv(csv_files, log_callback)

def eliminar_archivos_csv(csv_files, log_callback=print):
    for file in csv_files:
        if os.path.exists(file) and not file.endswith("_temp.csv"):
            os.remove(file)
            log_callback(f"[INFO] Eliminado archivo temporal: {file}")
