"""
===============================================================================
SCRIPT DE INICIALIZACIÓN DE BASE DE DATOS (inicializar_db.py)
===============================================================================
Aplica el esquema relacional SQLite (`esquema.sql`), habilita claves foráneas,
garantiza columnas y semillas clave ante bases preexistentes y verifica las
tablas y relaciones del sistema (incluyendo usuarios y roles).
===============================================================================
"""

import argparse
import hashlib
from pathlib import Path
import sqlite3
import sys

RUTA_BASE = Path(__file__).resolve().parent

RUTAS_ESQUEMA_CANDIDATAS = [
    RUTA_BASE / "esquema.sql",
    RUTA_BASE / "db" / "esquema.sql",
    RUTA_BASE / "infraestructura" / "esquema.sql",
]

RUTAS_DB_CANDIDATAS = [
    RUTA_BASE / "db" / "frankie_gestor.db",
    RUTA_BASE / "frankie_gestor.db",
]


def hashear_password(password_plano: str) -> str:
    """Genera hash SHA-256 en hexadecimal compatible con el esquema maestro."""
    return hashlib.sha256(password_plano.encode("utf-8")).hexdigest()


def verificar_password(password_plano: str, password_almacenado: str) -> bool:
    """Verifica una contraseña plana contra el hash almacenado."""
    return hashlib.compare_digest(hashear_password(password_plano), password_almacenado)


def localizar_esquema(ruta_explicitada: str | None = None) -> Path:
    """Devuelve la ruta al archivo esquema.sql."""
    if ruta_explicitada:
        ruta = Path(ruta_explicitada).resolve()
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el esquema en: {ruta}")
        return ruta

    for candidata in RUTAS_ESQUEMA_CANDIDATAS:
        if candidata.exists():
            return candidata

    raise FileNotFoundError(
        "No se encontró 'esquema.sql'. Colocalo en la raíz del proyecto o indicá --esquema."
    )


def localizar_db(ruta_explicitada: str | None = None) -> Path:
    """Devuelve la ruta destino de la base de datos SQLite."""
    if ruta_explicitada:
        return Path(ruta_explicitada).resolve()

    for candidata in RUTAS_DB_CANDIDATAS:
        if candidata.exists():
            return candidata

    return RUTAS_DB_CANDIDATAS[0]


def _columnas_tabla(conn: sqlite3.Connection, tabla: str) -> set[str]:
    """Obtiene los nombres de columnas actuales de una tabla."""
    filas = conn.execute(f"PRAGMA table_info({tabla});").fetchall()
    return {fila[1] for fila in filas}


def _asegurar_compatibilidad_columnas(conn: sqlite3.Connection) -> None:
    """
    Asegura columnas incorporadas en iteraciones recientes si la tabla ya existía
    de una versión anterior en la misma base de datos.
    """
    tablas_existentes = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        ).fetchall()
    }

    if "proveedores" in tablas_existentes:
        cols_prov = _columnas_tabla(conn, "proveedores")
        if "contacto_secundario" not in cols_prov:
            conn.execute(
                "ALTER TABLE proveedores ADD COLUMN contacto_secundario TEXT;"
            )
        if "activo" not in cols_prov:
            conn.execute(
                "ALTER TABLE proveedores ADD COLUMN activo INTEGER NOT NULL DEFAULT 1;"
            )

    if "productos" in tablas_existentes:
        cols_prod = _columnas_tabla(conn, "productos")
        if "activo" not in cols_prod:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN activo INTEGER NOT NULL DEFAULT 1;"
            )

    if "usuarios" in tablas_existentes:
        cols_usr = _columnas_tabla(conn, "usuarios")
        if "activo" not in cols_usr:
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN activo INTEGER NOT NULL DEFAULT 1;"
            )


