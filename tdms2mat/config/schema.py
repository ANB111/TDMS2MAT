"""Modelo de configuración de la aplicación validado con Pydantic v2.

Todos los parámetros que antes residían en el JSON plano ahora tienen tipo
explícito, valor por defecto documentado y validadores automáticos.

Uso típico::

    from tdms2mat.config.schema import AppConfig
    cfg = AppConfig.model_validate(raw_dict)
    cfg.model_dump()          # → dict JSON serializable
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppConfig(BaseModel):
    """Configuración completa de la aplicación TDMS2MAT.

    Los campos obligatorios son ``input_folder``, ``output_folder`` y
    ``excel_output_folder``; el resto tienen valores por defecto seguros.
    """

    model_config = ConfigDict(
        # Permite crear el modelo a partir de un dict (GUI) o de JSON.
        populate_by_name=True,
        # Convierte automáticamente strings a int/bool cuando corresponde.
        coerce_numbers_to_str=False,
        # Rechaza claves desconocidas en producción (advertencia en vez de error
        # para no romper configs antiguas que tengan claves extra).
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Carpetas principales (obligatorias en el pipeline de descompresión)
    # ------------------------------------------------------------------
    input_folder: str = Field(
        default="",
        description="Carpeta con los archivos .zip de entrada.",
    )
    output_folder: str = Field(
        default="",
        description="Carpeta donde se guardan los archivos .mat de salida.",
    )
    excel_output_folder: str = Field(
        default="",
        description="Carpeta donde se guardan los excels de salida.",
    )

    # ------------------------------------------------------------------
    # MATLAB
    # ------------------------------------------------------------------
    matlab_path: str = Field(
        default="",
        description="Ruta absoluta al ejecutable matlab.exe.",
    )
    ruta_matlab_script: str = Field(
        default="",
        description="Carpeta que contiene procesar_matlab.m.",
    )
    ruta_guardado_graficos: str = Field(
        default="",
        description="Carpeta donde MATLAB guardará los gráficos (PNG).",
    )

    # ------------------------------------------------------------------
    # Estado / reanudación
    # ------------------------------------------------------------------
    state_folder: str = Field(
        default="",
        description=(
            "Carpeta persistente donde se guardan los CSV de días incompletos "
            "entre ejecuciones.  Si está vacío se usa '{output_folder}/.state'."
        ),
    )
    last_processed: str = Field(
        default="",
        description="Nombre del último archivo .zip procesado (para reanudar).",
    )
    selected_files: List[str] = Field(
        default_factory=list,
        description="Lista de archivos .zip seleccionados para procesar.",
    )

    # ------------------------------------------------------------------
    # Parámetros de señal
    # ------------------------------------------------------------------
    FS: int = Field(  # noqa: N815 — nombre heredado del código legacy
        default=10,
        gt=0,
        description="Frecuencia de muestreo en Hz.",
    )
    n_channels: int = Field(
        default=16,
        gt=0,
        description="Número de canales esperados en cada archivo.",
    )
    unidad: str = Field(
        default="05",
        description="Identificador de la unidad (ej: '05' → sufijo -u05).",
    )

    # ------------------------------------------------------------------
    # Ajuste de zona horaria
    # ------------------------------------------------------------------
    timezone_offset_hours: int = Field(
        default=-3,
        description=(
            "Horas de desfase a aplicar a las marcas de tiempo TDMS. "
            "Default -3 (Argentina, UTC-3).  0 = sin ajuste."
        ),
    )

    # ------------------------------------------------------------------
    # Flags de etapas del pipeline
    # ------------------------------------------------------------------
    descomprimir: bool = Field(
        default=True,
        description="Habilita el pipeline ZIP→TDMS→CSV→MAT.",
    )
    procesar_incompleto: bool = Field(
        default=False,
        description="Incluye archivos _temp.csv (días incompletos) en la conversión.",
    )
    rainflow: bool = Field(
        default=False,
        description="Habilita el procesamiento MATLAB de rainflow.",
    )
    realizar_conteo: bool = Field(
        default=False,
        description="Habilita el conteo de arranques y paradas.",
    )
    concatenar_excels: bool = Field(
        default=False,
        description="Habilita la concatenación de excels de rainflow.",
    )
    graficos_matlab: bool = Field(
        default=False,
        description="Guarda los gráficos de MATLAB como PNG.",
    )
    mostrar_salida_matlab: bool = Field(
        default=False,
        description="Muestra la salida estándar de MATLAB en el log.",
    )
    escritura: bool = Field(
        default=True,
        description="Parámetro 'escritura' pasado al script MATLAB.",
    )

    # ------------------------------------------------------------------
    # Separador decimal CSV (expuesto como parámetro de configuración)
    # ------------------------------------------------------------------
    csv_decimal_separator: str = Field(
        default=".",
        description=(
            "Separador decimal usado al leer/escribir CSV intermedios. "
            "Usar '.' para configuraciones en inglés (NI LabVIEW)."
        ),
    )

    # ------------------------------------------------------------------
    # Validadores
    # ------------------------------------------------------------------
    @field_validator("FS", "n_channels", mode="before")
    @classmethod
    def coerce_to_int(cls, v: object) -> int:
        """Coerciona strings a entero (compatibilidad con tkinter IntVar)."""
        try:
            return int(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Debe ser un entero, se recibió: {v!r}") from exc

    @field_validator("csv_decimal_separator")
    @classmethod
    def valid_decimal_sep(cls, v: str) -> str:
        if v not in (".", ","):
            raise ValueError("csv_decimal_separator debe ser '.' o ','")
        return v

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def output_path(self) -> Path:
        """Devuelve ``output_folder`` como :class:`pathlib.Path`."""
        return Path(self.output_folder)

    def excel_path(self) -> Path:
        """Devuelve ``excel_output_folder`` como :class:`pathlib.Path`."""
        return Path(self.excel_output_folder)

    def to_legacy_dict(self) -> dict:
        """Serializa a un dict compatible con el código legacy (GUI / main()).

        Las claves y tipos son idénticos a los que espera ``main()`` y la GUI.
        """
        return self.model_dump()
