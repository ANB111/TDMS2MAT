import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from threading import Thread
from main import main  # Importa tu función principal

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Procesador de Archivos TDMS")
        self.root.geometry("850x650")
        self.root.resizable(False, False)
        
        # Variables de configuración
        self.config = {
            "input_folder": ttk.StringVar(),
            "output_folder": ttk.StringVar(),
            "excel_output_folder": ttk.StringVar(),
            "ruta_matlab_script": ttk.StringVar(),
            "matlab_path": ttk.StringVar(),
            "FS": ttk.IntVar(value=10),
            "escritura": ttk.BooleanVar(value=True),
            "n_channels": ttk.IntVar(value=16),
            "unidad": ttk.StringVar(value="05"),
            "procesar_incompleto": ttk.BooleanVar(value=False),
            "realizar_conteo": ttk.BooleanVar(value=False),
        }

        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # Título
        ttk.Label(main_frame, text="Configuración de Procesamiento", font=("Helvetica", 16, "bold")).pack(pady=10)
        
        # Sección de carpetas y archivos
        paths_frame = ttk.Labelframe(main_frame, text="Rutas de Archivos y Carpetas", padding=10)
        paths_frame.pack(fill=X, pady=10)
        self.create_folder_input(paths_frame, "Carpeta de Entrada:", "input_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida:", "output_folder")
        self.create_folder_input(paths_frame, "Carpeta de Salida Excel:", "excel_output_folder")
        self.create_file_input(paths_frame, "Ruta del Script de MATLAB:", "ruta_matlab_script")
        self.create_file_input(paths_frame, "Ruta del Ejecutable de MATLAB:", "matlab_path")
        
        # Parámetros
        params_frame = ttk.Labelframe(main_frame, text="Parámetros de Procesamiento", padding=10)
        params_frame.pack(fill=X, pady=10)
        grid_frame = ttk.Frame(params_frame)
        grid_frame.pack()
        
        self.create_labeled_entry(grid_frame, "Frecuencia de Muestreo (FS):", "FS", 0, 0)
        self.create_labeled_entry(grid_frame, "Número de Canales:", "n_channels", 0, 1)
        self.create_labeled_entry(grid_frame, "Unidad a Procesar:", "unidad", 1, 0)
        
        ttk.Checkbutton(params_frame, text="Habilitar escritura en MATLAB", variable=self.config["escritura"], bootstyle="round-toggle").pack(anchor=W, pady=5)
        ttk.Checkbutton(params_frame, text="Procesar archivos incompletos", variable=self.config["procesar_incompleto"], bootstyle="round-toggle").pack(anchor=W, pady=5)
        ttk.Checkbutton(params_frame, text="Realizar conteo de ciclos", variable=self.config["realizar_conteo"], bootstyle="round-toggle").pack(anchor=W, pady=5)
        
        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate", bootstyle="info-striped")
        self.progress.pack(fill=X, pady=10)
        
        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Iniciar Procesamiento", command=self.start_processing, bootstyle="success-outline").pack(side=LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancelar", command=self.root.quit, bootstyle="danger-outline").pack(side=LEFT, padx=10)
    
    def create_folder_input(self, parent, label, key):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=5)
        ttk.Label(row, text=label, width=30).pack(side=LEFT)
        ttk.Entry(row, textvariable=self.config[key], width=50).pack(side=LEFT, padx=5)
        ttk.Button(row, text="...", command=lambda: self.select_folder(key), bootstyle="secondary").pack(side=LEFT)
    
    def create_file_input(self, parent, label, key):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=5)
        ttk.Label(row, text=label, width=30).pack(side=LEFT)
        ttk.Entry(row, textvariable=self.config[key], width=50).pack(side=LEFT, padx=5)
        ttk.Button(row, text="...", command=lambda: self.select_file(key), bootstyle="secondary").pack(side=LEFT)
    
    def create_labeled_entry(self, parent, label, key, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col*2, padx=5, pady=5, sticky=W)
        ttk.Entry(parent, textvariable=self.config[key], width=10).grid(row=row, column=col*2+1, padx=5, pady=5, sticky=W)
    
    def select_folder(self, key):
        folder = filedialog.askdirectory()
        if folder:
            self.config[key].set(folder)
    
    def select_file(self, key):
        file = filedialog.askopenfilename()
        if file:
            self.config[key].set(file)
    
    def start_processing(self):
        required_keys = ["input_folder", "output_folder", "excel_output_folder", "ruta_matlab_script", "matlab_path"]
        for key in required_keys:
            if not self.config[key].get():
                messagebox.showerror("Error", f"Por favor, complete el campo '{key}'.")
                return
        
        self.progress.start()
        Thread(target=self.run_main, daemon=True).start()
    
    def run_main(self):
        try:
            config = {k: v.get() for k, v in self.config.items()}
            main(config)
            messagebox.showinfo("Completado", "El procesamiento ha finalizado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {e}")
        finally:
            self.progress.stop()

# Iniciar la aplicación
if __name__ == "__main__":
    root = ttk.Window(themename="superhero")  # Tema moderno
    app = App(root)
    root.mainloop()
