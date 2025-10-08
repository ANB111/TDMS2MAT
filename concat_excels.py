import os
import re
import pandas as pd
import numpy as np
import traceback
from openpyxl import load_workbook, Workbook
from tkinter import simpledialog, Tk, messagebox
from datetime import datetime

# Constantes de Paris
C = np.array([2.4e-11, 3.2e-11, 9.55e-12, 7.87e-12, 7.56e-12])
m = np.array([2.82, 2.82, 2.86, 2.89, 2.90])

def find_column_name(df, possible_names):
    """Encuentra el nombre de una columna en un DataFrame a partir de una lista de nombres posibles."""
    for name in possible_names:
        if name in df.columns:
            return name
    return None

def extract_date_from_filename(filename):
    # Busca patrones tipo 25.7.1-u05.xlsx o 25.9.4-u05.xlsx
    match = re.match(r"(\d{2})\.(\d{1,2})\.(\d{1,2})", filename)
    if match:
        # Devuelve tupla (anio, mes, dia) para orden y formato
        try:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except Exception:
            return None
    return None

def ask_start_date(min_date, max_date, prompt_func=None):
    """
    prompt_func: función opcional para pedir la fecha al usuario (para integración con GUI)
    """
    if prompt_func:
        return prompt_func(min_date, max_date)
    root = Tk()
    root.withdraw()
    while True:
        date_str = simpledialog.askstring(
            "Fecha de inicio",
            f"Ingrese la fecha desde la que desea concatenar (formato:DD.M.AA).\nRango disponible: {min_date.date()} a {max_date.date()}"
        )
        if date_str is None:
            root.destroy()
            raise Exception("Operación cancelada por el usuario.")
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date < min_date:
                messagebox.showinfo("Info", f"La fecha ingresada es anterior al archivo más antiguo. Se usará {min_date.date()}.")
                return min_date
            elif date > max_date:
                messagebox.showerror("Error", "La fecha ingresada es posterior al archivo más reciente.")
            else:
                return date
        except Exception:
            messagebox.showerror("Error", "Formato de fecha inválido. Use DD.M.AA.")

def get_excel_files(folder, start_date):
    files = []
    for f in sorted(os.listdir(folder)):
        if f.endswith(".xlsx") and not f.startswith("~$"):
            date = extract_date_from_filename(f)
            if date and date >= start_date:
                files.append((date, f))
    return files


