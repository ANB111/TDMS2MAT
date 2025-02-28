import os
from config_utils import load_config, save_config
from decompress_utils import decompress_zip_files
from tdms_utils import procesar_archivos_tdms_paralelo
from csv_utils import ordenar_y_agrupado_por_dia
from mat_utils import csv_to_mat
from matlab_utils import process_mat_files
from startup_shutdown_counter import process_mat_folder

def main(config, log_callback=None):
    # Asignar variables de configuración
    input_folder = config['input_folder']
    output_folder = config['output_folder']
    excel_output_folder = config['excel_output_folder']
    procesar_incompleto = config['procesar_incompleto']
    unidad = config['unidad']
    realizar_conteo = config['realizar_conteo']
    descomprimir = config['descomprimir']
    procesar = config['procesar']
    rainflow = config['rainflow']
    graficos_matlab = config['graficos_matlab']
    selected_files = config.get("selected_files", [])  # Archivos seleccionados

    # Validar y crear carpetas si no existen
    for folder in [input_folder, output_folder, excel_output_folder]:
        if not os.path.exists(folder):
            print(f"La carpeta '{folder}' no existe. Creándola...")
            os.makedirs(folder)
        # Función de registro

    # Función de registro
    def log(message):
        if log_callback:
            log_callback(message)
        else:
            print(message)

    # Procesar solo los archivos seleccionados
    if not selected_files:
        log("No se han seleccionado archivos para procesar.")
        return

    # Descomprimir archivos ZIP si está activado
    if descomprimir:
        print("Descomprimiendo archivos ZIP...")
        try:
            decompress_zip_files(input_folder, output_folder)
            print("Archivos ZIP descomprimidos correctamente.")
        except Exception as e:
            print(f"Error al descomprimir archivos ZIP: {e}")
            return

    # Procesar archivos TDMS si está activado

    print("Procesando archivos TDMS...")
    try:
        procesar_archivos_tdms_paralelo(output_folder)
        print("Archivos TDMS procesados correctamente.")
    except Exception as e:
        print(f"Error al procesar archivos TDMS: {e}")
        return

    # Ordenar y agrupar archivos CSV por día
    try:
        ordenar_y_agrupado_por_dia(output_folder, procesar_incompleto=procesar_incompleto)
    except Exception as e:
        print(f"Error al ordenar y agrupar archivos CSV: {e}")
        return

    # Convertir archivos CSV a MAT
    try:
        csv_to_mat(output_folder, unidad=unidad)
    except Exception as e:
        print(f"Error al convertir archivos CSV a MAT: {e}")
        return

    # Procesar archivos MAT con MATLAB si está activado
    if rainflow:
        print("Procesando archivos MAT con MATLAB...")
        try:
            process_mat_files(output_folder, config)
            print("Archivos MAT procesados correctamente con MATLAB.")
        except Exception as e:
            print(f"Error al procesar archivos MAT con MATLAB: {e}")
            return

    # Conteo de ciclos de arranque y parada si está activado
    if realizar_conteo:
        excel_path = os.path.join(excel_output_folder, "arranque_paradas.xlsx")
        print("Realizando conteo de ciclos de arranque y parada...")
        try:
            process_mat_folder(output_folder, excel_path)
            print("Conteo de ciclos de arranque y parada completado.")
        except Exception as e:
            print(f"Error al procesar el conteo de arranques y paradas: {e}")
            return

    print("Proceso completado exitosamente.")