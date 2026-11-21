"""
===============================================================================
REPOSITORIO DE VENTAS Y CLIENTES (repo_ventas.py)
===============================================================================
Gestiona el CRUD de clientes (personas físicas), consulta de productos y
vendedores activos, emisión de facturas con sincronización de stock y cálculo
de clientes frecuentes, comisiones y bono por mejor vendedor del mes.
===============================================================================
"""

import calendar
from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Tuple

import config
from dominio.entidades_ventas import (
    Cliente,
    DetalleFactura,
    Factura,
    es_documento_persona_fisica_valido,
    limpiar_documento,
)
from infraestructura.conexion import ConexionDB


def _a_int(valor: Any, por_defecto: int = 0) -> int:
    """Convierte un valor a int de forma segura para linters y datos SQLite."""
    if valor is None:
        return por_defecto
    return int(valor)


def _a_float(valor: Any, por_defecto: float = 0.0) -> float:
    """Convierte un valor a float de forma segura para linters y datos SQLite."""
    if valor is None:
        return por_defecto
    return float(valor)


def _tabla_tiene_columna(conn: sqlite3.Connection, tabla: str, columna: str) -> bool:
    """Verifica de forma segura si una tabla SQLite contiene una columna."""
    filas = conn.execute(f"PRAGMA table_info({tabla})").fetchall()
    return any(str(fila["name"]).lower() == columna.lower() for fila in filas)


