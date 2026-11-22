"""
===============================================================================
REPOSITORIO DE STOCK E INVENTARIO (infraestructura/repo_stock.py)
===============================================================================
Gestiona el catálogo de productos del inventario y las operaciones de stock:
- Listado con filtros (búsqueda, categoría, stock bajo, incluir inactivos).
- Alta y edición segura de productos contra `productos` (`esquema.sql`).
- Ajuste de existencias y baja/reactivación lógica (`activo`).
- Consulta de proveedores activos para emisión de órdenes de compra.
===============================================================================
"""

from typing import Any, Dict, List, Optional

from dominio.entidades_stock import Producto, calcular_precio_venta_sugerido
from infraestructura.conexion import ConexionDB


def _a_int(valor: Any, por_defecto: int = 0) -> int:
    if valor is None:
        return por_defecto
    return int(valor)


def _a_float(valor: Any, por_defecto: float = 0.0) -> float:
    if valor is None:
        return por_defecto
    return float(valor)


class RepositorioStock:
    """Acceso a datos para el inventario de productos y control de stock."""

    @classmethod
    def listar_productos(
        cls,
        criterio_busqueda: str = "",
        categoria_filtro: str = "",
        solo_stock_bajo: bool = False,
        incluir_inactivos: bool = False,
    ) -> List[Producto]:
        sql = """
            SELECT
                pr.id AS id_producto,
                pr.codigo,
                pr.descripcion,
                COALESCE(pr.categoria, '') AS categoria,
                pr.id_proveedor,
                pr.stock_actual,
                pr.stock_minimo,
                pr.precio_costo,
                pr.precio_venta,
                COALESCE(pr.ubicacion, '') AS ubicacion,
                COALESCE(pr.vencimiento, '') AS vencimiento,
                COALESCE(pr.activo, 1) AS activo,
                COALESCE(p.razon_social, '') AS proveedor_nombre
            FROM productos pr
            LEFT JOIN proveedores pv ON pv.id = pr.id_proveedor
            LEFT JOIN personas p ON p.id = pv.id_persona
            WHERE 1 = 1
        """
        params: List[Any] = []

        if not incluir_inactivos:
            sql += " AND COALESCE(pr.activo, 1) = 1"

        categoria_limpia = (categoria_filtro or "").strip()
        if categoria_limpia and categoria_limpia.lower() != "todas":
            sql += " AND COALESCE(pr.categoria, '') = ?"
            params.append(categoria_limpia)

        if solo_stock_bajo:
            sql += " AND pr.stock_actual <= pr.stock_minimo"

        criterio = (criterio_busqueda or "").strip()
        if criterio:
            like = f"%{criterio}%"
            sql += """
                AND (
                    pr.codigo LIKE ?
                    OR pr.descripcion LIKE ?
                    OR COALESCE(pr.categoria, '') LIKE ?
                    OR COALESCE(pr.ubicacion, '') LIKE ?
                    OR COALESCE(p.razon_social, '') LIKE ?
                )
            """
            params.extend([like, like, like, like, like])

        sql += " ORDER BY pr.descripcion ASC, pr.id DESC"

        with ConexionDB() as conn:
            filas = conn.execute(sql, params).fetchall()

        productos: List[Producto] = []
        for f in filas:
            costo = _a_float(f["precio_costo"], 0.0)
            venta_raw = _a_float(f["precio_venta"], 0.0)
            venta = (
                venta_raw
                if venta_raw > 0.0
                else calcular_precio_venta_sugerido(costo)
            )
            productos.append(
                Producto(
                    id_producto=_a_int(f["id_producto"]),
                    codigo=f["codigo"] or "",
                    descripcion=f["descripcion"] or "",
                    categoria=f["categoria"] or "",
                    id_proveedor=_a_int(f["id_proveedor"]),
                    stock_actual=_a_int(f["stock_actual"], 0),
                    stock_minimo=_a_int(f["stock_minimo"], 75),
                    precio_costo=costo,
                    precio_venta=venta,
                    ubicacion=f["ubicacion"] or "",
                    vencimiento=f["vencimiento"] or "",
                    activo=bool(_a_int(f["activo"], 1)),
                    proveedor_nombre=f["proveedor_nombre"] or "",
                )
            )
        return productos

    @classmethod
    def listar_productos_stock_bajo(
        cls, incluir_inactivos: bool = False
    ) -> List[Producto]:
        """Devuelve los productos cuyo stock actual está en o por debajo del mínimo."""
        return cls.listar_productos(
            solo_stock_bajo=True, incluir_inactivos=incluir_inactivos
        )

    @classmethod
    def guardar_producto(cls, producto: Producto) -> bool:
        codigo = (producto.codigo or "").strip()
        descripcion = (producto.descripcion or "").strip()
        if not codigo:
            raise ValueError("Debe ingresar el código del producto.")
        if not descripcion:
            raise ValueError("Debe ingresar la descripción del producto.")
        if int(producto.id_proveedor) <= 0:
            raise ValueError("Debe seleccionar un proveedor válido.")

        stock_actual = int(producto.stock_actual)
        stock_minimo = int(producto.stock_minimo)
        precio_costo = float(producto.precio_costo)
        precio_venta = (
            float(producto.precio_venta)
            if producto.precio_venta is not None and float(producto.precio_venta) > 0
            else calcular_precio_venta_sugerido(precio_costo)
        )

        if stock_actual < 0:
            raise ValueError("El stock actual no puede ser negativo.")
        if stock_minimo < 0:
            raise ValueError("El stock mínimo no puede ser negativo.")
        if precio_costo < 0 or precio_venta < 0:
            raise ValueError("Los precios no pueden ser negativos.")

        categoria = (producto.categoria or "").strip() or None
        ubicacion = (producto.ubicacion or "").strip() or None
        vencimiento = (producto.vencimiento or "").strip() or None
        activo_int = 1 if producto.activo else 0

        with ConexionDB() as conn:
            prov_existe = conn.execute(
                "SELECT id FROM proveedores WHERE id = ?",
                (int(producto.id_proveedor),),
            ).fetchone()
            if not prov_existe:
                raise ValueError("El proveedor seleccionado no existe en la base de datos.")

            if producto.id_producto is None:
                duplicado = conn.execute(
                    "SELECT id FROM productos WHERE codigo = ?",
                    (codigo,),
                ).fetchone()
                if duplicado:
                    raise ValueError(f"Ya existe un producto con el código '{codigo}'.")

                cur = conn.execute(
                    """
                    INSERT INTO productos (
                        codigo, descripcion, categoria, id_proveedor,
                        stock_actual, stock_minimo, precio_costo, precio_venta,
                        ubicacion, vencimiento, activo
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        codigo,
                        descripcion,
                        categoria,
                        int(producto.id_proveedor),
                        stock_actual,
                        stock_minimo,
                        round(precio_costo, 2),
                        round(precio_venta, 2),
                        ubicacion,
                        vencimiento,
                        activo_int,
                    ),
                )
                if cur.lastrowid is None:
                    raise RuntimeError("No se pudo registrar el producto.")
                producto.id_producto = _a_int(cur.lastrowid)
            else:
                duplicado = conn.execute(
                    "SELECT id FROM productos WHERE codigo = ? AND id != ?",
                    (codigo, int(producto.id_producto)),
                ).fetchone()
                if duplicado:
                    raise ValueError(
                        f"Otro producto ya utiliza el código '{codigo}'."
                    )

                cur = conn.execute(
                    """
                    UPDATE productos
                    SET codigo = ?,
                        descripcion = ?,
                        categoria = ?,
                        id_proveedor = ?,
                        stock_actual = ?,
                        stock_minimo = ?,
                        precio_costo = ?,
                        precio_venta = ?,
                        ubicacion = ?,
                        vencimiento = ?,
                        activo = ?
                    WHERE id = ?
                    """,
                    (
                        codigo,
                        descripcion,
                        categoria,
                        int(producto.id_proveedor),
                        stock_actual,
                        stock_minimo,
                        round(precio_costo, 2),
                        round(precio_venta, 2),
                        ubicacion,
                        vencimiento,
                        activo_int,
                        int(producto.id_producto),
                    ),
                )
                if cur.rowcount == 0:
                    raise ValueError("El producto seleccionado no existe.")

        producto.codigo = codigo
        producto.descripcion = descripcion
        producto.categoria = categoria or ""
        producto.stock_actual = stock_actual
        producto.stock_minimo = stock_minimo
        producto.precio_costo = round(precio_costo, 2)
        producto.precio_venta = round(precio_venta, 2)
        producto.ubicacion = ubicacion or ""
        producto.vencimiento = vencimiento or ""
        return True

    @classmethod
    def ajustar_stock(cls, id_producto: int, delta_stock: int) -> int:
        """Ajusta el stock actual en `delta_stock` (positivo o negativo) de forma segura."""
        with ConexionDB() as conn:
            fila = conn.execute(
                "SELECT stock_actual FROM productos WHERE id = ?",
                (int(id_producto),),
            ).fetchone()
            if not fila:
                raise ValueError("El producto seleccionado no existe.")

            nuevo_stock = _a_int(fila["stock_actual"], 0) + int(delta_stock)
            if nuevo_stock < 0:
                raise ValueError(
                    "Stock insuficiente: el ajuste dejaría el stock actual por debajo de 0."
                )

            conn.execute(
                "UPDATE productos SET stock_actual = ? WHERE id = ?",
                (nuevo_stock, int(id_producto)),
            )
            return nuevo_stock

    @classmethod
    def cambiar_estado_producto(cls, id_producto: int, activo: bool) -> bool:
        """Activa o desactiva lógicamente un producto del inventario."""
        with ConexionDB() as conn:
            cur = conn.execute(
                "UPDATE productos SET activo = ? WHERE id = ?",
                (1 if activo else 0, int(id_producto)),
            )
            return cur.rowcount > 0

    @classmethod
    def listar_proveedores_activos(cls) -> List[Dict[str, Any]]:
        """Devuelve proveedores activos para seleccionar al emitir una orden de compra."""
        sql = """
            SELECT
                pv.id AS id_proveedor,
                COALESCE(p.razon_social, '') AS razon_social,
                COALESCE(p.nro_documento, '') AS cuit,
                COALESCE(pv.rubro, '') AS rubro,
                COALESCE(pv.contacto_secundario, '') AS contacto,
                COALESCE(p.telefono, '') AS telefono,
                COALESCE(p.email, '') AS email
            FROM proveedores pv
            JOIN personas p ON p.id = pv.id_persona
            WHERE COALESCE(pv.activo, 1) = 1
            ORDER BY COALESCE(p.razon_social, ''), pv.id ASC
        """
        with ConexionDB() as conn:
            filas = conn.execute(sql).fetchall()

        return [
            {
                "id_proveedor": _a_int(f["id_proveedor"]),
                "razon_social": f["razon_social"] or "",
                "cuit": f["cuit"] or "",
                "rubro": f["rubro"] or "",
                "contacto": f["contacto"] or "",
                "telefono": f["telefono"] or "",
                "email": f["email"] or "",
            }
            for f in filas
        ]

    @classmethod
    def listar_categorias(cls) -> List[str]:
        """Devuelve las categorías distintas registradas en productos."""
        sql = """
            SELECT DISTINCT TRIM(categoria) AS cat
            FROM productos
            WHERE categoria IS NOT NULL AND TRIM(categoria) != ''
            ORDER BY cat ASC
        """
        with ConexionDB() as conn:
            filas = conn.execute(sql).fetchall()
        return [str(f["cat"]) for f in filas if f["cat"]]