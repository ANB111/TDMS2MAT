# TDMS2MAT

Convierte archivos TDMS de LabVIEW/NI a formato `.mat` de MATLAB,
con procesamiento por día, ejecución de scripts MATLAB, conteo de
arranques/paradas y generación de informes en Excel.

## Índice

- [Flujo de datos](#flujo-de-datos)
- [Requisitos](#requisitos)
- [Preparación del entorno de desarrollo](#preparación-del-entorno-de-desarrollo)
- [Configuración](#configuración-configjson)
- [Modificación del código y procesamiento](#modificación-del-código-y-procesamiento)
- [Ejecución en modo desarrollo](#ejecución-en-modo-desarrollo)
- [Pruebas y controles de calidad](#pruebas-y-controles-de-calidad)
- [Compilación con PyInstaller](#compilación-con-pyinstaller)
- [Ejecutar la versión compilada](#ejecutar-la-versión-compilada)
- [Solución de problemas](#solución-de-problemas)
- [Estructura del paquete](#estructura-del-paquete)

---

## Flujo de datos

```
ZIP(s)
  └── descomprimir  →  carpeta TDMS
        └── tdms_reader  →  CSV individuales (por canal)
              └── csv_processor  →  CSV diarios agrupados (YY.M.D.csv)
                    └── mat_writer  →  YY.M.D-uNN.mat
                          ├── matlab_runner  →  Excel de rainflow
                          ├── startup_counter  →  Excel arranques/paradas
                          └── excel_concat  →  Excel consolidado
```

El modo **TDMS directo** (`tdms_direct/converter.py`) omite la
etapa ZIP→CSV y convierte directamente TDMS → MAT conservando
todos los grupos y la fecha/hora originales.

---

## Requisitos

### Software obligatorio

- Windows.
- Python 3.8 o superior. El proyecto puede ejecutarse con versiones
  modernas de Python; antes de distribuir, debe probarse la versión
  concreta que se use para compilar.
- Git, si se va a obtener o actualizar el repositorio mediante Git.
- **7-Zip** instalado y disponible en el PATH (para descompresión)
- Las dependencias Python que administra `pyproject.toml`.

### Software opcional

- MATLAB, solo para las etapas de rainflow y generación de gráficos.
- MATLAB debe estar instalado y `matlab.exe` debe configurarse en
  `matlab_path`, o estar disponible mediante una ruta válida.

### Comprobación de 7-Zip

El pipeline ZIP necesita que el ejecutable `7z` pueda encontrarse
desde la terminal:

```powershell
7z
```

Si el comando no se reconoce, agregue a `PATH` la carpeta de
instalación, normalmente:

```text
C:\Program Files\7-Zip
```

Después cierre y vuelva a abrir PowerShell.

---

## Preparación del entorno de desarrollo

Abra PowerShell y sitúese en la raíz del repositorio:

```powershell
cd D:\Documents\Labse\TDMS2MAT
```

Compruebe la instalación de Python:

```powershell
py --version
python --version
```

Si usa Python desde el lanzador `py`, puede crear el entorno virtual
para 64 bits con:

```powershell
py -3.14 -m venv .venv
```

Para una instalación que siga el requisito general del proyecto, use
una versión admitida por las dependencias de `pyproject.toml`, por
ejemplo:

```powershell
py -3.12 -m venv .venv
```

Active el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script de activación, habilítelo solamente
para el usuario actual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Si no necesita activar el entorno, puede llamar siempre directamente:

```powershell
.\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe -m pip
```

Instale el proyecto editable junto con las herramientas de desarrollo:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

La instalación editable incluye pytest, cobertura, mypy, Ruff y
PyInstaller. Compruebe que el entorno esté sano:

```powershell
python -m pip check
python -c "import pydantic, ttkbootstrap, nptdms, pandas, numpy, scipy; print('Dependencias OK')"
```

Si `pyproject.toml` no puede utilizarse por una infraestructura
especial, las dependencias principales pueden instalarse directamente:

```powershell
python -m pip install "nptdms>=1.4,<2" "pandas>=1.5,<3" "scipy>=1.9,<2" "numpy>=1.23,<3" "ttkbootstrap>=1.10,<2" "openpyxl>=3.1,<4" "pydantic>=2,<3"
```

---

## Configuración (`config.json`)

Cree la configuración local antes de ejecutar la aplicación:

```powershell
Copy-Item config_example.json config.json
```

Edite `config.json` y adapte las rutas y opciones. `config.json` está
incluido en `.gitignore` porque contiene configuración local.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `input_folder` | str | `""` | Carpeta con los `.zip` de entrada |
| `output_folder` | str | `""` | Carpeta destino de los `.mat` |
| `excel_output_folder` | str | `""` | Carpeta Excel de rainflow |
| `tdms_input_folder` | str | `""` | Carpeta `.tdms` para modo directo |
| `tdms_output_folder` | str | `""` | Salida `.mat` del modo directo |
| `matlab_path` | str | `""` | Ruta al ejecutable `matlab.exe` |
| `ruta_matlab_script` | str | `""` | Carpeta con `procesar_matlab.m` |
| `ruta_guardado_graficos` | str | `""` | Carpeta para gráficos PNG |
| `FS` | int | `10` | Frecuencia de muestreo (Hz) |
| `n_channels` | int | `16` | Número de canales esperados |
| `unidad` | str | `"05"` | Sufijo de unidad (ej. `"05"` → `-u05`) |
| `timezone_offset_hours` | int | `-3` | Desfase horario (ej. `-3` = Argentina) |
| `csv_decimal_separator` | str | `"."` | Separador decimal de CSV (`"."` o `","`) |
| `descomprimir` | bool | `true` | Habilita el pipeline ZIP→MAT |
| `rainflow` | bool | `false` | Ejecuta script MATLAB de rainflow |
| `realizar_conteo` | bool | `false` | Conteo de arranques/paradas |
| `concatenar_excels` | bool | `false` | Concatena excels de rainflow |
| `graficos_matlab` | bool | `false` | Guarda gráficos MATLAB como PNG |
| `eliminar_tdms_original` | bool | `false` | Elimina TDMS tras conversión directa |
| `procesar_incompleto` | bool | `false` | Incluye días incompletos (`_temp.csv`) |

Rutas recomendadas en Windows:

```json
{
  "input_folder": "D:/datos_tdms/zips",
  "output_folder": "D:/datos_tdms/salida",
  "excel_output_folder": "D:/datos_tdms/excels",
  "tdms_input_folder": "D:/datos_tdms/tdms",
  "tdms_output_folder": "D:/datos_tdms/mat_directo",
  "matlab_path": "C:/Program Files/MATLAB/R2023b/bin/matlab.exe",
  "ruta_matlab_script": "D:/Documents/Labse/TDMS2MAT"
}
```

La configuración de la GUI se guarda automáticamente al presionar
Procesar. Para una ejecución de la CLI por configuración, consulte
el pipeline con:

```powershell
python -m tdms2mat.pipeline.orchestrator config.json
```

---

## Modificación del código y procesamiento

### Ubicación de cada etapa

| Cambio requerido | Archivo principal |
|---|---|
| Interfaz, botones y llamadas a procesamiento | `tdms2mat/gui/app.py` |
| Punto de entrada de la GUI | `tdms2mat/__main__.py` |
| Coordinación general del pipeline | `tdms2mat/pipeline/orchestrator.py` |
| Descompresión ZIP | `tdms2mat/pipeline/decompress.py` |
| Lectura de TDMS | `tdms2mat/pipeline/tdms_reader.py` |
| Agrupación por día y CSV | `tdms2mat/pipeline/csv_processor.py` |
| Escritura de archivos MAT | `tdms2mat/pipeline/mat_writer.py` |
| Ejecución del análisis MATLAB | `tdms2mat/pipeline/matlab_runner.py` |
| Script MATLAB de rainflow | `procesar_matlab.m` |
| Conteo de arranques/paradas | `tdms2mat/analysis/startup_counter.py` |
| Concatenación de Excel | `tdms2mat/analysis/excel_concat.py` |
| Conversión directa TDMS → MAT | `tdms2mat/tdms_direct/converter.py` |
| Campos y validación de la configuración | `tdms2mat/config/schema.py` |
| Lectura y escritura de `config.json` | `tdms2mat/config/config_utils.py` |

Al modificar el procesamiento:

1. Cree o ajuste primero una prueba en `tests/`.
2. Modifique la función correspondiente sin cambiar las interfaces
   existentes salvo que todas sus llamadas se actualicen.
3. Ejecute la prueba enfocada.
4. Ejecute toda la suite.
5. Pruebe al menos una conversión real desde la GUI.
6. Si agrega un campo a `config.json`, actualice:
   - `config/schema.py`
   - `config_example.json`
   - `tdms2mat/gui/app.py`
   - La tabla de este README.
7. Si modifica `procesar_matlab.m`, pruebe el script manualmente desde
   MATLAB y luego desde la GUI.

Los datos `.tdms`, `.zip`, `.mat`, `.csv` y `.xlsx` se excluyen del
repositorio por `.gitignore`. No modifique ni confirme archivos reales
de producción accidentalmente.

---

## Ejecución en modo desarrollo

### GUI

```powershell
.\.venv\Scripts\python.exe -m tdms2mat
```

Punto de entrada: `tdms2mat/__main__.py`.

### CLI: conversión directa TDMS → MAT

```powershell
# Convertir todos los TDMS de una carpeta
.\.venv\Scripts\python.exe -m tdms2mat.tdms_direct.converter .\mis_tdms .\salida_mat

# Con eliminación de originales y 8 hilos
.\.venv\Scripts\python.exe -m tdms2mat.tdms_direct.converter .\mis_tdms --eliminar --workers 8

# Ver información de estructura de un archivo
.\.venv\Scripts\python.exe -m tdms2mat.tdms_direct.converter .\mis_tdms --info
```

Use `--help` para consultar todas las opciones:

```powershell
.\.venv\Scripts\python.exe -m tdms2mat.tdms_direct.converter --help
```

### Ejecutable asociado al entorno

Después de una instalación editable también puede ejecutarse:

```powershell
tdms2mat
```

---

## Estructura del paquete

```
tdms2mat/
├── __init__.py           # versión del paquete
├── __main__.py           # python -m tdms2mat → lanza la GUI
├── config/
│   ├── schema.py         # AppConfig (Pydantic v2)
│   └── config_utils.py   # load/save/validate, escritura atómica
├── pipeline/
│   ├── decompress.py     # ZIP → TDMS
│   ├── tdms_reader.py    # TDMS → CSV
│   ├── csv_processor.py  # CSV → CSV por día
│   ├── mat_writer.py     # CSV → .mat
│   ├── matlab_runner.py  # llama a MATLAB
│   └── orchestrator.py   # coordina todas las etapas
├── analysis/
│   ├── startup_counter.py  # arranques/paradas → Excel
│   └── excel_concat.py     # concatena excels de rainflow
├── tdms_direct/
│   └── converter.py      # TDMS → MAT directo (sin CSV)
├── gui/
│   └── app.py            # interfaz gráfica (ttkbootstrap)
└── utils/
    ├── exceptions.py     # ProcessingError (única definición)
    ├── logging_utils.py  # setup_logging / get_logger
    └── threading_utils.py # check_stop_event
```

---

## Pruebas y controles de calidad

Ejecute todas las pruebas:

```powershell
# Ejecutar todos los tests
.\.venv\Scripts\python.exe -m pytest tests -v
```

Ejecute una prueba específica:

```powershell
# Solo el test de regresión del bug de estado global
.\.venv\Scripts\python.exe -m pytest tests/test_csv_processor.py::TestOrdenarYAgrupadoPorDia::test_no_global_state_contamination -v
```

Ejecute los analizadores incluidos:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy tdms2mat
```

Una modificación está lista para compilar cuando:

- Todas las pruebas pasan.
- `pip check` no informa conflictos.
- La aplicación abre desde el entorno virtual.
- Se procesa al menos un archivo real o representativo.
- Los `.mat`, archivos Excel o gráficos esperados se crean en la
  ubicación configurada.

### Información técnica adicional

Los archivos de pruebas usan datos sintéticos y temporales. No se
necesitan TDMS reales para las pruebas unitarias, pero sí se necesitan
para validar el procesamiento completo y las diferencias de
estructura/grupos en archivos reales.

---

## Compilación con PyInstaller

La especificación incluida es `gui.spec`. Compila la GUI en una ventana
sin consola.

### 1. Preparar archivos requeridos

Antes de compilar, confirme que existen en la raíz:

```text
gui.spec
tdms2mat/__main__.py
procesar_matlab.m
config.json
icon.ico
icon.png
```

`icon.png` es opcional en el código, pero se incluye en `gui.spec`.
Prepare `config.json` desde el ejemplo antes de empaquetar.

### 2. Compilar

Desde la raíz del proyecto y con el entorno activado:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean gui.spec
```

Si PyInstaller no se encuentra instalado:

```powershell
python -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean gui.spec
```

El resultado debe quedar en:

```text
dist\TDMS2MAT.exe
```

PyInstaller también genera/actualiza información en `build\` y
conserva temporalmente los recursos. Ambos directorios pueden
eliminarse en una compilación limpia.

No borre archivos manualmente mientras haya una compilación activa.
Para limpiar compilaciones anteriores:

```powershell
Remove-Item -Recurse -Force build
Remove-Item -Recurse -Force dist
```

Luego vuelva a ejecutar:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean gui.spec
```

### 3. Qué incluye el empaquetado

`gui.spec` incluye:

- El módulo y paquete `tdms2mat`.
- `procesar_matlab.m`.
- `config.json`.
- `icon.ico` e `icon.png`.
- Los módulos ocultos necesarios de Tkinter, Pillow y ttkbootstrap.

Si se agregan archivos `.m`, imágenes o recursos que usa el programa:

1. Agréguelos a `datas` en `gui.spec`.
2. Acceda a ellos mediante una ruta compatible con PyInstaller
   (`sys._MEIPASS`) si es parte del bundle.
3. Compile nuevamente.
4. Pruebe desde `dist\TDMS2MAT.exe`, no desde el entorno de desarrollo.

### 4. Cambiar el nombre o el icono

El nombre e icono están definidos en `gui.spec`:

```text
name='TDMS2MAT'
icon='icon.ico'
```

Después de cambiar el nombre o el icono, compile nuevamente con
`--clean`. Si cambia el nombre del ejecutable, también deberá ajustar
cualquier documentación o script que haga referencia a
`dist\TDMS2MAT.exe`.

---

## Ejecutar la versión compilada

Ejecute:

```powershell
.\dist\TDMS2MAT.exe
```

Distribuya normalmente:

```text
dist\TDMS2MAT.exe
config.json
procesar_matlab.m
```

Para cada equipo configure rutas absolutas válidas en `config.json`.
La versión compilada necesita:

- **7-Zip** disponible en `PATH`.
- Permisos de lectura/escritura en las carpetas configuradas.
- MATLAB solo si habilita `rainflow` o `graficos_matlab`.
- Las rutas de MATLAB y el script MATLAB configuradas correctamente.

No dependa de que el ejecutable encuentre datos en la carpeta actual
si no confirmó las rutas. Para rutas relativas, debe estar establecida
la carpeta de trabajo desde la cual se inicia el programa.

---

## Solución de problemas

### `No module named pydantic`

El entorno virtual no tiene las dependencias instaladas:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### `No module named pytest`

Instale el grupo de desarrollo:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### `7z` no se encuentra

Instale 7-Zip y agregue su carpeta al `PATH`, o verifique:

```powershell
where.exe 7z
```

### MATLAB no ejecuta el script

Compruebe:

1. `matlab_path` apunta a `matlab.exe`.
2. `ruta_matlab_script` apunta a la carpeta que contiene
   `procesar_matlab.m`.
3. El script existe con ese nombre exacto.
4. MATLAB puede abrir los archivos MAT de entrada.

### La GUI compilada no abre

Compile sin limpiar el log:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean gui.spec
```

Ejecute el compilador desde PowerShell y revise los errores anteriores
al finalizar. Confirme que `icon.ico`, `config.json`,
`procesar_matlab.m` y la carpeta `tdms2mat` existen antes de compilar.

### Dependencias rotas

Recree el entorno virtual:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pip check
```
