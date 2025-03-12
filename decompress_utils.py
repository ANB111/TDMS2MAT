import os
import subprocess
import shutil
from tqdm import tqdm

def decompress_files(input_folder, output_folder, selected_files):
    """
    Descomprime los archivos ZIP y RAR seleccionados en la carpeta de salida sin crear subcarpetas.
    Renombra automáticamente archivos si hay conflictos de nombres.
    """
    if shutil.which('7z') is None:
        raise EnvironmentError("❌ El programa '7z' no está instalado o no está en el PATH.")

    os.makedirs(output_folder, exist_ok=True)

    # Filtrar solo archivos ZIP y RAR
    archive_files = [f for f in selected_files if f.lower().endswith(('.zip', '.rar'))]

    if not archive_files:
        print("⚠️ No se encontraron archivos ZIP o RAR en la selección.")
        return

    for archive_file in tqdm(archive_files, desc="Descomprimiendo archivos", unit="archivo"):
        archive_path = os.path.join(input_folder, archive_file)
        print(f"🔄 Procesando archivo: {archive_file}")

        try:
            # Ejecutar el comando 7z para extraer el archivo
            subprocess.run(['7z', 'x', archive_path, f'-o{output_folder}', '-y'], check=True)

            # Mover archivos extraídos a la carpeta de salida evitando sobrescribir archivos existentes
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

            # Eliminar subcarpetas vacías después de la extracción
            for root, dirs, _ in os.walk(output_folder, topdown=False):
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    if not os.listdir(dir_path):
                        shutil.rmtree(dir_path)

        except subprocess.CalledProcessError as e:
            print(f"❌ Error al descomprimir {archive_file}: {e}")
        except Exception as e:
            print(f"❌ Error procesando {archive_file}: {e}")

