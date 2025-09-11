# TDMS2MAT

## Instalación de dependencias

1. Abre una consola en la carpeta donde se encuentra el archivo `requirements.txt`.
2. Ejecuta uno de los siguientes comandos:

   ```bash
   pip install -r requirements.txt
   ```
   o, alternativamente:
   ```bash
   py -m pip install -r requirements.txt
   ```

## Requisito adicional

Es necesario tener **7-Zip** instalado en el sistema y configurado en el **PATH** (variables de entorno) para que sea accesible desde la línea de comandos.

## Configuración del archivo `config.json`

El archivo de configuración es fundamental para el funcionamiento del programa. Debes crear un archivo `config.json` (puedes usar `config_example.json` como plantilla) y asegurarte de que las rutas estén correctamente configuradas:

- **input_folder**: Ruta absoluta a la carpeta donde se encuentran los archivos de entrada (por ejemplo, archivos `.zip` o `.tdms`).  
  **Ejemplo:**  
  `"input_folder": "C:/ruta/a/tu/carpeta/entrada"`

- **output_folder**: Ruta absoluta a la carpeta donde se guardarán los archivos de salida procesados.  
  **Ejemplo:**  
  `"output_folder": "C:/ruta/a/tu/carpeta/salida"`

- **excel_output_folder**: Ruta absoluta a la carpeta donde se guardarán los archivos Excel generados.  
  **Ejemplo:**  
  `"excel_output_folder": "C:/ruta/a/tu/carpeta/salida_excels"`

- **last_processed**: Nombre del último archivo procesado (incluye la extensión del archivo, por ejemplo, `"Prueba.zip"`).  
  **Ejemplo:**  
  `"last_processed": "Prueba.zip"`

- **ruta_matlab_script**: Ruta absoluta a la carpeta donde se encuentra el script de MATLAB que será ejecutado.  
  **Ejemplo:**  
  `"ruta_matlab_script": "C:/ruta/a/tu/carpeta/matlab_script"`

- **matlab_path**: Ruta absoluta al ejecutable de MATLAB (incluye el nombre del archivo ejecutable, por ejemplo, `"matlab.exe"`).  
  **Ejemplo:**  
  `"matlab_path": "C:/Program Files/Polyspace/R2021a/bin/matlab.exe"`

- **selected_files**: Lista de archivos específicos a procesar. Deben incluir el nombre y la extensión del archivo, no la ruta completa.  
  **Ejemplo:**  
  `"selected_files": ["Prueba.zip"]`

**Resumen:**
- Las rutas que terminan en `/carpeta` deben apuntar a carpetas.
- Las rutas que terminan en `.exe` o `.m` deben apuntar a archivos específicos.
- Los nombres de archivos (como en `last_processed` y `selected_files`) deben incluir la extensión, pero no la ruta completa.

## Ejemplo de configuración

```json
{
    "input_folder": "C:/Users/Documents/TDMS2MAT/entrada",
    "output_folder": "C:/Users/Documents/TDMS2MAT/salida",
    "excel_output_folder": "C:/Users/Documents/TDMS2MAT/salida_excels",
    "last_processed": "Prueba.zip",
    "ruta_matlab_script": "C:/Users/Documents/TDMS2MAT",
    "matlab_path": "C:/Program Files/Polyspace/R2021a/bin/matlab.exe",
    // ...otros parámetros...
    "selected_files": [
        "Prueba.zip"
    ]
}
```

Asegúrate de modificar las rutas según la ubicación real de tus carpetas y archivos en tu sistema.

## Ejecución

Una vez configurado todo, ejecuta el script principal según las instrucciones de tu proyecto.
