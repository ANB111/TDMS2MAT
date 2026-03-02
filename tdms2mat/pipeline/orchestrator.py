"""Orquestador del pipeline de procesamiento TDMS → MAT.

Reemplaza al antiguo ``main.py``.  Coordina las etapas del pipeline en orden,
con manejo de errores uniforme, verificaciones de cancelación y logging.

Cambios respecto al original:
- ``ProcessingError`` importada desde ``utils.exceptions`` (no duplicada).
- ``logging.basicConfig`` eliminado (lo gestiona ``utils.logging_utils``).
- Los imports apuntan a los módulos refactorizados del paquete.
- El ``timezone_offset_hours`` se pasa explícitamente desde el config en lugar
  de estar hardcodeado en ``tdms_reader``.
- **Gestión de estado persistente**: los días incompletos (``_temp.csv``) se
  guardan en ``state_folder`` entre ejecuciones, sobreviviendo reinicios del
  sistema.  Al inicio de cada run se restauran automáticamente para ser
  completados con los nuevos datos.
"""
from __future__ import annotations

import glob
import os
import shutil
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from tdms2mat.config.schema import AppConfig
from tdms2mat.pipeline.decompress import decompress_zip_files
from tdms2mat.pipeline.tdms_reader import procesar_archivos_tdms_paralelo
from tdms2mat.pipeline.csv_processor import ordenar_y_agrupado_por_dia
from tdms2mat.pipeline.mat_writer import csv_to_mat
from tdms2mat.pipeline.matlab_runner import process_mat_files
from tdms2mat.analysis.startup_counter import process_mat_folder
from tdms2mat.analysis.excel_concat import concat_excels
from tdms2mat.utils.exceptions import ProcessingError
from tdms2mat.utils.threading_utils import check_stop_event
from tdms2mat.utils.logging_utils import get_logger

logger = get_logger("orchestrator")

