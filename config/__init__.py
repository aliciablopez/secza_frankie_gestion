"""
===============================================================================
PAQUETE DE CONFIGURACIÓN GLOBAL: SISTEMA FRANKIE (config/__init__.py)
===============================================================================
Define rutas ancladas a la raíz del proyecto y parámetros base de RR. HH.
===============================================================================
"""

from pathlib import Path
from typing import Dict, List

# config/__init__.py -> config -> raíz del proyecto (secza_frankie)
RAIZ_PROYECTO: Path = Path(__file__).resolve().parent.parent

# Estructura centralizada de comprobantes dentro del proyecto
COMPROBANTES_DIR: Path = RAIZ_PROYECTO / "comprobantes"
DIR_RECIBOS_HABERES: Path = COMPROBANTES_DIR / "recibo_haberes"
DIR_FACTURAS: Path = COMPROBANTES_DIR / "facturas"
DIR_ORDENES_COMPRA: Path = COMPROBANTES_DIR / "ordenes_de_compra"

for _carpeta in (
    COMPROBANTES_DIR,
    DIR_RECIBOS_HABERES,
    DIR_FACTURAS,
    DIR_ORDENES_COMPRA,
):
    _carpeta.mkdir(parents=True, exist_ok=True)

CARGOS_EMPLEADO: List[str] = ["Gerente", "Admin", "Administrativo", "Vendedor"]
SECTORES_EMPLEADO: List[str] = [
    "Gestión",
    "Staff",
    "Ventas",
    "Compras",
    "Administración",
]
TIPOS_VINCULO_EMPLEADO: List[str] = [
    "Propietario",
    "Contratado",
    "Pasante",
    "Permanente",
]

SUELDOS_BASICOS_POR_CARGO: Dict[str, float] = {
    "Gerente": 1800000.0,
    "Admin": 1350000.0,
    "Administrativo": 1150000.0,
    "Vendedor": 1100000.0,
}

FACTOR_VINCULO_SUELDO: Dict[str, float] = {
    "Propietario": 1.0,
    "Permanente": 1.0,
    "Contratado": 0.90,
    "Pasante": 0.65,
}


def obtener_sueldo_basico(cargo: str, tipo_vinculo: str) -> float:
    """Calcula el sueldo básico según cargo y tipo de vínculo."""
    base = float(SUELDOS_BASICOS_POR_CARGO.get(cargo, 1000000.0))
    factor = float(FACTOR_VINCULO_SUELDO.get(tipo_vinculo, 1.0))
    return round(base * factor, 2)