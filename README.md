# TDMS2MAT

## Instalación paso a paso

Abre PowerShell en la carpeta del proyecto:

```powershell
cd D:\Documents\Labse\TDMS2MAT
```

### 1. Crear el entorno virtual

El entorno virtual mantiene las dependencias del proyecto separadas de otras instalaciones de Python:

```powershell
python -m venv .venv
```

Si `.venv` ya existe, este paso no es necesario. Si `python` no apunta a Python 3.14, usa el ejecutable de Python 3.14 instalado en tu equipo. Por ejemplo, con una instalación gestionada por `uv`:

```powershell
& C:\ruta\a\python3.14.exe -m venv .venv
```

### 2. Instalar las dependencias

Usa siempre el Python de `.venv`, tanto para instalar paquetes como para ejecutar el programa:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para compilar el ejecutable también es necesario instalar PyInstaller:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

### 3. Instalar 7-Zip

Es necesario tener **7-Zip** instalado en el sistema y configurado en el **PATH** (variables de entorno) para que sea accesible desde la línea de comandos.

Puedes comprobarlo desde PowerShell con:

```powershell
7z
```

Si el comando no se reconoce, añade la carpeta de instalación de 7-Zip al `PATH` y reinicia PowerShell.

## Configuración de `config.json`

El programa necesita un archivo `config.json` en la carpeta del proyecto. Créalo a partir de la plantilla:

```powershell
Copy-Item .\config_example.json .\config.json
```

Después, edita `config.json` y configura las rutas reales:

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

- **FS**: Frecuencia de muestreo utilizada por el procesamiento.
- **descomprimir**, **procesar_incompleto**, **rainflow**, **realizar_conteo**, **graficos_matlab** y **concatenar_excels**: Opciones booleanas (`true` o `false`) que activan o desactivan partes del procesamiento.
- **n_channels**: Número de canales del archivo de entrada.
- **unidad**: Identificador de la unidad o configuración de medida.

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
    "FS": 10,
    "descomprimir": true,
    "n_channels": 16,
    "unidad": "05",
    "procesar_incompleto": true,
    "rainflow": true,
    "realizar_conteo": true,
    "graficos_matlab": false,
    "concatenar_excels": true,
    "selected_files": [
        "Prueba.zip"
    ]
}
```

Asegúrate de modificar las rutas según la ubicación real de tus carpetas y archivos en tu sistema.

## Ejecutar la aplicación

Desde la carpeta del proyecto, ejecuta:

```powershell
.\.venv\Scripts\python.exe .\gui.py
```

También puedes seleccionar `.venv\Scripts\python.exe` como intérprete de Python en VS Code y ejecutar `gui.py` desde el editor.

No ejecutes la aplicación con otro `python.exe` ni con un `pip` diferente: las dependencias podrían quedar instaladas en un intérprete distinto.

## Compilar el ejecutable `.exe`

El proyecto incluye [gui.spec](gui.spec), que contiene la configuración de PyInstaller y añade `procesar_matlab.m` y `config.json` al paquete.

1. Comprueba que `config.json` existe y contiene tus rutas reales.
2. Instala PyInstaller siguiendo el paso 2 anterior.
3. Ejecuta la compilación:

  ```powershell
  .\.venv\Scripts\pyinstaller.exe --clean .\gui.spec
  ```

El ejecutable se generará en:

```text
dist\gui.exe
```

Puedes iniciarlo con:

```powershell
.\dist\gui.exe
```

Si modificas el código, vuelve a ejecutar el comando de compilación. Las carpetas `build` y `dist` se pueden regenerar; no es necesario ejecutar PyInstaller con un Python global.
