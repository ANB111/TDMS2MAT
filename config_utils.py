import os
import json

def load_config(config_path):
    """
    Carga la configuración desde el archivo JSON. Si no existe, devuelve un diccionario vacío.
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error al cargar el archivo de configuración: {e}")
            return {}
    return {}

def save_config(config, config_path):
    """
    Guarda la configuración en un archivo JSON.
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar el archivo de configuración: {e}")

def validate_config(config):
    """
    Valida que la configuración tenga los campos necesarios.
    
    Args:
        config: Diccionario con la configuración
        
    Returns:
        True si la configuración es válida, False en caso contrario
    """
    # Campos requeridos
    required_fields = ['input_folder', 'output_folder', 'excel_output_folder']
    
    # Verificar campos requeridos
    for field in required_fields:
        if not config.get(field):
            print(f"ERROR: Falta el campo requerido '{field}' en la configuración")
            return False
    
    # Verificar tipos de datos (opcional)
    if not isinstance(config.get('FS', 10), int):
        print("ERROR: El campo 'FS' debe ser un número entero")
        return False
    
    if not isinstance(config.get('n_channels', 16), int):
        print("ERROR: El campo 'n_channels' debe ser un número entero")
        return False
    
    # Todos los campos son válidos
    return True