def concat_excels(excel_folder, concat_file, prompt_func=None, log_func=print, confirm_continue_func=None):
    """
    Función principal para concatenar excels.
    - excel_folder: carpeta donde están los excels individuales
    - concat_file: ruta del archivo excel concatenado
    - prompt_func: función para pedir fecha al usuario (opcional, para integración con GUI)
    - log_func: función para loguear mensajes (por defecto print)
    """
    # Buscar archivos
    all_files = [(extract_date_from_filename(f), f) for f in os.listdir(excel_folder)
                 if f.endswith(".xlsx") and not f.startswith("~$")]
    all_files = [(d, f) for d, f in all_files if d]
    if not all_files:
        log_func("ERROR: No hay archivos Excel válidos para concatenar.")
        return
    # Ordenar por fecha real (anio, mes, dia)
    all_files.sort(key=lambda x: x[0])
    min_date, max_date = all_files[0][0], all_files[-1][0]


    # Determinar archivos a agregar y ciclo inicial
    ciclo_inicial = 0
    rutas_existentes = set()
    fechas_existentes = set()
    if os.path.exists(concat_file):
        wb = load_workbook(concat_file, read_only=True)
        if "archivo" in wb.sheetnames:
            hoja_archivo = wb["archivo"]
            for row in hoja_archivo.iter_rows(min_row=2, values_only=True):
                rutas_existentes.add(row[3])  # Dirección Almacenamiento
                fechas_existentes.add(row[1]) # Fecha en formato 25.7.15
            ciclo_inicial = hoja_archivo.max_row - 1  # asume que no hay filas vacías
        wb.close()
        files = [(d, f) for d, f in all_files if os.path.join(excel_folder, f) not in rutas_existentes]
    else:
        # Si no existe, preguntar fecha de inicio
        start_date = ask_start_date(min_date, max_date, prompt_func)
        if start_date is None:
            log_func("Concatenación cancelada por el usuario.")
            return
        # start_date es una tupla (anio, mes, dia)
        files = [(d, f) for d, f in all_files if d >= start_date]

    if not files:
        log_func("No hay archivos nuevos para agregar.")
        return

    # Validar que los días sean consecutivos
    files_sorted = sorted(files, key=lambda x: x[0])
    fechas = [d for d, _ in files_sorted]
    if fechas:
        # Si ya hay fechas existentes, tomar la última fecha agregada
        if fechas_existentes:
            try:
                # Convertir formato 25.7.15 a tupla (25,7,15)
                last_fecha = max([tuple(map(int, f.split('.'))) for f in fechas_existentes if isinstance(f, str)])
            except Exception:
                last_fecha = None
        else:
            last_fecha = None
        # Comprobar saltos
        prev = last_fecha
        from datetime import date
        def to_date(t):
            return date(2000+t[0], t[1], t[2])
        for idx, fecha in enumerate(fechas):
            if prev is not None:
                delta = (to_date(fecha) - to_date(prev)).days
                if delta > 1:
                    msg = f"Se detectó un salto de {delta-1} día(s) entre {prev[0]}.{prev[1]}.{prev[2]} y {fecha[0]}.{fecha[1]}.{fecha[2]} al agregar archivos. ¿Desea continuar?"
                    log_func(msg)
                    if confirm_continue_func:
                        if not confirm_continue_func(msg):
                            log_func("Concatenación cancelada por el usuario debido a salto de días.")
                            return
                    else:
                        log_func("No se puede continuar sin confirmación del usuario. Proceso cancelado.")
                        return
            prev = fecha

    # Concatenar datos
    archivo_rows = []
    delta_sheets = {}
    ciclo = 0
    for d, f in files_sorted:
        ruta = os.path.join(excel_folder, f)
        try:
            xls = pd.ExcelFile(ruta)
            df_archivo = xls.parse("Conteo Rainflow")
            # Fecha en formato 25.7.15
            fecha_str = f"{d[0]}.{d[1]}.{d[2]}"
            archivo_rows.append({
                "": ciclo,  # Primera columna vacía en encabezado, pero contiene el índice
                "Fecha": fecha_str,
                "Archivo": f,
                "Dirección Almacenamiento": ruta
            })
            # Para cada hoja delta K (sin columnas extra)
            for sheet in xls.sheet_names:
                if sheet.startswith("delta K"):
                    df = xls.parse(sheet)

                    # --- BÚSQUEDA ROBUSTA DE COLUMNAS ---
                    ciclos_col_name = find_column_name(df, ['Ciclos', 'ciclos'])
                    delta_k_col_name = find_column_name(df, ['ΔK', 'delta K', 'd'])

                    # Verificar que las columnas necesarias existen
                    if not all([ciclos_col_name, delta_k_col_name]):
                        log_func(f"ADVERTENCIA: La hoja '{sheet}' en el archivo '{f}' no contiene una columna de Ciclos o Delta K. Omitiendo cálculos.")
                        fecha_col = [fecha_str] + [None]*(len(df)-1)
                        df.insert(0, 'Fecha', fecha_col)
                        if sheet not in delta_sheets:
                            delta_sheets[sheet] = []
                        delta_sheets[sheet].append((df, ciclo == 0))
                        continue

                    # --- INICIO DE CÁLCULOS NUEVOS ---
                    original_columns = df.columns.tolist()

                    # Asegurar tipos de datos
                    df[ciclos_col_name] = pd.to_numeric(df[ciclos_col_name], errors='coerce').fillna(0)
                    df[delta_k_col_name] = pd.to_numeric(df[delta_k_col_name], errors='coerce').fillna(0)

                    # Calcular suma acumulada (corregido para la primera ejecución)
                    ciclos_acumulados = df[ciclos_col_name].cumsum()
                    if sheet in last_valid_rows and 'Ciclos Acumulados' in last_valid_rows[sheet].columns:
                        ciclos_acumulados += last_valid_rows[sheet]['Ciclos Acumulados'].iloc[0]

                    # Listas para mantener el orden
                    paris_cols, a_final_cols = [], []

                    # Calcular columnas de Paris y a_final
                    for i in range(len(C)):
                        paris_col = f'C{i+1}(ΔK)^m{i+1}'
                        delta_a_col = f'Δa{i+1}'
                        a_final_header = f'C{i+1}={C[i]}'

                        df[paris_col] = C[i] * (df[delta_k_col_name] ** m[i])
                        df[delta_a_col] = df[paris_col] * ciclos_acumulados
                        df[a_final_header] = 100 + (df[delta_a_col] * 1000)
                        
                        paris_cols.extend([paris_col, delta_a_col])
                        a_final_cols.append(a_final_header)
                    
                    # Calcular la columna Dias
                    N = len(df)
                    if N > 0:
                        current_day_integer = ciclo_inicial + ciclo
                        df['Dias'] = current_day_integer + (np.arange(1, N + 1) / N)
                    else:
                        df['Dias'] = None

                    df['Ciclos Acumulados'] = ciclos_acumulados

                    # Definir el orden final de las columnas
                    final_columns = original_columns + paris_cols + ['Dias'] + a_final_cols + ['Ciclos Acumulados']
                    df = df[final_columns]

                    # Insertar columna 'Fecha' al inicio
                    fecha_col = [fecha_str] + [None]*(len(df)-1)
                    df.insert(0, 'Fecha', fecha_col)
                    if sheet not in delta_sheets:
                        delta_sheets[sheet] = []
                    
                    is_first_ever_write = (ciclo == 0 and not fechas_existentes)
                    delta_sheets[sheet].append((df, is_first_ever_write))
                    last_valid_rows[sheet] = df.iloc[[-1]].copy()
            ciclo += 1
        except Exception as e:
            log_func(f"Error procesando {ruta}: {e}")
            log_func(traceback.format_exc())

    # Escribir al archivo concatenado
    from openpyxl.styles import Font
    if os.path.exists(concat_file):
        with pd.ExcelWriter(concat_file, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
            # Hoja archivo
            df_archivo = pd.DataFrame(archivo_rows, columns=["", "Fecha", "Archivo", "Dirección Almacenamiento"])
            df_archivo.to_excel(writer, sheet_name="archivo", index=False, header=False, startrow=writer.sheets["archivo"].max_row)
            # Hojas delta (con columna Fecha)
            for sheet, dfs in delta_sheets.items():
                df_list = [df for df, _ in dfs]
                df = pd.concat(df_list, ignore_index=True)
                startrow = writer.sheets[sheet].max_row
                df.to_excel(writer, sheet_name=sheet, index=False, header=False, startrow=startrow)
        # Formato negrita y subrayado para la celda de fecha si ciclo==0
        wb = load_workbook(concat_file)
        for sheet, dfs in delta_sheets.items():
            ws = wb[sheet]
            row_offset = ws.max_row - sum(len(df) for df, _ in dfs) + 1
            for df, is_ciclo0 in dfs:
                if is_ciclo0:
                    ws[f'A{row_offset}'].font = Font(bold=True, underline="single")
                row_offset += len(df)
        wb.save(concat_file)
    else:
        with pd.ExcelWriter(concat_file, engine="openpyxl") as writer:
            pd.DataFrame(archivo_rows, columns=["", "Fecha", "Archivo", "Dirección Almacenamiento"]).to_excel(writer, sheet_name="archivo", index=False)
            for sheet, dfs in delta_sheets.items():
                df_list = [df for df, _ in dfs]
                df = pd.concat(df_list, ignore_index=True)
                df.to_excel(writer, sheet_name=sheet, index=False)
        # Formato negrita y subrayado para la celda de fecha si ciclo==0
        wb = load_workbook(concat_file)
        for sheet, dfs in delta_sheets.items():
            ws = wb[sheet]
            row_offset = 2  # 1-based, primera fila después del header
            for df, is_ciclo0 in dfs:
                if is_ciclo0:
                    ws[f'A{row_offset}'].font = Font(bold=True, underline="single")
                row_offset += len(df)
        wb.save(concat_file)
    log_func(f"Concatenación completada. Archivos agregados: {len(files)}")

if __name__ == "__main__":
    excel_folder = input("Carpeta de excels de salida: ").strip()
    concat_file = os.path.join(excel_folder, "concatenado.xlsx")
    concat_excels(excel_folder, concat_file)
