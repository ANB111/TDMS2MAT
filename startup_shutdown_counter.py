import os
import pandas as pd
from scipy.io import loadmat

def extract_numeric_key(filename):
    """
    Extrae una clave numérica de un nombre de archivo con formato '25.2.11-u05.mat'.
    Devuelve una tupla de enteros para ordenar correctamente.
    """
    # Tomar la parte antes del primer '-'
    base = filename.split('-')[0]
    # Separar por '.' y convertir a enteros
    try:
        parts = tuple(int(p) for p in base.split('.'))
    except Exception:
        parts = (0,)
    return parts

def count_startups_shutdowns(mat_data):
    """
    Cuenta los ciclos de arranque y parada en los datos del canal 13.
    
    Parámetros:
    - mat_data (dict): Datos cargados desde el archivo .mat.
    
    Retorna:
    - tuple: (número de arranques, número de paradas, estado inicial, estado final)
    """
    # Extraer los datos del canal 13 (velocidad de la turbina)
    try:
        speed_data = mat_data['data'][:, 13] 
    except IndexError:
        print("El archivo .mat no tiene datos en el canal 13.")
        return 0, 0, "Desconocido", "Desconocido"

    # Contadores para arranques y paradas
    startups = 0
    shutdowns = 0

    # Detectar transiciones
    for i in range(1, len(speed_data)):
        if speed_data[i - 1] == 0 and speed_data[i] > 0:
            startups += 1
        elif speed_data[i - 1] > 0 and speed_data[i] == 0:
            shutdowns += 1

    # Determinar el estado inicial y final
    estado_inicial = "Encendida" if speed_data[0] > 0 else "Apagada"
    estado_final = "Encendida" if speed_data[-1] > 0 else "Apagada"

    return startups, shutdowns, estado_inicial, estado_final

def process_mat_folder(mat_folder, excel_path, log_callback=None):
    """
    Procesa todos los archivos .mat en la carpeta especificada y actualiza el archivo Excel.
    Solo procesa archivos que no han sido contabilizados previamente.
    
    Parámetros:
    - mat_folder (str): Ruta de la carpeta que contiene los archivos .mat.
    - excel_path (str): Ruta del archivo Excel donde se guardarán los resultados.
    - log_callback (function): Función de callback para registrar mensajes en el log.
    """
    # Función de registro
    def log(message):
        if log_callback:
            log_callback(message)
        else:
            print(message)

    # Verificar si el archivo Excel ya existe
    if os.path.exists(excel_path):
        df_excel = pd.read_excel(excel_path)
        processed_files = set(df_excel["Archivo"])  # Conjunto de archivos ya procesados
    else:
        # Crear un DataFrame vacío si el archivo no existe
        df_excel = pd.DataFrame(columns=["Fecha", "Arranques", "Paradas", "Total", "Movimientos", "Estado Inicial", "Estado Final", "Archivo"])
        processed_files = set()

    # Obtener y ordenar archivos .mat de forma numérica
    mat_files = [f for f in os.listdir(mat_folder) if f.endswith('.mat')]
    mat_files.sort(key=extract_numeric_key)

    # Procesar cada archivo .mat en la carpeta
    for mat_file in mat_files:
        # Verificar si el archivo ya fue procesado
        if mat_file in processed_files:
            log(f"El archivo {mat_file} ya fue procesado. Saltando...")
            continue

        mat_path = os.path.join(mat_folder, mat_file)

        try:
            # Cargar los datos del archivo .mat
            mat_data = loadmat(mat_path)

            # Usar solo el nombre base sin el sufijo de la unidad ni extensión para la columna "Fecha"
            # Ejemplo: de '25.2.11-u05.mat' -> '25.2.11'
            date_str = mat_file.split('-')[0]

            # Contar arranques, paradas y obtener estados inicial y final
            startups, shutdowns, estado_inicial, estado_final = count_startups_shutdowns(mat_data)
            total = startups + shutdowns

            # Calcular movimientos del día (canal 8, índice 8)
            try:
                movimientos = mat_data['data'][-1, 7] - mat_data['data'][0, 7]

            except Exception:
                movimientos = None

            # Mostrar una previsualización en el log
            log(f"Procesado: {mat_file}")
            log(f"  Fecha: {date_str}")
            log(f"  Arranques: {startups}, Paradas: {shutdowns}, Total: {total}")
            log(f"  Movimientos: {movimientos}")
            log(f"  Estado Inicial: {estado_inicial}, Estado Final: {estado_final}")

            # Agregar nueva fila al DataFrame
            new_row = {
                "Fecha": date_str,
                "Arranques": startups,
                "Paradas": shutdowns,
                "Total": total,
                "Movimientos": movimientos,
                "Estado Inicial": estado_inicial,
                "Estado Final": estado_final,
                "Archivo": mat_file  # Registrar el nombre del archivo procesado
            }
            df_excel = pd.concat([df_excel, pd.DataFrame([new_row])], ignore_index=True)

            # Agregar el archivo al conjunto de archivos procesados
            processed_files.add(mat_file)

        except Exception as e:
            log(f"Error procesando {mat_file}: {e}")

    # Guardar el archivo Excel actualizado
    df_excel.to_excel(excel_path, index=False)
    log(f"Resultados guardados en {excel_path}")