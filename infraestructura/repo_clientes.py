"""
===============================================================================
REPOSITORIO DE CLIENTES (infraestructura/repo_clientes.py)
===============================================================================
Gestiona el CRUD de clientes (siempre Persona Física, Consumidor Final y CUIT)
vinculados a `personas` y el cálculo de cliente frecuente mensual.
===============================================================================
"""

import calendar
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import config
from dominio.entidades_clientes import (
    Cliente,
    es_cuit_persona_fisica_valido,
    limpiar_cuit,
)
from infraestructura.conexion import ConexionDB


def _a_int(valor: Any, por_defecto: int = 0) -> int:
    if valor is None:
        return por_defecto
    return int(valor)


class RepositorioClientes:
    """Acceso a datos exclusivo del padrón de clientes."""

    @staticmethod
    def _rango_mes(periodo: str) -> Tuple[str, str]:
        partes = (periodo or "").strip().split("-")
        if len(partes) != 2 or len(partes[0]) != 4 or len(partes[1]) != 2:
            raise ValueError(
                f"Período inválido '{periodo}'. Se espera formato 'YYYY-MM'."
            )
        anio = int(partes[0])
        mes = int(partes[1])
        if not (1 <= mes <= 12):
            raise ValueError(
                f"Mes fuera de rango en período '{periodo}': debe estar entre 01 y 12."
            )
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return (
            f"{anio:04d}-{mes:02d}-01 00:00:00",
            f"{anio:04d}-{mes:02d}-{ultimo_dia:02d} 23:59:59",
        )

    @classmethod
    def listar_clientes(
        cls,
        criterio_busqueda: str = "",
        incluir_inactivos: bool = False,
        periodo: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
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
                     p.nro_documento, p.nombres, p.apellidos,
                     p.telefono, p.email, p.domicilio, p.ciudad, p.provincia,
                     p.codigo_postal
            ORDER BY COALESCE(p.apellidos, ''), COALESCE(p.nombres, ''), c.id DESC
        """

        with ConexionDB() as conn:
            filas = conn.execute(sql, params).fetchall()

        resultado: List[Dict[str, Any]] = []
        for f in filas:
            compras = _a_int(f["compras_mes"])
            cliente = Cliente(
                id_cliente=_a_int(f["id_cliente"]),
                id_persona=_a_int(f["id_persona"]),
                cuit=f["nro_documento"] or "",
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
                    "es_frecuente": compras >= min_frecuente,
                }
            )
        return resultado

    @classmethod
    def guardar_cliente(cls, cliente: Cliente) -> bool:
        cuit_limpio = limpiar_cuit(cliente.cuit)
        if not es_cuit_persona_fisica_valido(cuit_limpio):
            raise ValueError(
                "El CUIT del cliente debe tener 11 dígitos y corresponder a "
                "Persona Física (prefijos configurados, ej. 20 o 27)."
            )
        if not (cliente.apellidos or "").strip() or not (cliente.nombres or "").strip():
            raise ValueError("Debe ingresar apellido y nombre del cliente.")

        with ConexionDB() as conn:
            if cliente.id_cliente is None:
                fila_persona = conn.execute(
                    "SELECT id FROM personas WHERE nro_documento = ?",
                    (cuit_limpio,),
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
                            tipo_documento = 'CUIT',
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
                            cliente.telefono.strip() or None,
                            cliente.email.strip() or None,
                            cliente.domicilio.strip() or None,
                            cliente.ciudad.strip() or None,
                            cliente.provincia.strip() or None,
                            cliente.codigo_postal.strip() or None,
                            id_persona,
                        ),
                    )
                    fila_cli = conn.execute(
                        "SELECT id FROM clientes WHERE id_persona = ?",
                        (id_persona,),
                    ).fetchone()
                    if fila_cli:
                        id_cli = _a_int(fila_cli["id"])
                        conn.execute(
                            "UPDATE clientes SET activo = ? WHERE id = ?",
                            (1 if cliente.activo else 0, id_cli),
                        )
                        cliente.id_cliente = id_cli
                        cliente.id_persona = id_persona
                        cliente.cuit = cuit_limpio
                        return True
                else:
                    cur_p = conn.execute(
                        """
                        INSERT INTO personas (
                            tipo_persona, nombres, apellidos, razon_social,
                            tipo_documento, nro_documento, telefono, email,
                            domicilio, ciudad, provincia, codigo_postal
                        )
                        VALUES ('Fisica', ?, ?, NULL, 'CUIT', ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cliente.nombres.strip(),
                            cliente.apellidos.strip(),
                            cuit_limpio,
                            cliente.telefono.strip() or None,
                            cliente.email.strip() or None,
                            cliente.domicilio.strip() or None,
                            cliente.ciudad.strip() or None,
                            cliente.provincia.strip() or None,
                            cliente.codigo_postal.strip() or None,
                        ),
                    )
                    if cur_p.lastrowid is None:
                        raise RuntimeError("No se pudo crear el registro en personas.")
                    id_persona = _a_int(cur_p.lastrowid)

                cur_c = conn.execute(
                    "INSERT INTO clientes (id_persona, activo) VALUES (?, ?)",
                    (id_persona, 1 if cliente.activo else 0),
                )
                if cur_c.lastrowid is None:
                    raise RuntimeError("No se pudo crear el registro en clientes.")
                cliente.id_cliente = _a_int(cur_c.lastrowid)
                cliente.id_persona = id_persona
                cliente.cuit = cuit_limpio
            else:
                fila_cli = conn.execute(
                    "SELECT id_persona FROM clientes WHERE id = ?",
                    (cliente.id_cliente,),
                ).fetchone()
                if not fila_cli:
                    raise ValueError("El cliente seleccionado no existe.")
                id_persona = _a_int(fila_cli["id_persona"])

                conn.execute(
                    """
                    UPDATE personas
                    SET tipo_persona = 'Fisica',
                        nombres = ?,
                        apellidos = ?,
                        razon_social = NULL,
                        tipo_documento = 'CUIT',
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
                        cuit_limpio,
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
                cliente.cuit = cuit_limpio

        return True

    @classmethod
    def cambiar_estado_cliente(cls, id_cliente: int, activo: bool) -> bool:
        with ConexionDB() as conn:
            cur = conn.execute(
                "UPDATE clientes SET activo = ? WHERE id = ?",
                (1 if activo else 0, id_cliente),
            )
            return cur.rowcount > 0