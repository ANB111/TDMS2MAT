"""Conversión de CSV diarios a archivos MAT (scipy.io.savemat).

Correcciones respecto al original (mat_utils.py):
- Guarda los **nombres de columna** en ``channel_names`` dentro del .mat, de
  modo que el script MATLAB ya no depende de índices numéricos ciegos.
- ``decimal`` es consistente con el ``csv_processor`` (ambos usan ``.`` por
  defecto; configurable vía parámetro).
- Los CSV de días **completos** se eliminan tras la conversión.
- Los CSV ``_temp`` (días incompletos) se dejan intactos: el orquestador los
  mueve a la carpeta de estado persistente para el próximo run.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.io import savemat  # type: ignore[import]


def csv_to_mat(
    input_folder: str,
    output_folder: str,
    unidad: str = "05",
    procesar_incompleto: bool = False,
    decimal: str = ".",
    log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Convierte todos los CSV diarios de *input_folder* a archivos MAT.

    Formato del .mat generado:
    - ``time_epoch`` — vector float64 con el tiempo UNIX (segundos desde 1970).
    - ``data`` — matriz float64 con las columnas numéricas (sin la columna Time).
    - ``channel_names`` — array de strings con los nombres originales de las
      columnas numéricas (permite referenciarlas por nombre en MATLAB).

    Args:
        input_folder: Carpeta con los CSV generados por :mod:`csv_processor`.
        output_folder: Carpeta destino de los .mat.
        unidad: Sufijo de unidad para el nombre de archivo (ej. ``"05"``).
        procesar_incompleto: Si ``True`` incluye archivos ``_temp.csv``.
        decimal: Separador decimal de los CSV (debe coincidir con el usado al
            escribirlos; default ``"."``.
        log_callback: Función de logging.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    if not os.path.exists(input_folder):
        log(f"[CSV→MAT] La carpeta de entrada '{input_folder}' no existe.")
        return

    os.makedirs(output_folder, exist_ok=True)

    csv_files = [
        f
        for f in os.listdir(input_folder)
        if f.endswith(".csv")
        and (procesar_incompleto or "_temp" not in f)
    ]

    if not csv_files:
        log(f"[CSV→MAT] No se encontraron CSV en '{input_folder}'.")
        return

    log(f"[CSV→MAT] Convirtiendo {len(csv_files)} archivo(s)...")

    for csv_file in csv_files:
        output_name = csv_file.replace("_temp", "")
        input_path = os.path.join(input_folder, csv_file)
        date_part = os.path.splitext(output_name)[0].split("-")[0]
        output_path = os.path.join(output_folder, f"{date_part}-u{unidad}.mat")

        try:
            data = pd.read_csv(input_path, delimiter=";", decimal=decimal)

            if "Time" not in data.columns:
                log(f"[CSV→MAT] '{csv_file}' omitido: falta columna 'Time'.")
                continue

            data["Time"] = pd.to_datetime(data["Time"], errors="coerce")
            if data["Time"].isnull().all():
                log(f"[CSV→MAT] '{csv_file}' omitido: errores en conversión de fechas.")
                continue

            data["Time_epoch"] = (
                data["Time"] - pd.Timestamp("1970-01-01")
            ) / pd.Timedelta("1s")

            # Columnas numéricas (todo excepto Time y Time_epoch)
            numeric_cols = [
                c for c in data.columns if c not in ("Time", "Time_epoch")
            ]

            mat_data = {
                "time_epoch": data["Time_epoch"].values.astype(np.float64),
                "data": data[numeric_cols].values.astype(np.float64),
                # Metadato clave: nombres de columnas → MATLAB no necesita
                # usar índices ciegos.
                "channel_names": np.array(numeric_cols, dtype="U100"),
            }

            savemat(output_path, mat_data)
            log(
                f"[CSV→MAT] {csv_file} → {os.path.basename(output_path)} "
                f"({len(numeric_cols)} canales)"
            )

            # Sólo eliminar CSVs de días completos.
            # Los _temp.csv (días incompletos) los gestiona el orquestador:
            # los mueve a la carpeta de estado persistente para el próximo run.
            if "_temp" not in csv_file:
                os.remove(input_path)
                log(f"[CSV→MAT] CSV eliminado: {csv_file}")

        except Exception as exc:
            log(f"[CSV→MAT] Error procesando '{csv_file}': {exc}")
