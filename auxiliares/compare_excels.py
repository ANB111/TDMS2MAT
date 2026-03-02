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

            if df1.shape != df2.shape:
                print(f"\n[DIFERENTES] {os.path.basename(file1)}: La hoja '{sheet_name}' tiene distinto número de filas/columnas.")
                return False

            if list(df1.columns) != list(df2.columns):
                print(f"\n[DIFERENTES] {os.path.basename(file1)}: La hoja '{sheet_name}' tiene columnas distintas.")
                return False

            # Comparar con tolerancia numérica para evitar falsos positivos por
            # diferencias de precisión flotante entre archivos Excel.
            # check_dtype=False permite comparar int64 vs float64 como equivalentes.
            try:
                pd.testing.assert_frame_equal(
                    df1.reset_index(drop=True),
                    df2.reset_index(drop=True),
                    check_exact=False,
                    rtol=1e-9,
                    check_dtype=False,
                    check_names=True,
                )
            except AssertionError:
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


    folder1 = r"D:\Carpeta Becario 19\Nueva carpeta (2)\TDMS2MAT\salida_excels"
    folder2 = r"D:\Carpeta Becario 19\Nueva carpeta (2)\TDMS2MAT\salida_excels\original"

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
