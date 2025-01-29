import numpy as np
import scipy.io
import pandas as pd
from scipy.interpolate import splev, splrep
import os
import rainflow_lib as rainflow

# Parámetros de configuración
escritura = True
n_channels = 16  # Ajustar según la etapa de adquisición
name = '2025.01.16-u05'

# Cargar archivo .mat
path = r'C:\Users\Becario 4\Documents\TDMS2MAT\salida'
filename = f"{name}.mat"
file = os.path.join(path, filename)
data = scipy.io.loadmat(file)['data']

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
t = np.arange(0, len(Fza_Hid) / Fs, 1 / Fs)

# Conteo de ciclos Rainflow
cycles = list(rainflow.extract_cycles(Fza_Hid))
cFs = np.array([[c[2], c[1], c[0], 0, 0] for c in cycles])  # Ciclos, Media, Rango, ti, ts

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

# Interpolación Spline corregida
pp = splrep(F_sorted, K_sorted)

f_range = np.arange(0, 1800.1, 0.1)
k_p = splev(f_range, pp)

# Filtrado por umbral de avance de fisura
dK_thresholds = [14, 10.5, 7]
filtered_dK = {thr: [] for thr in dK_thresholds}

for cycle in cFs:
    f_i = cycle[2] - cycle[1] / 2  # Media - Rango/2
    f_s = cycle[2] + cycle[1] / 2  # Media + Rango/2
    k_i = splev(f_i, pp) if f_i >= 0 else 0
    k_s = splev(f_s, pp) if f_s >= 0 else 0
    dK = k_s - k_i  # delta K

    for thr in dK_thresholds:
        if dK >= thr:
            filtered_dK[thr].append(np.append(cycle, dK))

# Escritura de resultados en Excel
if escritura:
    output_file = os.path.join(path, f"{name}.xlsx")
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # Guardar conteo Rainflow
        df = pd.DataFrame(cFs, columns=['Ciclos', 'Media [kN]', 'Rango [kN]', 'ti [s]', 'ts [s]'])
        # Reordenar columnas
        df = df[['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]']]
        df.to_excel(writer, sheet_name='Conteo Rainflow', index=False)

        # Guardar filtrado por umbrales de dK
        for thr in dK_thresholds:
            df_filtered = pd.DataFrame(filtered_dK[thr], 
                                       columns=['Ciclos', 'Media [kN]', 'Rango [kN]', 'ti [s]', 'ts [s]', 'delta K'])
            df_filtered = df_filtered[['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]']]
            df_filtered.to_excel(writer, sheet_name=f'delta K = {thr}', index=False)


# Mensaje final
X = f"{name} - Cantidad de Movimientos: {data[-1, 7] - data[0, 7]}"
print(X)
print("FINALIZADO")