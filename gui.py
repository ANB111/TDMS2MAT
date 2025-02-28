import os
import json
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, StringVar, IntVar, BooleanVar, Listbox
from threading import Thread, Event
from main import main  # Importa tu función principal

CONFIG_FILE = "config.json"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Procesador de Archivos TDMS")
        self.root.geometry("1000x800")  # Ventana más grande
        self.root.resizable(True, True)  # Permitir el redimensionado
        
        # Variables de configuración
        self.config = {
            "input_folder": StringVar(),
            "output_folder": StringVar(),
            "excel_output_folder": StringVar(),
            "ruta_matlab_script": StringVar(),
            "matlab_path": StringVar(),
            "FS": IntVar(value=10),
            "escritura": BooleanVar(value=True),
            "n_channels": IntVar(value=16),
            "unidad": StringVar(value="05"),
            "procesar_incompleto": BooleanVar(value=False),
            "descomprimir": BooleanVar(value=False),
            "rainflow": BooleanVar(value=False),
            "realizar_conteo": BooleanVar(value=False),
            "graficos_matlab": BooleanVar(value=False)
        }
        
        # Bandera para detener el procesamiento
        self.stop_event = Event()
        
        # Lista de archivos seleccionados
        self.selected_files = []
        
        self.load_config()
        self.create_widgets()

    def create_labeled_entry(self, parent, label_text, config_key, row, column):
        """Crea un campo de entrada con una etiqueta."""
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, padx=5, pady=2, sticky="w")

        ttk.Label(frame, text=label_text).grid(row=0, column=0, padx=5, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.config[config_key], width=20)
        entry.grid(row=0, column=1)

        # Validación para campos numéricos
        if isinstance(self.config[config_key], IntVar):
            validate_cmd = (self.root.register(self.validate_int), '%P')
            entry.config(validate="key", validatecommand=validate_cmd)

    def validate_int(self, value):
        """Valida que el valor ingresado sea un entero positivo."""
        return value == "" or value.isdigit()

    def create_folder_input(self, parent, label_text, config_key):
        """Crea un campo de entrada con un botón para seleccionar carpetas."""
        frame = ttk.Frame(parent)
        frame.grid(pady=2, sticky="ew")

        ttk.Label(frame, text=label_text).grid(row=0, column=0, padx=5, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.config[config_key], width=40)
        entry.grid(row=0, column=1, padx=5, sticky="ew")

        def select_folder():
            folder = filedialog.askdirectory()
            if folder:
                self.config[config_key].set(folder)
                if config_key == "input_folder":
                    self.refresh_file_list()

        ttk.Button(frame, text="...", command=select_folder, bootstyle="secondary").grid(row=0, column=2, padx=5)

    def refresh_file_list(self):
        """Actualiza la lista de archivos en el Listbox."""
        input_folder = self.config["input_folder"].get()
        if not os.path.isdir(input_folder):
            return
        
        files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]
        self.file_listbox.delete(0, "end")
        for file in files:
            self.file_listbox.insert("end", file)

    def toggle_all_files(self, select=True):
        """Selecciona o deselecciona todos los archivos en el Listbox."""
        for i in range(self.file_listbox.size()):
            self.file_listbox.selection_set(i) if select else self.file_listbox.selection_clear(i)

    def get_selected_files(self):
        """Obtiene los archivos seleccionados en el Listbox."""
        selected_indices = self.file_listbox.curselection()
        input_folder = self.config["input_folder"].get()
        return [os.path.join(input_folder, self.file_listbox.get(i)) for i in selected_indices]

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(7, weight=1)
        
        # Título
        ttk.Label(main_frame, text="Configuración de Procesamiento", font=("Helvetica", 14, "bold")).grid(row=0, column=0, pady=10, sticky="w")
        
        # Rutas de archivos y carpetas
        paths_frame = ttk.Labelframe(main_frame, text="Rutas de Archivos y Carpetas", padding=10)
        paths_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        paths_frame.grid_columnconfigure(0, weight=1)
        self.create_folder_input(paths_frame, "Carpeta de Entrada:", "input_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida:", "output_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida Excel:", "excel_output_folder")
        
        # Archivos a procesar
        file_selection_frame = ttk.Labelframe(main_frame, text="Archivos a Procesar", padding=10)
        file_selection_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        file_selection_frame.grid_columnconfigure(0, weight=1)
        file_selection_frame.grid_rowconfigure(0, weight=1)
        
        self.file_listbox = Listbox(file_selection_frame, selectmode="extended")
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(file_selection_frame, orient="vertical", command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        button_frame = ttk.Frame(file_selection_frame)
        button_frame.grid(row=1, column=0, pady=5)
        ttk.Button(button_frame, text="Seleccionar Todos", command=lambda: self.toggle_all_files(select=True)).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Deseleccionar Todos", command=lambda: self.toggle_all_files(select=False)).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Refrescar Lista", command=self.refresh_file_list).grid(row=0, column=2, padx=5)  # Botón para refrescar
        
        # Parámetros de procesamiento
        params_frame = ttk.Labelframe(main_frame, text="Parámetros de Procesamiento", padding=10)
        params_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        grid_frame = ttk.Frame(params_frame)
        grid_frame.grid(row=0, column=0)
        self.create_labeled_entry(grid_frame, "Frecuencia de Muestreo (FS):", "FS", 0, 0)
        self.create_labeled_entry(grid_frame, "Número de Canales:", "n_channels", 0, 1)
        self.create_labeled_entry(grid_frame, "Unidad a Procesar:", "unidad", 1, 0)
        
        ttk.Checkbutton(params_frame, text="Habilitar escritura en MATLAB", variable=self.config["escritura"], bootstyle="round-toggle").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(params_frame, text="Procesar archivos incompletos", variable=self.config["procesar_incompleto"], bootstyle="round-toggle").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(params_frame, text="Generar Gráficos MATLAB", variable=self.config["graficos_matlab"], bootstyle="round-toggle").grid(row=3, column=0, sticky="w", pady=2)
        
        # Procesos a ejecutar
        process_frame = ttk.Labelframe(main_frame, text="Procesos a Ejecutar", padding=10)
        process_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        ttk.Checkbutton(process_frame, text="Descomprimir Archivos", variable=self.config["descomprimir"], bootstyle="round-toggle").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(process_frame, text="Aplicar Rainflow", variable=self.config["rainflow"], bootstyle="round-toggle").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(process_frame, text="Realizar Conteo de Arranques/Paradas", variable=self.config["realizar_conteo"], bootstyle="round-toggle").grid(row=2, column=0, sticky="w", pady=2)
        
        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate", bootstyle="info-striped")
        self.progress.grid(row=5, column=0, sticky="ew", pady=5)
        
        # Área de registro (log)
        log_frame = ttk.Labelframe(main_frame, text="Registro de Procesamiento", padding=10)
        log_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        self.log_text = ttk.Text(log_frame, wrap="word", height=10)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Botones de acción
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=7, column=0, sticky="ew", pady=5)
        ttk.Button(btn_frame, text="Iniciar Procesamiento", command=self.start_processing, bootstyle="success-outline").grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Detener Procesamiento", command=self.stop_processing, bootstyle="danger-outline").grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Configuración Avanzada", command=self.open_advanced_config, bootstyle="info-outline").grid(row=0, column=2, padx=5)

    def log_message(self, message):
        """Añade un mensaje al área de registro."""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def start_processing(self):
        required_keys = ["input_folder", "output_folder", "excel_output_folder"]
        for key in required_keys:
            if not self.config[key].get():
                messagebox.showerror("Error", f"Por favor, complete el campo '{key}'.")
                return
        
        self.selected_files = self.get_selected_files()
        if not self.selected_files:
            messagebox.showerror("Error", "No se han seleccionado archivos para procesar.")
            return
        
        self.stop_event.clear()
        self.progress.start()
        self.log_text.delete("1.0", "end")
        Thread(target=self.run_main, daemon=True).start()

    def stop_processing(self):
        """Detiene el procesamiento en curso."""
        self.stop_event.set()
        self.log_message("El procesamiento ha sido detenido por el usuario.")

    def run_main(self):
        try:
            while not self.stop_event.is_set():
                config = {k: v.get() for k, v in self.config.items()}
                config["selected_files"] = self.selected_files
                self.save_config()
                main(config, log_callback=self.log_message)
                if self.stop_event.is_set():
                    break
            self.log_message("El procesamiento ha finalizado correctamente.")
        except Exception as e:
            self.log_message(f"Ocurrió un error: {e}")
        finally:
            self.progress.stop()

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({k: v.get() for k, v in self.config.items()}, f, indent=4)

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k in self.config:
                            self.config[k].set(v)
        except Exception as e:
            messagebox.showwarning("Advertencia", f"No se pudo cargar la configuración: {e}")

    def open_advanced_config(self):
        """Abre la configuración avanzada (por implementar)."""
        messagebox.showinfo("Información", "La configuración avanzada aún no está disponible.")

# Inicialización de la aplicación
root = ttk.Window(themename="superhero")
app = App(root)
root.mainloop()