"""
===============================================================================
MÓDULO DE CONTROL: ORQUESTADOR DE VENTAS (controladores/orquestador_ventas.py)
===============================================================================
"""

from typing import Any, Dict, List, Optional, Tuple
from config.config import CONFIG_SISTEMA
from dominio.entidades_ventas import DetalleFactura, Factura
from infraestructura.repo_ventas import RepositorioVentas


class OrquestadorVentas:
    """
    Controlador de casos de uso del módulo de Ventas.
    Valida datos de entrada, aplica reglas de cálculo y coordina la persistencia.
    """

    def __init__(
        self,
        repo_ventas: Optional[RepositorioVentas] = None,
        porcentaje_iva: Optional[float] = None,
    ):
        self.repo = repo_ventas or RepositorioVentas()
        iva = CONFIG_SISTEMA.iva if porcentaje_iva is None else porcentaje_iva
        self.porcentaje_iva = self._validar_porcentaje_decimal(iva, "porcentaje_iva")

    @staticmethod
    def _es_numero_valido(valor: Any) -> bool:
        """Verifica que el valor sea int o float y no un booleano."""
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)

    @classmethod
    def _validar_porcentaje_decimal(cls, valor: Any, nombre_campo: str) -> float:
        """Valida un porcentaje expresado como fracción (ej. 0.21 para 21%)."""
        if not cls._es_numero_valido(valor) or not (0.0 <= float(valor) <= 1.0):
            raise ValueError(f"'{nombre_campo}' debe ser un número entre 0.0 y 1.0.")
        return float(valor)

    @classmethod
    def calcular_renglon(
        cls,
        cantidad: int,
        precio_unitario: float,
        descuento_porc: float = 0.0,
    ) -> float:
        """Calcula el subtotal de un renglón aplicando descuento porcentual (0 a 100)."""
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("La cantidad del ítem debe ser un número entero mayor a cero.")
        if not cls._es_numero_valido(precio_unitario) or float(precio_unitario) < 0:
            raise ValueError("El precio unitario debe ser un número mayor o igual a cero.")
        if not cls._es_numero_valido(descuento_porc) or not (0.0 <= float(descuento_porc) <= 100.0):
            raise ValueError("El descuento porcentual debe estar entre 0 y 100.")

        subtotal_bruto = cantidad * float(precio_unitario)
        descuento_monto = subtotal_bruto * (float(descuento_porc) / 100.0)
        return round(subtotal_bruto - descuento_monto, 2)

    def calcular_totales_factura(
        self,
        lista_detalles: List[DetalleFactura],
        aplicar_iva: bool = True,
    ) -> Tuple[float, float, float]:
        """Calcula (subtotal_base, monto_iva, total_final) a partir de los detalles."""
        if not isinstance(aplicar_iva, bool):
            raise ValueError("'aplicar_iva' debe ser un valor booleano.")

        subtotal_base = round(sum(det.subtotal for det in lista_detalles), 2)
        monto_iva = round((subtotal_base * self.porcentaje_iva) if aplicar_iva else 0.0, 2)
        total_final = round(subtotal_base + monto_iva, 2)
        return subtotal_base, monto_iva, total_final

    def emitir_factura(
        self,
        id_cliente: int,
        id_vendedor: int,
        items_raw: List[Dict[str, Any]],
        aplicar_iva: bool = True,
    ) -> Factura:
        """Valida cliente e ítems, arma la factura con sus totales y la persiste."""
        if isinstance(id_cliente, bool) or not isinstance(id_cliente, int) or id_cliente <= 0:
            raise ValueError("El ID de cliente debe ser un entero positivo.")
        if isinstance(id_vendedor, bool) or not isinstance(id_vendedor, int) or id_vendedor <= 0:
            raise ValueError("El ID de vendedor debe ser un entero positivo.")
        if not items_raw or not isinstance(items_raw, list):
            raise ValueError("Debe proporcionar al menos un ítem para emitir la factura.")

        cliente = self.repo.obtener_cliente_por_id(id_cliente)
        if not cliente:
            raise ValueError(f"El Cliente con ID #{id_cliente} no existe en el sistema.")

        detalles_entidad: List[DetalleFactura] = []
        for indice, item in enumerate(items_raw, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"El ítem #{indice} debe ser un diccionario válido.")

            try:
                id_producto = item["id_producto"]
                cantidad = item["cantidad"]
                precio_unitario = item["precio_unitario"]
            except KeyError as exc:
                raise ValueError(
                    f"Falta el campo obligatorio {exc} en el ítem #{indice}."
                ) from exc

            if isinstance(id_producto, bool) or not isinstance(id_producto, int) or id_producto <= 0:
                raise ValueError(f"El 'id_producto' del ítem #{indice} debe ser un entero positivo.")

            descuento_porc = item.get("descuento", 0.0)
            subtotal_item = self.calcular_renglon(cantidad, precio_unitario, descuento_porc)

            det = DetalleFactura(
                id_producto=id_producto,
                cantidad=cantidad,
                precio_unitario=round(float(precio_unitario), 2),
                descuento_porcentaje=round(float(descuento_porc), 2),
                subtotal=subtotal_item,
            )
            detalles_entidad.append(det)

        subtotal_base, monto_iva, total_final = self.calcular_totales_factura(
            detalles_entidad,
            aplicar_iva=aplicar_iva,
        )

        factura = Factura(
            id_factura=None,
            cliente=cliente,
            id_vendedor=id_vendedor,
            subtotal_base=subtotal_base,
            monto_iva=monto_iva,
            total=total_final,
            detalles=detalles_entidad,
        )

        return self.repo.guardar_factura(factura)