import os
import pandas as pd
from scipy.io import savemat
from tqdm import tqdm

def csv_to_mat(folder_path, unidad="05"):
    if not os.path.exists(folder_path):
        print(f"La carpeta {folder_path} no existe.")
        return

    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

    if not csv_files:
        print(f"No se encontraron archivos CSV en la carpeta {folder_path}.")
        return

    for csv_file in tqdm(csv_files, desc="Convirtiendo archivos", unit="archivo"):
        input_file = os.path.join(folder_path, csv_file)
        output_file = os.path.join(folder_path, f"{os.path.splitext(csv_file)[0].replace('-', '.')}-u{unidad}.mat")

        data = pd.read_csv(input_file, delimiter=";", decimal=".")
        data["Time"] = pd.to_datetime(data["Time"])
        data["Time_epoch"] = (data["Time"] - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s")

        mat_data = {
            "time_epoch": data["Time_epoch"].values,
            "data": data.drop(columns=["Time", "Time_epoch"]).values
        }

        savemat(output_file, mat_data)
        os.remove(input_file)