# Tipado reutilizable
LogFunc = Callable[[str], None]
ConfirmFunc = Callable[[str], bool]
PromptFunc = Callable[..., Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def setup_folders(folders: List[str], log: LogFunc) -> bool:
    """Crea las carpetas necesarias si no existen."""
    for folder in folders:
        if not folder:
            log("ADVERTENCIA: Ruta de carpeta vacía detectada.")
            return False
        p = Path(folder)
        if not p.exists():
            try:
                log(f"Creando carpeta: '{folder}'")
                p.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                log(f"ERROR: No se pudo crear '{folder}': {exc}")
                return False
    return True


def process_stage(
    name: str,
    func: Callable,
    args: tuple,
    log: LogFunc,
    continue_on_error: bool = False,
) -> bool:
    """Ejecuta una etapa del pipeline con captura de excepciones uniforme."""
    log(f"Iniciando: {name}...")
    try:
        func(*args)
        log(f"Completado: {name}.")
        return True
    except ProcessingError:
        raise  # Dejar que el bucle principal capture la cancelación.
    except Exception as exc:
        log(f"ERROR en {name}: {exc}")
        log(f"Detalles: {traceback.format_exc()}")
        if not continue_on_error:
            return False
        log("Continuando a pesar del error...")
        return False


# ---------------------------------------------------------------------------
# Gestión de estado persistente (días incompletos)
# ---------------------------------------------------------------------------

def restore_incomplete_days(state_folder: str, temp_folder: str, log: LogFunc) -> None:
    """Copia los CSV de días incompletos del estado persistente al temp de procesamiento.

    Esto permite que el nuevo batch de datos sea mezclado por ``csv_processor``
    con el último día incompleto del run anterior, completándolo si hay datos
    suficientes.

    Precondición: tanto ``state_folder`` como ``temp_folder`` deben existir.
    """
    incomplete = glob.glob(os.path.join(state_folder, "*_temp.csv"))
    if not incomplete:
        return
    log(f"[Estado] Restaurando {len(incomplete)} día(s) incompleto(s) del estado anterior.")
    for src in incomplete:
        basename = os.path.basename(src)
        dst = os.path.join(temp_folder, basename)
        shutil.copy2(src, dst)
        log(f"[Estado] Restaurado: {basename}")


def update_incomplete_days(temp_folder: str, state_folder: str, log: LogFunc) -> None:
    """Actualiza el estado persistente tras la conversión CSV→MAT.

    Lógica:
    - Los ``_temp.csv`` que quedan en *temp_folder* son días que siguen
      incompletos → se mueven a *state_folder* (reemplazando la versión
      anterior si existía).
    - Los días que estaban en *state_folder* y ya NO aparecen como incompletos
      en *temp_folder* se completaron en este run → se eliminan del estado.

    Finalmente limpia *temp_folder* de cualquier CSV diario ya convertido.
    """
    # Días incompletos que quedan tras este run
    new_incomplete = {
        os.path.basename(f): f
        for f in glob.glob(os.path.join(temp_folder, "*_temp.csv"))
    }

    # Días que estaban guardados en el estado anterior
    old_state = {
        os.path.basename(f): f
        for f in glob.glob(os.path.join(state_folder, "*_temp.csv"))
    }

    # Mover incompletos nuevos a state_folder
    for name, src in new_incomplete.items():
        dst = os.path.join(state_folder, name)
        shutil.move(src, dst)
        log(f"[Estado] Día incompleto guardado: {name}")

    # Eliminar del estado los días que se completaron en este run
    for name, old_f in old_state.items():
        if name not in new_incomplete and os.path.exists(old_f):
            os.remove(old_f)
            log(f"[Estado] Día completado, removido del estado: {name}")

    # Limpiar temp_folder: eliminar los CSVs diarios ya convertidos (no _temp)
    remaining_csvs = glob.glob(os.path.join(temp_folder, "*.csv"))
    cleaned = 0
    for f in remaining_csvs:
        try:
            os.remove(f)
            cleaned += 1
        except OSError as exc:
            log(f"[Estado] No se pudo limpiar '{os.path.basename(f)}': {exc}")
    if cleaned:
        log(f"[Estado] Limpiados {cleaned} CSV temporales de procesamiento.")

    if new_incomplete:
        log(
            f"[Estado] {len(new_incomplete)} día(s) incompleto(s) guardados para el próximo run: "
            + ", ".join(new_incomplete.keys())
        )
    else:
        log("[Estado] Todos los días procesados fueron completos.")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def main(
    config: Dict[str, Any],
    log_callback: Optional[LogFunc] = None,
    confirm_continue_func: Optional[ConfirmFunc] = None,
    prompt_func: Optional[PromptFunc] = None,
    stop_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> bool:
    """Punto de entrada del pipeline de procesamiento.

    Args:
        config: Dict con la configuración (compatible con :class:`AppConfig`).
        log_callback: Función para emitir mensajes al usuario (GUI o CLI).
        confirm_continue_func: Función que muestra un diálogo yes/no y devuelve
            ``bool``.  Usada al detectar saltos de días en la concatenación.
        prompt_func: Función que pide al usuario una fecha de inicio para la
            concatenación de excels.
        stop_event: Evento de cancelación cooperativa.
        progress_callback: ``(paso_actual, total_pasos, nombre_etapa)`` — llamada
            antes de iniciar cada etapa para actualizar la barra de progreso.

    Returns:
        ``True`` si el pipeline completó todas sus etapas, ``False`` si hubo
        error o cancelación.
    """

    def log(msg: str) -> None:
        if log_callback:
            log_callback(msg)
        else:
            logger.info(msg)

    log("----- Iniciando procesamiento -----")

    # Validar config
    try:
        cfg = AppConfig.model_validate(config)
    except Exception as exc:
        log(f"ERROR: Configuración inválida: {exc}")
        return False

    # Extraer parámetros
    input_folder = cfg.input_folder
    output_folder = cfg.output_folder
    excel_output_folder = cfg.excel_output_folder
    procesar_incompleto = cfg.procesar_incompleto
    unidad = cfg.unidad
    realizar_conteo = cfg.realizar_conteo
    descomprimir = cfg.descomprimir
    rainflow = cfg.rainflow
    selected_files = cfg.selected_files
    concatenar = cfg.concatenar_excels
    tz_offset = cfg.timezone_offset_hours
    decimal = cfg.csv_decimal_separator

    # La carpeta de estado es persistente (sobrevive reinicios).
    # Default: output_folder/.state  (oculta junto a los MAT)
    state_folder = cfg.state_folder or str(Path(output_folder) / ".state")
    # Temp: sólo para procesamiento dentro del run actual.
    temp_folder = os.path.join(tempfile.gettempdir(), "tdms2mat_temp")

    # Crear carpetas necesarias
    if not setup_folders(
        [input_folder, output_folder, excel_output_folder, temp_folder, state_folder], log
    ):
        log("ERROR: No se pudieron configurar las carpetas. Abortando.")
        return False

    if descomprimir and not selected_files:
        log("ADVERTENCIA: No se seleccionaron archivos para procesar.")
        return False

    if selected_files:
        log(f"Se procesarán {len(selected_files)} archivo(s).")
    else:
        log("No se seleccionaron archivos; solo se ejecutarán etapas independientes.")

    # ------------------------------------------------------------------
    # Fase A: ZIP → TDMS → CSV (agrupado por día) → MAT
    # Esta fase incluye gestión de estado de días incompletos.
    # ------------------------------------------------------------------
    phase_a_stages: List[Tuple[str, Callable, tuple]] = []

    if descomprimir:
        phase_a_stages += [
            (
                "Descompresión de archivos ZIP",
                decompress_zip_files,
                (input_folder, temp_folder, selected_files, stop_event, log_callback),
            ),
            (
                "Conversión TDMS → CSV",
                procesar_archivos_tdms_paralelo,
                (temp_folder, None, tz_offset, log_callback, stop_event),
            ),
            (
                "Ordenamiento y agrupación CSV por día",
                ordenar_y_agrupado_por_dia,
                (temp_folder, None, None, decimal, log_callback),
            ),
            (
                "Conversión CSV → MAT",
                csv_to_mat,
                (temp_folder, output_folder, unidad, procesar_incompleto, decimal, log_callback),
            ),
        ]

    # ------------------------------------------------------------------
    # Fase B: post-processing (MATLAB, conteo, concat)
    # ------------------------------------------------------------------
    phase_b_stages: List[Tuple[str, Callable, tuple]] = []

    if rainflow:
        phase_b_stages.append(
            (
                "Procesamiento rainflow con MATLAB",
                process_mat_files,
                (output_folder, cfg.to_legacy_dict(), log_callback),
            )
        )

    if realizar_conteo:
        excel_path = str(Path(excel_output_folder) / "arranque_paradas.xlsx")
        phase_b_stages.append(
            (
                "Conteo de arranques y paradas",
                process_mat_folder,
                (output_folder, excel_path, log_callback),
            )
        )

    if concatenar:
        concat_file = str(Path(excel_output_folder) / "concatenado.xlsx")

        def _run_concat() -> None:
            concat_excels(
                excel_output_folder,
                concat_file,
                prompt_func=prompt_func,
                log_func=log_callback or log,
            )

        phase_b_stages.append(
            (
                "Concatenación de excels",
                _run_concat,
                (),
            )
        )

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------
    success = True
    # Compute total stage count upfront for accurate progress reporting
    all_stages = phase_a_stages + phase_b_stages
    total_stages = len(all_stages)
    step = 0

    def _progress(name_stage: str) -> None:
        nonlocal step
        step += 1
        if progress_callback:
            progress_callback(step, total_stages, name_stage)

    try:
        # Antes de procesar nuevos datos: restaurar días incompletos del
        # run anterior al temp de procesamiento para que csv_processor los
        # incorpore en la agrupación por día.
        if descomprimir:
            restore_incomplete_days(state_folder, temp_folder, log)

        # --- Fase A ---
        for name_stage, func, args in phase_a_stages:
            check_stop_event(stop_event)
            _progress(name_stage)
            if not process_stage(name_stage, func, args, log):
                success = False
                log(f"Pipeline detenido en etapa: '{name_stage}'.")
                break

        # Actualizar estado de días incompletos (siempre, aunque haya error,
        # para no perder datos parciales ya procesados).
        if descomprimir:
            update_incomplete_days(temp_folder, state_folder, log)

        # --- Fase B (sólo si la Fase A fue exitosa) ---
        if success:
            for name_stage, func, args in phase_b_stages:
                check_stop_event(stop_event)
                _progress(name_stage)
                if not process_stage(name_stage, func, args, log):
                    success = False
                    log(f"Pipeline detenido en etapa: '{name_stage}'.")
                    break

    except ProcessingError as exc:
        log(str(exc))
        # Intentar guardar estado parcial antes de salir
        if descomprimir:
            try:
                update_incomplete_days(temp_folder, state_folder, log)
            except Exception:
                pass
        success = False

    if success:
        log("----- Proceso completado exitosamente -----")
    else:
        log("El proceso no se completó. Revise los errores anteriores.")

    return success


# ---------------------------------------------------------------------------
# CLI mínimo (sin GUI)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    raw = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    sys.exit(0 if main(raw) else 1)
