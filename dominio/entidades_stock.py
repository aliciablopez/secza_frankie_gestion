"""
===============================================================================
ENTIDAD DE DOMINIO: STOCK E INVENTARIO (dominio/entidades_stock.py)
===============================================================================
Modela el producto del catálogo de inventario y las reglas operativas de stock:
- Detección de stock bajo / reposición (stock_actual <= stock_minimo).
- Cálculo de cantidad sugerida para orden de compra.
- Cálculo automático de precio de venta con margen del 20% si no se informa.
===============================================================================
"""

from dataclasses import dataclass
from typing import Optional

STOCK_MINIMO_DEFECTO = 75
MARGEN_GANANCIA_DEFECTO = 0.20


def calcular_precio_venta_sugerido(
    precio_costo: float, margen: float = MARGEN_GANANCIA_DEFECTO
) -> float:
    """Calcula el precio de venta aplicando un margen porcentual sobre el costo."""
    costo = max(0.0, float(precio_costo))
    return round(costo * (1.0 + margen), 2)


@dataclass
class Producto:
    """Entidad de dominio para un producto del inventario y su control de stock."""

    codigo: str
    descripcion: str
    id_proveedor: int
    precio_costo: float
    precio_venta: Optional[float] = None
    stock_actual: int = 0
    stock_minimo: int = STOCK_MINIMO_DEFECTO
    categoria: str = ""
    ubicacion: str = ""
    vencimiento: str = ""
    activo: bool = True
    id_producto: Optional[int] = None
    proveedor_nombre: str = ""

    def __post_init__(self) -> None:
        self.codigo = (self.codigo or "").strip()
        self.descripcion = (self.descripcion or "").strip()
        self.categoria = (self.categoria or "").strip()
        self.ubicacion = (self.ubicacion or "").strip()
        self.vencimiento = (self.vencimiento or "").strip()
        self.id_proveedor = int(self.id_proveedor)
        self.stock_actual = max(0, int(self.stock_actual))
        self.stock_minimo = max(0, int(self.stock_minimo))
        self.precio_costo = max(0.0, round(float(self.precio_costo), 2))
        self.activo = bool(self.activo)
        self.proveedor_nombre = (self.proveedor_nombre or "").strip()

        if self.precio_venta is None or float(self.precio_venta) <= 0.0:
            self.precio_venta = calcular_precio_venta_sugerido(self.precio_costo)
        else:
            self.precio_venta = max(0.0, round(float(self.precio_venta), 2))

    @property
    def alerta_stock_bajo(self) -> bool:
        """Indica si el stock actual está en o por debajo del stock mínimo."""
        return self.stock_actual <= self.stock_minimo

    @property
    def cantidad_sugerida_orden(self) -> int:
        """
        Cantidad sugerida a pedir en orden de compra cuando el stock cae
        en o por debajo del stock mínimo.
        """
        if not self.alerta_stock_bajo:
            return 0
        objetivo = max(self.stock_minimo, STOCK_MINIMO_DEFECTO)
        return max(1, objetivo - self.stock_actual)