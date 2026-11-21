from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RUTA_BACKUP = Path(
    r"C:\Users\ASUS\Dropbox\Programacion-Backend\frankie_gestor_v2\db\backups\respaldo_frankie_20261116_133914.db"
)
RUTA_DESTINO = BASE_DIR / "db" / "frankie_gestor.db"

CARGOS_VALIDOS = ("Gerente", "Admin", "Administrativo", "Vendedor")

# Valores del backup (izquierda) -> valores vigentes en destino (derecha)
MAPEO_CARGOS = {
    "Gerente": "Gerente",
    "Administrador": "Admin",
    "Admin": "Admin",
    "Empleado_Admin": "Administrativo",
    "Empleado_Compras": "Administrativo",
    "Administrativo": "Administrativo",
    "Empleado_Ventas": "Vendedor",
    "Vendedor": "Vendedor",
}


def crear_respaldo_previo(destino: Path) -> Path:
    carpeta_respaldos = destino.parent / "backups"
    carpeta_respaldos.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_copia = carpeta_respaldos / f"pre_migracion_{timestamp}_{destino.name}"
    shutil.copy2(destino, ruta_copia)
    return ruta_copia


def limpiar_texto_opcional(valor: Any) -> str | None:
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio if limpio else None


def a_int(valor: Any, nombre_campo: str = "id") -> int:
    if valor is None:
        raise ValueError(f"Se esperaba un entero no nulo para '{nombre_campo}', pero llegó None.")
    return int(valor)


def obtener_columnas(conn: sqlite3.Connection, tabla: str) -> set[str]:
    return {fila[1] for fila in conn.execute(f"PRAGMA table_info([{tabla}])").fetchall()}


def recrear_tabla_limpia(
    conn: sqlite3.Connection,
    nombre_tabla: str,
    crear_sql: str,
    cols_copia: list[str],
    normalizar_cargo: bool = False,
) -> None:
    """Recrea una tabla en SQLite limpiando referencias internas a tablas renombradas."""
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (nombre_tabla,),
    ).fetchone()
    if not existe:
        return

    triggers = [
        r[0]
        for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql IS NOT NULL",
            (nombre_tabla,),
        ).fetchall()
    ]
    indices = [
        r[0]
        for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (nombre_tabla,),
        ).fetchall()
    ]

    filas_previas = [dict(r) for r in conn.execute(f"SELECT * FROM [{nombre_tabla}]").fetchall()]
    temp_tabla = f"__temp_{nombre_tabla}"

    conn.execute(f"DROP TABLE IF EXISTS [{temp_tabla}];")
    conn.execute(f"CREATE TABLE [{temp_tabla}] AS SELECT * FROM [{nombre_tabla}];")
    conn.execute(f"DROP TABLE [{nombre_tabla}];")
    conn.execute(crear_sql)

    cols_disponibles = [c for c in cols_copia if filas_previas and c in filas_previas[0]]
    if not cols_disponibles:
        cols_disponibles = [
            r[1]
            for r in conn.execute(f"PRAGMA table_info([{nombre_tabla}])").fetchall()
            if r[1] not in ("id", "id_liquidacion")
        ]

    cols_sql = ", ".join(f"[{c}]" for c in cols_disponibles)
    ph_sql = ", ".join("?" for _ in cols_disponibles)

    for fila in filas_previas:
        valores = []
        for col in cols_disponibles:
            val = fila.get(col)
            if normalizar_cargo and col == "cargo" and val is not None:
                val = MAPEO_CARGOS.get(str(val).strip(), str(val).strip())
            valores.append(val)
        conn.execute(f"INSERT INTO [{nombre_tabla}] ({cols_sql}) VALUES ({ph_sql});", valores)

    conn.execute(f"DROP TABLE [{temp_tabla}];")

    for idx_sql in indices:
        conn.execute(idx_sql)
    for trg_sql in triggers:
        conn.execute(trg_sql.replace("empleados_old", "empleados"))