class RepositorioVentas:
    """Acceso a datos para clientes, facturación y métricas comerciales."""

    @staticmethod
    def _rango_mes(periodo: str) -> Tuple[str, str]:
        """
        Recibe 'YYYY-MM' (ej. '2026-11') y devuelve (fecha_inicio, fecha_fin)
        considerando la cantidad real de días del mes (28, 29, 30 o 31).
        """
        partes = (periodo or "").strip().split("-")
        if len(partes) != 2 or len(partes[0]) != 4 or len(partes[1]) != 2:
            raise ValueError(
                f"Período inválido '{periodo}'. Se espera formato 'YYYY-MM'."
            )
        try:
            anio = int(partes[0])
            mes = int(partes[1])
        except ValueError as exc:
            raise ValueError(
                f"Período inválido '{periodo}'. Año y mes deben ser numéricos."
            ) from exc

        if not (1 <= mes <= 12):
            raise ValueError(
                f"Mes fuera de rango en período '{periodo}': debe estar entre 01 y 12."
            )

        ultimo_dia = calendar.monthrange(anio, mes)[1]
        inicio = f"{anio:04d}-{mes:02d}-01 00:00:00"
        fin = f"{anio:04d}-{mes:02d}-{ultimo_dia:02d} 23:59:59"
        return inicio, fin

    @staticmethod
    def obtener_descuento_cantidad(cantidad: int) -> float:
        """Devuelve la proporción de descuento según cantidad usando un diccionario."""
        if cantidad <= 0:
            return 0.0
        tramos: Dict[int, float] = getattr(
            config, "TRAMOS_DESCUENTO_CANTIDAD", {10: 0.10, 5: 0.05}
        )
        for minimo in sorted(tramos.keys(), reverse=True):
            if cantidad >= _a_int(minimo):
                return _a_float(tramos[minimo])
        return 0.0

    @staticmethod
    def calcular_previsualizacion_factura(
        items_crudos: List[Dict[str, Any]],
        condicion_venta: str,
    ) -> Dict[str, Any]:
        """
        Calcula renglones y totales de la factura en formato decimal:
        - Descuento por cantidad sobre precio de lista
        - Ajuste por condición de venta (positivo = descuento, negativo = recargo)
        - Impuesto provincial sobre precio de lista
        - IVA sobre base imponible neta
        """
        iva_tasa = _a_float(getattr(config, "IVA_POR_DEFECTO", 0.21), 0.21)
        prov_tasa = _a_float(getattr(config, "IMPUESTO_PROVINCIAL_PORC", 0.03), 0.03)
        condiciones_map = getattr(config, "CONDICIONES_VENTA_PORC", {})

        detalles_calculados: List[DetalleFactura] = []
        base_bruta = 0.0
        descuento_cantidad_total = 0.0
        impuesto_prov_total = 0.0

        for item in items_crudos:
            cant = _a_int(item.get("cantidad"))
            precio_lista = _a_float(item.get("precio_lista"))
            if cant <= 0:
                raise ValueError(
                    f"La cantidad del producto '{item.get('descripcion', '')}' debe ser mayor a 0."
                )
            if precio_lista < 0.0:
                raise ValueError(
                    f"El precio de lista del producto '{item.get('descripcion', '')}' no puede ser negativo."
                )

            bruto_linea = cant * precio_lista
            pct_cant = RepositorioVentas.obtener_descuento_cantidad(cant)
            desc_cant_monto = bruto_linea * pct_cant
            neto_linea = bruto_linea - desc_cant_monto
            imp_prov_linea = bruto_linea * prov_tasa

            base_bruta += bruto_linea
            descuento_cantidad_total += desc_cant_monto
            impuesto_prov_total += imp_prov_linea

            detalles_calculados.append(
                DetalleFactura(
                    id_producto=_a_int(item.get("id_producto")),
                    codigo_producto=str(item.get("codigo", "")),
                    descripcion_producto=str(item.get("descripcion", "")),
                    cantidad=cant,
                    precio_lista=precio_lista,
                    descuento_cantidad_pct=pct_cant,
                    subtotal_neto=round(neto_linea, 2),
                    impuesto_provincial=round(imp_prov_linea, 2),
                )
            )

        subtotal_tras_cantidad = base_bruta - descuento_cantidad_total
        tasa_condicion = _a_float(condiciones_map.get(condicion_venta, 0.0), 0.0)
        ajuste_condicion = subtotal_tras_cantidad * tasa_condicion
        base_imponible = max(0.0, subtotal_tras_cantidad - ajuste_condicion)

        iva_total = base_imponible * iva_tasa
        total_final = base_imponible + impuesto_prov_total + iva_total

        for det in detalles_calculados:
            proporcion = (
                (det.subtotal_neto / subtotal_tras_cantidad)
                if subtotal_tras_cantidad > 0
                else 0.0
            )
            iva_linea = iva_total * proporcion
            det.iva = round(iva_linea, 2)
            det.subtotal_final = round(
                det.subtotal_neto + det.impuesto_provincial + det.iva, 2
            )

        return {
            "detalles": detalles_calculados,
            "subtotal_items": round(subtotal_tras_cantidad, 2),
            "ajuste_condicion_monto": round(ajuste_condicion, 2),
            "impuesto_provincial_total": round(impuesto_prov_total, 2),
            "iva_total": round(iva_total, 2),
            "total": round(total_final, 2),
        }

    # -------------------------------------------------------------------------
    # CRUD DE CLIENTES (Solo Persona Física)
    # -------------------------------------------------------------------------
    @classmethod
    def listar_clientes(
        cls,
        criterio_busqueda: str = "",
        incluir_inactivos: bool = False,
        periodo: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Lista clientes (personas físicas) con estado de cliente frecuente
        (>= MINIMO_COMPRAS_CLIENTE_FRECUENTE compras en el mes indicado).
        """
        periodo_ref = periodo or datetime.now().strftime("%Y-%m")
        inicio_mes, fin_mes = cls._rango_mes(periodo_ref)
        min_frecuente = _a_int(
            getattr(config, "MINIMO_COMPRAS_CLIENTE_FRECUENTE", 3), 3
        )

        sql = """
            SELECT
                c.id AS id_cliente,
                c.id_persona,
                c.fecha_alta,
                COALESCE(c.activo, 1) AS activo,
                p.tipo_documento,
                p.nro_documento,
                p.nombres,
                p.apellidos,
                p.telefono,
                p.email,
                p.domicilio,
                p.ciudad,
                p.provincia,
                p.codigo_postal,
                COUNT(f.id) AS compras_mes
            FROM clientes c
            JOIN personas p ON p.id = c.id_persona
            LEFT JOIN facturas f
                ON f.id_cliente = c.id
               AND f.fecha >= ?
               AND f.fecha <= ?
            WHERE p.tipo_persona = 'Fisica'
        """
        params: List[Any] = [inicio_mes, fin_mes]

        if not incluir_inactivos:
            sql += " AND COALESCE(c.activo, 1) = 1"

        criterio = (criterio_busqueda or "").strip()
        if criterio:
            like = f"%{criterio}%"
            sql += """
                AND (
                    p.nro_documento LIKE ?
                    OR COALESCE(p.nombres, '') LIKE ?
                    OR COALESCE(p.apellidos, '') LIKE ?
                    OR COALESCE(p.email, '') LIKE ?
                    OR COALESCE(p.telefono, '') LIKE ?
                )
            """
            params.extend([like, like, like, like, like])

        sql += """
            GROUP BY c.id, c.id_persona, c.fecha_alta, c.activo,
                     p.tipo_documento, p.nro_documento, p.nombres, p.apellidos,
                     p.telefono, p.email, p.domicilio, p.ciudad, p.provincia,
                     p.codigo_postal
            ORDER BY COALESCE(p.apellidos, ''), COALESCE(p.nombres, ''), c.id DESC
        """

        with ConexionDB() as conn:
            filas = conn.execute(sql, params).fetchall()

        resultado: List[Dict[str, Any]] = []
        for f in filas:
            compras = _a_int(f["compras_mes"])
            es_frecuente = compras >= min_frecuente
            cliente = Cliente(
                id_cliente=_a_int(f["id_cliente"]),
                id_persona=_a_int(f["id_persona"]),
                tipo_documento=f["tipo_documento"] or "CUIL",
                nro_documento=f["nro_documento"] or "",
                nombres=f["nombres"] or "",
                apellidos=f["apellidos"] or "",
                telefono=f["telefono"] or "",
                email=f["email"] or "",
                domicilio=f["domicilio"] or "",
                ciudad=f["ciudad"] or "",
                provincia=f["provincia"] or "",
                codigo_postal=f["codigo_postal"] or "",
                fecha_alta=str(f["fecha_alta"] or ""),
                activo=bool(_a_int(f["activo"], 1)),
            )
            resultado.append(
                {
                    "cliente": cliente,
                    "compras_mes": compras,
                    "es_frecuente": es_frecuente,
                }
            )
        return resultado

    @classmethod
    def guardar_cliente(cls, cliente: Cliente) -> bool:
        """Crea o actualiza un cliente de persona física de forma atómica."""
        doc_limpio = limpiar_documento(cliente.nro_documento)
        if not es_documento_persona_fisica_valido(doc_limpio):
            raise ValueError(
                "El documento de cliente debe corresponder a Persona Física "
                "(prefijo 20 o 27 en CUIL/CUIT, o DNI válido)."
            )

        tipo_doc = (cliente.tipo_documento or "").strip().upper()
        if tipo_doc not in ("DNI", "CUIT", "CUIL", "PASAPORTE"):
            tipo_doc = "CUIL" if len(doc_limpio) == 11 else "DNI"

        with ConexionDB() as conn:
            if cliente.id_cliente is None:
                fila_persona = conn.execute(
                    "SELECT id FROM personas WHERE nro_documento = ?",
                    (doc_limpio,),
                ).fetchone()

                if fila_persona:
                    id_persona = _a_int(fila_persona["id"])
                    conn.execute(
                        """
                        UPDATE personas
                        SET tipo_persona = 'Fisica',
                            nombres = ?,
                            apellidos = ?,
                            razon_social = NULL,
                            tipo_documento = ?,
                            telefono = ?,
                            email = ?,
                            domicilio = ?,
                            ciudad = ?,
                            provincia = ?,
                            codigo_postal = ?
                        WHERE id = ?
                        """,
                        (
                            cliente.nombres.strip(),
                            cliente.apellidos.strip(),
                            tipo_doc,
                            cliente.telefono.strip() or None,
                            cliente.email.strip() or None,
                            cliente.domicilio.strip() or None,
                            cliente.ciudad.strip() or None,
                            cliente.provincia.strip() or None,
                            cliente.codigo_postal.strip() or None,
                            id_persona,
                        ),
                    )
                else:
                    cur_p = conn.execute(
                        """
                        INSERT INTO personas (
                            tipo_persona, nombres, apellidos, razon_social,
                            tipo_documento, nro_documento, telefono, email,
                            domicilio, ciudad, provincia, codigo_postal
                        )
                        VALUES ('Fisica', ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cliente.nombres.strip(),
                            cliente.apellidos.strip(),
                            tipo_doc,
                            doc_limpio,
                            cliente.telefono.strip() or None,
                            cliente.email.strip() or None,
                            cliente.domicilio.strip() or None,
                            cliente.ciudad.strip() or None,
                            cliente.provincia.strip() or None,
                            cliente.codigo_postal.strip() or None,
                        ),
                    )
                    nuevo_persona_id = cur_p.lastrowid
                    if nuevo_persona_id is None:
                        raise RuntimeError("No se pudo obtener el ID de persona creada.")
                    id_persona = _a_int(nuevo_persona_id)

                cur_c = conn.execute(
                    """
                    INSERT INTO clientes (id_persona, activo)
                    VALUES (?, ?)
                    """,
                    (id_persona, 1 if cliente.activo else 0),
                )
                nuevo_cliente_id = cur_c.lastrowid
                if nuevo_cliente_id is None:
                    raise RuntimeError("No se pudo obtener el ID de cliente creado.")
                cliente.id_cliente = _a_int(nuevo_cliente_id)
                cliente.id_persona = id_persona
            else:
                fila_cli = conn.execute(
                    "SELECT id_persona FROM clientes WHERE id = ?",
                    (cliente.id_cliente,),
                ).fetchone()
                if not fila_cli:
                    raise ValueError(
                        "El cliente seleccionado no existe en la base de datos."
                    )
                id_persona = _a_int(fila_cli["id_persona"])

                conn.execute(
                    """
                    UPDATE personas
                    SET tipo_persona = 'Fisica',
                        nombres = ?,
                        apellidos = ?,
                        razon_social = NULL,
                        tipo_documento = ?,
                        nro_documento = ?,
                        telefono = ?,
                        email = ?,
                        domicilio = ?,
                        ciudad = ?,
                        provincia = ?,
                        codigo_postal = ?
                    WHERE id = ?
                    """,
                    (
                        cliente.nombres.strip(),
                        cliente.apellidos.strip(),
                        tipo_doc,
                        doc_limpio,
                        cliente.telefono.strip() or None,
                        cliente.email.strip() or None,
                        cliente.domicilio.strip() or None,
                        cliente.ciudad.strip() or None,
                        cliente.provincia.strip() or None,
                        cliente.codigo_postal.strip() or None,
                        id_persona,
                    ),
                )
                conn.execute(
                    "UPDATE clientes SET activo = ? WHERE id = ?",
                    (1 if cliente.activo else 0, cliente.id_cliente),
                )
                cliente.id_persona = id_persona

        return True

    @classmethod
    def cambiar_estado_cliente(cls, id_cliente: int, activo: bool) -> bool:
        """Activa o deshabilita lógicamente un cliente."""
        with ConexionDB() as conn:
            cur = conn.execute(
                "UPDATE clientes SET activo = ? WHERE id = ?",
                (1 if activo else 0, id_cliente),
            )
            return cur.rowcount > 0

    # -------------------------------------------------------------------------
    # VENDEDORES ACTIVOS Y PRODUCTOS DISPONIBLES
    # -------------------------------------------------------------------------
    @classmethod
    def listar_vendedores_activos(cls) -> List[Dict[str, Any]]:
        """Devuelve únicamente empleados activos (para seleccionar vendedor)."""
        with ConexionDB() as conn:
            filas = conn.execute(
                """
                SELECT
                    e.id AS id_empleado,
                    e.legajo,
                    e.cargo,
                    COALESCE(p.apellidos, '') || ', ' || COALESCE(p.nombres, '') AS nombre_completo
                FROM empleados e
                JOIN personas p ON p.id = e.id_persona
                WHERE COALESCE(e.activo, 1) = 1
                ORDER BY e.legajo ASC
                """
            ).fetchall()
        return [dict(f) for f in filas]

    @classmethod
    def listar_productos_venta(cls, criterio: str = "") -> List[Dict[str, Any]]:
        """Lista productos disponibles con stock y precio de venta."""
        with ConexionDB() as conn:
            tiene_activo = _tabla_tiene_columna(conn, "productos", "activo")
            sql = """
                SELECT
                    id,
                    codigo,
                    descripcion,
                    categoria,
                    stock_actual,
                    stock_minimo,
                    precio_venta
                FROM productos
                WHERE 1 = 1
            """
            if tiene_activo:
                sql += " AND COALESCE(activo, 1) = 1"

            params: List[Any] = []
            txt = (criterio or "").strip()
            if txt:
                like = f"%{txt}%"
                sql += (
                    " AND (codigo LIKE ? OR descripcion LIKE ? "
                    "OR COALESCE(categoria, '') LIKE ?)"
                )
                params.extend([like, like, like])
            sql += " ORDER BY descripcion ASC"

            filas = conn.execute(sql, params).fetchall()
        return [dict(f) for f in filas]

    # -------------------------------------------------------------------------
    # EMISIÓN DE FACTURA Y ACTUALIZACIÓN DE STOCK
    # -------------------------------------------------------------------------
    @classmethod
    def emitir_factura(
        cls,
        id_cliente: int,
        id_vendedor: int,
        condicion_venta: str,
        items_crudos: List[Dict[str, Any]],
    ) -> Factura:
        """
        Registra cabecera (`facturas`) y renglones (`facturas_detalles`) en una
        sola transacción, validando cliente/vendedor activos, consolidando stock
        por producto y respetando los triggers de SQLite.
        """
        if not items_crudos:
            raise ValueError("Debe agregar al menos un producto a la factura.")

        calculo = cls.calcular_previsualizacion_factura(items_crudos, condicion_venta)
        detalles: List[DetalleFactura] = calculo["detalles"]
        total_factura = _a_float(calculo["total"])

        cantidad_por_producto: Dict[int, int] = {}
        for det in detalles:
            cantidad_por_producto[det.id_producto] = (
                cantidad_por_producto.get(det.id_producto, 0) + det.cantidad
            )

        with ConexionDB() as conn:
            fila_cliente = conn.execute(
                """
                SELECT
                    c.id,
                    COALESCE(c.activo, 1) AS activo,
                    COALESCE(p.nro_documento, '') AS nro_documento,
                    COALESCE(p.apellidos, '') AS apellidos,
                    COALESCE(p.nombres, '') AS nombres
                FROM clientes c
                JOIN personas p ON p.id = c.id_persona
                WHERE c.id = ?
                """,
                (id_cliente,),
            ).fetchone()
            if not fila_cliente:
                raise ValueError(f"Cliente ID {id_cliente} no encontrado.")
            if _a_int(fila_cliente["activo"], 1) != 1:
                raise ValueError(f"El cliente ID {id_cliente} está inactivo.")

            apellidos_cli = str(fila_cliente["apellidos"] or "").strip()
            nombres_cli = str(fila_cliente["nombres"] or "").strip()
            if apellidos_cli and nombres_cli:
                cliente_nombre = f"{apellidos_cli}, {nombres_cli}"
            else:
                cliente_nombre = apellidos_cli or nombres_cli or f"Cliente #{id_cliente}"
            cliente_documento = str(fila_cliente["nro_documento"] or "").strip()

            fila_vendedor = conn.execute(
                """
                SELECT
                    e.id,
                    COALESCE(e.activo, 1) AS activo,
                    COALESCE(p.apellidos, '') AS apellidos,
                    COALESCE(p.nombres, '') AS nombres
                FROM empleados e
                JOIN personas p ON p.id = e.id_persona
                WHERE e.id = ?
                """,
                (id_vendedor,),
            ).fetchone()
            if not fila_vendedor:
                raise ValueError(f"Vendedor ID {id_vendedor} no encontrado.")
            if _a_int(fila_vendedor["activo"], 1) != 1:
                raise ValueError(f"El vendedor ID {id_vendedor} está inactivo.")

            apellidos_vend = str(fila_vendedor["apellidos"] or "").strip()
            nombres_vend = str(fila_vendedor["nombres"] or "").strip()
            if apellidos_vend and nombres_vend:
                vendedor_nombre = f"{apellidos_vend}, {nombres_vend}"
            else:
                vendedor_nombre = apellidos_vend or nombres_vend or f"Vendedor #{id_vendedor}"

            for id_prod, cant_total_req in cantidad_por_producto.items():
                fila_prod = conn.execute(
                    "SELECT stock_actual, descripcion FROM productos WHERE id = ?",
                    (id_prod,),
                ).fetchone()
                if not fila_prod:
                    raise ValueError(f"Producto ID {id_prod} no encontrado.")
                stock_disp = _a_int(fila_prod["stock_actual"])
                if stock_disp < cant_total_req:
                    raise ValueError(
                        f"Stock insuficiente para '{fila_prod['descripcion']}': "
                        f"disponible {stock_disp}, solicitado {cant_total_req}."
                    )

            cur_f = conn.execute(
                """
                INSERT INTO facturas (id_cliente, id_vendedor, total)
                VALUES (?, ?, ?)
                """,
                (id_cliente, id_vendedor, total_factura),
            )
            nueva_factura_id = cur_f.lastrowid
            if nueva_factura_id is None:
                raise RuntimeError("No se pudo generar el ID de la factura.")
            id_factura = _a_int(nueva_factura_id)

            for det in detalles:
                conn.execute(
                    """
                    INSERT INTO facturas_detalles (
                        id_factura, id_producto, cantidad, precio_unitario,
                        descuento_porcentaje, subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        id_factura,
                        det.id_producto,
                        det.cantidad,
                        det.precio_lista,
                        det.descuento_cantidad_pct * 100.0,
                        det.subtotal_final,
                    ),
                )

            fila_tot = conn.execute(
                "SELECT total, fecha FROM facturas WHERE id = ?", (id_factura,)
            ).fetchone()
            total_db = _a_float(fila_tot["total"], 0.0) if fila_tot else 0.0
            total_persistido = total_db if total_db > 0 else total_factura
            conn.execute(
                "UPDATE facturas SET total = ? WHERE id = ?",
                (total_persistido, id_factura),
            )

        return Factura(
            id_factura=id_factura,
            id_cliente=id_cliente,
            id_vendedor=id_vendedor,
            condicion_venta=condicion_venta,
            fecha=(
                str(fila_tot["fecha"])
                if fila_tot and fila_tot["fecha"]
                else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
            cliente_nombre=cliente_nombre,
            cliente_documento=cliente_documento,
            vendedor_nombre=vendedor_nombre,
            subtotal_items=_a_float(calculo["subtotal_items"]),
            ajuste_condicion_monto=_a_float(calculo["ajuste_condicion_monto"]),
            impuesto_provincial_total=_a_float(calculo["impuesto_provincial_total"]),
            iva_total=_a_float(calculo["iva_total"]),
            total=round(total_persistido, 2),
            detalles=detalles,
        )

    # -------------------------------------------------------------------------
    # COMISIONES Y BONO POR MEJOR VENDEDOR DEL MES
    # -------------------------------------------------------------------------
    @classmethod
    def calcular_comisiones_periodo(cls, periodo: str) -> Dict[int, Dict[str, float]]:
        """
        Calcula por `id_empleado` para el mes indicado ('YYYY-MM') del día 1
        al último día calendario del mes:
        - `ventas_mes`: total facturado en el período
        - `comision_monto`: comisión porcentual sobre ventas del vendedor
        - `bono_mejor_vendedor`: bono porcentual extra si es el de mayor venta
        - `total_adicional_ventas`: suma de comisión + bono
        """
        tasa_comision = _a_float(getattr(config, "COMISION_VENDEDOR_PORC", 0.05), 0.05)
        tasa_bono = _a_float(getattr(config, "BONO_MEJOR_VENDEDOR_PORC", 0.03), 0.03)

        inicio, fin = cls._rango_mes(periodo)
        with ConexionDB() as conn:
            filas = conn.execute(
                """
                SELECT
                    e.id AS id_empleado,
                    COALESCE(SUM(f.total), 0.0) AS ventas_mes
                FROM empleados e
                LEFT JOIN facturas f
                    ON f.id_vendedor = e.id
                   AND f.fecha >= ?
                   AND f.fecha <= ?
                WHERE COALESCE(e.activo, 1) = 1
                GROUP BY e.id
                """,
                (inicio, fin),
            ).fetchall()

        ventas_por_emp = {
            _a_int(f["id_empleado"]): _a_float(f["ventas_mes"]) for f in filas
        }
        max_venta = max(ventas_por_emp.values(), default=0.0)

        resultado: Dict[int, Dict[str, float]] = {}
        for id_emp, monto_ventas in ventas_por_emp.items():
            comision = monto_ventas * tasa_comision
            es_mejor = monto_ventas > 0 and abs(monto_ventas - max_venta) < 1e-6
            bono = (monto_ventas * tasa_bono) if es_mejor else 0.0
            resultado[id_emp] = {
                "ventas_mes": round(monto_ventas, 2),
                "comision_monto": round(comision, 2),
                "bono_mejor_vendedor": round(bono, 2),
                "total_adicional_ventas": round(comision + bono, 2),
            }
        return resultado