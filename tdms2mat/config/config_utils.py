"""Carga, guardado y validación de la configuración de la aplicación.

Esta es la **única** implementación de I/O de configuración; tanto el pipeline
como la GUI deben usar estas funciones para garantizar escritura atómica y
validación con Pydantic.

Escritura atómica (tmp → rename → backup):
    1. Se escribe en ``config.json.tmp``.
    2. El archivo anterior (si existe) se renombra a ``config.json.bak``.
    3. El tmp se renombra a ``config.json``.

De esta forma un corte de corriente no deja la configuración corrupta.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Union

from pydantic import ValidationError

from tdms2mat.config.schema import AppConfig

logger = logging.getLogger("tdms2mat.config")


def load_config(config_path: Union[str, Path]) -> AppConfig:
    """Carga y valida la configuración desde un archivo JSON.

    Si el archivo no existe o está corrupto intenta el backup (``.bak``).
    Si el backup también falla devuelve un ``AppConfig`` con valores por defecto.

    Args:
        config_path: Ruta al archivo ``config.json``.

    Returns:
        :class:`AppConfig` validado o con valores por defecto.
    """
    config_path = Path(config_path)
    backup_path = config_path.with_suffix(".json.bak")

    for candidate in (config_path, backup_path):
        if not candidate.exists():
            continue
        try:
            raw: Dict[str, Any] = json.loads(
                candidate.read_text(encoding="utf-8")
            )
            cfg = AppConfig.model_validate(raw)
            if candidate == backup_path:
                logger.warning(
                    "Se cargó la configuración desde el backup '%s'", backup_path
                )
            return cfg
        except json.JSONDecodeError as exc:
            logger.error("JSON inválido en '%s': %s", candidate, exc)
        except ValidationError as exc:
            logger.error("Configuración inválida en '%s': %s", candidate, exc)
        except Exception as exc:  # pragma: no cover
            logger.error("Error inesperado leyendo '%s': %s", candidate, exc)

    logger.warning(
        "No se encontró configuración válida en '%s'; usando valores por defecto.",
        config_path,
    )
    return AppConfig()


def save_config(config: AppConfig, config_path: Union[str, Path]) -> None:
    """Guarda la configuración en disco de forma atómica.

    Args:
        config: Instancia de :class:`AppConfig` a guardar.
        config_path: Ruta destino (normalmente ``config.json``).
    """
    config_path = Path(config_path)
    tmp_path = config_path.with_suffix(".json.tmp")
    backup_path = config_path.with_suffix(".json.bak")

    try:
        # 1) Escribir en archivo temporal
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(config.model_dump(), indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

        # 2) Rotar: config → backup
        if config_path.exists():
            if backup_path.exists():
                backup_path.unlink()
            os.rename(config_path, backup_path)

        # 3) tmp → config (rename atómico en mismo filesystem)
        os.rename(tmp_path, config_path)

    except Exception as exc:  # pragma: no cover
        logger.error("Error guardando configuración en '%s': %s", config_path, exc)
        # Limpiar tmp si quedó a medias
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def validate_config(config: Union[AppConfig, Dict[str, Any]]) -> bool:
    """Validación rápida de compatibilidad con el pipeline principal.

    Comprueba que las rutas obligatorias estén definidas cuando el pipeline de
    descompresión está habilitado.

    Args:
        config: Un :class:`AppConfig` ya validado o un dict raw.

    Returns:
        ``True`` si la configuración es suficiente para correr el pipeline.
    """
    if isinstance(config, dict):
        try:
            cfg = AppConfig.model_validate(config)
        except ValidationError as exc:
            logger.error("Configuración inválida: %s", exc)
            return False
    else:
        cfg = config

    required = ["input_folder", "output_folder", "excel_output_folder"]
    for field in required:
        if not getattr(cfg, field, ""):
            logger.error("Falta el campo requerido '%s' en la configuración.", field)
            return False
    return True
