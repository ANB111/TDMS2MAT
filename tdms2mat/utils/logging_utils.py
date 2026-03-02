"""Helpers de logging para el paquete tdms2mat.

Centraliza la configuración del logging para que no sea llamado múltiples veces
por distintos módulos.  Llama a ``setup_logging()`` una sola vez desde
``__main__.py`` antes de arrancar la GUI o el CLI.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

_configured = False


def setup_logging(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
) -> None:
    """Configura el sistema de logging global.

    Debe llamarse **una sola vez** al inicio de la aplicación.
    Las llamadas posteriores son un no-op.

    Args:
        log_file: Ruta al archivo de log.  Si es ``None``, solo se emite por
                  consola (stdout).
        level: Nivel mínimo de logging (default ``logging.INFO``).
    """
    global _configured
    if _configured:
        return
    _configured = True

    fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger con el nombre dado, prefijado con ``tdms2mat``."""
    return logging.getLogger(f"tdms2mat.{name}")
