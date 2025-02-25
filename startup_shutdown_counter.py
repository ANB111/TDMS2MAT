import os
import pandas as pd
from scipy.io import loadmat
from datetime import datetime

def count_startups_shutdowns(mat_data):
    """
    Cuenta los ciclos de arranque y parada en los datos del canal 13.
    
    Parámetros:
    - mat_data (dict): Datos cargados desde el archivo .mat.
    
    Retorna:
    - tuple: (número de arranques, número de paradas, estado inicial, estado final)
    """
    # Extraer los datos del canal 13 (velocidad de la turbina)
    try:
        speed_data = mat_data['data'][:, 13]  # Asumimos que el canal 13 es el índice 13
    except IndexError:
        print("El archivo .mat no tiene datos en el canal 13.")
        return 0, 0, "Desconocido", "Desconocido"

    # Contadores para arranques y paradas
    startups = 0
    shutdowns = 0

    # Detectar transiciones
    for i in range(1, len(speed_data)):
        if speed_data[i - 1] == 0 and speed_data[i] > 0:
            startups += 1
        elif speed_data[i - 1] > 0 and speed_data[i] == 0:
            shutdowns += 1

    # Determinar el estado inicial y final
    estado_inicial = "Encendida" if speed_data[0] > 0 else "Apagada"
    estado_final = "Encendida" if speed_data[-1] > 0 else "Apagada"

    return startups, shutdowns, estado_inicial, estado_final

def process_mat_folder(mat_folder, excel_path):
    """
    Procesa todos los archivos .mat en la carpeta especificada y actualiza el archivo Excel.
    Solo procesa archivos que no han sido contabilizados previamente.
    
    Parámetros:
    - mat_folder (str): Ruta de la carpeta que contiene los archivos .mat.
    - excel_path (str): Ruta del archivo Excel donde se guardarán los resultados.
    """
    # Verificar si el archivo Excel ya existe
    if os.path.exists(excel_path):
        df_excel = pd.read_excel(excel_path)
        processed_files = set(df_excel["Archivo"])  # Conjunto de archivos ya procesados
    else:
        # Crear un DataFrame vacío si el archivo no existe
        df_excel = pd.DataFrame(columns=["Fecha", "Arranques", "Paradas", "Total", "Estado Inicial", "Estado Final", "Archivo"])
        processed_files = set()

    # Procesar cada archivo .mat en la carpeta
    for mat_file in os.listdir(mat_folder):
        if not mat_file.endswith('.mat'):
            continue

        mat_path = os.path.join(mat_folder, mat_file)

        # Verificar si el archivo ya fue procesado
        if mat_file in processed_files:
            print(f"El archivo {mat_file} ya fue procesado. Saltando...")
            continue

        try:
            # Cargar los datos del archivo .mat
            mat_data = loadmat(mat_path)

            # Extraer la fecha del nombre del archivo (asumiendo formato YYYY.MM.DD-uXX.mat)
            date_str = mat_file.split('-')[0]
            date = datetime.strptime(date_str, "%Y.%m.%d").date()

            # Contar arranques, paradas y obtener estados inicial y final
            startups, shutdowns, estado_inicial, estado_final = count_startups_shutdowns(mat_data)
            total = startups + shutdowns

            # Agregar nueva fila al DataFrame
            new_row = {
                "Fecha": date,
                "Arranques": startups,
                "Paradas": shutdowns,
                "Total": total,
                "Estado Inicial": estado_inicial,
                "Estado Final": estado_final,
                "Archivo": mat_file  # Registrar el nombre del archivo procesado
            }
            df_excel = pd.concat([df_excel, pd.DataFrame([new_row])], ignore_index=True)

            # Agregar el archivo al conjunto de archivos procesados
            processed_files.add(mat_file)

        except Exception as e:
            print(f"Error procesando {mat_file}: {e}")

    # Guardar el archivo Excel actualizado
    df_excel.to_excel(excel_path, index=False)
    print(f"Resultados guardados en {excel_path}")
