import os
import subprocess
import shutil
from tqdm import tqdm

def decompress_zip_files(input_folder, output_folder, selected_files):
    """
    Descomprime los archivos ZIP seleccionados directamente en la carpeta de salida sin crear subcarpetas.
    Si hay conflictos de nombres, los archivos se renombran automáticamente.
    """
    if shutil.which('7z') is None:
        raise EnvironmentError("El programa '7z' no está instalado o no está en el PATH.")

    os.makedirs(output_folder, exist_ok=True)

    for zip_file in tqdm(selected_files, desc="Descomprimiendo archivos", unit="archivo"):
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