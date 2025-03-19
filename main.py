import os
from config_utils import load_config, save_config
from decompress_utils import decompress_zip_files
from tdms_utils import procesar_archivos_tdms_paralelo
from csv_utils import ordenar_y_agrupado_por_dia
from mat_utils import csv_to_mat
from matlab_utils import process_mat_files
from startup_shutdown_counter import process_mat_folder

def main(config, log_callback=None):
    # Función de registro
    def log(message):
        if log_callback:
            log_callback(message)
        else:
            print(message)

    # Asignar variables de configuración
    input_folder = config.get('input_folder', '')
    output_folder = config.get('output_folder', '')
    excel_output_folder = config.get('excel_output_folder', '')
    procesar_incompleto = config.get('procesar_incompleto', False)
    unidad = config.get('unidad', '05')
    realizar_conteo = config.get('realizar_conteo', False)
    descomprimir = config.get('descomprimir', False)
    rainflow = config.get('rainflow', False)
    graficos_matlab = config.get('graficos_matlab', False)
    selected_files = config.get("selected_files", [])  # Archivos seleccionados

    # verificar y crear carpeta temp en la ruta del script
    temp_folder = os.path.join(os.path.dirname(__file__), "temp")


    # Validar carpetas
    for folder in [input_folder, output_folder, excel_output_folder, temp_folder]:
        if not os.path.exists(folder):
            log(f"La carpeta '{folder}' no existe. Creándola...")
            os.makedirs(folder)

    # Validar archivos seleccionados
    if not selected_files:
        log("No se han seleccionado archivos para procesar.")
        return

    # Descomprimir archivos ZIP si está activado
    if descomprimir:
        log("Descomprimiendo archivos ZIP...")
        try:
            decompress_zip_files(input_folder, temp_folder, selected_files)
            log("Archivos ZIP descomprimidos correctamente.")
        except Exception as e: 
            log(f"Error al descomprimir archivos ZIP: {e}")
            return

    log("Procesando archivos TDMS...")
    try:
        procesar_archivos_tdms_paralelo(temp_folder)
        log("Archivos TDMS procesados correctamente.")
    except Exception as e:
        log(f"Error al procesar archivos TDMS: {e}")
        return

    # Ordenar y agrupar archivos CSV por día
    log("Ordenando y agrupando archivos CSV por día...")
    try:
        ordenar_y_agrupado_por_dia(temp_folder)
        log("Archivos CSV ordenados y agrupados correctamente.")
    except Exception as e:
        log(f"Error al ordenar y agrupar archivos CSV: {e}")
        return

    # Convertir archivos CSV a MAT
    log("Convirtiendo archivos CSV a MAT...")
    try:
        csv_to_mat(temp_folder, output_folder, unidad=unidad, procesar_incompleto=procesar_incompleto)
        log("Archivos CSV convertidos a MAT correctamente.")
    except Exception as e:
        log(f"Error al convertir archivos CSV a MAT: {e}")
        return

    # Procesar archivos MAT con MATLAB si está activado
    if rainflow:
        log("Procesando archivos MAT con MATLAB...")
        try:
            process_mat_files(output_folder, config)
            log("Archivos MAT procesados correctamente con MATLAB.")
        except Exception as e:
            log(f"Error al procesar archivos MAT con MATLAB: {e}")
            return

    # Conteo de ciclos de arranque y parada si está activado
    if realizar_conteo:
        excel_path = os.path.join(excel_output_folder, "arranque_paradas.xlsx")
        log("Realizando conteo de ciclos de arranque y parada...")
        try:
            process_mat_folder(output_folder, excel_path)
            log("Conteo de ciclos de arranque y parada completado.")
        except Exception as e:
            log(f"Error al procesar el conteo de arranques y paradas: {e}")
            return

    log("Proceso completado exitosamente.")