import pandas as pd
import sys
import os

def compare_excel_files(file1, file2):
    """
    Compara el contenido de dos archivos Excel.

    Args:
        file1 (str): Ruta al primer archivo Excel.
        file2 (str): Ruta al segundo archivo Excel.

    Returns:
        bool: True si los archivos son idénticos en contenido, False en caso contrario.
    """
    try:
        # Leer todas las hojas de ambos archivos
        xls1 = pd.read_excel(file1, sheet_name=None)
        xls2 = pd.read_excel(file2, sheet_name=None)

        # Comparar los nombres de las hojas
        if sorted(xls1.keys()) != sorted(xls2.keys()):
            print(f"\n[DIFERENTES] {os.path.basename(file1)}: Las hojas son diferentes.")
            return False

        # Comparar el contenido de cada hoja
        for sheet_name in xls1.keys():
            df1 = xls1[sheet_name]
            df2 = xls2[sheet_name]

            # Llenar valores NaN con un valor consistente para la comparación
            df1_filled = df1.fillna('-')
            df2_filled = df2.fillna('-')

            if not df1_filled.equals(df2_filled):
                print(f"\n[DIFERENTES] {os.path.basename(file1)}: El contenido de la hoja '{sheet_name}' es diferente.")
                return False

        print(f"\n[IDÉNTICOS] {os.path.basename(file1)}")
        return True

    except FileNotFoundError as e:
        print(f"\n[ERROR] Archivo no encontrado: {e.filename}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error al comparar {os.path.basename(file1)}: {e}")
        return False

if __name__ == "__main__":


    folder1 = r"C:\Users\BECARIO 8\Documents\TDMS2MAT\ejecucuion consola\salida_excels"
    folder2 = r"C:\Users\BECARIO 8\Documents\TDMS2MAT\salida_excels"

    if not os.path.isdir(folder1):
        print(f"Error: La carpeta no existe - {folder1}")
        sys.exit(1)

    if not os.path.isdir(folder2):
        print(f"Error: La carpeta no existe - {folder2}")
        sys.exit(1)

    print(f"Comparando archivos Excel en:\n- Carpeta 1: {folder1}\n- Carpeta 2: {folder2}\n")

    files_in_folder1 = [f for f in os.listdir(folder1) if f.endswith(('.xlsx', '.xls'))]

    for filename in files_in_folder1:
        file1_path = os.path.join(folder1, filename)
        file2_path = os.path.join(folder2, filename)

        if os.path.exists(file2_path):
            compare_excel_files(file1_path, file2_path)
        else:
            print(f"\n[NO ENCONTRADO] El archivo {filename} no existe en la carpeta 2.")
