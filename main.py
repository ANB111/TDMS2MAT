import os
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List

# Importaciones más específicas
from config_utils import load_config, save_config, validate_config
from decompress_utils import decompress_zip_files
from tdms_utils import procesar_archivos_tdms_paralelo
from csv_utils import ordenar_y_agrupado_por_dia
from mat_utils import csv_to_mat
from matlab_utils import process_mat_files
from startup_shutdown_counter import process_mat_folder


class ProcessingError(Exception):
    """Excepción personalizada para errores de procesamiento."""
    pass


def setup_folders(folders: List[str], log_func: Callable[[str], None]) -> bool:
    """
    Configura y verifica las carpetas necesarias.
    
    Args:
        folders: Lista de carpetas a verificar/crear
        log_func: Función para registrar mensajes
    
    Returns:
        True si todo fue exitoso, False en caso contrario
    """
    for folder in folders:
        if not folder:  # Evitar crear carpetas vacías
            log_func(f"ADVERTENCIA: Ruta de carpeta vacía detectada")
            return False
            
        folder_path = Path(folder)
        if not folder_path.exists():
            try:
                log_func(f"La carpeta '{folder}' no existe. Creándola...")
                folder_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log_func(f"ERROR: No se pudo crear la carpeta '{folder}': {e}")
                return False
    return True


def process_stage(name: str, func: Callable, args: tuple, 
                  log_func: Callable[[str], None], continue_on_error: bool = False) -> bool:
    """
    Ejecuta una etapa de procesamiento con manejo de errores estándar.
    
    Args:
        name: Nombre de la etapa para el registro
        func: Función a ejecutar
        args: Argumentos para la función
        log_func: Función para registrar mensajes
        continue_on_error: Si es True, no detiene el proceso en caso de error
    
    Returns:
        True si la etapa fue exitosa, False en caso contrario
    """
    log_func(f"Iniciando: {name}...")
    try:
        func(*args)
        log_func(f"Completado: {name}.")
        return True
    except Exception as e:
        error_details = traceback.format_exc()
        log_func(f"ERROR en {name}: {e}")
        log_func(f"Detalles: {error_details}")
        if not continue_on_error:
            return False
        log_func(f"Continuando a pesar del error...")
        return False


def main(config: Dict[str, Any], log_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Función principal de procesamiento con manejo mejorado de errores y configuración.
    
    Args:
        config: Diccionario de configuración
        log_callback: Función opcional para registrar mensajes
    
    Returns:
        True si el proceso fue exitoso, False en caso contrario
    """
    # Configurar registro
    def log(message: str, level: int = logging.INFO):
        if log_callback:
            log_callback(message)
        else:
            print(message)
        
        # También podríamos registrar en un archivo de registro
        logging.log(level, message)
    
    # Configurar registro a archivo
    log_file = Path(config.get('output_folder', '.')) / 'processing.log'
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    log(f"Iniciando procesamiento con configuración: {config}", logging.DEBUG)
    
    # Validar configuración
    if not validate_config(config):
        log("ERROR: Configuración inválida. Abortando proceso.", logging.ERROR)
        return False
    
    # Extraer parámetros de configuración con valores por defecto
    input_folder = config.get('input_folder', '')
    output_folder = config.get('output_folder', '')
    excel_output_folder = config.get('excel_output_folder', '')
    procesar_incompleto = config.get('procesar_incompleto', False)
    unidad = config.get('unidad', '05')
    realizar_conteo = config.get('realizar_conteo', False)
    descomprimir = config.get('descomprimir', False)
    rainflow = config.get('rainflow', False)
    selected_files = config.get("selected_files", [])

    # verificar y crear carpeta temp en la ruta del script
    temp_folder = os.path.join(os.path.dirname(__file__), "temp")
    
    # Validar carpetas
    folders = [input_folder, output_folder, excel_output_folder, str(temp_folder)]
    if not setup_folders(folders, log):
        log("ERROR: No se pudo configurar las carpetas necesarias. Abortando.", logging.ERROR)
        return False
    
    # Validar archivos seleccionados
    if not selected_files:
        log("ADVERTENCIA: No se han seleccionado archivos para procesar.", logging.WARNING)
        return False
    
    log(f"Se procesarán {len(selected_files)} archivos")
    
    # Proceso por etapas
    stages = []
    
    # Etapa 1: Descompresión de archivos ZIP
    
    if descomprimir:
        stages.append((
            "Descompresión de archivos ZIP",
            decompress_zip_files,
            (input_folder, str(temp_folder), selected_files)
        ))
    
        # Etapa 2: Procesamiento TDMS
        stages.append((
            "Procesamiento de archivos TDMS",
            procesar_archivos_tdms_paralelo,
            (str(temp_folder),)
        ))
        
        # Etapa 3: Ordenamiento y agrupación CSV
        stages.append((
            "Ordenamiento y agrupación de archivos CSV",
            ordenar_y_agrupado_por_dia,
            (str(temp_folder),)
        ))
        
        # Etapa 4: Conversión CSV a MAT
        stages.append((
            "Conversión de CSV a MAT",
            csv_to_mat,
            (str(temp_folder), output_folder, unidad, procesar_incompleto)
        ))
    
    # Etapa 5: Procesamiento MAT con MATLAB (opcional)
    if rainflow:
        stages.append((
            "Procesamiento de archivos MAT con MATLAB",
            process_mat_files,
            (output_folder, config)
        ))
    
    # Etapa 6: Conteo de ciclos (opcional)
    if realizar_conteo:
        excel_path = str(Path(excel_output_folder) / "arranque_paradas.xlsx")
        stages.append((
            "Conteo de ciclos de arranque y parada",
            process_mat_folder,
            (output_folder, excel_path, log)
        ))
    
    # Ejecutar etapas
    success = True
    for name, func, args in stages:
        if not process_stage(name, func, args, log):
            success = False
            log(f"Proceso detenido debido a un error en la etapa: {name}", logging.ERROR)
            break
    
    if success:
        log("Proceso completado exitosamente.")
    else:
        log("El proceso no se completó correctamente. Revise los errores anteriores.", logging.ERROR)
    
    # Limpieza (opcional)
    # cleanup_temp_files(temp_folder)
    
    return success


if __name__ == "__main__":
    # Código para ejecutar el script directamente para pruebas
    test_config = load_config("config.json")
    main(test_config)