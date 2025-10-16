"""CLI robusta para convertir archivos ``.dat`` en archivos ``.mat`` compatibles con MATLAB.

El script intenta detectar automáticamente el formato del ``.dat``: CSV con distintos
delimitadores/encodings o binarios de ``float64`` con múltiples canales. Ofrece una interfaz
de línea de comandos e interfaz interactiva y puede reconstruir el vector de tiempo a partir
de una frecuencia de muestreo proporcionada manualmente.
"""

from __future__ import annotations


import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.io import savemat


DEFAULT_UNIT = "05"
DEFAULT_INPUT_PATH = (
    r"C:\Users\BECARIO 8\Documents\TDMS2MAT\salida"
)
DEFAULT_OUTPUT_PATH = (
    r"C:\Users\BECARIO 8\Documents\TDMS2MAT\salida\MAT"
)
FALLBACK_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "salida"
TIME_COLUMN_CANDIDATES = {"time", "timestamp", "fecha", "date", "datetime"}
CSV_READ_ATTEMPTS = [
    (";", ","),
    (";", "."),
    (",", "."),
    ("\t", "."),
    (None, ","),
    (None, "."),
]
CSV_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
_BINARY_PROBE_BYTES = 2048
_DEFAULT_BINARY_COLUMN_NAMES = [
    "Potencia",
    "Paletas",
    "Alabes",
    "Pres_Abr_Pal",
    "Pres_Cerr_Pal",
    "Pres_Abr_Alab",
    "Pres_Cerr_Alab",
    "Cont_Potencia",
    "Consigna_Pal",
    "Consigna_Pot",
    "Consigna_Alab",
    "Salto_Reg",
    "Velocidad",
    "Frecuencia",
    "ModoPotCon",
]


@dataclass
class Measurement:
    """Contenedor en memoria para los datos numéricos de un archivo ``.dat``."""

    data: np.ndarray
    column_names: list[str]
    time_epoch: Optional[np.ndarray] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_mat_payload(self, *, time_override: Optional[np.ndarray] = None) -> dict[str, np.ndarray]:
        """Genera el diccionario listo para ``savemat`` respetando longitudes y tipos."""

        data_array = np.asarray(self.data, dtype=np.float64)
        payload: dict[str, np.ndarray] = {"data": data_array}

        time_data = self.time_epoch if time_override is None else time_override
        if time_data is not None:
            time_array = np.asarray(time_data, dtype=np.float64)
            if time_array.shape[0] != data_array.shape[0]:
                min_len = min(time_array.shape[0], data_array.shape[0])
                payload["data"] = data_array[:min_len]
                time_array = time_array[:min_len]
            payload["time_epoch"] = time_array

        if self.column_names:
            payload["column_names"] = np.asarray(self.column_names, dtype=object)

        return payload


def _log(message: str, *, verbose: bool) -> None:
    if verbose:
        print(message)


def _is_probably_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(_BINARY_PROBE_BYTES)
    except OSError:
        return False
    if not chunk:
        return False
    return b"\x00" in chunk


