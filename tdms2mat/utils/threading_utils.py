"""Helpers de threading compartidos entre módulos de tdms2mat."""
from __future__ import annotations

import sys
import threading
from concurrent.futures import ProcessPoolExecutor, Future, as_completed
from typing import Callable, Dict, Iterable, Optional, TypeVar

from tdms2mat.utils.exceptions import ProcessingError

T = TypeVar("T")


def check_stop_event(stop_event: Optional[threading.Event]) -> None:
    """Lanza :class:`ProcessingError` si ``stop_event`` está activo.

    Args:
        stop_event: Evento de cancelación cooperativa compartido entre el hilo
                    principal (GUI) y el hilo de procesamiento.  Puede ser
                    ``None`` cuando no se requiere cancelación.
    """
    if stop_event and stop_event.is_set():
        raise ProcessingError("Proceso cancelado por el usuario.")


def cancelable_pool_map(
    executor: ProcessPoolExecutor,
    futuros: Dict["Future[T]", object],
    stop_event: Optional[threading.Event],
    on_result: Callable[["Future[T]", object], None],
    on_cancel_msg: str = "Proceso cancelado por el usuario.",
) -> bool:
    """Itera sobre ``as_completed(futuros)`` con soporte de cancelación rápida.

    Cuando ``stop_event`` se activa:
    1. Cancela todos los futuros pendientes (evita que se encolen en workers).
    2. Hace ``shutdown(wait=False)`` del executor para no bloquear el hilo
       principal esperando procesos hijos que ya no interesan.

    Args:
        executor: El ``ProcessPoolExecutor`` activo (debe estar abierto).
        futuros: Mapa ``{future: identificador}`` generado antes de llamar aquí.
        stop_event: Evento de cancelación del hilo principal (GUI).
        on_result: Callback ``(future, identificador)`` llamado por cada futuro
                   completado **antes** de cancelar.
        on_cancel_msg: Texto que se devuelve en lugar de levantar excepción.

    Returns:
        ``True`` si completó sin cancelación, ``False`` si fue cancelado.
    """
    cancelled = False
    for fut in as_completed(futuros):
        if stop_event and stop_event.is_set():
            cancelled = True
            # Cancelar futuros que aún no empezaron
            for pending in futuros:
                pending.cancel()
            # Apagar el pool sin esperar procesos en curso
            # cancel_futures=True disponible desde Python 3.9
            if sys.version_info >= (3, 9):
                executor.shutdown(wait=False, cancel_futures=True)
            else:
                executor.shutdown(wait=False)
            break
        on_result(fut, futuros[fut])
    return not cancelled
