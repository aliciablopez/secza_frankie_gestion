"""
===============================================================================
MÓDULO DE DOMINIO: ENTIDADES DE RECURSOS HUMANOS (dominio/entidades_rrhh.py)
===============================================================================
Define las listas de dominio y la entidad 'Empleado' heredada de 'Persona',
manteniendo la capa de dominio libre de SQLite y Tkinter.
===============================================================================
"""

from typing import Optional

from dominio.entidades_persona import Persona, limpiar_documento

try:
    from config import (
        CARGOS_EMPLEADO as _CARGOS_CFG,
        SECTORES_EMPLEADO as _SECTORES_CFG,
        TIPOS_VINCULO_EMPLEADO as _VINCULOS_CFG,
    )
except ImportError:
    _CARGOS_CFG = ("Gerente", "Admin", "Administrativo", "Vendedor")
    _SECTORES_CFG = ("Gestión", "Staff", "Ventas", "Compras", "Administración")
    _VINCULOS_CFG = ("Propietario", "Contratado", "Pasante", "Permanente")

CARGOS: list[str] = list(_CARGOS_CFG)
SECTORES: list[str] = list(_SECTORES_CFG)
TIPOS_VINCULO: list[str] = list(_VINCULOS_CFG)


class Empleado(Persona):
    """Entidad de dominio que representa a un trabajador dentro de la organización."""

    def __init__(
        self,
        nro_documento: str,
        nombres: str,
        legajo: str,
        sueldo: float,
        cargo: str = "Vendedor",
        sector: str = "Ventas",
        tipo_vinculo: str = "Contratado",
        apellidos: Optional[str] = None,
        tipo_documento: str = "CUIT",
        email: Optional[str] = None,
        telefono: Optional[str] = None,
        domicilio: Optional[str] = None,
        ciudad: Optional[str] = None,
        provincia: Optional[str] = None,
        codigo_postal: Optional[str] = None,
        id_empleado: Optional[int] = None,
        id_persona: Optional[int] = None,
        id_usuario: Optional[int] = None,
        activo: bool = True,
    ) -> None:
        super().__init__(
            id_persona=id_persona,
            nro_documento=nro_documento,
            nombres=nombres,
            apellidos=apellidos or "",
            email=email or "",
            telefono=telefono or "",
            tipo_persona="Fisica",
            tipo_documento=tipo_documento,
            domicilio=domicilio or "",
            ciudad=ciudad or "",
            provincia=provincia or "",
            codigo_postal=codigo_postal or "",
        )
        self.id_empleado = id_empleado
        self.id_persona = id_persona
        self.id_usuario = id_usuario
        self.nro_documento = limpiar_documento(nro_documento)
        self.legajo = (legajo or "").strip()
        self.cargo = cargo if cargo in CARGOS else "Vendedor"
        self.sector = sector if sector in SECTORES else "Ventas"
        self.tipo_vinculo = (
            tipo_vinculo if tipo_vinculo in TIPOS_VINCULO else "Contratado"
        )
        self.sueldo = float(sueldo) if sueldo is not None else 0.0
        self.activo = bool(activo)

    @property
    def requiere_factura(self) -> bool:
        """Indica si el vínculo laboral requiere factura por locación de servicios."""
        return self.tipo_vinculo in ("Propietario", "Contratado")

    @property
    def requiere_comprobante_afip(self) -> bool:
        """Indica si el vínculo laboral corresponde a situación monotributista/independiente."""
        return self.tipo_vinculo in ("Propietario", "Contratado")

    @property
    def es_pasante(self) -> bool:
        """Indica si el vínculo es pasantía con carga horaria específica."""
        return self.tipo_vinculo == "Pasante"

    @property
    def es_permanente(self) -> bool:
        """Indica si el vínculo es contrato de duración indefinida."""
        return self.tipo_vinculo == "Permanente"

    def obtener_nombre_completo(self) -> str:
        """Retorna 'Apellidos, Nombres' o el dato disponible si falta alguno."""
        if self.apellidos and self.nombres:
            return f"{self.apellidos}, {self.nombres}"
        return self.nombres or self.apellidos or "Sin Nombre"

    def __str__(self) -> str:
        return (
            f"Empleado [{self.legajo}] - {self.obtener_nombre_completo()} "
            f"({self.cargo} · {self.tipo_vinculo})"
        )