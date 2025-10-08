import os
import re
import pandas as pd
import numpy as np
import traceback
from openpyxl import load_workbook
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
        try:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except Exception:
            return None
    return None

def ask_start_date(min_date, max_date, prompt_func=None):
    """Pregunta al usuario desde qué fecha concatenar."""
    if prompt_func:
        return prompt_func(min_date, max_date)
    root = Tk()
    root.withdraw()
    while True:
        date_str = simpledialog.askstring(
            "Fecha de inicio",
            f"Ingrese la fecha desde la que desea concatenar (formato: DD.M.AA).\nRango disponible: {min_date.date()} a {max_date.date()}"
        )
        if date_str is None:
            root.destroy()
            raise Exception("Operación cancelada por el usuario.")
        try:
            date = datetime.strptime(date_str, "%d.%m.%y")
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


def concat_excels(excel_folder, concat_file, prompt_func=None, confirm_continue_func=None, log_func=print, ):
    """Función principal para concatenar excels."""
    # Buscar archivos disponibles
    all_files = [(extract_date_from_filename(f), f) for f in os.listdir(excel_folder)
                 if f.endswith(".xlsx") and not f.startswith("~$")]
    all_files = [(d, f) for d, f in all_files if d]
    if not all_files:
        log_func("ERROR: No hay archivos Excel válidos para concatenar.")
        return

    # Ordenar por fecha real
    all_files.sort(key=lambda x: x[0])
    min_date_tuple, max_date_tuple = all_files[0][0], all_files[-1][0]
    min_date = datetime(2000 + min_date_tuple[0], min_date_tuple[1], min_date_tuple[2])
    max_date = datetime(2000 + max_date_tuple[0], max_date_tuple[1], max_date_tuple[2])

    ciclo_inicial = 0
    rutas_existentes = set()
    fechas_existentes = set()
    last_valid_rows = {}

    # Si existe un concatenado previo, recuperar último estado
    if os.path.exists(concat_file):
        try:
            wb = load_workbook(concat_file, read_only=True)
            if "archivo" in wb.sheetnames:
                hoja_archivo = wb["archivo"]
                for row in hoja_archivo.iter_rows(min_row=2, values_only=True):
                    if len(row) > 3 and row[3]:
                        rutas_existentes.add(row[3])
                    if len(row) > 1 and row[1]:
                        fechas_existentes.add(row[1])
                ciclo_inicial = hoja_archivo.max_row - 1
            wb.close()

            xls_existing = pd.ExcelFile(concat_file)
            for sheet_name in xls_existing.sheet_names:
                if sheet_name.startswith("delta K"):
                    df_existing = xls_existing.parse(sheet_name)
                    if not df_existing.empty:
                        last_valid_row_df = df_existing[pd.to_numeric(
                            df_existing.get('Ciclos Acumulados'), errors='coerce'
                        ).notna()]
                        if not last_valid_row_df.empty:
                            last_valid_rows[sheet_name] = last_valid_row_df.iloc[[-1]].copy()
        except Exception as e:
            log_func(f"ADVERTENCIA: No se pudo leer el archivo concatenado existente '{concat_file}'. Se tratará como nuevo. Error: {e}")
            ciclo_inicial = 0
            rutas_existentes = set()
            fechas_existentes = set()
            last_valid_rows = {}

        files = [(d, f) for d, f in all_files if os.path.join(excel_folder, f) not in rutas_existentes]
    else:
        start_date_val = ask_start_date(min_date, max_date, prompt_func)
        if start_date_val is None:
            log_func("Concatenación cancelada por el usuario.")
            return
        if isinstance(start_date_val, datetime):
            start_date_tuple = (start_date_val.year - 2000, start_date_val.month, start_date_val.day)
        else:
            start_date_tuple = start_date_val
        files = [(d, f) for d, f in all_files if d >= start_date_tuple]

    if not files:
        log_func("No hay archivos nuevos para agregar.")
        return

    # Obtener rango completo de fechas
    fechas_rango = [x[0] for x in all_files if x[0] >= files[0][0] and x[0] <= files[-1][0]]
    fechas_archivos = {d: f for d, f in files}
    archivo_rows = []
    delta_sheets = {}
    ciclo_actual = 0
    # Para cada fecha en el rango
    for d in fechas_rango:
        if d in fechas_archivos:
            f = fechas_archivos[d]
            ruta = os.path.join(excel_folder, f)
            try:
                xls = pd.ExcelFile(ruta)
                fecha_str = f"{d[0]}.{d[1]}.{d[2]}"
                archivo_rows.append({
                    "": ciclo_inicial + ciclo_actual,
                    "Fecha": fecha_str,
                    "Archivo": f,
                    "Dirección Almacenamiento": ruta
                })
                for sheet in xls.sheet_names:
                    if sheet.startswith("delta K"):
                        df = xls.parse(sheet)
                        original_columns = df.columns.tolist()
                        ciclos_col = find_column_name(df, ['Ciclos', 'ciclos'])
                        dk_col = find_column_name(df, ['ΔK', 'delta K', 'dK'])
                        # Solo C1 y C2
                        paris_cols, a_final_cols = [], []
                        for i in range(2):
                            paris_col = f'C{i+1}(ΔK)^m{i+1}'
                            delta_a_col = f'Δa{i+1}'
                            a_final_header = f'C{i+1}={C[i]}'
                            df[paris_col] = C[i] * (pd.to_numeric(df.get(dk_col, 0), errors='coerce').fillna(0) ** m[i])
                            df[delta_a_col] = df[paris_col] * pd.to_numeric(df.get(ciclos_col, 0), errors='coerce').fillna(0)
                            df[a_final_header] = 100 + (df[delta_a_col].cumsum() * 1000)
                            paris_cols.extend([paris_col, delta_a_col])
                            a_final_cols.append(a_final_header)
                        # Recuperar ciclos acumulados previos
                        last_ciclos_acum = 0
                        if sheet in last_valid_rows and 'Ciclos Acumulados' in last_valid_rows[sheet].columns:
                            val = pd.to_numeric(last_valid_rows[sheet]['Ciclos Acumulados'].iloc[0], errors='coerce')
                            last_ciclos_acum = np.nan_to_num(val, nan=0.0)
                        if ciclos_col:
                            df['Ciclos Acumulados'] = pd.to_numeric(df[ciclos_col], errors='coerce').fillna(0).cumsum() + last_ciclos_acum
                        else:
                            df['Ciclos Acumulados'] = last_ciclos_acum
                        # Calcular días fraccionados
                        last_day_val = 0
                        if sheet in last_valid_rows and 'Dias' in last_valid_rows[sheet].columns:
                            val = pd.to_numeric(last_valid_rows[sheet]['Dias'].iloc[0], errors='coerce')
                            last_day_val = np.nan_to_num(val, nan=0.0)
                        N = len(df)
                        if N > 0:
                            df['Dias'] = last_day_val + (np.arange(1, N + 1) / N)
                        else:
                            df['Dias'] = last_day_val
                        # Reordenar columnas
                        final_order = [col for col in original_columns if col not in paris_cols + a_final_cols + ['Dias', 'Ciclos Acumulados']]
                        final_order.extend(paris_cols)
                        final_order.append('Dias')
                        final_order.extend(a_final_cols)
                        final_order.append('Ciclos Acumulados')
                        df = df[final_order]
                        df.insert(0, 'Fecha', [fecha_str] + [''] * (len(df) - 1))
                        if sheet not in delta_sheets: delta_sheets[sheet] = []
                        delta_sheets[sheet].append((df, ciclo_actual == 0 and not fechas_existentes))
                        last_valid_rows[sheet] = df.iloc[[-1]].copy()
                ciclo_actual += 1
            except Exception as e:
                log_func(f"Error procesando {ruta}: {e}")
                log_func(traceback.format_exc())
        else:
            # Día sin archivo: agregar fila vacía con valores acumulados constantes
            fecha_str = f"{d[0]}.{d[1]}.{d[2]}"
            archivo_rows.append({
                "": ciclo_inicial + ciclo_actual,
                "Fecha": fecha_str,
                "Archivo": "",
                "Dirección Almacenamiento": ""
            })
            for sheet in last_valid_rows:
                # Crear df vacío con valores acumulados constantes
                prev_row = last_valid_rows[sheet].copy()
                empty_row = prev_row.copy()
                for col in empty_row.columns:
                    if col not in ['Fecha', 'Ciclos Acumulados', 'Dias']:
                        empty_row[col] = ""
                empty_row['Fecha'] = fecha_str
                if sheet not in delta_sheets: delta_sheets[sheet] = []
                delta_sheets[sheet].append((empty_row, False))
            ciclo_actual += 1

    mode = 'a' if os.path.exists(concat_file) else 'w'
    if_sheet_exists = 'overlay' if mode == 'a' else None

    try:
        with pd.ExcelWriter(concat_file, engine="openpyxl", mode=mode, if_sheet_exists=if_sheet_exists) as writer:
            df_archivo_to_write = pd.DataFrame(archivo_rows)
            header = False if mode == 'a' and "archivo" in writer.sheets else True
            startrow = writer.sheets['archivo'].max_row if mode == 'a' and "archivo" in writer.sheets else 0
            df_archivo_to_write.to_excel(writer, sheet_name="archivo", index=False, header=header, startrow=startrow)

            for sheet, dfs in delta_sheets.items():
                df_to_write = pd.concat([d for d, _ in dfs], ignore_index=True)
                header = False if (mode == 'a' and sheet in writer.sheets) else True
                startrow = writer.sheets[sheet].max_row if (mode == 'a' and sheet in writer.sheets) else 0
                df_to_write.to_excel(writer, sheet_name=sheet, index=False, header=header, startrow=startrow)

        log_func(f"Concatenación completada. {len(files)} archivos procesados.")
    except Exception as e:
        log_func(f"Error al escribir en el archivo Excel: {e}")
        log_func(traceback.format_exc())
    return