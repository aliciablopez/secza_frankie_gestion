"""
===============================================================================
ENTIDADES DE DOMINIO: PROVEEDORES (dominio/entidades_proveedores.py)
===============================================================================
Reglas de negocio:
- Todos los proveedores son Personas Jurídicas.
- Identificados con CUIT de 11 dígitos y prefijo obligatorio "30".
- Rubros permitidos: "Bijou", "Accesorios", "Marroquinería".
- Sin posición frente al IVA por simplicidad del microemprendimiento.
- Incluye persona de contacto (persona física de enlace) y estado activo/inactivo.
===============================================================================
"""

from dataclasses import dataclass
from typing import Optional

PREFIJO_CUIT_PROVEEDOR = "30"
RUBROS_PROVEEDOR = ("Bijou", "Accesorios", "Marroquinería")


def limpiar_cuit(cuit_raw: str) -> str:
    """Extrae únicamente los dígitos de un CUIT."""
    return "".join(ch for ch in (cuit_raw or "") if ch.isdigit())


def es_cuit_proveedor_valido(cuit_raw: str) -> bool:
    """
    Valida que el CUIT tenga 11 dígitos y comience con el prefijo '30'
    correspondiente a Persona Jurídica para proveedores.
    """
    digitos = limpiar_cuit(cuit_raw)
    return len(digitos) == 11 and digitos.startswith(PREFIJO_CUIT_PROVEEDOR)


def validar_rubro_proveedor(rubro: str) -> str:
    """Normaliza y valida que el rubro pertenezca a las opciones permitidas."""
    valor = (rubro or "").strip()
    if valor not in RUBROS_PROVEEDOR:
        opciones = ", ".join(RUBROS_PROVEEDOR)
        raise ValueError(f"Rubro inválido '{valor}'. Opciones permitidas: {opciones}.")
    return valor


@dataclass
class Proveedor:
    """Entidad de dominio para un proveedor (Persona Jurídica, CUIT 30...)."""

    cuit: str
    razon_social: str
    rubro: str
    contacto: str = ""
    telefono: str = ""
    email: str = ""
    domicilio: str = ""
    activo: bool = True
    fecha_alta: str = ""
    id_proveedor: Optional[int] = None
    id_persona: Optional[int] = None

    def __post_init__(self) -> None:
        self.cuit = limpiar_cuit(self.cuit)
        self.razon_social = (self.razon_social or "").strip()
        self.rubro = validar_rubro_proveedor(self.rubro)
        self.contacto = (self.contacto or "").strip()
        self.telefono = (self.telefono or "").strip()
        self.email = (self.email or "").strip()
        self.domicilio = (self.domicilio or "").strip()
        self.activo = bool(self.activo)