"""
===============================================================================
ENTIDADES DE DOMINIO: VENTAS Y CLIENTES (entidades_ventas.py)
===============================================================================
Modela Clientes (personas físicas con prefijos configurados), Facturas y
Detalles sin dependencias de SQLite ni Tkinter.
===============================================================================
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import config


def limpiar_documento(doc_raw: str) -> str:
    """Extrae únicamente los dígitos de un CUIT/CUIL (11 caracteres)."""
    return "".join(ch for ch in str(doc_raw or "") if ch.isdigit())


def es_cuit_cuil_valido(
    doc_raw: str,
    prefijos_permitidos: Optional[Sequence[str]] = None,
) -> bool:
    """
    Valida un CUIT/CUIL de 11 dígitos numéricos (sin calcular dígito verificador):
    1. Longitud exacta de 11 dígitos.
    2. Comienza con alguno de los prefijos permitidos.
    """
    digitos = limpiar_documento(doc_raw)
    if len(digitos) != 11:
        return False

    if prefijos_permitidos is None:
        prefijos = tuple(
            str(p).strip()
            for p in getattr(
                config,
                "PREFIJOS_CUIT_CUIL_VALIDOS",
                getattr(config, "PREFIJOS_PERSONA_FISICA", ("20", "27", "30")),
            )
        )
    else:
        prefijos = tuple(str(p).strip() for p in prefijos_permitidos)

    return bool(prefijos) and digitos.startswith(prefijos)


def es_documento_persona_fisica_valido(doc_raw: str) -> bool:
    """
    Valida que el documento de cliente sea un CUIT/CUIL de 11 dígitos de persona
    física según los prefijos configurados en `config.PREFIJOS_PERSONA_FISICA`.
    """
    prefijos_fisica = tuple(
        str(p).strip()
        for p in getattr(config, "PREFIJOS_PERSONA_FISICA", ("20", "27"))
    )
    return es_cuit_cuil_valido(doc_raw, prefijos_permitidos=prefijos_fisica)


@dataclass
class Cliente:
    """Representa un cliente (siempre persona física) vinculado a `personas`."""

    nro_documento: str
    nombres: str
    apellidos: str
    id_cliente: Optional[int] = None
    id_persona: Optional[int] = None
    tipo_documento: str = "CUIL"
    telefono: str = ""
    email: str = ""
    domicilio: str = ""
    ciudad: str = ""
    provincia: str = ""
    codigo_postal: str = ""
    fecha_alta: str = ""
    activo: bool = True

    @property
    def nombre_completo(self) -> str:
        apellidos = (self.apellidos or "").strip()
        nombres = (self.nombres or "").strip()
        if apellidos and nombres:
            return f"{apellidos}, {nombres}"
        return apellidos or nombres or "Cliente"


@dataclass
class DetalleFactura:
    """Representa un renglón o ítem dentro de una factura."""

    id_producto: int
    codigo_producto: str
    descripcion_producto: str
    cantidad: int
    precio_lista: float
    descuento_cantidad_pct: float = 0.0
    subtotal_neto: float = 0.0
    impuesto_provincial: float = 0.0
    iva: float = 0.0
    subtotal_final: float = 0.0
    id_detalle: Optional[int] = None
    id_factura: Optional[int] = None


@dataclass
class Factura:
    """Representa una factura de tres niveles: cabecera, detalle y totales."""

    id_cliente: int
    id_vendedor: int
    condicion_venta: str = "Efectivo"
    fecha: str = ""
    cliente_nombre: str = ""
    cliente_documento: str = ""
    vendedor_nombre: str = ""
    subtotal_items: float = 0.0
    ajuste_condicion_monto: float = 0.0  # Positivo = descuento, negativo = recargo
    impuesto_provincial_total: float = 0.0
    iva_total: float = 0.0
    total: float = 0.0
    id_factura: Optional[int] = None
    detalles: List[DetalleFactura] = field(default_factory=list)