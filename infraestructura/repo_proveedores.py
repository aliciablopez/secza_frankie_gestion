"""
===============================================================================
REPOSITORIO DE PROVEEDORES (infraestructura/repo_proveedores.py)
===============================================================================
Gestiona el CRUD de proveedores (siempre Persona Jurídica con CUIT prefijo 30,
rubro en Bijou/Accesorios/Marroquinería, contacto de referencia y estado
activo/inactivo), sin posición frente al IVA.
===============================================================================
"""

from typing import Any, List

from dominio.entidades_proveedores import (
    Proveedor,
    RUBROS_PROVEEDOR,
    es_cuit_proveedor_valido,
    limpiar_cuit,
    validar_rubro_proveedor,
)
from infraestructura.conexion import ConexionDB


def _a_int(valor: Any, por_defecto: int = 0) -> int:
    if valor is None:
        return por_defecto
    return int(valor)


class RepositorioProveedores:
    """Acceso a datos exclusivo del padrón de proveedores."""

    @classmethod
    def listar_proveedores(
        cls,
        criterio_busqueda: str = "",
        rubro_filtro: str = "",
        incluir_inactivos: bool = False,
    ) -> List[Proveedor]:
        sql = """
            SELECT
                pr.id AS id_proveedor,
                pr.id_persona,
                pr.rubro,
                COALESCE(pr.contacto_secundario, '') AS contacto,
                COALESCE(pr.activo, 1) AS activo,
                p.nro_documento,
                COALESCE(p.razon_social, '') AS razon_social,
                COALESCE(p.telefono, '') AS telefono,
                COALESCE(p.email, '') AS email,
                COALESCE(p.domicilio, '') AS domicilio
            FROM proveedores pr
            JOIN personas p ON p.id = pr.id_persona
            WHERE p.tipo_persona = 'Juridica'
        """
        params: List[Any] = []

        if not incluir_inactivos:
            sql += " AND COALESCE(pr.activo, 1) = 1"

        rubro_limpio = (rubro_filtro or "").strip()
        if rubro_limpio and rubro_limpio in RUBROS_PROVEEDOR:
            sql += " AND pr.rubro = ?"
            params.append(rubro_limpio)

        criterio = (criterio_busqueda or "").strip()
        if criterio:
            like = f"%{criterio}%"
            sql += """
                AND (
                    p.nro_documento LIKE ?
                    OR COALESCE(p.razon_social, '') LIKE ?
                    OR COALESCE(pr.rubro, '') LIKE ?
                    OR COALESCE(pr.contacto_secundario, '') LIKE ?
                    OR COALESCE(p.email, '') LIKE ?
                    OR COALESCE(p.telefono, '') LIKE ?
                )
            """
            params.extend([like, like, like, like, like, like])

        sql += " ORDER BY COALESCE(p.razon_social, ''), pr.id DESC"

        with ConexionDB() as conn:
            filas = conn.execute(sql, params).fetchall()

        proveedores: List[Proveedor] = []
        for f in filas:
            rubro_db = (f["rubro"] or "").strip()
            rubro_valido = (
                rubro_db if rubro_db in RUBROS_PROVEEDOR else RUBROS_PROVEEDOR[0]
            )
            proveedores.append(
                Proveedor(
                    id_proveedor=_a_int(f["id_proveedor"]),
                    id_persona=_a_int(f["id_persona"]),
                    cuit=f["nro_documento"] or "",
                    razon_social=f["razon_social"] or "",
                    rubro=rubro_valido,
                    contacto=f["contacto"] or "",
                    telefono=f["telefono"] or "",
                    email=f["email"] or "",
                    domicilio=f["domicilio"] or "",
                    activo=bool(_a_int(f["activo"], 1)),
                )
            )
        return proveedores

    @classmethod
    def guardar_proveedor(cls, proveedor: Proveedor) -> bool:
        cuit_limpio = limpiar_cuit(proveedor.cuit)
        if not es_cuit_proveedor_valido(cuit_limpio):
            raise ValueError(
                "El CUIT del proveedor debe tener 11 dígitos y comenzar con '30' "
                "(Persona Jurídica)."
            )

        razon_social = (proveedor.razon_social or "").strip()
        if not razon_social:
            raise ValueError("Debe ingresar la razón social del proveedor.")

        rubro = validar_rubro_proveedor(proveedor.rubro)
        contacto = (proveedor.contacto or "").strip()
        telefono = (proveedor.telefono or "").strip()
        email = (proveedor.email or "").strip()
        domicilio = (proveedor.domicilio or "").strip()

        with ConexionDB() as conn:
            if proveedor.id_proveedor is None:
                fila_persona = conn.execute(
                    "SELECT id FROM personas WHERE nro_documento = ?",
                    (cuit_limpio,),
                ).fetchone()

                if fila_persona:
                    id_persona = _a_int(fila_persona["id"])
                    conn.execute(
                        """
                        UPDATE personas
                        SET tipo_persona = 'Juridica',
                            nombres = NULL,
                            apellidos = NULL,
                            razon_social = ?,
                            tipo_documento = 'CUIT',
                            telefono = ?,
                            email = ?,
                            domicilio = ?
                        WHERE id = ?
                        """,
                        (
                            razon_social,
                            telefono or None,
                            email or None,
                            domicilio or None,
                            id_persona,
                        ),
                    )
                    fila_prov = conn.execute(
                        "SELECT id FROM proveedores WHERE id_persona = ?",
                        (id_persona,),
                    ).fetchone()
                    if fila_prov:
                        id_prov = _a_int(fila_prov["id"])
                        conn.execute(
                            """
                            UPDATE proveedores
                            SET rubro = ?,
                                contacto_secundario = ?,
                                activo = ?
                            WHERE id = ?
                            """,
                            (
                                rubro,
                                contacto or None,
                                1 if proveedor.activo else 0,
                                id_prov,
                            ),
                        )
                        proveedor.id_proveedor = id_prov
                        proveedor.id_persona = id_persona
                        proveedor.cuit = cuit_limpio
                        proveedor.razon_social = razon_social
                        proveedor.rubro = rubro
                        return True
                else:
                    cur_p = conn.execute(
                        """
                        INSERT INTO personas (
                            tipo_persona, nombres, apellidos, razon_social,
                            tipo_documento, nro_documento, telefono, email, domicilio
                        )
                        VALUES ('Juridica', NULL, NULL, ?, 'CUIT', ?, ?, ?, ?)
                        """,
                        (
                            razon_social,
                            cuit_limpio,
                            telefono or None,
                            email or None,
                            domicilio or None,
                        ),
                    )
                    if cur_p.lastrowid is None:
                        raise RuntimeError("No se pudo crear el registro en personas.")
                    id_persona = _a_int(cur_p.lastrowid)

                cur_pr = conn.execute(
                    """
                    INSERT INTO proveedores (id_persona, rubro, contacto_secundario, activo)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        id_persona,
                        rubro,
                        contacto or None,
                        1 if proveedor.activo else 0,
                    ),
                )
                if cur_pr.lastrowid is None:
                    raise RuntimeError("No se pudo crear el registro en proveedores.")
                proveedor.id_proveedor = _a_int(cur_pr.lastrowid)
                proveedor.id_persona = id_persona
                proveedor.cuit = cuit_limpio
                proveedor.razon_social = razon_social
                proveedor.rubro = rubro
            else:
                fila_prov = conn.execute(
                    "SELECT id_persona FROM proveedores WHERE id = ?",
                    (proveedor.id_proveedor,),
                ).fetchone()
                if not fila_prov:
                    raise ValueError("El proveedor seleccionado no existe.")
                id_persona = _a_int(fila_prov["id_persona"])

                conn.execute(
                    """
                    UPDATE personas
                    SET tipo_persona = 'Juridica',
                        nombres = NULL,
                        apellidos = NULL,
                        razon_social = ?,
                        tipo_documento = 'CUIT',
                        nro_documento = ?,
                        telefono = ?,
                        email = ?,
                        domicilio = ?
                    WHERE id = ?
                    """,
                    (
                        razon_social,
                        cuit_limpio,
                        telefono or None,
                        email or None,
                        domicilio or None,
                        id_persona,
                    ),
                )
                conn.execute(
                    """
                    UPDATE proveedores
                    SET rubro = ?,
                        contacto_secundario = ?,
                        activo = ?
                    WHERE id = ?
                    """,
                    (
                        rubro,
                        contacto or None,
                        1 if proveedor.activo else 0,
                        proveedor.id_proveedor,
                    ),
                )
                proveedor.id_persona = id_persona
                proveedor.cuit = cuit_limpio
                proveedor.razon_social = razon_social
                proveedor.rubro = rubro

        return True

    @classmethod
    def cambiar_estado_proveedor(cls, id_proveedor: int, activo: bool) -> bool:
        with ConexionDB() as conn:
            cur = conn.execute(
                "UPDATE proveedores SET activo = ? WHERE id = ?",
                (1 if activo else 0, id_proveedor),
            )
            return cur.rowcount > 0