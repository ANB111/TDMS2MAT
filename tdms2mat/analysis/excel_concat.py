"""Concatenación de excels de rainflow y cálculo de avance de fisuras (Ley de Paris).

Correcciones respecto al original (concat_excels.py):
- ``get_excel_files`` (función muerta) eliminada.
- ``confirm_continue_func`` eliminado de la firma (no se usaba).
- Las constantes de la Ley de Paris están agrupadas en ``PARIS_LAW`` (dict
  documentado) en lugar de estar enterradas en el medio de la lógica.
- El import de ``tkinter`` fue eliminado: este módulo es puramente de negocio;
  la dependencia de diálogo se inyecta opcionalmente vía ``prompt_func``.
- El nombre del archivo de salida coincide con el parámetro ``concat_file``
  cuando se lo pasa; si no, usa el nombre por defecto.
"""
from __future__ import annotations

import os
import re
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from openpyxl import load_workbook  # type: ignore[import]

# ---------------------------------------------------------------------------
# Constantes de la Ley de Paris
# ---------------------------------------------------------------------------
#: Parámetros materiales (C, m) para 5 sets de constantes.
#: Unidades: C en mm/ciclo/(MPa·√m)^m, m adimensional.
#: Referencia: calibración interna de laboratorio.
PARIS_LAW: List[Dict[str, float]] = [
    {"C": 2.40e-11, "m": 2.82},
    {"C": 3.20e-11, "m": 2.82},
    {"C": 9.55e-12, "m": 2.86},
    {"C": 7.87e-12, "m": 2.89},
    {"C": 7.56e-12, "m": 2.90},
]

C_ARRAY = np.array([p["C"] for p in PARIS_LAW])
M_ARRAY = np.array([p["m"] for p in PARIS_LAW])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_column_name(
    df: pd.DataFrame, possible_names: List[str]
) -> Optional[str]:
    """Devuelve la primera columna del DataFrame que coincida con una de las
    *possible_names*, o ``None`` si ninguna existe."""
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def extract_date_from_filename(filename: str) -> Optional[Tuple[int, int, int]]:
    """Extrae ``(YY, M, D)`` de nombres tipo ``25.7.1-u05.xlsx``."""
    match = re.match(r"(\d{2})\.(\d{1,2})\.(\d{1,2})", filename)
    if match:
        try:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except Exception:
            return None
    return None


