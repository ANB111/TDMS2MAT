"""
Conversión directa de archivos TDMS a MAT.
- No agrupa por días
- Respeta fecha y hora originales
- Reconoce automáticamente las columnas de cada archivo
"""

import os
import re
import numpy as np
from nptdms import TdmsFile
from scipy.io import savemat
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import traceback

# Importar pandas una sola vez al inicio (mejora rendimiento)
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def sanitize_name(name):
    """Convierte un nombre de canal a un nombre válido para MATLAB."""
    if not name:
        return 'channel'
    # Reemplazar caracteres no válidos con _
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
    # Asegurar que no empiece con número
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    # Evitar nombres vacíos
    if not sanitized:
        sanitized = 'channel'
    # Limitar longitud (MATLAB tiene límite de 63 caracteres)
    return sanitized[:63]


def detectar_formato_tiempo(datos_muestra):
    """Detecta automáticamente el formato de tiempo de los datos."""
    formatos = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S.%f',
        '%d/%m/%Y %H:%M:%S',
        '%Y/%m/%d %H:%M:%S.%f',
        '%Y/%m/%d %H:%M:%S',
        '%d-%m-%Y %H:%M:%S.%f',
        '%d-%m-%Y %H:%M:%S',
    ]
    
    if not datos_muestra or len(datos_muestra) == 0:
        return None
    
    muestra = str(datos_muestra[0]) if datos_muestra[0] is not None else None
    if not muestra:
        return None
    
    for fmt in formatos:
        try:
            datetime.strptime(muestra, fmt)
            return fmt
        except (ValueError, TypeError):
            continue
    
    return None


def es_columna_tiempo(nombre_canal):
    """Determina si una columna es de tipo tiempo basándose en su nombre."""
    nombres_tiempo = ['time', 'fecha', 'date', 'timestamp', 'datetime', 'hora', 'tiempo']
    nombre_lower = nombre_canal.lower()
    return any(t in nombre_lower for t in nombres_tiempo)


def convertir_datetime_a_compatible(datos):
    """
    Convierte datos datetime a formatos compatibles con scipy.io.savemat.
    Retorna una tupla (datos_epoch, datos_string) o (datos_originales, None) si no son datetime.
    """
    if datos is None or len(datos) == 0:
        return np.array([]), None
    
    # Verificar si son objetos datetime
    muestra = datos[0] if len(datos) > 0 else None
    
    if muestra is None:
        return np.array(datos, dtype=np.float64), None
    
    # Si es datetime.datetime o numpy.datetime64
    if isinstance(muestra, datetime):
        # Convertir datetime de Python a epoch
        epoch = datetime(1970, 1, 1)
        try:
            epoch_values = np.array([(d - epoch).total_seconds() if d else np.nan for d in datos], dtype=np.float64)
            str_values = np.array([d.strftime('%Y-%m-%d %H:%M:%S.%f') if d else '' for d in datos], dtype='U30')
            return epoch_values, str_values
        except Exception:
            # Fallback: convertir a string
            str_values = np.array([str(d) if d else '' for d in datos], dtype='U50')
            return None, str_values
    
    # Si es numpy datetime64
    if hasattr(muestra, 'dtype') and np.issubdtype(type(muestra), np.datetime64):
        try:
            # Convertir a epoch (segundos desde 1970)
            epoch_values = datos.astype('datetime64[us]').astype(np.float64) / 1e6
            str_values = np.array([str(d) for d in datos], dtype='U30')
            return epoch_values, str_values
        except Exception:
            str_values = np.array([str(d) for d in datos], dtype='U50')
            return None, str_values
    
    # Si es pandas Timestamp
    if PANDAS_AVAILABLE and hasattr(muestra, 'timestamp'):
        try:
            epoch_values = np.array([d.timestamp() if pd.notna(d) else np.nan for d in datos], dtype=np.float64)
            str_values = np.array([str(d) if pd.notna(d) else '' for d in datos], dtype='U30')
            return epoch_values, str_values
        except Exception:
            str_values = np.array([str(d) if d else '' for d in datos], dtype='U50')
            return None, str_values
    
    # No es datetime, retornar None para indicar que no se procesó
    return None, None


def es_tipo_datetime(datos):
    """Verifica si los datos son de algún tipo datetime."""
    if datos is None or len(datos) == 0:
        return False
    
    muestra = datos[0]
    if muestra is None:
        return False
    
    # datetime de Python
    if isinstance(muestra, datetime):
        return True
    
    # numpy datetime64
    if hasattr(muestra, 'dtype') and 'datetime' in str(type(muestra)):
        return True
    
    # pandas Timestamp
    if PANDAS_AVAILABLE and isinstance(muestra, pd.Timestamp):
        return True
    
    return False


