"""
===============================================================================
MÓDULO DE DOMINIO: ENTIDADES DE RECURSOS HUMANOS (dominio/entidades_rrhh.py)
===============================================================================
Define las listas de dominio y la entidad 'Empleado' heredada de 'Persona',
manteniendo la capa de dominio libre de SQLite y Tkinter.
===============================================================================
"""

from typing import Dict, List, Optional, Tuple

from dominio.entidades_persona import Persona, limpiar_documento

_CARGOS_DEFAULT: Tuple[str, ...] = ("Gerente", "Admin", "Administrativo", "Vendedor")
_SECTORES_DEFAULT: Tuple[str, ...] = (
    "Gestión",
    "Staff",
    "Ventas",
    "Compras",
    "Administración",
)
_VINCULOS_DEFAULT: Tuple[str, ...] = ("Propietario", "Contratado", "Pasante", "Permanente")
_SUELDOS_DEFAULT: Dict[str, float] = {
    "Gerente": 1800000.0,
    "Admin": 1350000.0,
    "Administrativo": 1150000.0,
    "Vendedor": 1100000.0,
}
_FACTORES_DEFAULT: Dict[str, float] = {
    "Propietario": 1.0,
    "Permanente": 1.0,
    "Contratado": 0.90,
    "Pasante": 0.65,
}

try:
    from config import (
        CARGOS_EMPLEADO,
        FACTOR_VINCULO_SUELDO,
        SECTORES_EMPLEADO,
        SUELDOS_BASICOS_POR_CARGO,
        TIPOS_VINCULO_EMPLEADO,
    )
except ImportError:
    CARGOS_EMPLEADO = _CARGOS_DEFAULT
    SECTORES_EMPLEADO = _SECTORES_DEFAULT
    TIPOS_VINCULO_EMPLEADO = _VINCULOS_DEFAULT
    SUELDOS_BASICOS_POR_CARGO = _SUELDOS_DEFAULT
    FACTOR_VINCULO_SUELDO = _FACTORES_DEFAULT


def _a_lista_strings(valor: object, respaldo: Tuple[str, ...]) -> List[str]:
    """Convierte de forma segura una colección configurada en una lista de strings."""
    if isinstance(valor, (list, tuple)) and len(valor) > 0:
        return [str(item) for item in valor]
    return list(respaldo)


CARGOS: List[str] = _a_lista_strings(CARGOS_EMPLEADO, _CARGOS_DEFAULT)
SECTORES: List[str] = _a_lista_strings(SECTORES_EMPLEADO, _SECTORES_DEFAULT)
TIPOS_VINCULO: List[str] = _a_lista_strings(TIPOS_VINCULO_EMPLEADO, _VINCULOS_DEFAULT)


def _calcular_sueldo_config(cargo: str, tipo_vinculo: str) -> float:
    """Lee el sueldo básico desde config según cargo y situación de revista."""
    sueldos = (
        SUELDOS_BASICOS_POR_CARGO
        if isinstance(SUELDOS_BASICOS_POR_CARGO, dict) and SUELDOS_BASICOS_POR_CARGO
        else _SUELDOS_DEFAULT
    )
    factores = (
        FACTOR_VINCULO_SUELDO
        if isinstance(FACTOR_VINCULO_SUELDO, dict) and FACTOR_VINCULO_SUELDO
        else _FACTORES_DEFAULT
    )

    base = float(sueldos.get(cargo, 1000000.0))
    factor = float(factores.get(tipo_vinculo, 1.0))
    return round(base * factor, 2)


class Empleado(Persona):
    """Entidad de dominio que representa a un trabajador dentro de la organización."""

    def __init__(
        self,
        nro_documento: str,
        nombres: str,
        legajo: str,
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
        cargo_resuelto = cargo if cargo in CARGOS else "Vendedor"
        sector_resuelto = sector if sector in SECTORES else "Ventas"
        vinculo_resuelto = (
            tipo_vinculo if tipo_vinculo in TIPOS_VINCULO else "Contratado"
        )

        self.id_empleado = id_empleado
        self.id_persona = id_persona
        self.id_usuario = id_usuario
        self.nro_documento = limpiar_documento(nro_documento)
        self.legajo = (legajo or "").strip()
        self.cargo = cargo_resuelto
        self.sector = sector_resuelto
        self.tipo_vinculo = vinculo_resuelto
        self.sueldo = _calcular_sueldo_config(cargo_resuelto, vinculo_resuelto)
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