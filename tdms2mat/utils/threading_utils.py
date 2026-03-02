"""Helpers de threading compartidos entre módulos de tdms2mat."""
from __future__ import annotations

import threading
from typing import Optional

from tdms2mat.utils.exceptions import ProcessingError


def check_stop_event(stop_event: Optional[threading.Event]) -> None:
    """Lanza :class:`ProcessingError` si ``stop_event`` está activo.

    Args:
        stop_event: Evento de cancelación cooperativa compartido entre el hilo
                    principal (GUI) y el hilo de procesamiento.  Puede ser
                    ``None`` cuando no se requiere cancelación.
    """
    if stop_event and stop_event.is_set():
        raise ProcessingError("Proceso cancelado por el usuario.")