def convertir_tdms_a_mat(archivo_tdms, carpeta_salida, eliminar_original=False, 
                          ajuste_zona_horaria=0, log_callback=None):
    """
    Convierte un archivo TDMS a MAT directamente.
    
    Parámetros:
        archivo_tdms (str): Ruta al archivo TDMS.
        carpeta_salida (str): Carpeta donde guardar el archivo MAT.
        eliminar_original (bool): Si True, elimina el archivo TDMS después de convertir.
        ajuste_zona_horaria (int): Horas a ajustar en la zona horaria (ej: -3 para Argentina).
        log_callback (function): Función para registrar mensajes.
    
    Returns:
        dict: Información del resultado (éxito, columnas, errores)
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    resultado = {
        'archivo': os.path.basename(archivo_tdms),
        'exito': False,
        'columnas': 0,
        'filas': 0,
        'errores': [],
        'advertencias': []
    }

    try:
        # Validar archivo de entrada
        if not os.path.exists(archivo_tdms):
            raise FileNotFoundError(f"Archivo no encontrado: {archivo_tdms}")
        
        file_size = os.path.getsize(archivo_tdms)
        if file_size == 0:
            raise ValueError("El archivo está vacío")
        
        # Leer archivo TDMS
        tdms_file = TdmsFile.read(archivo_tdms)
        mat_data = {}
        columnas_info = []
        metadatos = {
            'archivo_origen': os.path.basename(archivo_tdms),
            'fecha_conversion': datetime.now().isoformat(),
            'tamano_bytes': file_size
        }

        for grupo in tdms_file.groups():
            grupo_name = sanitize_name(grupo.name) if grupo.name else 'default_group'
            
            for canal in grupo.channels():
                nombre_canal = canal.name
                nombre_sanitizado = sanitize_name(nombre_canal)
                
                # Evitar nombres duplicados
                base_nombre = nombre_sanitizado
                contador = 1
                while nombre_sanitizado in mat_data:
                    nombre_sanitizado = f"{base_nombre}_{contador}"
                    contador += 1

                # Procesar datos según tipo
                datos = canal.data
                
                if datos is None:
                    mat_data[nombre_sanitizado] = np.array([])
                    resultado['advertencias'].append(f"Canal '{nombre_canal}' sin datos")
                    columnas_info.append(nombre_canal)
                    continue
                
                num_filas = len(datos) if hasattr(datos, '__len__') else 0
                resultado['filas'] = max(resultado['filas'], num_filas)

                # Primero verificar si los datos son tipo datetime (independiente del nombre)
                if es_tipo_datetime(datos):
                    try:
                        epoch_vals, str_vals = convertir_datetime_a_compatible(datos)
                        if epoch_vals is not None:
                            mat_data[nombre_sanitizado] = epoch_vals
                        if str_vals is not None:
                            mat_data[f"{nombre_sanitizado}_str"] = str_vals
                        else:
                            # Solo tenemos epoch
                            pass
                    except Exception as e:
                        resultado['advertencias'].append(f"Error convirtiendo datetime '{nombre_canal}': {e}")
                        # Fallback: convertir a string
                        mat_data[nombre_sanitizado] = np.array([str(d) for d in datos], dtype='U50')
                
                # Detectar si es columna de tiempo por nombre (para strings de fecha)
                elif es_columna_tiempo(nombre_canal):
                    if PANDAS_AVAILABLE:
                        try:
                            # Detectar formato automáticamente
                            formato = detectar_formato_tiempo(datos[:10] if len(datos) > 10 else datos)
                            
                            if formato:
                                datos_tiempo = pd.to_datetime(datos, format=formato, errors='coerce')
                            else:
                                datos_tiempo = pd.to_datetime(datos, errors='coerce')
                            
                            # Aplicar ajuste de zona horaria si es necesario
                            if ajuste_zona_horaria != 0:
                                datos_tiempo = datos_tiempo - pd.Timedelta(hours=ajuste_zona_horaria)
                            
                            # Guardar como epoch
                            datos_epoch = (datos_tiempo - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s")
                            mat_data[nombre_sanitizado] = datos_epoch.values.astype(np.float64)
                            
                            # Guardar también como string para legibilidad
                            tiempo_str = datos_tiempo.dt.strftime('%Y-%m-%d %H:%M:%S.%f').fillna('')
                            mat_data[f"{nombre_sanitizado}_str"] = np.array(tiempo_str.tolist(), dtype='U30')
                            
                            # Verificar datos válidos
                            nulos = datos_tiempo.isna().sum()
                            if nulos > 0:
                                resultado['advertencias'].append(
                                    f"Canal '{nombre_canal}': {nulos}/{len(datos)} valores de tiempo inválidos"
                                )
                        except Exception as e:
                            resultado['advertencias'].append(f"Error procesando tiempo en '{nombre_canal}': {e}")
                            # Fallback: guardar como string
                            mat_data[nombre_sanitizado] = np.array([str(d) for d in datos], dtype='U50')
                    else:
                        # Sin pandas, guardar como string
                        mat_data[nombre_sanitizado] = np.array([str(d) for d in datos], dtype='U50')
                else:
                    # Datos numéricos o de otro tipo
                    if num_filas > 0:
                        try:
                            # Intentar convertir a float64
                            datos_numericos = np.array(datos, dtype=np.float64)
                            
                            # Verificar NaN/Inf
                            nan_count = np.isnan(datos_numericos).sum()
                            inf_count = np.isinf(datos_numericos).sum()
                            if nan_count > 0 or inf_count > 0:
                                resultado['advertencias'].append(
                                    f"Canal '{nombre_canal}': {nan_count} NaN, {inf_count} Inf"
                                )
                            
                            mat_data[nombre_sanitizado] = datos_numericos
                        except (ValueError, TypeError):
                            # Si no se puede convertir a float, convertir a string (compatible con MAT)
                            try:
                                mat_data[nombre_sanitizado] = np.array([str(d) for d in datos], dtype='U100')
                            except Exception:
                                mat_data[nombre_sanitizado] = np.array(['error'] * num_filas, dtype='U10')
                            resultado['advertencias'].append(
                                f"Canal '{nombre_canal}' guardado como string (no numérico)"
                            )
                    else:
                        mat_data[nombre_sanitizado] = np.array([])
                
                columnas_info.append(nombre_canal)

        # Guardar información de columnas originales y metadatos (como strings, no objetos)
        mat_data['columnas_originales'] = np.array(columnas_info, dtype='U100')
        mat_data['metadatos'] = np.array([str(metadatos)], dtype='U500')

        # Crear nombre de archivo de salida
        nombre_base = os.path.splitext(os.path.basename(archivo_tdms))[0]
        archivo_mat = os.path.join(carpeta_salida, f"{nombre_base}.mat")
        
        # Guardar con compresión
        savemat(archivo_mat, mat_data, do_compression=True)
        
        resultado['exito'] = True
        resultado['columnas'] = len(columnas_info)
        
        log(f"[TDMS2MAT] ✓ {os.path.basename(archivo_tdms)} -> {os.path.basename(archivo_mat)} "
            f"({len(columnas_info)} columnas, {resultado['filas']} filas)")

        # Eliminar original si se solicita y la conversión fue exitosa
        if eliminar_original and os.path.exists(archivo_mat):
            try:
                os.remove(archivo_tdms)
                archivo_tdms_index = archivo_tdms + '_index'
                if os.path.exists(archivo_tdms_index):
                    os.remove(archivo_tdms_index)
                log(f"[TDMS2MAT] Archivo TDMS eliminado: {os.path.basename(archivo_tdms)}")
            except PermissionError:
                resultado['advertencias'].append("No se pudo eliminar el archivo original (en uso)")
            except Exception as e:
                resultado['advertencias'].append(f"Error al eliminar original: {e}")

        # Reportar advertencias
        for adv in resultado['advertencias']:
            log(f"[TDMS2MAT] ⚠ {adv}")

        return resultado

    except FileNotFoundError as e:
        resultado['errores'].append(str(e))
        log(f"[TDMS2MAT] ✗ Archivo no encontrado: {archivo_tdms}")
        return resultado
    except PermissionError:
        resultado['errores'].append("Permiso denegado para leer el archivo")
        log(f"[TDMS2MAT] ✗ Permiso denegado: {archivo_tdms}")
        return resultado
    except Exception as e:
        resultado['errores'].append(str(e))
        log(f"[TDMS2MAT] ✗ Error al convertir '{os.path.basename(archivo_tdms)}': {e}")
        log(f"[TDMS2MAT] Detalles: {traceback.format_exc()}")
        return resultado


def procesar_tdms_a_mat(carpeta_entrada, carpeta_salida=None, eliminar_original=False, 
                         num_workers=4, ajuste_zona_horaria=0, log_callback=None, 
                         stop_event=None, progress_callback=None):
    """
    Procesa múltiples archivos TDMS y los convierte a MAT.
    
    Parámetros:
        carpeta_entrada (str): Carpeta con archivos TDMS.
        carpeta_salida (str): Carpeta para guardar MAT. Si es None, usa la misma carpeta.
        eliminar_original (bool): Si True, elimina archivos TDMS después de convertir.
        num_workers (int): Número de hilos para procesamiento paralelo.
        ajuste_zona_horaria (int): Horas a ajustar para zona horaria.
        log_callback (function): Función para registrar mensajes.
        stop_event: Evento para detener el proceso.
        progress_callback: Función para reportar progreso (actual, total).
    
    Returns:
        dict: Resumen del procesamiento
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    resumen = {
        'total': 0,
        'exitosos': 0,
        'fallidos': 0,
        'archivos_procesados': [],
        'errores': []
    }

    # Verificar cancelación
    if stop_event and stop_event.is_set():
        log("[TDMS2MAT] Proceso detenido por el usuario.")
        return resumen

    # Validar carpeta de entrada
    if not carpeta_entrada:
        log("[TDMS2MAT] Error: No se especificó carpeta de entrada.")
        return resumen
    
    if not os.path.exists(carpeta_entrada):
        log(f"[TDMS2MAT] Error: La carpeta '{carpeta_entrada}' no existe.")
        return resumen

    if not os.path.isdir(carpeta_entrada):
        log(f"[TDMS2MAT] Error: '{carpeta_entrada}' no es un directorio.")
        return resumen

    # Configurar carpeta de salida
    if carpeta_salida is None:
        carpeta_salida = carpeta_entrada
    
    try:
        os.makedirs(carpeta_salida, exist_ok=True)
    except PermissionError:
        log(f"[TDMS2MAT] Error: Sin permisos para crear carpeta de salida '{carpeta_salida}'")
        return resumen
    except Exception as e:
        log(f"[TDMS2MAT] Error al crear carpeta de salida: {e}")
        return resumen

    # Buscar archivos TDMS (ignorar .tdms_index)
    try:
        todos_archivos = os.listdir(carpeta_entrada)
        archivos_tdms = [
            os.path.join(carpeta_entrada, archivo)
            for archivo in todos_archivos
            if archivo.lower().endswith(".tdms") 
            and not archivo.lower().endswith(".tdms_index")
            and not archivo.startswith("~$")
        ]
        archivos_index = len([f for f in todos_archivos if f.lower().endswith(".tdms_index")])
        if archivos_index > 0:
            log(f"[TDMS2MAT] Se ignorarán {archivos_index} archivo(s) .tdms_index")
    except PermissionError:
        log(f"[TDMS2MAT] Error: Sin permisos para leer la carpeta '{carpeta_entrada}'")
        return resumen

    if not archivos_tdms:
        log(f"[TDMS2MAT] No se encontraron archivos TDMS en '{carpeta_entrada}'.")
        return resumen

    resumen['total'] = len(archivos_tdms)
    log(f"[TDMS2MAT] Encontrados {len(archivos_tdms)} archivo(s) TDMS para convertir...")
    log(f"[TDMS2MAT] Usando {num_workers} hilos de procesamiento")

    # Ajustar número de workers según cantidad de archivos
    num_workers = min(num_workers, len(archivos_tdms))
    procesados = 0

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futuros = {
            executor.submit(
                convertir_tdms_a_mat, 
                archivo, 
                carpeta_salida, 
                eliminar_original,
                ajuste_zona_horaria,
                log_callback
            ): archivo
            for archivo in archivos_tdms
        }

        for futuro in as_completed(futuros):
            # Verificar cancelación
            if stop_event and stop_event.is_set():
                log("[TDMS2MAT] Proceso interrumpido por el usuario.")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            
            archivo = futuros[futuro]
            procesados += 1
            
            # Reportar progreso
            if progress_callback:
                progress_callback(procesados, resumen['total'])
            
            try:
                resultado = futuro.result(timeout=300)  # 5 minutos timeout por archivo
                
                if resultado and resultado.get('exito', False):
                    resumen['exitosos'] += 1
                    resumen['archivos_procesados'].append({
                        'archivo': resultado['archivo'],
                        'columnas': resultado['columnas'],
                        'filas': resultado['filas']
                    })
                else:
                    resumen['fallidos'] += 1
                    if resultado:
                        resumen['errores'].extend(resultado.get('errores', []))
                        
            except TimeoutError:
                log(f"[TDMS2MAT] ✗ Timeout procesando {os.path.basename(archivo)}")
                resumen['fallidos'] += 1
                resumen['errores'].append(f"Timeout: {os.path.basename(archivo)}")
            except Exception as e:
                log(f"[TDMS2MAT] ✗ Error inesperado procesando {os.path.basename(archivo)}: {e}")
                resumen['fallidos'] += 1
                resumen['errores'].append(f"{os.path.basename(archivo)}: {str(e)}")

    # Resumen final
    log(f"[TDMS2MAT] ════════════════════════════════════════")
    log(f"[TDMS2MAT] Conversión completada:")
    log(f"[TDMS2MAT]   ✓ Exitosos: {resumen['exitosos']}/{resumen['total']}")
    log(f"[TDMS2MAT]   ✗ Fallidos: {resumen['fallidos']}/{resumen['total']}")
    log(f"[TDMS2MAT] ════════════════════════════════════════")
    
    return resumen


