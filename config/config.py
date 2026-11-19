"""
===============================================================================
MÓDULO DE CONFIGURACIÓN CENTRALIZADA (config.py)
===============================================================================
Centraliza constantes globales del sistema para evitar valores dispersos.
"""

from dataclasses import dataclass
from typing import Final

IVA_POR_DEFECTO: Final[float] = 0.21

# Parámetros orientativos para RR. HH. / Liquidación (ajustar según normativa vigente)
APORTE_JUBILACION_PORC: Final[float] = 0.11
APORTE_OBRA_SOCIAL_PORC: Final[float] = 0.03
APORTE_PAMI_PORC: Final[float] = 0.03
CONTRIBUCION_PATRONAL_PORC: Final[float] = 0.10


@dataclass(frozen=True)
class ConfiguracionSistema:
    """Contenedor inmutable de parámetros generales del sistema."""

    iva: float = IVA_POR_DEFECTO
    aporte_jubilacion: float = APORTE_JUBILACION_PORC
    aporte_obra_social: float = APORTE_OBRA_SOCIAL_PORC
    aporte_pami: float = APORTE_PAMI_PORC
    contribucion_patronal: float = CONTRIBUCION_PATRONAL_PORC

    def __post_init__(self) -> None:
        if not (0.0 <= self.iva <= 1.0):
            raise ValueError("El IVA configurado debe estar entre 0.0 y 1.0.")
        for nombre, valor in (
            ("aporte_jubilacion", self.aporte_jubilacion),
            ("aporte_obra_social", self.aporte_obra_social),
            ("aporte_pami", self.aporte_pami),
            ("contribucion_patronal", self.contribucion_patronal),
        ):
            if not (0.0 <= valor <= 1.0):
                raise ValueError(f"El parámetro '{nombre}' debe estar entre 0.0 y 1.0.")


CONFIG_SISTEMA: Final[ConfiguracionSistema] = ConfiguracionSistema()