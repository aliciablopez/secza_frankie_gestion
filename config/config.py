"""
===============================================================================
MÓDULO DE CONFIGURACIÓN CENTRALIZADA (config.py)
===============================================================================
Centraliza constantes globales del sistema para evitar valores dispersos.
===============================================================================
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Final, Tuple

BASE_DIR: Final[Path] = Path(__file__).resolve().parent

# Directorios de comprobantes generados
DIR_COMPROBANTES: Final[Path] = BASE_DIR / "comprobantes"
DIR_RECIBOS_HABERES: Final[Path] = DIR_COMPROBANTES / "recibo_haberes"
DIR_FACTURAS: Final[Path] = DIR_COMPROBANTES / "facturas"
DIR_ORDENES_COMPRA: Final[Path] = DIR_COMPROBANTES / "ordenes_de_compra"

for _carpeta in (
    DIR_COMPROBANTES,
    DIR_RECIBOS_HABERES,
    DIR_FACTURAS,
    DIR_ORDENES_COMPRA,
):
    _carpeta.mkdir(parents=True, exist_ok=True)

IVA_POR_DEFECTO: Final[float] = 0.21
IMPUESTO_PROVINCIAL_PORC: Final[float] = 0.03  # 3% sobre precio de lista

# Parámetros de RR. HH. / Liquidación
APORTE_JUBILACION_PORC: Final[float] = 0.11
APORTE_OBRA_SOCIAL_PORC: Final[float] = 0.03
APORTE_PAMI_PORC: Final[float] = 0.03
APORTE_SINDICATO_PORC: Final[float] = 0.025
PORC_PRESENTISMO: Final[float] = 0.0833
CONTRIBUCION_PATRONAL_PORC: Final[float] = 0.10

# Categorías de RR. HH. (deben mantenerse alineadas con el CHECK de empleados en esquema.sql)
CARGOS_EMPLEADO: Final[Tuple[str, ...]] = (
    "Gerente",
    "Admin",
    "Administrativo",
    "Vendedor",
)

SECTORES_EMPLEADO: Final[Tuple[str, ...]] = (
    "Gestión",
    "Staff",
    "Ventas",
    "Compras",
    "Administración",
)

TIPOS_VINCULO_EMPLEADO: Final[Tuple[str, ...]] = (
    "Propietario",
    "Contratado",
    "Pasante",
    "Permanente",
)

# Sueldos básicos de referencia por cargo y factor según situación de revista / vínculo
SUELDOS_BASICOS_POR_CARGO: Final[Dict[str, float]] = {
    "Gerente": 1800000.0,
    "Admin": 1350000.0,
    "Administrativo": 1150000.0,
    "Vendedor": 1100000.0,
}

FACTOR_VINCULO_SUELDO: Final[Dict[str, float]] = {
    "Propietario": 1.0,
    "Permanente": 1.0,
    "Contratado": 0.90,
    "Pasante": 0.65,
}


def obtener_sueldo_basico(cargo: str, tipo_vinculo: str = "Permanente") -> float:
    """Calcula el sueldo básico de referencia según cargo y situación de revista."""
    base = float(SUELDOS_BASICOS_POR_CARGO.get(cargo, 1000000.0))
    factor = float(FACTOR_VINCULO_SUELDO.get(tipo_vinculo, 1.0))
    return round(base * factor, 2)


# Parámetros comerciales y de ventas (Módulo 3)
# Tramos de descuento por cantidad: {cantidad_minima: descuento_proporcion}
TRAMOS_DESCUENTO_CANTIDAD: Final[Dict[int, float]] = {
    10: 0.10,
    5: 0.05,
}

# Condiciones de venta: valores positivos = descuento, valores negativos = recargo
CONDICIONES_VENTA_PORC: Final[Dict[str, float]] = {
    "Efectivo": 0.10,             # 10% de descuento
    "Fidelidad": 0.05,            # 5% de descuento por cuenta de fidelidad
    "Cuenta Corriente": 0.0,      # Sin ajuste por medio de pago
    "Tarjeta de Crédito": -0.08,  # 8% de recargo
}

CONDICIONES_VENTA: Final[Tuple[str, ...]] = tuple(CONDICIONES_VENTA_PORC.keys())

# Cliente frecuente: mínimo de compras en el mes calendario
MINIMO_COMPRAS_CLIENTE_FRECUENTE: Final[int] = 3

# Comisiones y bono por mejor vendedor del mes (proporciones sobre ventas del período)
COMISION_VENDEDOR_PORC: Final[float] = 0.05
BONO_MEJOR_VENDEDOR_PORC: Final[float] = 0.03

# Prefijos válidos de CUIT/CUIL (11 dígitos numéricos; último dígito solo completa longitud)
PREFIJOS_PERSONA_FISICA: Final[Tuple[str, ...]] = ("20", "27")
PREFIJOS_CUIT_CUIL_VALIDOS: Final[Tuple[str, ...]] = ("20", "27", "30")


@dataclass(frozen=True)
class ConfiguracionSistema:
    """Contenedor inmutable de parámetros generales del sistema."""

    iva: float = IVA_POR_DEFECTO
    impuesto_provincial: float = IMPUESTO_PROVINCIAL_PORC
    aporte_jubilacion: float = APORTE_JUBILACION_PORC
    aporte_obra_social: float = APORTE_OBRA_SOCIAL_PORC
    aporte_pami: float = APORTE_PAMI_PORC
    aporte_sindicato: float = APORTE_SINDICATO_PORC
    presentismo_porc: float = PORC_PRESENTISMO
    contribucion_patronal: float = CONTRIBUCION_PATRONAL_PORC
    comision_vendedor: float = COMISION_VENDEDOR_PORC
    bono_mejor_vendedor: float = BONO_MEJOR_VENDEDOR_PORC
    minimo_compras_frecuente: int = MINIMO_COMPRAS_CLIENTE_FRECUENTE
    prefijos_persona_fisica: Tuple[str, ...] = PREFIJOS_PERSONA_FISICA
    prefijos_cuit_cuil_validos: Tuple[str, ...] = PREFIJOS_CUIT_CUIL_VALIDOS
    cargos_empleado: Tuple[str, ...] = CARGOS_EMPLEADO
    sectores_empleado: Tuple[str, ...] = SECTORES_EMPLEADO
    tipos_vinculo_empleado: Tuple[str, ...] = TIPOS_VINCULO_EMPLEADO
    dir_comprobantes: Path = DIR_COMPROBANTES
    dir_recibos_haberes: Path = DIR_RECIBOS_HABERES
    dir_facturas: Path = DIR_FACTURAS
    dir_ordenes_compra: Path = DIR_ORDENES_COMPRA

    def __post_init__(self) -> None:
        parametros_tasa = (
            ("iva", self.iva),
            ("impuesto_provincial", self.impuesto_provincial),
            ("aporte_jubilacion", self.aporte_jubilacion),
            ("aporte_obra_social", self.aporte_obra_social),
            ("aporte_pami", self.aporte_pami),
            ("aporte_sindicato", self.aporte_sindicato),
            ("presentismo_porc", self.presentismo_porc),
            ("contribucion_patronal", self.contribucion_patronal),
            ("comision_vendedor", self.comision_vendedor),
            ("bono_mejor_vendedor", self.bono_mejor_vendedor),
        )
        for nombre, valor in parametros_tasa:
            if not (0.0 <= valor <= 1.0):
                raise ValueError(f"El parámetro '{nombre}' debe estar entre 0.0 y 1.0.")
        if self.minimo_compras_frecuente < 1:
            raise ValueError("El mínimo de compras para cliente frecuente debe ser al menos 1.")
        if not self.prefijos_persona_fisica:
            raise ValueError("Debe configurar al menos un prefijo para persona física.")
        if not self.prefijos_cuit_cuil_validos:
            raise ValueError("Debe configurar al menos un prefijo válido de CUIT/CUIL.")
        if not self.cargos_empleado:
            raise ValueError("Debe configurar al menos un cargo de empleado.")
        if not self.sectores_empleado:
            raise ValueError("Debe configurar al menos un sector de empleado.")
        if not self.tipos_vinculo_empleado:
            raise ValueError("Debe configurar al menos un tipo de vínculo de empleado.")


CONFIG_SISTEMA: Final[ConfiguracionSistema] = ConfiguracionSistema()
