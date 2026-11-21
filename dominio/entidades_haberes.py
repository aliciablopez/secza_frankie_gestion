"""
===============================================================================
MÓDULO DE DOMINIO: ENTIDADES DE HABERES (dominio/entidades_haberes.py)
===============================================================================
Modela la estructura de datos para la liquidación de sueldos, conceptos
remunerativos y deducciones de ley del personal, manteniendo compatibilidad
con los alias usados por repositorios y vistas.
===============================================================================
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LiquidacionHaberes:
    """
    Entidad de dominio que representa el recibo o liquidación de haberes
    de un empleado para un período fiscal determinado.
    """

    id_empleado: int
    periodo: str  # Formato AAAA-MM
    sueldo_basico: float = 0.0
    antiguedad_monto: float = 0.0
    presentismo_monto: float = 0.0
    horas_extra_monto: float = 0.0
    feriados_monto: float = 0.0
    comisiones_ventas: float = 0.0
    total_remunerativo: float = 0.0
    total_no_remunerativo: float = 0.0
    jubilacion: float = 0.0
    pami: float = 0.0
    obra_social: float = 0.0
    sindicato: float = 0.0
    adelantos: float = 0.0
    total_descuentos: float = 0.0
    neto_a_cobrar: float = 0.0
    id: Optional[int] = None
    fecha_registro: Optional[str] = None

    # --- Propiedades de compatibilidad para el Linter y Repositorio ---
    @property
    def id_liquidacion(self) -> Optional[int]:
        return self.id

    @id_liquidacion.setter
    def id_liquidacion(self, valor: Optional[int]) -> None:
        self.id = valor

    @property
    def sueldo_neto(self) -> float:
        return self.neto_a_cobrar

    @sueldo_neto.setter
    def sueldo_neto(self, valor: float) -> None:
        self.neto_a_cobrar = valor

    @property
    def periodo_formateado(self) -> str:
        """Retorna el período en formato legible si sigue el patrón AAAA-MM."""
        partes = (self.periodo or "").strip().split("-")
        if len(partes) == 2 and all(partes):
            return f"Mes {partes[1]} / Año {partes[0]}"
        return self.periodo

    def calcular_totales(self) -> None:
        """Recalcula remunerativos, descuentos y neto a cobrar en memoria."""
        self.total_remunerativo = round(
            float(self.sueldo_basico or 0.0)
            + float(self.antiguedad_monto or 0.0)
            + float(self.presentismo_monto or 0.0)
            + float(self.horas_extra_monto or 0.0)
            + float(self.feriados_monto or 0.0)
            + float(self.comisiones_ventas or 0.0),
            2,
        )
        self.total_descuentos = round(
            float(self.jubilacion or 0.0)
            + float(self.pami or 0.0)
            + float(self.obra_social or 0.0)
            + float(self.sindicato or 0.0)
            + float(self.adelantos or 0.0),
            2,
        )
        bruto = self.total_remunerativo + float(self.total_no_remunerativo or 0.0)
        self.neto_a_cobrar = round(max(0.0, bruto - self.total_descuentos), 2)