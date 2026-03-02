# AGENT_CONTEXT.md — Registro de la reestructuración TDMS2MAT

Este documento registra las decisiones de arquitectura, los bugs corregidos
y el orden de implementación de la migración del proyecto TDMS2MAT desde
una estructura plana (13 archivos en raíz) hacia un paquete Python correcto.

---

## 1. Motivación

El proyecto original tenía varios problemas graves:

1. **Bug crítico de estado global** — `datos_por_dia` y `datos_lock` en
   `csv_utils.py` eran variables de módulo. Un segundo procesamiento dentro
   del mismo proceso Python mezclaba datos del primer run.
2. **Duplicación de clases** — `ProcessingError` estaba definida en dos
   módulos distintos (`main.py` y `decompress_utils.py`).
3. **Zona horaria hardcodeada** — el offset de -3 horas estaba enterrado
   dentro de `tdms_utils.py` y no era configurable.
4. **`logging.basicConfig`** llamado dos veces (en `main.py` y en
   `matlab_utils.py`), lo que producía mensajes duplicados en el log.
5. **Inyección de rutas en MATLAB** — las comillas simples en rutas Windows
   (`C:\Users\Juan's files\...`) corrompían el comando `-batch`.
6. **`channel_names` ausente** en los `.mat`, obligando a MATLAB a usar
   índices numéricos ciegos.
7. **`cancel_futures=True`** en `ThreadPoolExecutor.shutdown()` sólo está
   disponible desde Python 3.9; el código declaraba soporte para 3.8.
8. Sin `pyproject.toml`, sin tests, sin separación de dominio.

---

## 2. Decisiones de arquitectura

### 2.1 Estructura de paquetes

```
tdms2mat/
├── config/         ← Pydantic v2 (AppConfig)
├── pipeline/       ← Etapas del pipeline principal
├── analysis/       ← Análisis post-proceso (startup, excel concat)
├── tdms_direct/    ← Conversión TDMS→MAT sin ZIP ni CSV
├── gui/            ← GUI ttkbootstrap
└── utils/          ← Utilidades transversales (logging, excepciones)
```

La separación por dominio (no por tipo de archivo) permite importar
módulos individuales sin arrastrar dependencias de la GUI o de MATLAB.

### 2.2 Pydantic v2 para configuración

Se eligió Pydantic v2 por:
- Validación de tipos automática y mensajes de error claros.
- `extra="ignore"` para compatibilidad con `config.json` anteriores que
  puedan tener claves desconocidas.
- `@field_validator(mode="before")` para coercionar strings de `tkinter
  IntVar` a `int`.
- Escritura atómica del JSON (`tmp → bak → config`) para evitar
  corrupción en caso de error.

### 2.3 Corrección del bug de estado global

```python
# ANTES (csv_utils.py) — BUG
datos_por_dia: Dict = defaultdict(list)   # módulo-level global
datos_lock = threading.Lock()

# DESPUÉS (csv_processor.py) — CORREGIDO
def ordenar_y_agrupado_por_dia(...):
    datos_por_dia: Dict = defaultdict(list)   # local a la función
    datos_lock = threading.Lock()
```

El test de regresión está en `tests/test_csv_processor.py::
TestOrdenarYAgrupadoPorDia::test_no_global_state_contamination`.

### 2.4 Escape de rutas para MATLAB

```python
def _escape_matlab_str(s: str) -> str:
    """Escapa comillas simples para uso en comandos -batch de MATLAB."""
    return s.replace("'", "''")
```

Aplicado a todas las rutas que se insertan en el string del comando.

### 2.5 Compatibilidad Python 3.8 para ThreadPoolExecutor

```python
# ANTES — Python 3.9+ only
executor.shutdown(cancel_futures=True)

# DESPUÉS — Python 3.8 compatible
for pending in futuros:
    pending.cancel()
executor.shutdown(wait=False)
```

---

## 3. Archivos originales y sus reemplazos

| Original | Nuevo | Notas |
|----------|-------|-------|
| `main.py` | `tdms2mat/pipeline/orchestrator.py` | Orquestador completo |
| `config_utils.py` | `tdms2mat/config/config_utils.py` | Escritura atómica |
| `decompress_utils.py` | `tdms2mat/pipeline/decompress.py` | log_callback en todo |
| `tdms_utils.py` | `tdms2mat/pipeline/tdms_reader.py` | TZ configurable, todos los grupos |
| `csv_utils.py` | `tdms2mat/pipeline/csv_processor.py` | **Bug global corregido** |
| `mat_utils.py` | `tdms2mat/pipeline/mat_writer.py` | Añade `channel_names` |
| `matlab_utils.py` | `tdms2mat/pipeline/matlab_runner.py` | Escapa rutas |
| `startup_shutdown_counter.py` | `tdms2mat/analysis/startup_counter.py` | Constantes nombradas |
| `concat_excels.py` | `tdms2mat/analysis/excel_concat.py` | Sin Tkinter, sin dead code |
| `gui.py` | `tdms2mat/gui/app.py` | Refactorizado en secciones |
| `tdms_to_mat_simple.py` | `tdms2mat/tdms_direct/converter.py` | Sin PANDAS_AVAILABLE |
| `user_interaction.py` | `auxiliares/legacy/` (mover manualmente) | Deprecado |

Los archivos originales en la raíz del proyecto **no han sido eliminados**
para preservar compatibilidad con scripts externos que los importen
directamente. Se recomienda eliminarlos una vez validada la migración.

---

## 4. Tests

| Archivo | Qué prueba |
|---------|-----------|
| `tests/test_config.py` | `AppConfig` (validación, coerción, round-trip JSON) |
| `tests/test_csv_processor.py` | Regresión del bug global + funcionalidad básica |
| `tests/test_mat_writer.py` | `channel_names` en .mat, shape de `data`, limpieza de CSV |
| `tests/test_startup_counter.py` | Counts, runtime hours, parse_fecha, process_mat_folder |

---

## 5. Comandos de verificación

```bash
# Instalar en modo desarrollo
pip install -e ".[dev]"

# Lint
ruff check tdms2mat/

# Type check
mypy tdms2mat/ --ignore-missing-imports

# Tests
pytest tests/ -v

# Smoke test: importar el orquestador
python -c "from tdms2mat.pipeline.orchestrator import main; print('OK')"

# Smoke test: importar el converter
python -c "from tdms2mat.tdms_direct.converter import procesar_tdms_a_mat; print('OK')"

# Lanzar GUI
python -m tdms2mat
```

---

## 6. Próximos pasos sugeridos

1. Eliminar los archivos `.py` raíz originales tras validar la migración.
2. Mover `user_interaction.py` → `auxiliares/legacy/user_interaction.py`.
3. Configurar CI (GitHub Actions) con `pytest` y `ruff`.
4. Empaquetar con PyInstaller usando el `gui.spec` existente (actualizar paths).