def obtener_info_tdms(archivo_tdms):
    """
    Obtiene información sobre la estructura de un archivo TDMS.
    
    Retorna un diccionario con grupos, canales y tipos de datos.
    """
    try:
        if not os.path.exists(archivo_tdms):
            return {'error': 'Archivo no encontrado'}
        
        tdms_file = TdmsFile.read(archivo_tdms)
        info = {
            'archivo': os.path.basename(archivo_tdms),
            'tamano_mb': round(os.path.getsize(archivo_tdms) / (1024 * 1024), 2),
            'grupos': []
        }
        
        for grupo in tdms_file.groups():
            grupo_info = {
                'nombre': grupo.name,
                'canales': []
            }
            
            for canal in grupo.channels():
                canal_info = {
                    'nombre': canal.name,
                    'dtype': str(canal.dtype) if hasattr(canal, 'dtype') else 'unknown',
                    'longitud': len(canal.data) if canal.data is not None else 0
                }
                grupo_info['canales'].append(canal_info)
            
            info['grupos'].append(grupo_info)
        
        return info
    
    except Exception as e:
        return {'error': str(e), 'traceback': traceback.format_exc()}


def validar_archivo_mat(archivo_mat):
    """Valida que un archivo MAT se pueda leer correctamente."""
    try:
        from scipy.io import loadmat
        data = loadmat(archivo_mat)
        return {
            'valido': True,
            'variables': list(data.keys()),
            'tamano_mb': round(os.path.getsize(archivo_mat) / (1024 * 1024), 2)
        }
    except Exception as e:
        return {'valido': False, 'error': str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convierte archivos TDMS a MAT de forma directa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python tdms_to_mat_simple.py ./datos_tdms
  python tdms_to_mat_simple.py ./datos_tdms ./salida_mat
  python tdms_to_mat_simple.py ./datos_tdms --eliminar --workers 8
  python tdms_to_mat_simple.py ./datos_tdms --info  # Solo muestra info del primer archivo
        """
    )
    
    parser.add_argument("carpeta_entrada", help="Carpeta con archivos TDMS")
    parser.add_argument("carpeta_salida", nargs="?", default=None, 
                        help="Carpeta de salida (opcional, por defecto usa la misma)")
    parser.add_argument("--eliminar", "-d", action="store_true", 
                        help="Eliminar archivos TDMS después de convertir")
    parser.add_argument("--workers", "-w", type=int, default=4,
                        help="Número de hilos para procesamiento paralelo (default: 4)")
    parser.add_argument("--zona-horaria", "-tz", type=int, default=0,
                        help="Ajuste de zona horaria en horas (ej: -3 para Argentina)")
    parser.add_argument("--info", "-i", action="store_true",
                        help="Solo mostrar información del primer archivo TDMS")
    
    args = parser.parse_args()
    
    if args.info:
        # Modo información
        archivos = [f for f in os.listdir(args.carpeta_entrada) if f.lower().endswith('.tdms')]
        if archivos:
            info = obtener_info_tdms(os.path.join(args.carpeta_entrada, archivos[0]))
            import json
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("No se encontraron archivos TDMS")
        sys.exit(0)
    
    resultado = procesar_tdms_a_mat(
        carpeta_entrada=args.carpeta_entrada, 
        carpeta_salida=args.carpeta_salida, 
        eliminar_original=args.eliminar,
        num_workers=args.workers,
        ajuste_zona_horaria=args.zona_horaria,
        log_callback=print
    )
    
    # Código de salida basado en resultado
    if resultado and resultado['fallidos'] == 0:
        sys.exit(0)
    else:
        sys.exit(1)
