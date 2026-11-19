"""Excepción única de procesamiento — punto central para evitar duplicación."""
from __future__ import annotations


class ProcessingError(Exception):
    """Excepción personalizada para errores del pipeline de procesamiento.

    Usada tanto para errores reales como para cancelaciones voluntarias del
    usuario (mediante el ``stop_event``).
    """
