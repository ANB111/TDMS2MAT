import os
import sys
from config_utils import load_config, save_config
from user_interaction import get_folders_from_user, select_processing_option
from decompress_utils import decompress_files
from tdms_utils import procesar_archivos_tdms_paralelo
from csv_utils import ordenar_y_agrupado_por_dia
from mat_utils import csv_to_mat
from matlab_utils import process_mat_files
from startup_shutdown_counter import process_mat_folder

def main():
    try:
        # Ruta del archivo de configuración
        config_path = "config.json"
        
        # Cargar configuración
        config = load_config(config_path)
        
        # Si falta información, solicitarla al usuario
        config = get_folders_from_user(config)
        save_config(config, config_path)
        
        # Asignar variables de configuración
        input_folder = config.get('input_folder', '')
        output_folder = config.get('output_folder', '')
        excel_output_folder = config.get('excel_output_folder', '')

        if not all([input_folder, output_folder, excel_output_folder]):
            print("Error: No se especificaron todas las carpetas requeridas.")
            sys.exit(1)

        script_folder = os.path.dirname(os.path.abspath(__file__))
        temp_folder = os.path.join(script_folder, 'temp')
        os.makedirs(temp_folder, exist_ok=True)
        
        # Solicitar al usuario cómo procesar los archivos
        files_to_process, procesar_incompleto, unidad, realizar_conteo = select_processing_option(input_folder, config)
        if files_to_process is None:
            print("Proceso cancelado por el usuario.")
            sys.exit(0)
        
        
        # Descomprimir archivos ZIP seleccionados
        decompress_files(input_folder, temp_folder, files_to_process)
        
        # Procesar archivos TDMS en paralelo
        procesar_archivos_tdms_paralelo(temp_folder)
        
        # Ordenar y agrupar archivos CSV por día
        ordenar_y_agrupado_por_dia(temp_folder)
        
        # Convertir archivos CSV a MAT
        csv_to_mat(temp_folder, output_folder, unidad=unidad, procesar_incompleto=procesar_incompleto)
        
        # Procesar archivos MAT con MATLAB
        process_mat_files(output_folder, config)
        
        # Conteo de ciclos de arranque y parada
        if realizar_conteo:
            excel_path = os.path.join(excel_output_folder, "arranque_paradas.xlsx")
            try:
                process_mat_folder(output_folder, excel_path)
            except Exception as e:
                print(f"Error al procesar el conteo de arranques y paradas: {e}")
        
        print("\n✅ Proceso completado con éxito.")
    
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
