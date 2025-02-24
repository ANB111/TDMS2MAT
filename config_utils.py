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