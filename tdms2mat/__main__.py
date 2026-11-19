"""
Punto de entrada cuando se ejecuta como módulo: python -m tdms2mat
Lanza la interfaz gráfica de usuario.
"""
from __future__ import annotations


def main() -> None:
    """Lanza la GUI de TDMS2MAT."""
    import multiprocessing
    # Necesario en Windows para que ProcessPoolExecutor funcione correctamente
    # tanto en desarrollo como en el ejecutable compilado con PyInstaller.
    multiprocessing.freeze_support()

    import ttkbootstrap as ttk  # type: ignore[import]
    from tdms2mat.gui.app import App

    root = ttk.Window(themename="superhero")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
