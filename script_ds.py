import numpy as np
import scipy.io
import pandas as pd
from scipy.interpolate import splev, splrep
import os
from rainflow import extract_cycles  # Importar la función extract_cycles del módulo

# Parámetros de configuración
escritura = True
n_channels = 16  # Ajustar según la etapa de adquisición
name = '2025.01.16-u05'

# Cargar archivo .mat
path = r'C:\Users\Becario 4\Documents\TDMS2MAT\salida'
filename = f"{name}.mat"
file = os.path.join(path, filename)

try:
    data = scipy.io.loadmat(file)['data']
except FileNotFoundError:
    raise FileNotFoundError(f"El archivo {filename} no se encontró en la ruta especificada.")
except Exception as e:
    raise RuntimeError(f"Error al cargar el archivo: {e}")

# Parámetros de la adquisición
Fs = 10  # Hz

# Valores geométricos
Da = 2 * 762 / 1000  # [m] Diam Cilindro
da = 2 * 350 / 1000  # [m] Diam Vastago
Dc = Da  # [m] Diam Cilindro
dc = 2 * 101.6 / 1000  # [m] Diam Cañería
A_a = np.pi * (Da**2 - da**2) / 4  # Área abrir
A_c = np.pi * (Dc**2 - dc**2) / 4  # Área cerrar

# Cálculo de fuerza hidráulica
Fza_Hid = (data[:, 6] * A_c - data[:, 5] * A_a) * 100 / 5


# Vector de tiempo
t = np.round(np.linspace(0, (len(Fza_Hid) - 1) / Fs, len(Fza_Hid)), decimals=1)

# Conteo de ciclos Rainflow
cycles = list(extract_cycles(Fza_Hid))  # Usar la función extract_cycles del módulo
cFs = np.array([[c[2], c[1], c[0]] for c in cycles])  # Ciclos, Media, Rango

# Obtener los índices de los ciclos
idx_start = [int(c[3]) for c in cycles]  # Índices iniciales
idx_end = [int(c[4]) for c in cycles]    # Índices finales

# Validar índices
if max(idx_start) >= len(t) or max(idx_end) >= len(t):
    raise IndexError("Los índices de los ciclos están fuera de los límites del vector de tiempo.")

# Calcular ti y ts usando los índices
ti = t[idx_start]  # Tiempo inicial
ts = t[idx_end]    # Tiempo final

# Redondear ti y ts a 1 decimal
ti = np.round(ti, decimals=1)
ts = np.round(ts, decimals=1)

# Definición de curva K
K = np.array([65.12307378, 57.01521195, 42.83250569, 27.55061352, 14.93805445, 
              7.055368592, 3.505949635, 2.470266626, 2.331041354])
F = np.array([1782, 1560, 1337, 1114, 891, 668, 446, 223, 100])

# Ordenar F y K en caso de que F no sea estrictamente creciente
sorted_indices = np.argsort(F)
F_sorted = F[sorted_indices]
K_sorted = K[sorted_indices]

# Verificar si hay valores duplicados en F_sorted
if len(np.unique(F_sorted)) != len(F_sorted):
    raise ValueError("Error: F contiene valores duplicados. Elimina duplicados antes de interpolar.")

# Interpolación Spline
pp = splrep(F_sorted, K_sorted)

# Filtrado por umbral de avance de fisura
dK_thresholds = [14, 10.5, 7]
filtered_dK = {thr: [] for thr in dK_thresholds}
for i in range(len(cFs)):
    f_i = cFs[i, 2] - cFs[i, 1] / 2  # Media - Rango/2
    f_s = cFs[i, 2] + cFs[i, 1] / 2  # Media + Rango/2
    k_i = splev(f_i, pp) if f_i >= 0 else 0
    k_s = splev(f_s, pp) if f_s >= 0 else 0
    dK = k_s - k_i  # delta K
    for thr in dK_thresholds:
        if dK >= thr:
            filtered_dK[thr].append(np.append(cFs[i], [ti[i], ts[i], dK]))

# Escritura de resultados en Excel
if escritura:
    output_file = os.path.join(path, f"{name}.xlsx")
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # Guardar conteo Rainflow
        df = pd.DataFrame(cFs, columns=['Ciclos', 'Rango [kN]', 'Media [kN]'])
        df['ti [s]'] = ti
        df['ts [s]'] = ts
        df.to_excel(writer, sheet_name='Conteo Rainflow', index=False)

        # Guardar filtrado por umbrales de dK
        for thr in dK_thresholds:
            if filtered_dK[thr]:
                df_filtered = pd.DataFrame(filtered_dK[thr], 
                                           columns=['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]', 'delta K'])
                df_filtered.to_excel(writer, sheet_name=f'delta K = {thr}', index=False)
            else:
                print(f"No hay datos para el umbral delta K = {thr}")

# Mensaje final
Mov_rel = data[-1, 7] - data[0, 7]
X = f"{name} - Cantidad de Movimientos: {Mov_rel}"
print(X)
print("FINALIZADO")