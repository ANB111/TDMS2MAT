import os
from config_utils import load_config, save_config
from user_interaction import get_folders_from_user, select_processing_option
from decompress_utils import decompress_zip_files
from tdms_utils import procesar_archivos_tdms_paralelo
from csv_utils import ordenar_y_agrupado_por_dia
from mat_utils import csv_to_mat
from matlab_utils import process_mat_files
from startup_shutdown_counter import process_mat_folder

def main():
    # Ruta del archivo de configuración
    config_path = "config.json"
    
    # Cargar configuración
    config = load_config(config_path)
    
    # Si falta información, solicitarla al usuario
    config = get_folders_from_user(config)
    save_config(config, config_path)
    
    # Asignar variables de configuración
    input_folder = config['input_folder']
    output_folder = config['output_folder']
    excel_output_folder = config['excel_output_folder']
    
    # Solicitar al usuario cómo procesar los archivos
    files_to_process, procesar_incompleto, unidad, realizar_conteo = select_processing_option(input_folder, config)
    if files_to_process is None:
        print("Proceso cancelado por el usuario.")
        exit()
    
    # Usar los valores devueltos en el flujo del programa
    print(f"Archivos seleccionados: {files_to_process}")
    print(f"Procesar archivos incompletos: {procesar_incompleto}")
    print(f"Unidad a procesar: {unidad}")
    print(f"Realizar conteo de ciclos de arranque y parada: {realizar_conteo}")
    
    # Descomprimir archivos ZIP seleccionados
    decompress_zip_files(input_folder, output_folder, files_to_process)
    
    # Procesar archivos TDMS en paralelo
    procesar_archivos_tdms_paralelo(output_folder)
    
    # Ordenar y agrupar archivos CSV por día
    ordenar_y_agrupado_por_dia(output_folder, procesar_incompleto=procesar_incompleto)
    
    # Convertir archivos CSV a MAT
    csv_to_mat(output_folder, unidad=unidad)
    
    # Procesar archivos MAT con MATLAB
    process_mat_files(output_folder, config)

    # Conteo arranques y paradas
    if realizar_conteo:
        # Ruta del archivo Excel
        excel_path = os.path.join(excel_output_folder, "arranque_paradas.xlsx")
        
        try:
            process_mat_folder(output_folder, excel_path)
        except Exception as e:
            print(f"Error al procesar el conteo de arranques y paradas: {e}")

    print("Proceso completado.")

if __name__ == "__main__":
    main()