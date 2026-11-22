"""
===============================================================================
ENTIDADES DE DOMINIO: CLIENTES (dominio/entidades_clientes.py)
===============================================================================
Modela Clientes (siempre Persona Física, Consumidor Final y con CUIT de 11 dígitos)
sin dependencias de SQLite ni Tkinter.
===============================================================================
"""

from dataclasses import dataclass
from typing import Optional, Sequence

import config

try:
    from dominio.entidades_persona import limpiar_documento as _limpiar_doc_persona
except ImportError:
    _limpiar_doc_persona = None


def limpiar_cuit(cuit_raw: str) -> str:
    """Extrae únicamente los dígitos de un CUIT (11 caracteres)."""
    if callable(_limpiar_doc_persona):
        return _limpiar_doc_persona(cuit_raw)
    return "".join(ch for ch in str(cuit_raw or "") if ch.isdigit())


def es_cuit_persona_fisica_valido(
    cuit_raw: str,
    prefijos_permitidos: Optional[Sequence[str]] = None,
) -> bool:
    """
    Valida que el CUIT tenga 11 dígitos y comience con un prefijo válido
    de Persona Física según la configuración (por defecto '20' o '27').
    """
    digitos = limpiar_cuit(cuit_raw)
    if len(digitos) != 11:
        return False

    if prefijos_permitidos is None:
        prefijos = tuple(
            str(p).strip()
            for p in getattr(
                config,
                "PREFIJOS_PERSONA_FISICA",
                getattr(config, "PREFIJOS_CUIT_PERSONA_FISICA", ("20", "27")),
            )
            if str(p).strip()
        )
    else:
        prefijos = tuple(str(p).strip() for p in prefijos_permitidos if str(p).strip())

    return bool(prefijos) and digitos.startswith(prefijos)


@dataclass
class Cliente:
    """Representa un cliente Persona Física, Consumidor Final, identificado con CUIT."""

    cuit: str
    nombres: str
    apellidos: str
    id_cliente: Optional[int] = None
    id_persona: Optional[int] = None
    tipo_documento: str = "CUIT"
    condicion_iva: str = "Consumidor Final"
    telefono: str = ""
    email: str = ""
    domicilio: str = ""
    ciudad: str = ""
    provincia: str = ""
    codigo_postal: str = ""
    fecha_alta: str = ""
    activo: bool = True

    def __post_init__(self) -> None:
        self.cuit = limpiar_cuit(self.cuit)
        self.nombres = (self.nombres or "").strip()
        self.apellidos = (self.apellidos or "").strip()
        self.tipo_documento = "CUIT"
        self.condicion_iva = "Consumidor Final"
        self.telefono = (self.telefono or "").strip()
        self.email = (self.email or "").strip()
        self.domicilio = (self.domicilio or "").strip()
        self.ciudad = (self.ciudad or "").strip()
        self.provincia = (self.provincia or "").strip()
        self.codigo_postal = (self.codigo_postal or "").strip()
        self.fecha_alta = (self.fecha_alta or "").strip()
        self.activo = bool(self.activo)

    @property
    def nro_documento(self) -> str:
        """Alias de compatibilidad hacia el CUIT normalizado."""
        return self.cuit

    @nro_documento.setter
    def nro_documento(self, valor: str) -> None:
        self.cuit = limpiar_cuit(valor)

    @property
    def nombre_completo(self) -> str:
        if self.apellidos and self.nombres:
            return f"{self.apellidos}, {self.nombres}"
        return self.apellidos or self.nombres or "Cliente"

    @property
    def nombre(self) -> str:
        return self.nombres

    @property
    def apellido(self) -> str:
        return self.apellidos