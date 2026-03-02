"""
Conversión directa de archivos TDMS a MAT.

- No agrupa por días
- Respeta fecha y hora originales
- Reconoce automáticamente las columnas de cada archivo
- Pandas es una dependencia obligatoria (no hay código alternativo)
"""

from __future__ import annotations

import json
import os
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from os import cpu_count
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from nptdms import TdmsFile
from scipy.io import loadmat, savemat

from tdms2mat.utils.logging_utils import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers: name sanitisation
# ---------------------------------------------------------------------------


def sanitize_name(name: str) -> str:
    """Convierte un nombre de canal a un nombre válido para MATLAB (máx 63 chars)."""
    if not name:
        return "channel"
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(name))
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    if not sanitized:
        sanitized = "channel"
    return sanitized[:63]


# ---------------------------------------------------------------------------
# Helpers: time detection / conversion
# ---------------------------------------------------------------------------

_TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S.%f",
    "%d-%m-%Y %H:%M:%S",
]

_TIME_KEYWORDS = frozenset(["time", "fecha", "date", "timestamp", "datetime", "hora", "tiempo"])


def detectar_formato_tiempo(datos_muestra: list) -> Optional[str]:
    """Detecta automáticamente el formato de tiempo de los datos."""
    if not datos_muestra:
        return None
    muestra = str(datos_muestra[0]) if datos_muestra[0] is not None else None
    if not muestra:
        return None
    for fmt in _TIME_FORMATS:
        try:
            datetime.strptime(muestra, fmt)
            return fmt
        except (ValueError, TypeError):
            continue
    return None


def es_columna_tiempo(nombre_canal: str) -> bool:
    """Determina si una columna es de tipo tiempo basándose en su nombre."""
    nombre_lower = nombre_canal.lower()
    return any(t in nombre_lower for t in _TIME_KEYWORDS)


def es_tipo_datetime(datos) -> bool:
    """Verifica si los datos son de algún tipo datetime."""
    if datos is None or len(datos) == 0:
        return False
    muestra = datos[0]
    if muestra is None:
        return False
    if isinstance(muestra, datetime):
        return True
    if "datetime" in str(type(muestra)):
        return True
    if isinstance(muestra, pd.Timestamp):
        return True
    return False


def convertir_datetime_a_compatible(datos):
    """
    Convierte datos datetime a formatos compatibles con scipy.io.savemat.

    Returns:
        tuple[np.ndarray | None, np.ndarray | None]: (epoch_values, string_values)
        Either value may be None when conversion fails or is not applicable.
    """
    if datos is None or len(datos) == 0:
        return np.array([]), None

    muestra = datos[0] if len(datos) > 0 else None
    if muestra is None:
        return np.array(datos, dtype=np.float64), None

    # datetime.datetime
    if isinstance(muestra, datetime):
        epoch = datetime(1970, 1, 1)
        try:
            epoch_values = np.array(
                [(d - epoch).total_seconds() if d else np.nan for d in datos],
                dtype=np.float64,
            )
            str_values = np.array(
                [d.strftime("%Y-%m-%d %H:%M:%S.%f") if d else "" for d in datos],
                dtype="U30",
            )
            return epoch_values, str_values
        except Exception:
            str_values = np.array([str(d) if d else "" for d in datos], dtype="U50")
            return None, str_values

    # numpy datetime64
    if hasattr(muestra, "dtype") and np.issubdtype(type(muestra), np.datetime64):
        try:
            epoch_values = datos.astype("datetime64[us]").astype(np.float64) / 1e6
            str_values = np.array([str(d) for d in datos], dtype="U30")
            return epoch_values, str_values
        except Exception:
            str_values = np.array([str(d) for d in datos], dtype="U50")
            return None, str_values

    # pandas Timestamp
    if isinstance(muestra, pd.Timestamp):
        try:
            epoch_values = np.array(
                [d.timestamp() if pd.notna(d) else np.nan for d in datos],
                dtype=np.float64,
            )
            str_values = np.array(
                [str(d) if pd.notna(d) else "" for d in datos],
                dtype="U30",
            )
            return epoch_values, str_values
        except Exception:
            str_values = np.array(
                [str(d) if d else "" for d in datos], dtype="U50"
            )
            return None, str_values

    return None, None


# ---------------------------------------------------------------------------
# Public API: single file
# ---------------------------------------------------------------------------


