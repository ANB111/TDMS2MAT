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
cFs = np.array([[c[2], c[1], c[0]] for c in cycles])  # Ciclos, Media, Rango

# Obtener los índices de los ciclos
idx = [c[3] for c in cycles]  # Índices de los ciclos
ti = t[idx]  # Tiempo inicial

# Calculando correctamente ts usando el índice final de cada ciclo
ts = []
for i in range(len(cycles)):
    cycle_end_idx = cycles[i][4]  # El índice final del ciclo
    ts.append(t[cycle_end_idx])  # Tiempo final según el índice de finalización del ciclo

ts = np.array(ts)  # Convertir a array de NumPy para manejarlo correctamente

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

# Filtrado por umbral de avance de fisura
dK_thresholds = [14, 10.5, 7]
filtered_dK = {thr: [] for thr in dK_thresholds}

for i in range(len(cFs)):
    f_i = cFs[i, 2] - cFs[i, 1] / 2  # Media - Rango/2
    f_s = cFs[i, 2] + cFs[i, 1] / 2  # Media + Rango/2
    k_i = splev(f_i, pp) if f_i >= 0 else 0
    k_s = splev(f_s, pp) if f_s >= 0 else 0
    dK = k_s - k_i  # delta K

    # Filtrar ciclos según los umbrales de dK
    if dK >= dK_thresholds[0]:
        filtered_dK[dK_thresholds[0]].append(np.append(cFs[i], [ti[i], ts[i], dK]))
    if dK >= dK_thresholds[1]:
        filtered_dK[dK_thresholds[1]].append(np.append(cFs[i], [ti[i], ts[i], dK]))
    if dK >= dK_thresholds[2]:
        filtered_dK[dK_thresholds[2]].append(np.append(cFs[i], [ti[i], ts[i], dK]))

# Escritura de resultados en Excel
if escritura:
    output_file = os.path.join(path, f"{name}.xlsx")
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # Guardar conteo Rainflow con el orden de columnas correcto
        df = pd.DataFrame(cFs, columns=['Ciclos', 'Rango [kN]', 'Media [kN]'])
        
        # Intercambiar las columnas de Media y Rango
        df['Rango [kN]'], df['Media [kN]'] = df['Media [kN]'], df['Rango [kN]']
        
        df['ti [s]'] = ti
        df['ts [s]'] = ts
        df = df[['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]']]  # Asegurarse que el orden sea correcto
        df.to_excel(writer, sheet_name='Conteo Rainflow', index=False)

        # Guardar filtrado por umbrales de dK con el orden de columnas correcto
        for thr in dK_thresholds:
            # Verificar si hay datos en el umbral
            if filtered_dK[thr]:  # Solo proceder si hay datos
                # Convertir a DataFrame
                df_filtered = pd.DataFrame(filtered_dK[thr], 
                                           columns=['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]', 'delta K'])
                
                # Intercambiar las columnas de Media y Rango
                df_filtered['Rango [kN]'], df_filtered['Media [kN]'] = df_filtered['Media [kN]'], df_filtered['Rango [kN]']
                
                # Escribir en el Excel
                df_filtered = df_filtered[['Ciclos', 'Rango [kN]', 'Media [kN]', 'ti [s]', 'ts [s]', 'delta K']]  # Asegurarse que el orden sea correcto
                df_filtered.to_excel(writer, sheet_name=f'delta K = {thr}', index=False)
            else:
                print(f"No hay datos para el umbral delta K = {thr}")

# Mensaje final
Mov_rel = data[-1, 7] - data[0, 7]
X = f"{name} - Cantidad de Movimientos: {Mov_rel}"
print(X)
print("FINALIZADO")
