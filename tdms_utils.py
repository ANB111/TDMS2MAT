import os
from nptdms import TdmsFile
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm



def convertir_tdms_a_csv(archivo_tdms, carpeta_salida, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)

    try:
        tdms_file = TdmsFile.read(archivo_tdms)
        grupo = tdms_file.groups()[0]
        data_dict = {}

        for canal in grupo.channels():
            nombre_canal = canal.name
            if canal.name.lower() == "time" or canal.name.lower().startswith("date"):
                datos_tiempo = pd.to_datetime(canal.data, format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
                datos_tiempo_corregidos = datos_tiempo - pd.Timedelta(hours=3)
                data_dict[nombre_canal] = datos_tiempo_corregidos
            else:
                data_dict[nombre_canal] = canal.data

        df = pd.DataFrame(data_dict)
        nombre_archivo_csv = os.path.splitext(os.path.basename(archivo_tdms))[0] + ".csv"
        ruta_archivo_csv = os.path.join(carpeta_salida, nombre_archivo_csv)
        df.to_csv(ruta_archivo_csv, index=False, sep=';')

        if os.path.exists(ruta_archivo_csv):
            os.remove(archivo_tdms)
            archivo_tdms_index = archivo_tdms + '_index'
            if os.path.exists(archivo_tdms_index):
                os.remove(archivo_tdms_index)
            log(f"[TDMS2CSV] Convertido y eliminado: {os.path.basename(archivo_tdms)}")
        else:
            log(f"[TDMS2CSV] Error: No se creó el archivo CSV {ruta_archivo_csv}. TDMS no eliminado.")

    except Exception as e:
        log(f"[TDMS2CSV] Error al convertir '{archivo_tdms}': {e}")


def procesar_archivos_tdms_paralelo(carpeta_tdms, num_workers=14, log_callback=None, stop_event=None):
    def log(msg):
        if log_callback:
            log_callback(msg)

    if stop_event and stop_event.is_set():
        log("[TDMS2CSV] Proceso detenido por el usuario.")
        return
    
    if not os.path.exists(carpeta_tdms):
        log(f"[TDMS2CSV] La carpeta '{carpeta_tdms}' no existe.")
        return

    archivos_tdms = [
        os.path.join(carpeta_tdms, archivo)
        for archivo in os.listdir(carpeta_tdms)
        if archivo.endswith(".tdms")
    ]

    if not archivos_tdms:
        log(f"[TDMS2CSV] No se encontraron archivos TDMS en '{carpeta_tdms}'.")
        return

    log(f"[TDMS2CSV] Procesando {len(archivos_tdms)} archivo(s) TDMS...")

    with tqdm(total=len(archivos_tdms), desc="Procesando archivos TDMS", unit="archivo") as barra:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futuros = {
                executor.submit(convertir_tdms_a_csv, archivo, carpeta_tdms, log_callback): archivo
                for archivo in archivos_tdms
            }

            for futuro in as_completed(futuros):
                archivo = futuros[futuro]
                try:
                    futuro.result()
                except Exception as e:
                    log(f"[TDMS2CSV] Error procesando {archivo}: {e}")
                finally:
                    barra.update(1)
