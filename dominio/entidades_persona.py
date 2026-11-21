"""
===============================================================================
NÚCLEO DE DOMINIO: ENTIDAD PERSONA (dominio/entidades_persona.py)
===============================================================================
Define la entidad base 'Persona' y sus funciones de saneamiento de datos.
Al ser un concepto transversal, es reutilizado por RRHH, Proveedores y Clientes.
===============================================================================
"""

from typing import Optional

TIPOS_PERSONA = ("Fisica", "Juridica")
TIPOS_DOCUMENTO = ("DNI", "CUIT", "CUIL", "Pasaporte")


def limpiar_documento(doc: str) -> str:
    """Sanitiza la cadena del documento eliminando guiones y espacios vacíos."""
    if not doc:
        return ""
    return str(doc).replace("-", "").replace(" ", "").strip()


class Persona:
    """Entidad base de dominio para representar a una persona física o jurídica."""

    def __init__(
        self,
        id_persona: Optional[int] = None,
        nro_documento: str = "",
        nombres: Optional[str] = "",
        apellidos: Optional[str] = "",
        email: Optional[str] = "",
        telefono: Optional[str] = "",
        tipo_persona: str = "Fisica",
        tipo_documento: str = "DNI",
        razon_social: Optional[str] = None,
        domicilio: Optional[str] = "",
        ciudad: Optional[str] = "",
        provincia: Optional[str] = "",
        codigo_postal: Optional[str] = "",
    ) -> None:
        self.id = id_persona
        self.nro_documento = limpiar_documento(nro_documento)
        self.nombres = (nombres or "").strip()
        self.apellidos = (apellidos or "").strip()
        self.email = (email or "").strip()
        self.telefono = (telefono or "").strip()
        self.tipo_persona = tipo_persona if tipo_persona in TIPOS_PERSONA else "Fisica"
        self.tipo_documento = (
            tipo_documento if tipo_documento in TIPOS_DOCUMENTO else "DNI"
        )
        self.razon_social = (
            razon_social.strip() if isinstance(razon_social, str) and razon_social.strip() else None
        )
        self.domicilio = (domicilio or "").strip()
        self.ciudad = (ciudad or "").strip()
        self.provincia = (provincia or "").strip()
        self.codigo_postal = (codigo_postal or "").strip()