def _read_dat_dataframe(filepath: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Intenta leer el ``.dat`` como CSV probando varias combinaciones comunes."""

    errors: list[str] = []

    for encoding in CSV_ENCODINGS:
        for delimiter, decimal in CSV_READ_ATTEMPTS:
            try:
                read_kwargs: dict[str, Any] = {
                    "decimal": decimal,
                    "encoding": encoding,
                    "engine": "python",
                }
                if delimiter is not None:
                    read_kwargs["sep"] = delimiter
                try:
                    df = pd.read_csv(filepath, on_bad_lines="skip", **read_kwargs)
                except TypeError:  # pandas < 1.3 no soporta on_bad_lines
                    df = pd.read_csv(filepath, **read_kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(
                    f"enc='{encoding}' sep='{delimiter or 'auto'}' dec='{decimal}': {exc}"
                )
                continue

            if df.empty:
                continue

            df = df.dropna(axis=1, how="all")
            if df.empty:
                continue

            metadata = {
                "encoding": encoding,
                "delimiter": delimiter or "auto",
                "decimal": decimal,
                "format": "csv",
            }
            return df, metadata

    error_context = "; ".join(errors[-5:]) if errors else "Formato desconocido"
    raise ValueError(
        f"No se pudo interpretar el archivo como texto delimitado. Últimos intentos: {error_context}"
    )


def _default_binary_column_names(num_channels: int) -> list[str]:
    if num_channels <= len(_DEFAULT_BINARY_COLUMN_NAMES):
        return _DEFAULT_BINARY_COLUMN_NAMES[:num_channels]
    return [f"channel_{idx+1}" for idx in range(num_channels)]


def _select_channel_count(total_values: int, n_channels_hint: Optional[int]) -> int:
    if n_channels_hint and n_channels_hint > 0 and total_values % n_channels_hint == 0:
        return n_channels_hint

    preferred = [
        len(_DEFAULT_BINARY_COLUMN_NAMES),
        16,
        15,
        14,
        12,
        10,
        8,
    ]
    for candidate in preferred:
        if candidate > 0 and total_values % candidate == 0:
            return candidate

    upper_bound = min(128, total_values)
    for candidate in range(2, upper_bound + 1):
        if total_values % candidate == 0:
            return candidate

    return total_values


def _read_binary_dat(filepath: Path, n_channels_hint: Optional[int]) -> Measurement:
    raw_data = np.fromfile(filepath, dtype="<f8")
    if raw_data.size == 0:
        raise ValueError("El archivo binario no contiene datos.")

    channels = _select_channel_count(raw_data.size, n_channels_hint)
    rows = raw_data.size // channels
    trimmed = raw_data[: rows * channels]
    # Los archivos binarios están guardados con cada canal completo de forma secuencial,
    # por lo que reconstruimos la matriz utilizando orden de columnas (Fortran).
    data_matrix = trimmed.reshape(channels, rows).T

    measurement = Measurement(
        data=data_matrix,
        column_names=_default_binary_column_names(channels),
        time_epoch=None,
        metadata={
            "format": "binary-float64",
            "channels_detected": channels,
            "rows": rows,
            "source": str(filepath),
        },
    )

    if n_channels_hint and channels != n_channels_hint:
        measurement.metadata["channel_count_expected"] = n_channels_hint

    return measurement


def _extract_time_epoch(series: pd.Series) -> tuple[Optional[np.ndarray], dict[str, Any]]:
    metadata: dict[str, Any] = {}

    if pd.api.types.is_datetime64_any_dtype(series):
        datetime_series = series
    else:
        datetime_series = pd.to_datetime(series, errors="coerce", dayfirst=True, utc=False)

    if datetime_series.notna().any():
        epoch = (datetime_series - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s")
        metadata["time_source"] = "datetime"
        return epoch.to_numpy(dtype=np.float64), metadata

    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.notna().any():
        metadata["time_source"] = "numeric"
        return numeric_series.to_numpy(dtype=np.float64), metadata

    metadata["time_source"] = "absent"
    return None, metadata


def _dataframe_to_measurement(
    df: pd.DataFrame,
    *,
    n_channels_hint: Optional[int] = None,
) -> Measurement:
    metadata: dict[str, Any] = {}

    time_column = next(
        (col for col in df.columns if col.strip().lower() in TIME_COLUMN_CANDIDATES),
        None,
    )

    time_epoch: Optional[np.ndarray] = None
    if time_column is not None:
        metadata["time_column"] = time_column
        time_epoch, time_metadata = _extract_time_epoch(df[time_column])
        metadata.update({f"time_{k}": v for k, v in time_metadata.items()})
        df = df.drop(columns=[time_column])

    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    numeric_df = numeric_df.dropna(axis=1, how="all")

    if numeric_df.empty:
        raise ValueError("No se encontraron columnas numéricas en el archivo.")

    valid_rows = ~numeric_df.isna().all(axis=1)
    if valid_rows.sum() == 0:
        raise ValueError("Todas las filas contienen valores no numéricos válidos.")

    numeric_df = numeric_df.loc[valid_rows]
    if time_epoch is not None:
        time_epoch = time_epoch[valid_rows.to_numpy()]

    column_names = numeric_df.columns.tolist()
    data_matrix = numeric_df.to_numpy(dtype=np.float64, copy=False)

    measurement = Measurement(
        data=data_matrix,
        column_names=column_names,
        time_epoch=time_epoch,
        metadata=metadata,
    )

    if n_channels_hint:
        measurement.metadata["channel_count_detected"] = measurement.data.shape[1]
        measurement.metadata["channel_count_expected"] = n_channels_hint

    return measurement


def load_measurement_file(filepath: str, n_channels_hint: int | None = None) -> Measurement:
    """Lee un archivo ``.dat`` y devuelve un :class:`Measurement` listo para guardar."""

    path = Path(filepath)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo '{filepath}'.")

    if _is_probably_binary(path):
        return _read_binary_dat(path, n_channels_hint)

    try:
        dataframe, read_metadata = _read_dat_dataframe(path)
    except ValueError as csv_error:
        try:
            return _read_binary_dat(path, n_channels_hint)
        except Exception as binary_error:  # pylint: disable=broad-except
            raise ValueError(
                f"No se pudo interpretar el archivo ni como texto delimitado ni como binario: {csv_error}"
            ) from binary_error

    measurement = _dataframe_to_measurement(
        dataframe,
        n_channels_hint=n_channels_hint,
    )
    measurement.metadata.update(read_metadata)
    measurement.metadata["source"] = str(path)

    return measurement


def _infer_output_name(dat_filename: str, unidad: str) -> str:
    base_name = os.path.splitext(dat_filename)[0]
    if "-" in base_name:
        date_part = base_name.split("-")[0]
        return f"{date_part}-u{unidad}.mat"
    return f"{base_name}.mat"


def convert_dat_to_mat(
    input_folder: str,
    output_folder: str,
    unidad: str = DEFAULT_UNIT,
    sample_rate: Optional[float] = None,
    n_channels_hint: Optional[int] = None,
    verbose: bool = True,
) -> None:
    """Convierte todos los archivos ``.dat`` de ``input_folder`` a ``.mat``."""

    input_path = Path(input_folder)
    output_path = Path(output_folder)

    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"La carpeta de entrada '{input_folder}' no existe o no es válida.")

    output_path.mkdir(parents=True, exist_ok=True)

    dat_files = sorted(
        f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() == ".dat"
    )

    if not dat_files:
        _log(f"[DAT2MAT] No se encontraron archivos .dat en '{input_folder}'.", verbose=verbose)
        return

    _log(f"[DAT2MAT] Procesando {len(dat_files)} archivo(s)...", verbose=verbose)

    processed = 0
    skipped = 0

    for dat_file in dat_files:
        output_name = _infer_output_name(dat_file.name, unidad)
        mat_path = output_path / output_name
        fallback_candidate = FALLBACK_OUTPUT_PATH / output_name

        try:
            if mat_path.exists():
                _log(
                    (
                        f"[DAT2MAT] Omitido '{dat_file.name}': ya existe '{mat_path.name}' en la "
                        "carpeta de salida."
                    ),
                    verbose=verbose,
                )
                skipped += 1
                continue

            if fallback_candidate.exists():
                _log(
                    (
                        f"[DAT2MAT] Omitido '{dat_file.name}': ya existe '{fallback_candidate.name}' "
                        "en la carpeta de respaldo."
                    ),
                    verbose=verbose,
                )
                skipped += 1
                continue

            measurement = load_measurement_file(str(dat_file), n_channels_hint=n_channels_hint)

            fmt = measurement.metadata.get("format")
            if fmt == "binary-float64":
                _log(
                    (
                        f"[DAT2MAT] '{dat_file.name}': formato binario float64 detectado con "
                        f"{measurement.data.shape[1]} canales."
                    ),
                    verbose=verbose,
                )
            elif fmt == "csv":
                encoding = measurement.metadata.get("encoding", "desconocida")
                delimiter = measurement.metadata.get("delimiter", "auto")
                _log(
                    (
                        f"[DAT2MAT] '{dat_file.name}': CSV detectado (enc={encoding}, sep={delimiter})."
                    ),
                    verbose=verbose,
                )

            if n_channels_hint and measurement.data.shape[1] != n_channels_hint:
                _log(
                    (
                        f"[DAT2MAT] Advertencia: {dat_file.name} tiene "
                        f"{measurement.data.shape[1]} columnas numéricas, se esperaban {n_channels_hint}."
                    ),
                    verbose=verbose,
                )

            inferred_time = measurement.time_epoch
            if (inferred_time is None or inferred_time.size == 0) and sample_rate:
                inferred_time = (
                    np.arange(measurement.data.shape[0], dtype=np.float64)
                    / float(sample_rate)
                )
                _log(
                    f"[DAT2MAT] '{dat_file.name}': se reconstruyó el tiempo con sample_rate={sample_rate} Hz.",
                    verbose=verbose,
                )

            mat_payload = measurement.as_mat_payload(time_override=inferred_time)

            try:
                savemat(str(mat_path), mat_payload)
                effective_mat_path = mat_path
            except PermissionError as perm_err:
                fallback_path = fallback_candidate
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                savemat(str(fallback_path), mat_payload)
                effective_mat_path = fallback_path
                _log(
                    (
                        f"[DAT2MAT] '{dat_file.name}': sin permisos de escritura en "
                        f"'{mat_path.parent}'. Archivo guardado en '{effective_mat_path}'."
                    ),
                    verbose=verbose,
                )
                measurement.metadata.setdefault("warnings", [])
                measurement.metadata["warnings"].append(
                    {
                        "type": "permission",
                        "original_path": str(mat_path),
                        "fallback_path": str(effective_mat_path),
                        "error": str(perm_err),
                    }
                )

            processed += 1
            _log(
                f"[DAT2MAT] Archivo convertido: {dat_file.name} -> {effective_mat_path.name}",
                verbose=verbose,
            )

        except Exception as exc:  # pylint: disable=broad-except
            skipped += 1
            _log(f"[DAT2MAT] Error procesando '{dat_file.name}': {exc}", verbose=verbose)

    summary = f"[DAT2MAT] Conversiones exitosas: {processed}. Omitidos/errores: {skipped}."
    _log(summary, verbose=verbose)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        dest="input_folder",
        default=DEFAULT_INPUT_PATH,
        help="Carpeta con archivos .dat (por defecto: ruta de red configurada)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_folder",
        default=DEFAULT_OUTPUT_PATH,
        help="Carpeta destino para archivos .mat (por defecto: ruta de red configurada)",
    )
    parser.add_argument(
        "-u",
        "--unidad",
        default=DEFAULT_UNIT,
        help="Sufijo de unidad para los archivos de salida (por defecto: %(default)s)",
    )
    parser.add_argument(
        "-r",
        "--sample-rate",
        type=float,
        help="Frecuencia de muestreo en Hz para reconstruir el tiempo cuando el .dat no lo incluye",
    )
    parser.add_argument(
        "-c",
        "--channels",
        dest="n_channels_hint",
        type=int,
        help="Cantidad esperada de canales numéricos (solo para advertencias)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Silencia los mensajes informativos",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Ignora los argumentos y abre el asistente interactivo",
    )

    return parser.parse_args(argv)


def interactive_loop(default_unit: str = DEFAULT_UNIT) -> int:
    print("--- Conversor interactivo de .dat a .mat ---")
    print("Consejo: si los .dat son binarios, indique la frecuencia de muestreo para reconstruir 'time_epoch'.")

    try:
        while True:
            input_folder = input("Ruta de entrada con .dat (ej: entrada): ").strip()
            if not input_folder:
                print("La ruta de entrada no puede estar vacía.")
                continue

            output_folder = input("Ruta de salida para .mat (ej: salida): ").strip()
            if not output_folder:
                print("La ruta de salida no puede estar vacía.")
                continue

            unidad = input(f"Unidad [por defecto {default_unit}]: ").strip() or default_unit

            sample_rate_str = input("Frecuencia de muestreo en Hz (opcional): ").strip()
            sample_rate = float(sample_rate_str) if sample_rate_str else None

            channels_hint_str = input("Cantidad esperada de canales (opcional): ").strip()
            channels_hint = int(channels_hint_str) if channels_hint_str else None

            try:
                convert_dat_to_mat(
                    input_folder=input_folder,
                    output_folder=output_folder,
                    unidad=unidad,
                    sample_rate=sample_rate,
                    n_channels_hint=channels_hint,
                )
            except Exception as exc:  # pylint: disable=broad-except
                print(f"ERROR: {exc}", file=sys.stderr)

            another = input("¿Desea realizar otra conversión? (s/n): ").strip().lower()
            if another != "s":
                break

    except (KeyboardInterrupt, EOFError):
        print("\nInteracción cancelada por el usuario.")

    print("Saliendo del programa.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.interactive or not args.input_folder or not args.output_folder:
        return interactive_loop(default_unit=args.unidad)

    try:
        convert_dat_to_mat(
            input_folder=args.input_folder,
            output_folder=args.output_folder,
            unidad=args.unidad,
            sample_rate=args.sample_rate,
            n_channels_hint=args.n_channels_hint,
            verbose=not args.quiet,
        )
        return 0
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Se ha producido un error inesperado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
