import os
import json
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, StringVar, IntVar, BooleanVar, Listbox, END
from threading import Thread, Event
from main import main  # Tu función principal

CONFIG_FILE = "config.json"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Procesador de Archivos TDMS")
        self.root.geometry("1000x950")
        self.root.resizable(True, True)

        # Flag para “desde último”
        self.use_last = BooleanVar(value=False)

        # Variables de configuración
        self.config = {
            "input_folder": StringVar(),
            "output_folder": StringVar(),
            "excel_output_folder": StringVar(),
            "last_processed": StringVar(value=""),
            "ruta_matlab_script": StringVar(),
            "matlab_path": StringVar(),
            "FS": IntVar(value=10),
            "descomprimir": BooleanVar(value=True),
            "n_channels": IntVar(value=16),
            "unidad": StringVar(value="05"),
            "procesar_incompleto": BooleanVar(value=False),
            "rainflow": BooleanVar(value=False),
            "realizar_conteo": BooleanVar(value=False),
            "graficos_matlab": BooleanVar(value=False)
        }

        self.stop_event = Event()
        self.selected_files = []

        self.load_config()
        self.create_widgets()

    def create_labeled_entry(self, parent, text, key, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, padx=5, pady=2, sticky="w")
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=5, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.config[key], width=20)
        entry.grid(row=0, column=1)
        if isinstance(self.config[key], IntVar):
            vc = (self.root.register(lambda v: v=="" or v.isdigit()), '%P')
            entry.config(validate="key", validatecommand=vc)

    def create_folder_input(self, parent, text, key, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, pady=2, sticky="ew")
        ttk.Label(frame, text=text).grid(row=0, column=0, padx=5, sticky="w")
        entry = ttk.Entry(frame, textvariable=self.config[key], width=40)
        entry.grid(row=0, column=1, sticky="ew")
        def sel():
            d = filedialog.askdirectory()
            if d and os.path.isdir(d):
                self.config[key].set(d)
                if key=="input_folder":
                    self.refresh_files()
        ttk.Button(frame, text="...", command=sel, bootstyle="secondary").grid(row=0, column=2, padx=5)
        frame.columnconfigure(1, weight=1)

    def refresh_files(self):
        folder = self.config["input_folder"].get()
        self.available_listbox.delete(0, END)
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if os.path.isfile(os.path.join(folder, f)):
                    self.available_listbox.insert(END, f)

    def toggle_last(self):
        """Al activar, auto-llena la lista de seleccionados desde last_processed."""
        if self.use_last.get():
            last = self.config["last_processed"].get()
            if not last:
                messagebox.showwarning("¡Atención!", "No hay un último archivo procesado guardado.")
                self.use_last.set(False)
                return

            inp = self.config["input_folder"].get()
            try:
                all_files = [f for f in sorted(os.listdir(inp))
                             if os.path.isfile(os.path.join(inp, f))]
                idx = all_files.index(last)
            except (FileNotFoundError, ValueError):
                messagebox.showwarning("¡Atención!",
                    f"El archivo '{last}' no existe en la carpeta de entrada.")
                self.use_last.set(False)
                return

            # Recorta a partir de next(after) last
            to_proc = all_files[idx+1:]
            self.selected_files = to_proc

            # Refresca la listbox de seleccionados con esa lista
            self.selected_listbox.delete(0, END)
            for f in to_proc:
                self.selected_listbox.insert(END, f)

        else:
            # vuelve al modo manual: limpia lista
            self.selected_files.clear()
            self.selected_listbox.delete(0, END)

    def add_selected(self):
        """Agrega manualmente a la cola."""
        for i in self.available_listbox.curselection():
            f = self.available_listbox.get(i)
            if f not in self.selected_files:
                self.selected_listbox.insert(END, f)
                self.selected_files.append(f)

    def remove_selected(self):
        """Quita manualmente de la cola."""
        for i in reversed(self.selected_listbox.curselection()):
            f = self.selected_listbox.get(i)
            self.selected_listbox.delete(i)
            self.selected_files.remove(f)

    def get_files_to_process(self):
        inp = self.config["input_folder"].get()
        return [os.path.join(inp, f) for f in self.selected_files]

    def start(self):
        # Validación mínima de carpetas
        for k in ("input_folder","output_folder","excel_output_folder"):
            if not self.config[k].get():
                messagebox.showerror("Error", f"Falta configurar: {k}")
                return

        files = self.get_files_to_process()
        if not files:
            messagebox.showerror("Error", "No hay archivos para procesar.")
            return

        self.save_config()
        self.stop_event.clear()
        self.progress.start()
        self.log_text.delete("1.0","end")
        Thread(target=self._run, daemon=True).start()

    def _run(self):
        cfg = {k:v.get() for k,v in self.config.items()}
        cfg["selected_files"] = self.selected_files
        try:
            main(cfg, log_callback=self.log_message)
            # al terminar, guarda el último
            if self.selected_files:
                last = self.selected_files[-1]
                self.config["last_processed"].set(last)
                with open(CONFIG_FILE,"r+") as f:
                    data = json.load(f)
                    data["last_processed"] = last
                    f.seek(0); f.truncate()
                    json.dump(data,f,indent=4)
                self.log_message(f"Guardado último archivo: {last}")
        except Exception as e:
            self.log_message(f"Error: {e}")
        finally:
            self.progress.stop()

    def log_message(self,msg):
        self.log_text.insert(END, msg+"\n")
        self.log_text.see(END)
        self.root.update_idletasks()

    def save_config(self):
        data = {k:v.get() for k,v in self.config.items()}
        data["selected_files"] = self.selected_files
        with open(CONFIG_FILE,"w") as f:
            json.dump(data,f,indent=4)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            for k in self.config:
                if k in data:
                    self.config[k].set(data[k])

    def create_widgets(self):
        self.root.columnconfigure(0, weight=1)
        mf = ttk.Frame(self.root, padding=10)
        mf.grid(sticky="nsew")
        mf.columnconfigure((0,1), weight=1)

        # Rutas (span=2)
        pf = ttk.Labelframe(mf, text="Rutas y Carpetas", padding=10)
        pf.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        pf.columnconfigure(1, weight=1)
        self.create_folder_input(pf,"Carpeta Entrada:","input_folder",0)
        self.create_folder_input(pf,"Carpeta Salida:","output_folder",1)
        self.create_folder_input(pf,"Excel Salida:","excel_output_folder",2)

        # “Desde último”
        cb = ttk.Checkbutton(
            mf,
            text="Procesar desde último archivo procesado",
            variable=self.use_last,
            command=self.toggle_last,
            bootstyle="info"
        )
        cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5,2))

        # Listas lado a lado
        self.files_frame_left = ttk.Labelframe(mf, text="Disponibles", padding=10)
        self.files_frame_left.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.files_frame_left.rowconfigure(0, weight=1)
        self.files_frame_left.columnconfigure(0, weight=1)
        self.available_listbox = Listbox(self.files_frame_left, selectmode="extended")
        self.available_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(self.files_frame_left, command=self.available_listbox.yview).grid(row=0, column=1, sticky="ns")
        btnf = ttk.Frame(self.files_frame_left)
        btnf.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btnf, text="Refrescar", command=self.refresh_files).grid(row=0, column=0, padx=5)
        ttk.Button(btnf, text="Agregar >", command=self.add_selected).grid(row=0, column=1, padx=5)

        self.files_frame_right = ttk.Labelframe(mf, text="Seleccionados", padding=10)
        self.files_frame_right.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
        self.files_frame_right.rowconfigure(0, weight=1)
        self.files_frame_right.columnconfigure(0, weight=1)
        self.selected_listbox = Listbox(self.files_frame_right, selectmode="extended")
        self.selected_listbox.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(self.files_frame_right, command=self.selected_listbox.yview).grid(row=0, column=1, sticky="ns")
        btnr = ttk.Frame(self.files_frame_right)
        btnr.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(btnr, text="< Quitar", command=self.remove_selected).grid(row=0, column=0, padx=5)

        # Parámetros y procesos
        pf2 = ttk.Labelframe(mf, text="Parámetros y Procesos", padding=10)
        pf2.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        pf2.columnconfigure((1,2,3), weight=1)
        self.create_labeled_entry(pf2,"FS (Hz):","FS",0,0)
        self.create_labeled_entry(pf2,"Canales:","n_channels",0,1)
        self.create_labeled_entry(pf2,"Unidad:","unidad",0,2)
        ttk.Checkbutton(pf2,text="Descomprimir y Procesar",variable=self.config["descomprimir"],bootstyle="round-toggle").grid(row=1,column=0,sticky="w",pady=2)
        ttk.Checkbutton(pf2,text="Incompletos",variable=self.config["procesar_incompleto"],bootstyle="round-toggle").grid(row=1,column=1,sticky="w",pady=2)
        ttk.Checkbutton(pf2,text="Gráficos MATLAB",variable=self.config["graficos_matlab"],bootstyle="round-toggle").grid(row=1,column=2,sticky="w",pady=2)
        ttk.Checkbutton(pf2,text="Rainflow",variable=self.config["rainflow"],bootstyle="round-toggle").grid(row=2,column=0,sticky="w",pady=2)
        ttk.Checkbutton(pf2,text="Conteo Arranques/Paradas",variable=self.config["realizar_conteo"],bootstyle="round-toggle").grid(row=2,column=1,sticky="w",pady=2)

        # Log
        lf = ttk.Labelframe(mf, text="Registro", padding=10)
        lf.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=5)
        lf.rowconfigure(0, weight=1); lf.columnconfigure(0, weight=1)
        self.log_text = ttk.Text(lf, wrap="word", height=10)
        self.log_text.grid(sticky="nsew")
        ttk.Scrollbar(lf, command=self.log_text.yview).grid(row=0, column=1, sticky="ns")

        # Progreso y botones
        self.progress = ttk.Progressbar(mf, mode="indeterminate", bootstyle="info-striped")
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        bf = ttk.Frame(mf)
        bf.grid(row=6, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Button(bf, text="Iniciar", command=self.start, bootstyle="success-outline").grid(row=0, column=0, padx=5)
        ttk.Button(bf, text="Detener", command=self.stop_event.set, bootstyle="danger-outline").grid(row=0, column=1, padx=5)
        ttk.Button(bf, text="Avanzada", command=self.open_advanced_config, bootstyle="info-outline").grid(row=0, column=2, padx=5)

    def open_advanced_config(self):
        messagebox.showinfo("Avanzada", "Pendiente...")

# Lanzamiento
root = ttk.Window(themename="superhero")
App(root)
root.mainloop()