def actualizar_esquema_destino(ruta_destino: Path) -> None:
    """Actualiza el CHECK de `empleados.cargo` y refresca tablas hijas con caché limpia."""
    conn = sqlite3.connect(ruta_destino, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        fila_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='empleados'"
        ).fetchone()
        if not fila_sql or not fila_sql[0]:
            return

        sql_actual = fila_sql[0]
        tiene_check_nuevo = (
            all(f"'{c}'" in sql_actual for c in CARGOS_VALIDOS)
            and "'Empleado_Compras'" not in sql_actual
        )

        cols_actuales = obtener_columnas(conn, "empleados")
        tiene_id_usuario = "id_usuario" in cols_actuales
        tiene_activo = "activo" in cols_actuales

        conn.execute("BEGIN IMMEDIATE;")
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("PRAGMA legacy_alter_table = ON;")

        if not tiene_check_nuevo:
            def_id_usuario = "\n                id_usuario INTEGER UNIQUE," if tiene_id_usuario else ""
            def_activo = ",\n                activo INTEGER DEFAULT 1" if tiene_activo else ""
            fk_usuario = (
                ",\n                FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE SET NULL"
                if tiene_id_usuario
                else ""
            )

            crear_empleados_sql = f"""
                CREATE TABLE empleados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_persona INTEGER NOT NULL UNIQUE,{def_id_usuario}
                    legajo TEXT NOT NULL UNIQUE,
                    cargo TEXT NOT NULL CHECK (cargo IN ('Gerente', 'Admin', 'Administrativo', 'Vendedor')),
                    sector TEXT NOT NULL,
                    tipo_vinculo TEXT NOT NULL,
                    sueldo REAL NOT NULL{def_activo},
                    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE{fk_usuario}
                );
            """
            cols_emp = ["id", "id_persona"]
            if tiene_id_usuario:
                cols_emp.append("id_usuario")
            cols_emp.extend(["legajo", "cargo", "sector", "tipo_vinculo", "sueldo"])
            if tiene_activo:
                cols_emp.append("activo")

            recrear_tabla_limpia(
                conn, "empleados", crear_empleados_sql, cols_emp, normalizar_cargo=True
            )

        existe_liq = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='liquidaciones_haberes'"
        ).fetchone()
        if existe_liq:
            crear_liq_sql = """
                CREATE TABLE liquidaciones_haberes (
                    id_liquidacion INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_empleado INTEGER NOT NULL,
                    periodo TEXT NOT NULL,
                    sueldo_basico REAL NOT NULL,
                    total_remunerativo REAL NOT NULL,
                    total_no_remunerativo REAL DEFAULT 0.00,
                    total_descuentos REAL NOT NULL,
                    neto_a_cobrar REAL NOT NULL,
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (id_empleado) REFERENCES empleados(id) ON DELETE CASCADE
                );
            """
            cols_liq = [
                "id_liquidacion",
                "id_empleado",
                "periodo",
                "sueldo_basico",
                "total_remunerativo",
                "total_no_remunerativo",
                "total_descuentos",
                "neto_a_cobrar",
                "fecha_registro",
            ]
            recrear_tabla_limpia(conn, "liquidaciones_haberes", crear_liq_sql, cols_liq)

        fila_fact = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='facturas' AND sql LIKE '%empleados%'"
        ).fetchone()
        if fila_fact:
            crear_fact_sql = """
                CREATE TABLE facturas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                    id_cliente INTEGER NOT NULL,
                    id_vendedor INTEGER NOT NULL,
                    total REAL DEFAULT 0.00,
                    FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON DELETE RESTRICT,
                    FOREIGN KEY (id_vendedor) REFERENCES empleados(id) ON DELETE RESTRICT
                );
            """
            cols_fact = ["id", "fecha", "id_cliente", "id_vendedor", "total"]
            recrear_tabla_limpia(conn, "facturas", crear_fact_sql, cols_fact)

        triggers_rotos = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND sql LIKE '%empleados_old%'"
        ).fetchall()
        for trg_name, trg_sql in triggers_rotos:
            conn.execute(f"DROP TRIGGER IF EXISTS [{trg_name}];")
            conn.execute(trg_sql.replace("empleados_old", "empleados"))

        conn.execute("PRAGMA legacy_alter_table = OFF;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def migrar() -> None:
    if not RUTA_BACKUP.exists():
        raise FileNotFoundError(f"No se encontró el archivo de backup: {RUTA_BACKUP}")
    if not RUTA_DESTINO.exists():
        raise FileNotFoundError(f"No se encontró la base destino: {RUTA_DESTINO}")

    respaldo_seguridad = crear_respaldo_previo(RUTA_DESTINO)
    print(f"Respaldo previo creado en: {respaldo_seguridad}")

    actualizar_esquema_destino(RUTA_DESTINO)

    src = sqlite3.connect(f"file:{RUTA_BACKUP}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    dst = sqlite3.connect(RUTA_DESTINO)
    dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys = ON;")

    try:
        cols_personas_dst = obtener_columnas(dst, "personas")
        cols_empleados_dst = obtener_columnas(dst, "empleados")
        cols_proveedores_dst = obtener_columnas(dst, "proveedores")
        cols_clientes_dst = obtener_columnas(dst, "clientes")
        cols_productos_dst = obtener_columnas(dst, "productos")
        cols_liq_dst = obtener_columnas(dst, "liquidaciones_haberes")

        mapa_persona_id: dict[int, int] = {}
        personas_src = src.execute("SELECT * FROM personas ORDER BY id").fetchall()
        for p in personas_src:
            id_p_src = a_int(p["id"], "personas.id")
            nro_doc = str(p["nro_documento"]).strip()
            existente = dst.execute(
                "SELECT id FROM personas WHERE nro_documento = ?",
                (nro_doc,),
            ).fetchone()

            if existente:
                mapa_persona_id[id_p_src] = a_int(existente["id"], "personas.id")
                continue

            datos_persona = {
                "tipo_persona": p["tipo_persona"],
                "nombres": limpiar_texto_opcional(p["nombres"]),
                "apellidos": limpiar_texto_opcional(p["apellidos"]),
                "razon_social": limpiar_texto_opcional(p["razon_social"]),
                "tipo_documento": p["tipo_documento"],
                "nro_documento": nro_doc,
                "telefono": limpiar_texto_opcional(p["telefono"]),
                "email": limpiar_texto_opcional(p["email"]),
                "domicilio": limpiar_texto_opcional(p["domicilio"]),
                "ciudad": limpiar_texto_opcional(p["ciudad"]),
                "provincia": limpiar_texto_opcional(p["provincia"]),
                "codigo_postal": limpiar_texto_opcional(p["codigo_postal"]),
            }
            campos_validos = [k for k in datos_persona if k in cols_personas_dst]
            placeholders = ", ".join("?" for _ in campos_validos)
            columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
            valores = [datos_persona[c] for c in campos_validos]

            cur = dst.execute(
                f"INSERT INTO personas ({columnas_sql}) VALUES ({placeholders})",
                valores,
            )
            mapa_persona_id[id_p_src] = a_int(cur.lastrowid, "personas.lastrowid")

        mapa_empleado_id: dict[int, int] = {}
        empleados_src = src.execute("SELECT * FROM empleados ORDER BY id").fetchall()
        for e in empleados_src:
            id_e_src = a_int(e["id"], "empleados.id")
            id_p_src = a_int(e["id_persona"], "empleados.id_persona")
            id_persona_dst = mapa_persona_id.get(id_p_src)
            if id_persona_dst is None:
                continue

            legajo = str(e["legajo"]).strip()
            cargo_src = str(e["cargo"]).strip()
            cargo_dst = MAPEO_CARGOS.get(cargo_src, cargo_src)

            existente = dst.execute(
                "SELECT id FROM empleados WHERE legajo = ? OR id_persona = ?",
                (legajo, id_persona_dst),
            ).fetchone()

            if existente:
                id_e_dst = a_int(existente["id"], "empleados.id")
                dst.execute(
                    "UPDATE empleados SET cargo = ? WHERE id = ?",
                    (cargo_dst, id_e_dst),
                )
                mapa_empleado_id[id_e_src] = id_e_dst
                continue

            datos_empleado = {
                "id_persona": id_persona_dst,
                "id_usuario": e["id_usuario"] if "id_usuario" in e.keys() else None,
                "legajo": legajo,
                "cargo": cargo_dst,
                "sector": limpiar_texto_opcional(e["sector"]),
                "tipo_vinculo": limpiar_texto_opcional(e["tipo_vinculo"]),
                "sueldo": float(a_int(e["sueldo"], "empleados.sueldo") if isinstance(e["sueldo"], int) else e["sueldo"]),
                "activo": a_int(e["activo"], "empleados.activo") if e["activo"] is not None else 1,
            }
            campos_validos = [k for k in datos_empleado if k in cols_empleados_dst]
            placeholders = ", ".join("?" for _ in campos_validos)
            columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
            valores = [datos_empleado[c] for c in campos_validos]

            cur = dst.execute(
                f"INSERT INTO empleados ({columnas_sql}) VALUES ({placeholders})",
                valores,
            )
            mapa_empleado_id[id_e_src] = a_int(cur.lastrowid, "empleados.lastrowid")

        mapa_proveedor_id: dict[int, int] = {}
        proveedores_src = src.execute("SELECT * FROM proveedores ORDER BY id").fetchall()
        for pr in proveedores_src:
            id_pr_src = a_int(pr["id"], "proveedores.id")
            id_p_src = a_int(pr["id_persona"], "proveedores.id_persona")
            id_persona_dst = mapa_persona_id.get(id_p_src)
            if id_persona_dst is None:
                continue

            existente = dst.execute(
                "SELECT id FROM proveedores WHERE id_persona = ?",
                (id_persona_dst,),
            ).fetchone()
            if existente:
                mapa_proveedor_id[id_pr_src] = a_int(existente["id"], "proveedores.id")
                continue

            datos_proveedor = {
                "id_persona": id_persona_dst,
                "rubro": limpiar_texto_opcional(pr["rubro"]),
                "contacto_secundario": limpiar_texto_opcional(pr["contacto_secundario"]),
                "activo": a_int(pr["activo"], "proveedores.activo") if "activo" in pr.keys() and pr["activo"] is not None else 1,
            }
            campos_validos = [k for k in datos_proveedor if k in cols_proveedores_dst]
            placeholders = ", ".join("?" for _ in campos_validos)
            columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
            valores = [datos_proveedor[c] for c in campos_validos]

            cur = dst.execute(
                f"INSERT INTO proveedores ({columnas_sql}) VALUES ({placeholders})",
                valores,
            )
            mapa_proveedor_id[id_pr_src] = a_int(cur.lastrowid, "proveedores.lastrowid")

        clientes_src = src.execute("SELECT * FROM clientes ORDER BY id").fetchall()
        for cl in clientes_src:
            id_p_src = a_int(cl["id_persona"], "clientes.id_persona")
            id_persona_dst = mapa_persona_id.get(id_p_src)
            if id_persona_dst is None:
                continue

            existente = dst.execute(
                "SELECT id FROM clientes WHERE id_persona = ?",
                (id_persona_dst,),
            ).fetchone()
            if existente:
                continue

            datos_cliente = {
                "id_persona": id_persona_dst,
                "fecha_alta": cl["fecha_alta"] if "fecha_alta" in cl.keys() else None,
            }
            campos_validos = [
                k for k in datos_cliente if k in cols_clientes_dst and datos_cliente[k] is not None
            ]
            placeholders = ", ".join("?" for _ in campos_validos)
            columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
            valores = [datos_cliente[c] for c in campos_validos]

            dst.execute(
                f"INSERT INTO clientes ({columnas_sql}) VALUES ({placeholders})",
                valores,
            )

        productos_src = src.execute("SELECT * FROM productos ORDER BY id").fetchall()
        for pd in productos_src:
            id_pr_src = a_int(pd["id_proveedor"], "productos.id_proveedor")
            id_proveedor_dst = mapa_proveedor_id.get(id_pr_src)
            if id_proveedor_dst is None:
                continue

            codigo = str(pd["codigo"]).strip()
            existente = dst.execute(
                "SELECT id FROM productos WHERE codigo = ?",
                (codigo,),
            ).fetchone()
            if existente:
                continue

            datos_producto = {
                "codigo": codigo,
                "descripcion": limpiar_texto_opcional(pd["descripcion"]),
                "categoria": limpiar_texto_opcional(pd["categoria"]),
                "id_proveedor": id_proveedor_dst,
                "stock_actual": a_int(pd["stock_actual"], "productos.stock_actual"),
                "stock_minimo": a_int(pd["stock_minimo"], "productos.stock_minimo"),
                "precio_costo": float(pd["precio_costo"]),
                "precio_venta": float(pd["precio_venta"]),
                "ubicacion": limpiar_texto_opcional(pd["ubicacion"]),
                "vencimiento": limpiar_texto_opcional(pd["vencimiento"]),
                "activo": a_int(pd["activo"], "productos.activo") if "activo" in pd.keys() and pd["activo"] is not None else 1,
            }
            campos_validos = [k for k in datos_producto if k in cols_productos_dst]
            placeholders = ", ".join("?" for _ in campos_validos)
            columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
            valores = [datos_producto[c] for c in campos_validos]

            dst.execute(
                f"INSERT INTO productos ({columnas_sql}) VALUES ({placeholders})",
                valores,
            )

        liq_src = src.execute(
            "SELECT * FROM liquidaciones_haberes ORDER BY fecha_registro ASC, id_liquidacion ASC"
        ).fetchall()
        liq_por_clave: dict[tuple[int, str], sqlite3.Row] = {}
        for lq in liq_src:
            id_e_src = a_int(lq["id_empleado"], "liquidaciones_haberes.id_empleado")
            id_emp_dst = mapa_empleado_id.get(id_e_src)
            if id_emp_dst is None:
                continue
            clave = (id_emp_dst, str(lq["periodo"]).strip())
            liq_por_clave[clave] = lq

        for (id_emp_dst, periodo), lq in liq_por_clave.items():
            remunerativo = float(lq["total_remunerativo"])
            no_remunerativo = float(lq["total_no_remunerativo"] or 0.0)
            descuentos = float(lq["total_descuentos"])
            neto_calculado = round(remunerativo + no_remunerativo - descuentos, 2)

            existente = dst.execute(
                "SELECT id_liquidacion FROM liquidaciones_haberes WHERE id_empleado = ? AND periodo = ?",
                (id_emp_dst, periodo),
            ).fetchone()

            if existente:
                id_liq_dst = a_int(existente["id_liquidacion"], "liquidaciones_haberes.id_liquidacion")
                dst.execute(
                    """
                    UPDATE liquidaciones_haberes
                    SET sueldo_basico = ?,
                        total_remunerativo = ?,
                        total_no_remunerativo = ?,
                        total_descuentos = ?,
                        neto_a_cobrar = ?,
                        fecha_registro = ?
                    WHERE id_liquidacion = ?
                    """,
                    (
                        float(lq["sueldo_basico"]),
                        remunerativo,
                        no_remunerativo,
                        descuentos,
                        neto_calculado,
                        lq["fecha_registro"],
                        id_liq_dst,
                    ),
                )
            else:
                datos_liq = {
                    "id_empleado": id_emp_dst,
                    "periodo": periodo,
                    "sueldo_basico": float(lq["sueldo_basico"]),
                    "total_remunerativo": remunerativo,
                    "total_no_remunerativo": no_remunerativo,
                    "total_descuentos": descuentos,
                    "neto_a_cobrar": neto_calculado,
                    "fecha_registro": lq["fecha_registro"],
                }
                campos_validos = [k for k in datos_liq if k in cols_liq_dst]
                placeholders = ", ".join("?" for _ in campos_validos)
                columnas_sql = ", ".join(f"[{c}]" for c in campos_validos)
                valores = [datos_liq[c] for c in campos_validos]

                dst.execute(
                    f"INSERT INTO liquidaciones_haberes ({columnas_sql}) VALUES ({placeholders})",
                    valores,
                )

        fk_errores = dst.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_errores:
            raise sqlite3.IntegrityError(f"Se detectaron errores de clave foránea: {fk_errores}")

        dst.commit()
        print("Migración completada con éxito.")
    except Exception:
        dst.rollback()
        raise
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    migrar()