def _asegurar_semillas_usuarios(conn: sqlite3.Connection) -> None:
    """Garantiza roles base, usuario admin inicial y vínculo en usuarios_roles."""
    tablas_existentes = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        ).fetchall()
    }
    if not {"roles", "usuarios", "usuarios_roles"}.issubset(tablas_existentes):
        return

    conn.execute(
        """
        INSERT OR IGNORE INTO roles (nombre, descripcion) VALUES
        ('Administrador', 'Control total del sistema'),
        ('Gerente', 'Gestión operativa sin acceso a roles superiores'),
        ('Empleado - Ventas', 'Acceso a clientes y facturación'),
        ('Empleado - Compras', 'Acceso a proveedores y stock');
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO usuarios (username, password, activo) VALUES
        ('admin', ?, 1);
        """,
        (hashear_password("admin123"),),
    )
    fila_admin = conn.execute(
        "SELECT id FROM usuarios WHERE username = 'admin';"
    ).fetchone()
    fila_rol_admin = conn.execute(
        "SELECT id FROM roles WHERE nombre = 'Administrador';"
    ).fetchone()
    if fila_admin and fila_rol_admin:
        conn.execute(
            """
            INSERT OR IGNORE INTO usuarios_roles (id_usuario, id_rol)
            VALUES (?, ?);
            """,
            (fila_admin[0], fila_rol_admin[0]),
        )


def inicializar_base_datos(
    ruta_db: Path,
    ruta_esquema: Path,
    reiniciar: bool = False,
) -> None:
    """Crea o actualiza la base de datos a partir de esquema.sql."""
    sql_esquema = ruta_esquema.read_text(encoding="utf-8")

    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    if reiniciar and ruta_db.exists():
        ruta_db.unlink()

    with sqlite3.connect(str(ruta_db)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(sql_esquema)
        _asegurar_compatibilidad_columnas(conn)
        _asegurar_semillas_usuarios(conn)
        conn.commit()

        check_fk = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if check_fk:
            raise sqlite3.IntegrityError(
                f"Se detectaron violaciones de claves foráneas: {check_fk}"
            )

        resumen_prov = conn.execute(
            """
            SELECT
                COUNT(*) AS total_proveedores,
                SUM(CASE WHEN activo = 1 THEN 1 ELSE 0 END) AS activos
            FROM proveedores;
            """
        ).fetchone()
        fks_prov = conn.execute("PRAGMA foreign_key_list(proveedores);").fetchall()

        resumen_usr = conn.execute(
            """
            SELECT
                COUNT(*) AS total_usuarios,
                SUM(CASE WHEN activo = 1 THEN 1 ELSE 0 END) AS activos
            FROM usuarios;
            """
        ).fetchone()

    print(f"[OK] Base de datos inicializada en: {ruta_db}")
    print(f"[OK] Esquema aplicado desde: {ruta_esquema}")
    print(
        f"[OK] Tabla 'proveedores' lista | Total: {resumen_prov[0]} | "
        f"Activos: {resumen_prov[1] or 0} | FKs: {len(fks_prov)}"
    )
    print(
        f"[OK] Tabla 'usuarios' lista | Total: {resumen_usr[0]} | "
        f"Activos: {resumen_usr[1] or 0}"
    )


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicializa o actualiza la base de datos SQLite de Frankie Gestor."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Ruta al archivo .db (por defecto: db/frankie_gestor.db).",
    )
    parser.add_argument(
        "--esquema",
        type=str,
        default=None,
        help="Ruta al archivo esquema.sql (por defecto: esquema.sql).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Elimina el archivo .db previo antes de crearlo desde cero.",
    )
    return parser.parse_args()


def main() -> int:
    args = parsear_argumentos()
    try:
        ruta_esquema = localizar_esquema(args.esquema)
        ruta_db = localizar_db(args.db)
        inicializar_base_datos(
            ruta_db=ruta_db,
            ruta_esquema=ruta_esquema,
            reiniciar=args.reset,
        )
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
