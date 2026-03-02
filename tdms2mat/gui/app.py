"""Interfaz gráfica principal de TDMS2MAT.

Refactorizaciones respecto al original (gui.py):
- Añadido ``if __name__ == "__main__"`` guard (lanzamiento no ocurre al importar).
- ``save_config`` / ``load_config`` usan la implementación única de
  ``tdms2mat.config.config_utils`` (escritura atómica; no coexisten dos estrategias).
- ``_run`` ya no escribe directamente al JSON con ``f.seek(0); f.truncate()``.
- ``log_message``: el ``messagebox.showerror`` por línea fue reemplazado por un
  flag ``_pending_errors`` que acumula errores; el popups se muestra al terminar.
- Los métodos de construcción de widgets están separados por sección:
  ``_build_folder_section``, ``_build_file_section``, ``_build_params_section``,
- ``_build_process_section``, ``_build_log_section``.
- Se añaden type hints a los métodos principales.
- Los imports del paquete apuntan a ``tdms2mat.*``.
"""
from __future__ import annotations

import json
import glob
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Event, Thread
from typing import Any, Dict, List, Optional

import tkinter as tk
import tkinter.simpledialog as sd
from tkinter import END, BooleanVar, IntVar, Listbox, StringVar, filedialog, messagebox

import ttkbootstrap as ttk  # type: ignore[import]
from ttkbootstrap.constants import *  # noqa: F403

from tdms2mat.config.config_utils import load_config, save_config
from tdms2mat.config.schema import AppConfig
from tdms2mat.pipeline.orchestrator import main as run_pipeline

# ---------------------------------------------------------------------------
# Constantes del módulo
# ---------------------------------------------------------------------------
CONFIG_FILE = "config.json"
BASE_DIR: Path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON_PATH: Path = BASE_DIR / "icon.png"


