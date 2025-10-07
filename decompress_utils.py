import os
import subprocess
import shutil
import threading
from typing import Optional

# Copied from main.py to avoid circular import
class ProcessingError(Exception):
    """Custom exception for processing errors."""
    pass

def check_stop_event(stop_event: Optional[threading.Event]):
    """Checks if the stop event is set and raises an exception if it is."""
    if stop_event and stop_event.is_set():
        raise ProcessingError("Proceso cancelado por el usuario.")

def decompress_zip_files(input_folder, output_folder, selected_files, stop_event: Optional[threading.Event] = None):
    """
    Decompresses selected ZIP files directly into the output folder without creating subfolders.
    If there are name conflicts, files are automatically renamed.
    Checks for a cancellation event before processing each file.
    """
    if shutil.which('7z') is None:
        raise EnvironmentError("El programa '7z' no está instalado o no está en el PATH.")

    os.makedirs(output_folder, exist_ok=True)

    for zip_file in selected_files:
        # Check for cancellation before processing the next file
        check_stop_event(stop_event)

        zip_path = os.path.join(input_folder, zip_file)
        print(f"Procesando archivo: {zip_file}")

        try:
            subprocess.run(['7z', 'x', zip_path, f'-o{output_folder}', '-y'], check=True)

            for root, _, files in os.walk(output_folder):
                for file in files:
                    src_path = os.path.join(root, file)
                    dest_path = os.path.join(output_folder, file)

                    if src_path != dest_path:
                        if os.path.exists(dest_path):
                            base, ext = os.path.splitext(file)
                            counter = 1
                            while os.path.exists(dest_path):
                                dest_path = os.path.join(output_folder, f"{base}_{counter}{ext}")
                                counter += 1
                        shutil.move(src_path, dest_path)

            for root, dirs, _ in os.walk(output_folder):
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    if not os.listdir(dir_path):
                        shutil.rmtree(dir_path)

        except subprocess.CalledProcessError as e:
            print(f"Error al descomprimir {zip_file}: {e}")
        except Exception as e:
            print(f"Error procesando {zip_file}: {e}")