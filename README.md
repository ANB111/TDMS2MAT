# TDMS2MAT

Convierte archivos TDMS de LabVIEW/NI a formato `.mat` de MATLAB,
con procesamiento por día, ejecución de scripts MATLAB, conteo de
arranques/paradas y generación de informes en Excel.

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

## Instalación

### Requisitos del sistema

- Python ≥ 3.8
- **7-Zip** instalado y disponible en el PATH (para descompresión)
- MATLAB (opcional, solo para etapas de rainflow y gráficos)

### Instalar el paquete

```bash
# Desarrollo (editable, incluye pytest/mypy/ruff)
pip install -e ".[dev]"

# Producción
pip install -e .
```

> Si tu entorno no admite `pyproject.toml`, instala directamente:
> `pip install nptdms pandas scipy numpy ttkbootstrap openpyxl pydantic`

---

## Configuración (`config.json`)

Copia `config_example.json` → `config.json` y adapta los valores.

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

---

## Ejecución

### GUI (interfaz gráfica)

```bash
python -m tdms2mat
```

### CLI — conversión directa TDMS → MAT

```bash
# Convertir todos los TDMS de una carpeta
python -m tdms2mat.tdms_direct.converter ./mis_tdms ./salida_mat

# Con eliminación de originales y 8 hilos
python -m tdms2mat.tdms_direct.converter ./mis_tdms --eliminar --workers 8

# Ver información de estructura de un archivo
python -m tdms2mat.tdms_direct.converter ./mis_tdms --info
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

## Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Solo el test de regresión del bug de estado global
pytest tests/test_csv_processor.py::TestOrdenarYAgrupadoPorDia::test_no_global_state_contamination -v
```

---

## Bugs corregidos en esta versión

| Bug | Módulo original | Fix |
|-----|----------------|-----|
| `datos_por_dia` y `datos_lock` como globales → contaminación entre runs | `csv_utils.py` | Variables locales en `csv_processor.py` |
| Zona horaria hardcodeada `-3` | `tdms_utils.py` | Parámetro `timezone_offset_hours` en `AppConfig` |
| `ProcessingError` definido dos veces | `main.py`, `decompress_utils.py` | Definición única en `utils/exceptions.py` |
| `logging.basicConfig` llamado dos veces | `main.py`, `matlab_utils.py` | Centralizado en `utils/logging_utils.py` |
| Rutas con `'` rompen el comando `-batch` de MATLAB | `matlab_utils.py` | `_escape_matlab_str()` en `matlab_runner.py` |
| `channel_names` ausente en `.mat` | `mat_utils.py` | Campo `channel_names` añadido en `mat_writer.py` |
| `cancel_futures=True` requiere Python 3.9+ | `tdms_to_mat_simple.py` | Reemplazado por `future.cancel()` + `wait=False` |

---

## Dependencias externas

- **7-Zip** (`7z` en PATH) — para descompresión de archivos `.zip`
- **MATLAB** — solo para los pasos `rainflow` y `graficos_matlab`