class App:
    """Ventana principal de la aplicación TDMS2MAT."""

    def __init__(self, root: ttk.Window) -> None:
        self.root = root
        self.root.title("Procesador de Archivos TDMS")
        self.root.geometry("1000x950")
        self.root.resizable(True, True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        self._set_window_icon()

        # Flag "procesar desde último"
        self.use_last: BooleanVar = BooleanVar(value=False)

        # Variables de configuración (espejo de AppConfig para Tkinter)
        self.config: Dict[str, Any] = {
            "input_folder": StringVar(),
            "output_folder": StringVar(),
            "excel_output_folder": StringVar(),
            "last_processed": StringVar(value=""),
            "ruta_matlab_script": StringVar(),
            "matlab_path": StringVar(),
            "ruta_guardado_graficos": StringVar(),
            "FS": IntVar(value=10),
            "descomprimir": BooleanVar(value=True),
            "n_channels": IntVar(value=16),
            "unidad": StringVar(value="05"),
            "procesar_incompleto": BooleanVar(value=False),
            "rainflow": BooleanVar(value=False),
            "realizar_conteo": BooleanVar(value=False),
            "concatenar_excels": BooleanVar(value=False),
            "graficos_matlab": BooleanVar(value=False),
        }

        self.stop_event: Event = Event()
        self.selected_files: List[str] = []
        # Acumulador de errores para mostrar al finalizar (en vez de popup por línea)
        self._pending_errors: List[str] = []
        # Estado de la barra de progreso
        self._stage_text: StringVar = StringVar(value="")
        self._detail_text: StringVar = StringVar(value="")
        self._status_text: StringVar = StringVar(value="● Listo")
        self._run_start_time: float = 0.0
        self._elapsed_timer_id: Optional[str] = None
        # Snapshot de archivos .mat existentes antes del run (para limpieza en cancelación)
        self._mat_files_before: set = set()

        self._load_config()
        self._create_widgets()
        self.toggle_processing_options()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def _on_closing(self) -> None:
        if messagebox.askokcancel("Salir", "¿Desea salir de la aplicación?"):
            self.stop_event.set()
            self.root.destroy()

    # ------------------------------------------------------------------
    # Config I/O — usa la implementación única del paquete
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Carga configuración desde disco y la aplica a las variables Tk."""
        cfg: AppConfig = load_config(CONFIG_FILE)
        raw: Dict[str, Any] = cfg.model_dump()
        for key, var in self.config.items():
            if key in raw:
                try:
                    var.set(raw[key])  # type: ignore[arg-type]
                except Exception as exc:
                    self.logger.warning("No se pudo cargar config '%s': %s", key, exc)

    def _save_config(self) -> None:
        """Guarda las variables Tk en ``config.json`` de forma atómica."""
        try:
            raw: Dict[str, Any] = {k: v.get() for k, v in self.config.items()}
            raw["selected_files"] = self.selected_files
            cfg = AppConfig.model_validate(raw)
            save_config(cfg, CONFIG_FILE)
        except Exception as exc:
            self.logger.error("Error guardando configuración: %s", exc)

    # ------------------------------------------------------------------
    # Construcción de la interfaz — separada por secciones
    # ------------------------------------------------------------------

    def _create_widgets(self) -> None:
        self.root.columnconfigure(0, weight=1)
        mf = ttk.Frame(self.root, padding=10)
        mf.grid(sticky="nsew")
        mf.columnconfigure((0, 1), weight=1)

        self._build_folder_section(mf, row=0)
        self._build_file_section(mf, row=2)
        self._build_params_section(mf, row=3)
        self._build_process_section(mf, row=4)
        self._build_log_section(mf, row=5)
        self._build_action_bar(mf, row=7)

    def _build_folder_section(self, parent: ttk.Frame, row: int) -> None:
        pf = ttk.Labelframe(parent, text="Configuración de Carpetas", padding=10)
        pf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        pf.columnconfigure(1, weight=1)
        self._create_folder_input(pf, "Carpeta Entrada (.ZIP):", "input_folder", 0)
        self._create_folder_input(pf, "Carpeta de Salida (.MAT):", "output_folder", 1)
        self._create_folder_input(pf, "Carpeta de Salida (EXCELS):", "excel_output_folder", 2)

        # Checkbutton "desde último"
        cb = ttk.Checkbutton(
            parent,
            text="Procesar desde último archivo procesado",
            variable=self.use_last,
            command=self.toggle_last,
            bootstyle="info",
        )
        cb.grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=(5, 2))

    def _build_file_section(self, parent: ttk.Frame, row: int) -> None:
        # Lista disponibles
        self._available_lf = ttk.Labelframe(parent, text="Disponibles", padding=10)
        left = self._available_lf
        left.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.available_listbox = Listbox(left, selectmode="extended")
        self.available_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(left, command=self.available_listbox.yview).grid(
            row=0, column=1, sticky="ns"
        )
        btnf = ttk.Frame(left)
        btnf.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btnf, text="Refrescar", command=self.refresh_files).grid(
            row=0, column=0, padx=5
        )
        ttk.Button(btnf, text="Agregar >", command=self.add_selected).grid(
            row=0, column=1, padx=5
        )

        # Lista seleccionados
        self._selected_lf = ttk.Labelframe(parent, text="Seleccionados", padding=10)
        right = self._selected_lf
        right.grid(row=row, column=1, sticky="nsew", padx=5, pady=5)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.selected_listbox = Listbox(right, selectmode="extended")
        self.selected_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(right, command=self.selected_listbox.yview).grid(
            row=0, column=1, sticky="ns"
        )
        btnr = ttk.Frame(right)
        btnr.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btnr, text="< Quitar", command=self.remove_selected).grid(
            row=0, column=0, padx=5
        )

    def _build_params_section(self, parent: ttk.Frame, row: int) -> None:
        pf = ttk.Labelframe(parent, text="Parámetros de Procesamiento", padding=10)
        pf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        pf.columnconfigure((0, 1, 2), weight=1)
        self._create_labeled_entry(pf, "FS (Hz):", "FS", 0, 0)
        self._create_labeled_entry(pf, "Canales:", "n_channels", 0, 1)
        self._create_labeled_entry(pf, "Unidad:", "unidad", 0, 2)

    def _build_process_section(self, parent: ttk.Frame, row: int) -> None:
        pf = ttk.Labelframe(parent, text="Procesos", padding=10)
        pf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        pf.columnconfigure((0, 1), weight=1)

        ttk.Checkbutton(
            pf,
            text="Descomprimir y Procesar",
            variable=self.config["descomprimir"],
            bootstyle="round-toggle",
            command=self.toggle_processing_options,
        ).grid(row=0, column=0, sticky="w", pady=2)

        self.incompletos_cb = ttk.Checkbutton(
            pf,
            text="Procesar días incompletos",
            variable=self.config["procesar_incompleto"],
            bootstyle="round-toggle",
        )
        self.incompletos_cb.grid(row=0, column=1, sticky="w", pady=2)

        self.rainflow_cb = ttk.Checkbutton(
            pf,
            text="Rainflow",
            variable=self.config["rainflow"],
            bootstyle="round-toggle",
        )
        self.rainflow_cb.grid(row=1, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            pf,
            text="Conteo de Arranques/Paradas",
            variable=self.config["realizar_conteo"],
            bootstyle="round-toggle",
        ).grid(row=1, column=1, sticky="w", pady=2)

        self.graficos_matlab_cb = ttk.Checkbutton(
            pf,
            text="Almacenar gráficas de MATLAB",
            variable=self.config["graficos_matlab"],
            bootstyle="round-toggle",
        )
        self.graficos_matlab_cb.grid(row=2, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            pf,
            text="Concatenar Excels",
            variable=self.config["concatenar_excels"],
            bootstyle="round-toggle",
        ).grid(row=2, column=1, sticky="w", pady=2)

    def _build_log_section(self, parent: ttk.Frame, row: int) -> None:
        lf = ttk.Labelframe(parent, text="Registro de Actividad", padding=10)
        lf.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=5)
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self.log_text = ttk.Text(lf, wrap="word", height=10, state="disabled")
        self.log_text.grid(sticky="nsew")
        ttk.Scrollbar(lf, command=self.log_text.yview).grid(row=0, column=1, sticky="ns")

        # Colores del log
        self.log_text.tag_config("error",    foreground="#ff5555")
        self.log_text.tag_config("warn",     foreground="#ffb86c")
        self.log_text.tag_config("ok",       foreground="#50fa7b")
        self.log_text.tag_config("stage",    foreground="#8be9fd", font=("TkDefaultFont", 9, "bold"))
        self.log_text.tag_config("state",    foreground="#bd93f9")
        self.log_text.tag_config("default",  foreground="")

        # Área de progreso
        prog_frame = ttk.Frame(parent)
        prog_frame.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        prog_frame.columnconfigure(0, weight=1)

        # Fila superior: etapa + tiempo
        info_frame = ttk.Frame(prog_frame)
        info_frame.grid(row=0, column=0, sticky="ew")
        info_frame.columnconfigure(0, weight=1)
        self._stage_label = ttk.Label(info_frame, textvariable=self._stage_text,
                                      font=("TkDefaultFont", 9), bootstyle="info")
        self._stage_label.grid(row=0, column=0, sticky="w")
        self._elapsed_label = ttk.Label(info_frame, text="",
                                        font=("TkDefaultFont", 9), bootstyle="secondary")
        self._elapsed_label.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # Fila de detalle por archivo
        self._detail_label = ttk.Label(prog_frame, textvariable=self._detail_text,
                                       font=("TkDefaultFont", 8), bootstyle="secondary")
        self._detail_label.grid(row=1, column=0, sticky="w", pady=(0, 1))

        # Barra de progreso
        self.progress = ttk.Progressbar(prog_frame, mode="determinate",
                                        bootstyle="info-striped", maximum=1, value=0)
        self.progress.grid(row=2, column=0, sticky="ew", pady=(2, 0))

    def _build_action_bar(self, parent: ttk.Frame, row: int) -> None:
        bf = ttk.Frame(parent)
        bf.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        bf.columnconfigure(4, weight=1)  # empuja el indicador de estado a la derecha

        self._btn_start = ttk.Button(
            bf, text="▶  Procesar Archivos", command=self.start, bootstyle="success"
        )
        self._btn_start.grid(row=0, column=0, padx=5)

        self._btn_cancel = ttk.Button(
            bf, text="■  Cancelar", command=self._cancel, bootstyle="danger-outline",
            state="disabled"
        )
        self._btn_cancel.grid(row=0, column=1, padx=5)

        ttk.Button(
            bf, text="🗑 Limpiar Log", command=self.clear_log, bootstyle="secondary-outline"
        ).grid(row=0, column=2, padx=5)

        ttk.Button(
            bf, text="⚙️  Avanzado", command=self.open_advanced_config, bootstyle="info-outline"
        ).grid(row=0, column=3, padx=5)

        # Indicador de estado (extremo derecho)
        self._status_indicator = ttk.Label(
            bf, textvariable=self._status_text, font=("TkDefaultFont", 9, "bold"),
            bootstyle="secondary"
        )
        self._status_indicator.grid(row=0, column=5, padx=(20, 5), sticky="e")

    # ------------------------------------------------------------------
    # Helpers de construcción de widgets reutilizables
    # ------------------------------------------------------------------

    def _create_labeled_entry(
        self,
        parent: ttk.Frame,
        text: str,
        key: str,
        row: int,
        col: int,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, padx=5, pady=2, sticky="w")
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=5, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.config[key], width=20)
        entry.grid(row=0, column=1)
        if isinstance(self.config[key], IntVar):
            vc = (self.root.register(lambda v: v == "" or v.isdigit()), "%P")
            entry.config(validate="key", validatecommand=vc)

    def _create_folder_input(
        self, parent: ttk.Frame, text: str, key: str, row: int
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, pady=2, sticky="ew")
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=5, sticky="w")
        ttk.Entry(frame, textvariable=self.config[key], width=40).grid(
            row=0, column=1, sticky="ew"
        )

        def sel() -> None:
            d = filedialog.askdirectory()
            if d and os.path.isdir(d):
                self.config[key].set(d)
                if key == "input_folder":
                    self.refresh_files()

        ttk.Button(frame, text="...", command=sel, bootstyle="secondary").grid(
            row=0, column=2, padx=5
        )
        frame.columnconfigure(1, weight=1)

    def _create_file_input(
        self,
        parent: ttk.Frame,
        text: str,
        key: str,
        row: int,
        filetypes: tuple,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, pady=2, sticky="ew")
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=5, sticky="w")
        ttk.Entry(frame, textvariable=self.config[key], width=40).grid(
            row=0, column=1, sticky="ew"
        )

        def sel() -> None:
            f = filedialog.askopenfilename(filetypes=filetypes)
            if f and os.path.isfile(f):
                self.config[key].set(f)

        ttk.Button(frame, text="...", command=sel, bootstyle="secondary").grid(
            row=0, column=2, padx=5
        )
        frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Listas de archivos
    # ------------------------------------------------------------------

    def _update_list_labels(self) -> None:
        """Actualiza los títulos de las listboxes con el conteo de archivos."""
        n_avail = self.available_listbox.size()
        n_sel = len(self.selected_files)
        self._available_lf.config(text=f"Disponibles  ({n_avail})" if n_avail else "Disponibles")
        self._selected_lf.config(text=f"Seleccionados  ({n_sel})" if n_sel else "Seleccionados")

    def refresh_files(self) -> None:
        folder = self.config["input_folder"].get()
        self.available_listbox.delete(0, END)
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if os.path.isfile(os.path.join(folder, f)):
                    self.available_listbox.insert(END, f)
        self._update_list_labels()

    def toggle_last(self) -> None:
        """Auto-llena la lista de seleccionados a partir de *last_processed*."""
        if self.use_last.get():
            last = self.config["last_processed"].get()
            if not last:
                messagebox.showwarning(
                    "¡Atención!", "No hay un último archivo procesado guardado."
                )
                self.use_last.set(False)
                return
            inp = self.config["input_folder"].get()
            try:
                all_files = [
                    f
                    for f in sorted(os.listdir(inp))
                    if os.path.isfile(os.path.join(inp, f))
                ]
                idx = all_files.index(last)
            except (FileNotFoundError, ValueError):
                messagebox.showwarning(
                    "¡Atención!",
                    f"El archivo '{last}' no existe en la carpeta de entrada.",
                )
                self.use_last.set(False)
                return
            to_proc = all_files[idx + 1 :]
            self.selected_files = to_proc
            self.selected_listbox.delete(0, END)
            for f in to_proc:
                self.selected_listbox.insert(END, f)
        else:
            self.selected_files.clear()
            self.selected_listbox.delete(0, END)

    def add_selected(self) -> None:
        for i in self.available_listbox.curselection():
            f = self.available_listbox.get(i)
            if f not in self.selected_files:
                self.selected_listbox.insert(END, f)
                self.selected_files.append(f)
        self._update_list_labels()

    def remove_selected(self) -> None:
        for i in reversed(self.selected_listbox.curselection()):
            f = self.selected_listbox.get(i)
            self.selected_listbox.delete(i)
            self.selected_files.remove(f)
        self._update_list_labels()

    # ------------------------------------------------------------------
    # Pipeline principal
    # ------------------------------------------------------------------

    def start(self) -> None:
        for k in ("input_folder", "output_folder", "excel_output_folder"):
            if not self.config[k].get():
                messagebox.showerror("Error", f"Falta configurar: {k}")
                return

        if not self.selected_files and self.config["descomprimir"].get():
            messagebox.showerror("Error", "No hay archivos para procesar.")
            return

        self._save_config()
        self.stop_event.clear()
        self._pending_errors.clear()

        # Snapshot: archivos .mat ya existentes antes del run (para limpiar si se cancela)
        out_dir = self.config["output_folder"].get()
        self._mat_files_before = set()
        if os.path.isdir(out_dir):
            self._mat_files_before = {
                os.path.join(out_dir, f)
                for f in os.listdir(out_dir)
                if f.endswith(".mat")
            }

        self._set_running_state(True)
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        cfg: Dict[str, Any] = {k: v.get() for k, v in self.config.items()}
        cfg["selected_files"] = self.selected_files
        success = False

        def confirm_continue_func(msg: str) -> bool:
            return self._run_on_main_thread(
                messagebox.askyesno,
                "Salto de días detectado",
                msg + "\n¿Desea continuar?",
            )

        def prompt_func(min_date: Any, max_date: Any) -> Optional[Any]:
            try:
                return self._run_on_main_thread(
                    self.prompt_start_date, min_date, max_date
                )
            except Exception as exc:
                self.log_message(f"Operación cancelada: {exc}")
                return None

        # Timestamp de inicio de la etapa actual; lista mutable para compartir
        # entre los dos closures sin 'nonlocal'.
        _stage_start: list[float] = [0.0]

        def on_progress(step: int, total: int, stage_name: str) -> None:
            _stage_start[0] = time.time()  # reinicia el cronómetro de ETA
            def _upd() -> None:
                if not self.root.winfo_exists():
                    return
                self.progress.config(maximum=total, value=step)
                self._stage_text.set(f"Etapa {step}/{total} — {stage_name}")
                self._detail_text.set("")  # limpiar detalle al cambiar de etapa
            self.root.after(0, _upd)

        def on_file_progress(current: int, total: int, name: str) -> None:
            """Actualiza detalle con progreso y ETA basado en promedio por archivo."""
            # Calcular ETA en el hilo del pipeline (antes del after())
            eta_str = ""
            if current > 0 and _stage_start[0] > 0:
                elapsed = time.time() - _stage_start[0]
                avg_per_file = elapsed / current
                remaining_secs = avg_per_file * (total - current)
                if remaining_secs >= 3600:
                    h = int(remaining_secs // 3600)
                    m = int((remaining_secs % 3600) // 60)
                    eta_str = f"  |  ETA: {h}h {m}m"
                elif remaining_secs >= 60:
                    m = int(remaining_secs // 60)
                    s = int(remaining_secs % 60)
                    eta_str = f"  |  ETA: {m}m {s}s"
                elif remaining_secs > 0:
                    eta_str = f"  |  ETA: {int(remaining_secs)}s"
            detail = f"{current}/{total} — {name}{eta_str}"
            def _upd() -> None:
                if not self.root.winfo_exists():
                    return
                self._detail_text.set(detail)
            self.root.after(0, _upd)

        try:
            success = run_pipeline(
                cfg,
                log_callback=self.log_message,
                confirm_continue_func=confirm_continue_func,
                prompt_func=prompt_func,
                stop_event=self.stop_event,
                progress_callback=on_progress,
                file_progress_callback=on_file_progress,
            )
            if success and self.selected_files:
                last = self.selected_files[-1]
                self.config["last_processed"].set(last)
                self._save_config()
                self.log_message(f"Guardado último archivo: {last}")
        except Exception as exc:
            self.log_message(f"ERROR: {exc}")
        finally:
            # Limpieza si fue cancelado
            if self.stop_event.is_set():
                self._cleanup_cancelled_run(cfg)
            self._set_running_state(False, success=success)
            # Mostrar errores acumulados al final (un solo popup)
            if self._pending_errors:
                errors_text = "\n".join(self._pending_errors[:10])
                if len(self._pending_errors) > 10:
                    errors_text += f"\n... y {len(self._pending_errors) - 10} más."
                self._run_on_main_thread(
                    messagebox.showerror, "Errores durante el procesamiento", errors_text
                )
                self._pending_errors.clear()

    # ------------------------------------------------------------------
    # Logging thread-safe
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Helpers de estado UI
    # ------------------------------------------------------------------

    def _set_running_state(self, running: bool, success: bool = False) -> None:
        """Activa/desactiva controles y actualiza indicadores visuales."""
        def _upd() -> None:
            if not self.root.winfo_exists():
                return
            if running:
                self._btn_start.config(state="disabled")
                self._btn_cancel.config(state="normal")
                self._status_text.set("● Procesando...")
                self._status_indicator.config(bootstyle="info")
                self._run_start_time = time.time()
                self._tick_elapsed()
                self.progress.config(value=0, maximum=1)
                self._stage_text.set("Preparando...")
                self._detail_text.set("")
            else:
                self._btn_start.config(state="normal")
                self._btn_cancel.config(state="disabled")
                self._stop_elapsed()
                self._detail_text.set("")
                if success:
                    self._status_text.set("● Completado")
                    self._status_indicator.config(bootstyle="success")
                    self._stage_text.set("Proceso finalizado correctamente.")
                    self.progress.config(bootstyle="success")
                else:
                    stopped = self.stop_event.is_set()
                    self._status_text.set("● Cancelado" if stopped else "● Error")
                    self._status_indicator.config(bootstyle="warning" if stopped else "danger")
                    self._stage_text.set("Proceso cancelado." if stopped else "El proceso terminó con errores.")
                    self.progress.config(bootstyle="warning" if stopped else "danger")
        self.root.after(0, _upd)

    def _tick_elapsed(self) -> None:
        """Actualiza el label de tiempo transcurrido cada segundo."""
        if not self.root.winfo_exists() or not self._run_start_time:
            return
        if not self.config.get("_running"):  # early guard — use btn state
            pass
        elapsed = int(time.time() - self._run_start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        txt = f"{m:02d}:{s:02d}" if h == 0 else f"{h}h {m:02d}:{s:02d}"
        self._elapsed_label.config(text=f"⏱ {txt}")
        # Seguir actualizando solo si el botón de cancelar está activo
        if str(self._btn_cancel.cget("state")) == "normal":
            self._elapsed_timer_id = self.root.after(1000, self._tick_elapsed)  # type: ignore

    def _stop_elapsed(self) -> None:
        if self._elapsed_timer_id:
            self.root.after_cancel(self._elapsed_timer_id)
            self._elapsed_timer_id = None

    # ------------------------------------------------------------------
    # Cancelación y limpieza
    # ------------------------------------------------------------------

    def _cancel(self) -> None:
        """Muestra confirmación y cancela el procesamiento si el usuario acepta."""
        if messagebox.askyesno(
            "Cancelar procesamiento",
            "¿Desea cancelar el procesamiento?\n"
            "Se eliminarán todos los archivos generados durante esta sesión.",
        ):
            self.stop_event.set()

    def _cleanup_cancelled_run(self, cfg: dict) -> None:
        """Elimina archivos generados desde que se inició el procesamiento cancelado."""
        self.log_message("[Limpieza] Eliminando archivos generados durante el procesamiento cancelado...")

        # 1. Carpeta temporal de extracción/CSVs
        temp_folder = os.path.join(tempfile.gettempdir(), "tdms2mat_temp")
        if os.path.exists(temp_folder):
            try:
                shutil.rmtree(temp_folder)
                self.log_message("[Limpieza] Carpeta temporal eliminada.")
            except Exception as exc:
                self.log_message(f"[Limpieza] No se pudo limpiar temp: {exc}")

        # 2. Archivos .mat nuevos (no existían antes del run)
        out_dir = cfg.get("output_folder", "")
        if os.path.isdir(out_dir):
            deleted = 0
            for fname in os.listdir(out_dir):
                if not fname.endswith(".mat"):
                    continue
                fp = os.path.join(out_dir, fname)
                if fp not in self._mat_files_before:
                    try:
                        os.remove(fp)
                        deleted += 1
                    except Exception:
                        pass
            if deleted:
                self.log_message(f"[Limpieza] {deleted} archivo(s) .mat eliminados.")

        # 3. Archivos _temp.csv del estado parcial
        state_folder = os.path.join(out_dir, ".state")
        if os.path.exists(state_folder):
            for f in glob.glob(os.path.join(state_folder, "*_temp.csv")):
                try:
                    os.remove(f)
                except Exception:
                    pass
        self.log_message("[Limpieza] Limpieza completada.")

    # ------------------------------------------------------------------
    # Logging thread-safe con colores
    # ------------------------------------------------------------------

    def log_message(self, msg: str) -> None:
        """Inserta *msg* en el log de forma thread-safe con color por tipo."""
        if not self.root.winfo_exists():
            return

        msg_l = msg.lower()
        if "error" in msg_l or msg.startswith("ERROR"):
            tag = "error"
            self._pending_errors.append(msg)
        elif "advertencia" in msg_l or "warning" in msg_l:
            tag = "warn"
        elif any(x in msg_l for x in ("completado:", "✔", "exitosamente", "ok ", "correcto")):
            tag = "ok"
        elif any(x in msg_l for x in ("iniciando:", "[estado]", "-----")):
            tag = "stage"
        elif any(x in msg_l for x in ("guardado", "restaurado", "procesado:")):
            tag = "state"
        else:
            tag = "default"

        def _update() -> None:
            self.log_text.config(state="normal")
            self.log_text.insert(END, msg + "\n", tag)
            self.log_text.see(END)
            self.log_text.config(state="disabled")
            self.root.update_idletasks()

        self.root.after(0, _update)

    def _run_on_main_thread(self, func: Any, *args: Any) -> Any:
        """Ejecuta *func* en el hilo principal y devuelve su resultado."""
        q: Queue = Queue()

        def wrapper() -> None:
            try:
                q.put(func(*args))
            except Exception as exc:
                q.put(exc)

        self.root.after(0, wrapper)
        result = q.get()
        if isinstance(result, Exception):
            raise result
        return result

    # ------------------------------------------------------------------
    # Diálogo de fecha de inicio (para concat_excels)
    # ------------------------------------------------------------------

    def prompt_start_date(self, min_date: Any, max_date: Any) -> Optional[Any]:
        from datetime import datetime as dt_

        def date_to_str(d: Any) -> str:
            if isinstance(d, tuple):
                return f"{d[0]}.{d[1]}.{d[2]}"
            return d.strftime("%y.%m.%d")

        while True:
            prompt = (
                "Ingrese la fecha de inicio de concatenación\n"
                "(formato: AA.MM.DD, ej: 25.7.15)\n"
                f"Rango: {date_to_str(min_date)} — {date_to_str(max_date)}"
            )
            date_str = sd.askstring("Fecha de inicio", prompt, parent=self.root)
            if date_str is None:
                raise Exception("Operación cancelada por el usuario.")

            parsed = None
            try:
                parts = date_str.strip().split(".")
                if len(parts) == 3:
                    y, m, d = map(int, parts)
                    parsed = (y, m, d)
            except (ValueError, TypeError):
                pass

            if not parsed:
                messagebox.showerror(
                    "Error", "Formato inválido. Use AA.MM.DD (ej: 25.7.15)"
                )
                continue

            min_dt = (
                dt_(2000 + min_date[0], min_date[1], min_date[2])
                if isinstance(min_date, tuple)
                else min_date
            )
            max_dt = (
                dt_(2000 + max_date[0], max_date[1], max_date[2])
                if isinstance(max_date, tuple)
                else max_date
            )
            parsed_dt = dt_(2000 + parsed[0], parsed[1], parsed[2])

            if parsed_dt < min_dt:
                messagebox.showinfo(
                    "Info",
                    f"Fecha anterior al primer archivo. Se usará {date_to_str(min_date)}.",
                )
                return (
                    (min_date.year - 2000, min_date.month, min_date.day)
                    if isinstance(min_date, dt_)
                    else min_date
                )
            if parsed_dt > max_dt:
                messagebox.showerror(
                    "Error", "Fecha posterior al último archivo disponible."
                )
            else:
                return parsed

    # ------------------------------------------------------------------
    # Controles de opciones
    # ------------------------------------------------------------------

    def toggle_processing_options(self) -> None:
        state = "normal" if self.config["descomprimir"].get() else "disabled"
        if state == "disabled":
            self.config["rainflow"].set(False)
            self.config["graficos_matlab"].set(False)
            self.config["procesar_incompleto"].set(False)
        for cb in (self.rainflow_cb, self.graficos_matlab_cb, self.incompletos_cb):
            cb.config(state=state)

    def clear_log(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Configuración avanzada (MATLAB)
    # ------------------------------------------------------------------

    def open_advanced_config(self) -> None:
        win = ttk.Toplevel(self.root)
        win.title("Configuración Avanzada")
        win.geometry("700x250")
        win.resizable(True, True)

        matlab_frame = ttk.Labelframe(win, text="Rutas de MATLAB", padding=10)
        matlab_frame.pack(fill="x", expand=True, padx=10, pady=10)
        matlab_frame.columnconfigure(0, weight=1)

        self._create_file_input(
            matlab_frame,
            "Ruta de matlab.exe:",
            "matlab_path",
            0,
            (("Executable files", "*.exe"), ("All files", "*.*")),
        )
        self._create_folder_input(
            matlab_frame, "Carpeta de script .m:", "ruta_matlab_script", 1
        )
        self._create_folder_input(
            matlab_frame, "Carpeta para guardar gráficos:", "ruta_guardado_graficos", 2
        )

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=10)

        def save_and_close() -> None:
            self._save_config()
            win.destroy()

        ttk.Button(
            btn_frame, text="Guardar y Cerrar", command=save_and_close, bootstyle="success"
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="Cancelar", command=win.destroy, bootstyle="secondary"
        ).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Icono de la ventana
    # ------------------------------------------------------------------

    def _set_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            self.root.iconbitmap(default=str(ICON_PATH))
        except Exception:
            pass
        if ICON_PATH.suffix.lower() in {".png", ".gif"}:
            try:
                self._icon_image = tk.PhotoImage(file=str(ICON_PATH))
                self.root.iconphoto(False, self._icon_image)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Punto de entrada standalone (no se ejecuta al importar el módulo)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = ttk.Window(themename="superhero")
    App(root)
    root.mainloop()