def ask_start_date(
    min_date: Any,
    max_date: Any,
    prompt_func: Optional[Callable] = None,
) -> Optional[Any]:
    """Pide al usuario la fecha desde la que concatenar.

    Delega completamente al ``prompt_func`` proporcionado por la GUI.
    Si no se proporciona, lanza una excepción (este módulo no incluye Tkinter).

    Args:
        min_date: Fecha más antigua disponible.
        max_date: Fecha más reciente disponible.
        prompt_func: Función que recibe ``(min_date, max_date)`` y devuelve la
            fecha seleccionada por el usuario.

    Returns:
        La fecha de inicio seleccionada, o ``None`` si el usuario canceló.
    """
    if prompt_func is None:
        raise RuntimeError(
            "Se requiere un 'prompt_func' para solicitar la fecha de inicio al usuario. "
            "Pase una función que muestre un diálogo y devuelva la fecha."
        )
    return prompt_func(min_date, max_date)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def concat_excels(
    excel_folder: str,
    concat_file: str,
    prompt_func: Optional[Callable] = None,
    log_func: Optional[Callable[[str], None]] = None,
) -> None:
    """Concatena los excels diarios de rainflow y calcula avance de fisuras.

    Cuando ya existe un archivo de salida previo, solo agrega los días nuevos
    (modo incremental).

    Args:
        excel_folder: Carpeta con los .xlsx por día generados por MATLAB.
        concat_file: Ruta de salida para el archivo concatenado.
        prompt_func: Función callback ``(min_date, max_date) → fecha_inicio``.
            Requerida cuando no existe un concatenado previo.
        log_func: Función de logging.
    """
    log = log_func or print

    # Descubrir archivos disponibles
    all_files: List[Tuple[Tuple[int, int, int], str]] = [
        (d, f)
        for f in os.listdir(excel_folder)
        if f.endswith(".xlsx") and not f.startswith("~$")
        for d in [extract_date_from_filename(f)]
        if d is not None
    ]
    if not all_files:
        log("ERROR: No hay archivos Excel válidos para concatenar.")
        return

    all_files.sort(key=lambda x: x[0])
    min_date_t, max_date_t = all_files[0][0], all_files[-1][0]
    min_date_dt = datetime(2000 + min_date_t[0], min_date_t[1], min_date_t[2])
    max_date_dt = datetime(2000 + max_date_t[0], max_date_t[1], max_date_t[2])

    # Determinar el archivo de salida real
    output_path = concat_file if concat_file else os.path.join(
        excel_folder, "estimacion-avance-fisuras.xlsx"
    )

    ciclo_inicial = 0
    rutas_existentes: set = set()
    fechas_existentes: set = set()
    last_valid_rows: Dict[str, pd.DataFrame] = {}

    # Recuperar estado previo si existe
    if os.path.exists(output_path):
        try:
            wb = load_workbook(output_path, read_only=True)
            if "archivo" in wb.sheetnames:
                hoja = wb["archivo"]
                for row in hoja.iter_rows(min_row=2, values_only=True):
                    if len(row) > 3 and row[3]:
                        rutas_existentes.add(row[3])
                    if len(row) > 1 and row[1]:
                        fechas_existentes.add(row[1])
                ciclo_inicial = hoja.max_row - 1
            wb.close()

            with pd.ExcelFile(output_path) as xls_ex:
                for sheet_name in xls_ex.sheet_names:
                    if sheet_name.startswith("delta K"):
                        df_ex = xls_ex.parse(sheet_name)
                        if not df_ex.empty:
                            nums = pd.to_numeric(
                                df_ex.get("Ciclos Acumulados"), errors="coerce"
                            )
                            valid = df_ex[nums.notna()]
                            if not valid.empty:
                                last_valid_rows[sheet_name] = valid.iloc[[-1]].copy()
        except Exception as exc:
            log(f"ADVERTENCIA: No se pudo leer el concatenado previo: {exc}")
            ciclo_inicial = 0
            rutas_existentes = set()
            fechas_existentes = set()
            last_valid_rows = {}

        files = [
            (d, f)
            for d, f in all_files
            if os.path.join(excel_folder, f) not in rutas_existentes
        ]
    else:
        start_date_val = ask_start_date(min_date_dt, max_date_dt, prompt_func)
        if start_date_val is None:
            log("Concatenación cancelada por el usuario.")
            return
        if isinstance(start_date_val, datetime):
            start_tuple = (
                start_date_val.year - 2000,
                start_date_val.month,
                start_date_val.day,
            )
        else:
            start_tuple = start_date_val
        files = [(d, f) for d, f in all_files if d >= start_tuple]

    if not files:
        log("No hay archivos nuevos para agregar.")
        return

    # Procesamiento por día / hoja
    fechas_archivos: Dict[Tuple[int, int, int], str] = {d: f for d, f in files}
    archivo_rows: List[Dict] = []
    delta_sheets: Dict[str, List] = {}
    ciclo_actual = 0

    fecha_inicio = datetime(2000 + files[0][0][0], files[0][0][1], files[0][0][2])
    fecha_fin = datetime(2000 + files[-1][0][0], files[-1][0][1], files[-1][0][2])
    dias_totales = (fecha_fin - fecha_inicio).days + 1
    fechas_rango = [fecha_inicio + timedelta(days=i) for i in range(dias_totales)]
    fechas_rango_tuplas = [(f.year - 2000, f.month, f.day) for f in fechas_rango]

    for d_tuple, d_dt in zip(fechas_rango_tuplas, fechas_rango):
        fecha_str = f"{d_tuple[0]}.{d_tuple[1]}.{d_tuple[2]}"

        if d_tuple in fechas_archivos:
            f_name = fechas_archivos[d_tuple]
            ruta = os.path.join(excel_folder, f_name)
            try:
                archivo_rows.append(
                    {
                        "": ciclo_inicial + ciclo_actual,
                        "Fecha": fecha_str,
                        "Archivo": f_name,
                        "Dirección Almacenamiento": ruta,
                    }
                )
                with pd.ExcelFile(ruta) as xls:
                    for sheet in xls.sheet_names:
                        if not sheet.startswith("delta K"):
                            continue
                        df = xls.parse(sheet)
                        original_columns = df.columns.tolist()
                        ciclos_col = find_column_name(df, ["Ciclos", "ciclos"])
                        dk_col = find_column_name(df, ["ΔK", "delta K", "dK"])

                        paris_cols: List[str] = []
                        a_final_cols: List[str] = []

                        for i, (c_val, m_val) in enumerate(
                            zip(C_ARRAY, M_ARRAY)
                        ):
                            paris_col = f"C{i+1}(ΔK)^m{i+1}"
                            delta_a_col = f"Δa{i+1}"
                            a_final_header = f"C{i+1}={c_val}"

                            dk_numeric = pd.to_numeric(
                                df.get(dk_col, 0), errors="coerce"
                            ).fillna(0)
                            ciclos_numeric = pd.to_numeric(
                                df.get(ciclos_col, 0), errors="coerce"
                            ).fillna(0)

                            df[paris_col] = c_val * (dk_numeric**m_val)
                            df[delta_a_col] = df[paris_col] * ciclos_numeric

                            # a_final solo para C1 y C2
                            if i < 2:
                                prev_a = 100.0
                                if (
                                    sheet in last_valid_rows
                                    and a_final_header
                                    in last_valid_rows[sheet].columns
                                ):
                                    val = pd.to_numeric(
                                        last_valid_rows[sheet][a_final_header].iloc[0],
                                        errors="coerce",
                                    )
                                    prev_a = float(np.nan_to_num(val, nan=100.0))
                                df[a_final_header] = prev_a + (
                                    df[delta_a_col].cumsum() * 1000
                                )
                                a_final_cols.append(a_final_header)

                            paris_cols.extend([paris_col, delta_a_col])

                        # Ciclos acumulados
                        last_ciclos = 0.0
                        if (
                            sheet in last_valid_rows
                            and "Ciclos Acumulados" in last_valid_rows[sheet].columns
                        ):
                            val = pd.to_numeric(
                                last_valid_rows[sheet]["Ciclos Acumulados"].iloc[0],
                                errors="coerce",
                            )
                            last_ciclos = float(np.nan_to_num(val, nan=0.0))

                        if ciclos_col:
                            df["Ciclos Acumulados"] = (
                                pd.to_numeric(df[ciclos_col], errors="coerce")
                                .fillna(0)
                                .cumsum()
                                + last_ciclos
                            )
                        else:
                            df["Ciclos Acumulados"] = last_ciclos

                        # Días fraccionados
                        last_day = 0.0
                        if (
                            sheet in last_valid_rows
                            and "Dias" in last_valid_rows[sheet].columns
                        ):
                            val = pd.to_numeric(
                                last_valid_rows[sheet]["Dias"].iloc[0], errors="coerce"
                            )
                            last_day = float(np.nan_to_num(val, nan=0.0))

                        n = len(df)
                        if n > 0:
                            if sheet in delta_sheets and delta_sheets[sheet]:
                                last_df, _ = delta_sheets[sheet][-1]
                                last_dias = pd.to_numeric(
                                    last_df["Dias"].iloc[-1], errors="coerce"
                                )
                                df["Dias"] = float(last_dias) + (
                                    np.arange(1, n + 1) / n
                                )
                            else:
                                df["Dias"] = last_day + (np.arange(1, n + 1) / n)
                        else:
                            df["Dias"] = last_day

                        # Reordenar columnas
                        final_order = [
                            c
                            for c in original_columns
                            if c
                            not in paris_cols
                            + a_final_cols
                            + ["Dias", "Ciclos Acumulados"]
                        ]
                        final_order += paris_cols + ["Dias"] + a_final_cols + ["Ciclos Acumulados"]
                        df = df[final_order]
                        df.insert(
                            0,
                            "Fecha",
                            [fecha_str] + [""] * (len(df) - 1),
                        )

                        if sheet not in delta_sheets:
                            delta_sheets[sheet] = []
                        delta_sheets[sheet].append(
                            (df, ciclo_actual == 0 and not fechas_existentes)
                        )
                        last_valid_rows[sheet] = df.iloc[[-1]].copy()

                ciclo_actual += 1

            except Exception as exc:
                log(f"Error procesando '{ruta}': {exc}")
                log(traceback.format_exc())
        else:
            # Día sin archivo
            archivo_rows.append(
                {
                    "": ciclo_inicial + ciclo_actual,
                    "Fecha": fecha_str,
                    "Archivo": "",
                    "Dirección Almacenamiento": "",
                }
            )
            for sheet, prev_row in last_valid_rows.items():
                empty_row = prev_row.copy()
                empty_row["Fecha"] = fecha_str

                if "Dias" in prev_row.columns:
                    if sheet in delta_sheets and delta_sheets[sheet]:
                        last_df, _ = delta_sheets[sheet][-1]
                        last_dias = pd.to_numeric(
                            last_df["Dias"].iloc[-1], errors="coerce"
                        )
                        empty_row["Dias"] = int(np.ceil(float(last_dias))) + 1
                    else:
                        last_day_val = pd.to_numeric(
                            prev_row["Dias"].iloc[0], errors="coerce"
                        )
                        empty_row["Dias"] = int(np.ceil(float(last_day_val))) + 1

                for col in empty_row.columns:
                    if col not in ["Fecha", "Dias", "Ciclos Acumulados"] and not (
                        col.startswith("C1=") or col.startswith("C2=")
                    ):
                        empty_row[col] = 0

                if sheet not in delta_sheets:
                    delta_sheets[sheet] = []
                delta_sheets[sheet].append((empty_row, False))
            ciclo_actual += 1

    # Escribir Excel
    mode = "a" if os.path.exists(output_path) else "w"
    if_sheet_exists = "overlay" if mode == "a" else None

    try:
        kwargs: dict = {"engine": "openpyxl", "mode": mode}
        if if_sheet_exists:
            kwargs["if_sheet_exists"] = if_sheet_exists

        with pd.ExcelWriter(output_path, **kwargs) as writer:
            df_archivo = pd.DataFrame(archivo_rows)
            header = not (mode == "a" and "archivo" in writer.sheets)
            startrow = (
                writer.sheets["archivo"].max_row
                if mode == "a" and "archivo" in writer.sheets
                else 0
            )
            df_archivo.to_excel(
                writer,
                sheet_name="archivo",
                index=False,
                header=header,
                startrow=startrow,
            )

            for sheet, dfs in delta_sheets.items():
                df_write = pd.concat([d for d, _ in dfs], ignore_index=True)
                header = not (mode == "a" and sheet in writer.sheets)
                startrow = (
                    writer.sheets[sheet].max_row
                    if mode == "a" and sheet in writer.sheets
                    else 0
                )
                df_write.to_excel(
                    writer,
                    sheet_name=sheet,
                    index=False,
                    header=header,
                    startrow=startrow,
                )

        log(
            f"Concatenación completada. {len(files)} archivo(s) procesados. "
            f"Salida: {output_path}"
        )
    except Exception as exc:
        log(f"Error al escribir el Excel de salida: {exc}")
        log(traceback.format_exc())
