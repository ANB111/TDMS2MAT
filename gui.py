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
        self.root.geometry("1000x950")  # Ventana más grande
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

        # Lista de archivos seleccionados (almacena rutas completas)
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
            if folder and os.path.isdir(folder):  # Verificar si la carpeta existe
                self.config[config_key].set(folder)
                if config_key == "input_folder":
                    self.refresh_file_list()

        ttk.Button(frame, text="...", command=select_folder, bootstyle="secondary").grid(row=0, column=2, padx=5)

    def refresh_file_list(self):
        """Actualiza la lista de archivos disponibles en el Listbox."""
        input_folder = self.config["input_folder"].get()
        if not os.path.isdir(input_folder):
            return

        files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]
        self.available_listbox.delete(0, "end")
        for file in files:
            self.available_listbox.insert("end", file)

    def toggle_all_files(self, listbox, select=True):
        """Selecciona o deselecciona todos los archivos en el Listbox."""
        for i in range(listbox.size()):
            listbox.selection_set(i) if select else listbox.selection_clear(i)

    def get_selected_files(self):
        """Obtiene las rutas completas de los archivos seleccionados."""
        input_folder = self.config["input_folder"].get()
        return [os.path.join(input_folder, file) for file in self.selected_files]
    
    def add_selected_files(self):
        """Agrega archivos seleccionados de la lista disponible a la lista de archivos seleccionados."""
        selected_indices = self.available_listbox.curselection()
        for index in selected_indices:
            file = self.available_listbox.get(index)
            if file not in self.selected_files:  # Evitar duplicados
                self.selected_listbox.insert("end", file)  # Agregar a la lista visible
                self.selected_files.append(file)  # Agregar solo el nombre del archivo

    def remove_selected_files(self):
        """Quita archivos seleccionados de la lista de archivos seleccionados."""
        selected_indices = self.selected_listbox.curselection()
        for index in reversed(selected_indices):  # Eliminar en orden inverso para evitar problemas con los índices
            file = self.selected_listbox.get(index)
            self.selected_listbox.delete(index)  # Quitar de la lista visible
            self.selected_files.remove(file)  # Quitar el nombre del archivo

    def log_message(self, message):
        """Añade un mensaje al área de registro."""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def stop_processing(self):
        """Detiene el procesamiento en curso."""
        self.stop_event.set()
        self.log_message("El procesamiento ha sido detenido por el usuario.")

    def start_processing(self):
        """
        Inicia el procesamiento después de actualizar y guardar la configuración.
        """
        # Actualizar los valores de self.config desde los widgets
        for key, var in self.config.items():
            if isinstance(var, StringVar):
                self.config[key].set(var.get())  # Actualizar variables de texto
            elif isinstance(var, IntVar):
                self.config[key].set(var.get())  # Actualizar variables numéricas
            elif isinstance(var, BooleanVar):
                self.config[key].set(var.get())  # Actualizar variables booleanas

        # Validar campos obligatorios
        required_keys = ["input_folder", "output_folder", "excel_output_folder"]
        for key in required_keys:
            if not self.config[key].get():
                messagebox.showerror("Error", f"Por favor, complete el campo '{key}'.")
                return

        # Obtener las rutas completas de los archivos seleccionados
        self.selected_files_full_paths = self.get_selected_files()
        if not self.selected_files_full_paths:
            messagebox.showerror("Error", "No se han seleccionado archivos para procesar.")
            return

        # Guardar la configuración actualizada en el archivo JSON
        self.save_config()

        # Reiniciar la bandera de detención y limpiar el área de registro
        self.stop_event.clear()
        self.progress.start()
        self.log_text.delete("1.0", "end")

        # Ejecutar el procesamiento en un hilo separado
        Thread(target=self.run_main, daemon=True).start()


    def run_main(self):
        """
        Ejecuta la función principal con la configuración actualizada.
        """
        try:
            # Crear una copia de la configuración actualizada
            config = {k: v.get() for k, v in self.config.items()}
            config["selected_files"] = self.selected_files  # Agregar los archivos seleccionados

            # Llamar a la función principal
            main(config, log_callback=self.log_message)

            self.log_message("El procesamiento ha finalizado correctamente.")
        except Exception as e:
            self.log_message(f"Ocurrió un error: {e}")
        finally:
            self.progress.stop()  # Detener la barra de progreso

    def save_config(self):
        """
        Guarda la configuración actual en el archivo JSON, incluyendo los archivos seleccionados.
        """
        try:
            # Crear una copia del diccionario de configuración
            config_to_save = {k: v.get() for k, v in self.config.items()}
            config_to_save["selected_files"] = self.selected_files  # Guardar solo los nombres de los archivos
            # Guardar en el archivo JSON
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_to_save, f, indent=4)
            print("Configuración guardada correctamente.")
        except Exception as e:
            messagebox.showwarning("Advertencia", f"No se pudo guardar la configuración: {e}")

    def load_config(self):
        """
        Carga la configuración desde el archivo JSON y elimina la lista de archivos seleccionados.
        """
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    # Eliminar la clave "selected_files" si existe
                    if "selected_files" in data:
                        del data["selected_files"]
                    # Restaurar las variables de configuración
                    for k, v in data.items():
                        if k in self.config:
                            self.config[k].set(v)
                # Guardar la configuración actualizada sin "selected_files"
                self.save_config()
        except Exception as e:
            messagebox.showwarning("Advertencia", f"No se pudo cargar la configuración: {e}")

    def open_advanced_config(self):
        """Abre la configuración avanzada (por implementar)."""
        messagebox.showinfo("Información", "La configuración avanzada aún no está disponible.")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)  # Columna izquierda
        main_frame.grid_columnconfigure(1, weight=1)  # Columna derecha
        main_frame.grid_rowconfigure(7, weight=1)     # Fila expansiva para el log

        # Título
        ttk.Label(main_frame, text="Configuración de Procesamiento", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, pady=10, sticky="w"
        )

        # Columna izquierda
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(4, weight=1)

        # Rutas de archivos y carpetas
        paths_frame = ttk.Labelframe(left_frame, text="Rutas de Archivos y Carpetas", padding=10)
        paths_frame.grid(row=0, column=0, sticky="ew", pady=5)
        paths_frame.grid_columnconfigure(0, weight=1)
        self.create_folder_input(paths_frame, "Carpeta de Entrada:", "input_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida:", "output_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida Excel:", "excel_output_folder")

        # Archivos disponibles
        available_files_frame = ttk.Labelframe(left_frame, text="Archivos Disponibles", padding=10)
        available_files_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        available_files_frame.grid_columnconfigure(0, weight=1)
        available_files_frame.grid_rowconfigure(0, weight=1)

        self.available_listbox = Listbox(available_files_frame, selectmode="extended")
        self.available_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar_available = ttk.Scrollbar(available_files_frame, orient="vertical", command=self.available_listbox.yview)
        scrollbar_available.grid(row=0, column=1, sticky="ns")
        self.available_listbox.config(yscrollcommand=scrollbar_available.set)

        # Botones para refrescar y seleccionar
        button_frame_left = ttk.Frame(available_files_frame)
        button_frame_left.grid(row=1, column=0, pady=5)
        ttk.Button(button_frame_left, text="Refrescar Lista", command=self.refresh_file_list).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame_left, text="Seleccionar Todos", command=lambda: self.toggle_all_files(self.available_listbox, select=True)).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame_left, text="Deseleccionar Todos", command=lambda: self.toggle_all_files(self.available_listbox, select=False)).grid(row=0, column=2, padx=5)

        # Parámetros de procesamiento
        params_frame = ttk.Labelframe(left_frame, text="Parámetros de Procesamiento", padding=10)
        params_frame.grid(row=2, column=0, sticky="ew", pady=5)
        grid_frame = ttk.Frame(params_frame)
        grid_frame.grid(row=0, column=0)
        self.create_labeled_entry(grid_frame, "Frecuencia de Muestreo (FS):", "FS", 0, 0)
        self.create_labeled_entry(grid_frame, "Número de Canales:", "n_channels", 0, 1)
        self.create_labeled_entry(grid_frame, "Unidad a Procesar:", "unidad", 1, 0)

        ttk.Checkbutton(params_frame, text="Habilitar escritura en MATLAB", variable=self.config["escritura"], bootstyle="round-toggle").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(params_frame, text="Procesar archivos incompletos", variable=self.config["procesar_incompleto"], bootstyle="round-toggle").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(params_frame, text="Generar Gráficos MATLAB", variable=self.config["graficos_matlab"], bootstyle="round-toggle").grid(row=3, column=0, sticky="w", pady=2)

        # Columna derecha
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        # Archivos seleccionados
        selected_files_frame = ttk.Labelframe(right_frame, text="Archivos Seleccionados", padding=10)
        selected_files_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        selected_files_frame.grid_columnconfigure(0, weight=1)
        selected_files_frame.grid_rowconfigure(0, weight=1)

        self.selected_listbox = Listbox(selected_files_frame, selectmode="extended")
        self.selected_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar_selected = ttk.Scrollbar(selected_files_frame, orient="vertical", command=self.selected_listbox.yview)
        scrollbar_selected.grid(row=0, column=1, sticky="ns")
        self.selected_listbox.config(yscrollcommand=scrollbar_selected.set)

        # Botones para agregar/quitar archivos
        button_frame_right = ttk.Frame(selected_files_frame)
        button_frame_right.grid(row=1, column=0, pady=5)
        ttk.Button(button_frame_right, text="Agregar >", command=self.add_selected_files).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame_right, text="< Quitar", command=self.remove_selected_files).grid(row=0, column=1, padx=5)

        # Procesos a ejecutar
        process_frame = ttk.Labelframe(right_frame, text="Procesos a Ejecutar", padding=10)
        process_frame.grid(row=1, column=0, sticky="ew", pady=5)
        ttk.Checkbutton(process_frame, text="Descomprimir Archivos", variable=self.config["descomprimir"], bootstyle="round-toggle").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(process_frame, text="Aplicar Rainflow", variable=self.config["rainflow"], bootstyle="round-toggle").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(process_frame, text="Realizar Conteo de Arranques/Paradas", variable=self.config["realizar_conteo"], bootstyle="round-toggle").grid(row=2, column=0, sticky="w", pady=2)

        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate", bootstyle="info-striped")
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

        # Área de registro (log)
        log_frame = ttk.Labelframe(main_frame, text="Registro de Procesamiento", padding=10)
        log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ttk.Text(log_frame, wrap="word", height=10)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar_log = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar_log.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=scrollbar_log.set)

        # Botones de acción
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Button(btn_frame, text="Iniciar Procesamiento", command=self.start_processing, bootstyle="success-outline").grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Detener Procesamiento", command=self.stop_processing, bootstyle="danger-outline").grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Configuración Avanzada", command=self.open_advanced_config, bootstyle="info-outline").grid(row=0, column=2, padx=5)

# Inicialización de la aplicación
root = ttk.Window(themename="superhero")
app = App(root)
root.mainloop()