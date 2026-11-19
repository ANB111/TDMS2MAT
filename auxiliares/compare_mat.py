import hashlib
import os

root = r"D:\Carpeta Becario 19\Nueva carpeta (2)\TDMS2MAT\salida"
original = os.path.join(root, "original")
if not os.path.isdir(original):
    original = os.path.join(root, "orginal")

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

mat_files = [f for f in os.listdir(root) if f.endswith(".mat")]

print(f"{'Archivo':<30} {'Identicos':<12} {'Tamaño raíz':>12} {'Tamaño original':>16}")
print("-" * 75)

all_ok = True
for name in sorted(mat_files):
    root_path = os.path.join(root, name)
    orig_path = os.path.join(original, name)
    if not os.path.exists(orig_path):
        print(f"{name:<30} {'SIN PAR':<12}")
        all_ok = False
        continue
    h1 = file_hash(root_path)
    h2 = file_hash(orig_path)
    identical = h1 == h2
    if not identical:
        all_ok = False
    size_root = os.path.getsize(root_path)
    size_orig = os.path.getsize(orig_path)
    mark = "SI" if identical else "NO  <-- DIFERENTE"
    print(f"{name:<30} {mark:<20} {size_root:>12,} {size_orig:>16,}")

print()
if all_ok:
    print("RESULTADO: Todos los archivos son IDENTICOS.")
else:
    print("RESULTADO: Hay archivos DIFERENTES o sin par.")
