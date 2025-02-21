import subprocess

# Parámetros que quieres pasar al script de MATLAB
name = '2025.01.16-u05'
FS = 10  # Frecuencia de muestreo
escritura = True  # Booleano para habilitar/deshabilitar la escritura (como booleano)
n_channels = 16  # Número de canales
ruta = r'C:\Users\Becario 4\Documents\TDMS2MAT\salida'  # Ruta del archivo (usando r para evitar problemas con las barras invertidas)

# Ruta al ejecutable de MATLAB (ajusta según tu sistema)
matlab_path = r"C:\Program Files\Polyspace\R2021a\bin\matlab.exe"

# Comando para ejecutar el script de MATLAB
command = [
    matlab_path,
    "-batch",
    f"cd('C:\\Users\\Becario 4\\Downloads'); matlab_script('{name}', {str(escritura).lower()}, {FS}, {n_channels}, '{ruta}')"
]

# Ejecutar el comando
try:
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
except subprocess.CalledProcessError as e:
    print("Error al ejecutar MATLAB:")
    print(e.stderr)