def convertir_tdms_a_mat(
    archivo_tdms: str,
    carpeta_salida: str,
    eliminar_original: bool = False,
    ajuste_zona_horaria: int = 0,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict:
    """
    Convierte un único archivo TDMS al formato .mat (SciPy).

    Parameters
    ----------
    archivo_tdms:
        Ruta absoluta al archivo TDMS de origen.
    carpeta_salida:
        Carpeta donde guardar el archivo .mat resultante.
    eliminar_original:
        Si True, elimina el .tdms (y su _index) tras una conversión exitosa.
    ajuste_zona_horaria:
        Desplazamiento en horas para columnas de tiempo (e.g. -3 para Argentina).
    log_callback:
        Función opcional para recibir mensajes de progreso.

    Returns
    -------
    dict con keys: ``archivo``, ``exito``, ``columnas``, ``filas``,
    ``errores``, ``advertencias``.
    """

    def _log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    resultado: Dict = {
        "archivo": os.path.basename(archivo_tdms),
        "exito": False,
        "columnas": 0,
        "filas": 0,
        "errores": [],
        "advertencias": [],
    }

    try:
        if not os.path.exists(archivo_tdms):
            raise FileNotFoundError(f"Archivo no encontrado: {archivo_tdms}")

        file_size = os.path.getsize(archivo_tdms)
        if file_size == 0:
            raise ValueError("El archivo está vacío")

        tdms_file = TdmsFile.read(archivo_tdms)
        mat_data: Dict[str, object] = {}
        columnas_info: List[str] = []
        metadatos = {
            "archivo_origen": os.path.basename(archivo_tdms),
            "fecha_conversion": datetime.now().isoformat(),
            "tamano_bytes": file_size,
        }

        for grupo in tdms_file.groups():
            for canal in grupo.channels():
                nombre_canal = canal.name
                nombre_sanitizado = sanitize_name(nombre_canal)

                # Desambiguación de nombres duplicados
                base_nombre = nombre_sanitizado
                contador = 1
                while nombre_sanitizado in mat_data:
                    nombre_sanitizado = f"{base_nombre}_{contador}"
                    contador += 1

                datos = canal.data

                if datos is None:
                    mat_data[nombre_sanitizado] = np.array([])
                    resultado["advertencias"].append(
                        f"Canal '{nombre_canal}' sin datos"
                    )
                    columnas_info.append(nombre_canal)
                    continue

                num_filas = len(datos) if hasattr(datos, "__len__") else 0
                resultado["filas"] = max(resultado["filas"], num_filas)

                # ── datetime (independiente del nombre) ────────────────────
                if es_tipo_datetime(datos):
                    try:
                        epoch_vals, str_vals = convertir_datetime_a_compatible(datos)
                        if epoch_vals is not None:
                            mat_data[nombre_sanitizado] = epoch_vals
                        if str_vals is not None:
                            mat_data[f"{nombre_sanitizado}_str"] = str_vals
                    except Exception as exc:
                        resultado["advertencias"].append(
                            f"Error convirtiendo datetime '{nombre_canal}': {exc}"
                        )
                        mat_data[nombre_sanitizado] = np.array(
                            [str(d) for d in datos], dtype="U50"
                        )

                # ── string de tiempo (detectado por nombre) ────────────────
                elif es_columna_tiempo(nombre_canal):
                    try:
                        sample = datos[:10] if len(datos) > 10 else datos
                        fmt = detectar_formato_tiempo(list(sample))
                        if fmt:
                            datos_tiempo = pd.to_datetime(
                                datos, format=fmt, errors="coerce"
                            )
                        else:
                            datos_tiempo = pd.to_datetime(datos, errors="coerce")

                        if ajuste_zona_horaria != 0:
                            datos_tiempo = datos_tiempo - pd.Timedelta(
                                hours=ajuste_zona_horaria
                            )

                        epoch = (
                            datos_tiempo - pd.Timestamp("1970-01-01")
                        ) / pd.Timedelta("1s")
                        mat_data[nombre_sanitizado] = epoch.values.astype(np.float64)
                        tiempo_str = (
                            datos_tiempo.dt.strftime("%Y-%m-%d %H:%M:%S.%f").fillna("")
                        )
                        mat_data[f"{nombre_sanitizado}_str"] = np.array(
                            tiempo_str.tolist(), dtype="U30"
                        )

                        nulos = datos_tiempo.isna().sum()
                        if nulos > 0:
                            resultado["advertencias"].append(
                                f"Canal '{nombre_canal}': "
                                f"{nulos}/{len(datos)} valores de tiempo inválidos"
                            )
                    except Exception as exc:
                        resultado["advertencias"].append(
                            f"Error procesando tiempo en '{nombre_canal}': {exc}"
                        )
                        mat_data[nombre_sanitizado] = np.array(
                            [str(d) for d in datos], dtype="U50"
                        )

                # ── numérico u otro tipo ───────────────────────────────────
                else:
                    if num_filas > 0:
                        try:
                            datos_numericos = np.array(datos, dtype=np.float64)
                            nan_count = int(np.isnan(datos_numericos).sum())
                            inf_count = int(np.isinf(datos_numericos).sum())
                            if nan_count or inf_count:
                                resultado["advertencias"].append(
                                    f"Canal '{nombre_canal}': "
                                    f"{nan_count} NaN, {inf_count} Inf"
                                )
                            mat_data[nombre_sanitizado] = datos_numericos
                        except (ValueError, TypeError):
                            try:
                                mat_data[nombre_sanitizado] = np.array(
                                    [str(d) for d in datos], dtype="U100"
                                )
                            except Exception:
                                mat_data[nombre_sanitizado] = np.array(
                                    ["error"] * num_filas, dtype="U10"
                                )
                            resultado["advertencias"].append(
                                f"Canal '{nombre_canal}' guardado como string (no numérico)"
                            )
                    else:
                        mat_data[nombre_sanitizado] = np.array([])

                columnas_info.append(nombre_canal)

        # Metadatos en el .mat
        mat_data["columnas_originales"] = np.array(columnas_info, dtype="U100")
        mat_data["metadatos"] = np.array([json.dumps(metadatos)], dtype="U500")

        nombre_base = Path(archivo_tdms).stem
        archivo_mat = os.path.join(carpeta_salida, f"{nombre_base}.mat")
        savemat(archivo_mat, mat_data, do_compression=True)

        resultado["exito"] = True
        resultado["columnas"] = len(columnas_info)

        _log(
            f"[TDMS_DIRECT] ✓ {os.path.basename(archivo_tdms)} -> "
            f"{os.path.basename(archivo_mat)} "
            f"({len(columnas_info)} columnas, {resultado['filas']} filas)"
        )

        if eliminar_original and os.path.exists(archivo_mat):
            try:
                os.remove(archivo_tdms)
                index_file = archivo_tdms + "_index"
                if os.path.exists(index_file):
                    os.remove(index_file)
                _log(
                    f"[TDMS_DIRECT] Archivo TDMS eliminado: "
                    f"{os.path.basename(archivo_tdms)}"
                )
            except PermissionError:
                resultado["advertencias"].append(
                    "No se pudo eliminar el archivo original (en uso)"
                )
            except Exception as exc:
                resultado["advertencias"].append(
                    f"Error al eliminar original: {exc}"
                )

        for adv in resultado["advertencias"]:
            _log(f"[TDMS_DIRECT] ⚠ {adv}")

    except FileNotFoundError as exc:
        resultado["errores"].append(str(exc))
        _log(f"[TDMS_DIRECT] ✗ Archivo no encontrado: {archivo_tdms}")
    except PermissionError:
        resultado["errores"].append("Permiso denegado para leer el archivo")
        _log(f"[TDMS_DIRECT] ✗ Permiso denegado: {archivo_tdms}")
    except Exception as exc:
        resultado["errores"].append(str(exc))
        _log(
            f"[TDMS_DIRECT] ✗ Error al convertir "
            f"'{os.path.basename(archivo_tdms)}': {exc}"
        )
        _log(f"[TDMS_DIRECT] Detalles:\n{traceback.format_exc()}")

    return resultado


# ---------------------------------------------------------------------------
# Public API: batch
# ---------------------------------------------------------------------------


def procesar_tdms_a_mat(
    carpeta_entrada: str,
    carpeta_salida: Optional[str] = None,
    eliminar_original: bool = False,
    num_workers: int = 4,
    ajuste_zona_horaria: int = 0,
    log_callback: Optional[Callable[[str], None]] = None,
    stop_event=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict:
    """
    Convierte todos los archivos TDMS de *carpeta_entrada* a formato .mat.

    Parameters
    ----------
    carpeta_entrada:
        Carpeta con los archivos ``.tdms``.
    carpeta_salida:
        Carpeta destino para los ``.mat``. ``None`` ⇒ misma que entrada.
    eliminar_original:
        Elimina cada ``.tdms`` tras una conversión exitosa.
    num_workers:
        Hilos de CPU a usar (máximo: ``min(cpu_count(), num_workers)``).
    ajuste_zona_horaria:
        Desplazamiento horario para columnas de tiempo.
    log_callback:
        Función para recibir mensajes de texto.
    stop_event:
        ``threading.Event`` — si está activado se abandona el proceso.
    progress_callback:
        Función ``(procesados: int, total: int) -> None`` para barra de progreso.

    Returns
    -------
    dict con keys: ``total``, ``exitosos``, ``fallidos``,
    ``archivos_procesados``, ``errores``.
    """

    def _log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    resumen: Dict = {
        "total": 0,
        "exitosos": 0,
        "fallidos": 0,
        "archivos_procesados": [],
        "errores": [],
    }

    if stop_event and stop_event.is_set():
        _log("[TDMS_DIRECT] Proceso detenido antes de comenzar.")
        return resumen

    if not carpeta_entrada:
        _log("[TDMS_DIRECT] Error: No se especificó carpeta de entrada.")
        return resumen

    if not os.path.isdir(carpeta_entrada):
        _log(f"[TDMS_DIRECT] Error: '{carpeta_entrada}' no es un directorio válido.")
        return resumen

    if carpeta_salida is None:
        carpeta_salida = carpeta_entrada

    try:
        os.makedirs(carpeta_salida, exist_ok=True)
    except PermissionError:
        _log(
            f"[TDMS_DIRECT] Error: Sin permisos para crear "
            f"carpeta de salida '{carpeta_salida}'"
        )
        return resumen
    except Exception as exc:
        _log(f"[TDMS_DIRECT] Error al crear carpeta de salida: {exc}")
        return resumen

    try:
        todos = os.listdir(carpeta_entrada)
        archivos_tdms = [
            os.path.join(carpeta_entrada, f)
            for f in todos
            if f.lower().endswith(".tdms")
            and not f.lower().endswith(".tdms_index")
            and not f.startswith("~$")
        ]
        n_index = sum(1 for f in todos if f.lower().endswith(".tdms_index"))
        if n_index:
            _log(f"[TDMS_DIRECT] Se ignorarán {n_index} archivo(s) .tdms_index")
    except PermissionError:
        _log(
            f"[TDMS_DIRECT] Error: Sin permisos para leer "
            f"la carpeta '{carpeta_entrada}'"
        )
        return resumen

    if not archivos_tdms:
        _log(f"[TDMS_DIRECT] No se encontraron archivos TDMS en '{carpeta_entrada}'.")
        return resumen

    resumen["total"] = len(archivos_tdms)
    num_workers = min(num_workers, len(archivos_tdms), cpu_count() or 4)
    _log(
        f"[TDMS_DIRECT] {len(archivos_tdms)} archivo(s) TDMS — "
        f"{num_workers} hilos de procesamiento"
    )

    procesados = 0
    cancelled = False

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futuros = {
            executor.submit(
                convertir_tdms_a_mat,
                archivo,
                carpeta_salida,
                eliminar_original,
                ajuste_zona_horaria,
                log_callback,
            ): archivo
            for archivo in archivos_tdms
        }

        for futuro in as_completed(futuros):
            if stop_event and stop_event.is_set():
                _log("[TDMS_DIRECT] Proceso interrumpido por el usuario.")
                # Python 3.8-compatible: cancel pending futures manually
                for pending in futuros:
                    pending.cancel()
                executor.shutdown(wait=False)
                cancelled = True
                break

            archivo = futuros[futuro]
            procesados += 1

            if progress_callback:
                progress_callback(procesados, resumen["total"])

            try:
                resultado = futuro.result(timeout=300)  # 5 min por archivo
                if resultado and resultado.get("exito", False):
                    resumen["exitosos"] += 1
                    resumen["archivos_procesados"].append(
                        {
                            "archivo": resultado["archivo"],
                            "columnas": resultado["columnas"],
                            "filas": resultado["filas"],
                        }
                    )
                else:
                    resumen["fallidos"] += 1
                    if resultado:
                        resumen["errores"].extend(resultado.get("errores", []))
            except TimeoutError:
                _log(
                    f"[TDMS_DIRECT] ✗ Timeout procesando "
                    f"{os.path.basename(archivo)}"
                )
                resumen["fallidos"] += 1
                resumen["errores"].append(f"Timeout: {os.path.basename(archivo)}")
            except Exception as exc:
                _log(
                    f"[TDMS_DIRECT] ✗ Error inesperado procesando "
                    f"{os.path.basename(archivo)}: {exc}"
                )
                resumen["fallidos"] += 1
                resumen["errores"].append(
                    f"{os.path.basename(archivo)}: {str(exc)}"
                )

    if not cancelled:
        _log("[TDMS_DIRECT] ════════════════════════════════════════")
        _log("[TDMS_DIRECT] Conversión completada:")
        _log(
            f"[TDMS_DIRECT]   ✓ Exitosos: "
            f"{resumen['exitosos']}/{resumen['total']}"
        )
        _log(
            f"[TDMS_DIRECT]   ✗ Fallidos: "
            f"{resumen['fallidos']}/{resumen['total']}"
        )
        _log("[TDMS_DIRECT] ════════════════════════════════════════")

    return resumen


# ---------------------------------------------------------------------------
# Public API: inspection / validation
# ---------------------------------------------------------------------------


def obtener_info_tdms(archivo_tdms: str) -> Dict:
    """
    Devuelve metadatos de un archivo TDMS (grupos, canales, tipos y longitudes).
    """
    try:
        if not os.path.exists(archivo_tdms):
            return {"error": "Archivo no encontrado"}

        tdms_file = TdmsFile.read(archivo_tdms)
        info: Dict = {
            "archivo": os.path.basename(archivo_tdms),
            "tamano_mb": round(os.path.getsize(archivo_tdms) / (1024 * 1024), 2),
            "grupos": [],
        }

        for grupo in tdms_file.groups():
            grupo_info: Dict = {"nombre": grupo.name, "canales": []}
            for canal in grupo.channels():
                grupo_info["canales"].append(
                    {
                        "nombre": canal.name,
                        "dtype": str(canal.dtype)
                        if hasattr(canal, "dtype")
                        else "unknown",
                        "longitud": len(canal.data) if canal.data is not None else 0,
                    }
                )
            info["grupos"].append(grupo_info)

        return info

    except Exception as exc:
        return {"error": str(exc), "traceback": traceback.format_exc()}


def validar_archivo_mat(archivo_mat: str) -> Dict:
    """Valida que un archivo .mat sea legible y devuelve sus variables."""
    try:
        data = loadmat(archivo_mat)
        return {
            "valido": True,
            "variables": [k for k in data.keys() if not k.startswith("__")],
            "tamano_mb": round(os.path.getsize(archivo_mat) / (1024 * 1024), 2),
        }
    except Exception as exc:
        return {"valido": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Convierte archivos TDMS a MAT de forma directa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -m tdms2mat.tdms_direct.converter ./datos_tdms
  python -m tdms2mat.tdms_direct.converter ./datos_tdms ./salida_mat
  python -m tdms2mat.tdms_direct.converter ./datos_tdms --eliminar --workers 8
  python -m tdms2mat.tdms_direct.converter ./datos_tdms --info
        """,
    )
    parser.add_argument("carpeta_entrada", help="Carpeta con archivos TDMS")
    parser.add_argument(
        "carpeta_salida",
        nargs="?",
        default=None,
        help="Carpeta de salida (por defecto usa la carpeta de entrada)",
    )
    parser.add_argument(
        "--eliminar",
        "-d",
        action="store_true",
        help="Eliminar archivos TDMS originales tras convertir",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Hilos de procesamiento paralelo (default: 4)",
    )
    parser.add_argument(
        "--zona-horaria",
        "-tz",
        type=int,
        default=0,
        help="Ajuste de zona horaria en horas (ej: -3 para Argentina)",
    )
    parser.add_argument(
        "--info",
        "-i",
        action="store_true",
        help="Mostrar información del primer TDMS encontrado y salir",
    )

    args = parser.parse_args()

    if args.info:
        tdms_files = [
            f
            for f in os.listdir(args.carpeta_entrada)
            if f.lower().endswith(".tdms")
        ]
        if tdms_files:
            info = obtener_info_tdms(
                os.path.join(args.carpeta_entrada, tdms_files[0])
            )
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("No se encontraron archivos TDMS.")
        sys.exit(0)

    resultado = procesar_tdms_a_mat(
        carpeta_entrada=args.carpeta_entrada,
        carpeta_salida=args.carpeta_salida,
        eliminar_original=args.eliminar,
        num_workers=args.workers,
        ajuste_zona_horaria=args.zona_horaria,
        log_callback=print,
    )

    sys.exit(0 if resultado["fallidos"] == 0 else 1)
