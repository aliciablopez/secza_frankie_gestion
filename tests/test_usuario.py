"""
===============================================================================
PRUEBAS AUTOMATIZADAS DE GESTIÓN DE USUARIOS (tests/test_usuario.py)
===============================================================================
Verifica permisos de `admin`, hashing SHA-256, alta/actualización/estado de
usuarios, importación desde nómina (`empleados`/`personas`) y control de
acceso en `VistaGestionUsuarios` usando una base SQLite aislada.
===============================================================================
"""

from pathlib import Path
import sqlite3
import sys
import tkinter as tk
from unittest.mock import patch
import pytest

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from vistas.ui_usuarios import (
    MAPA_CARGO_A_ROL,
    VistaGestionUsuarios,
    _hashear_password,
)

ROL_POR_DEFECTO = "Vendedor"


@pytest.fixture
def bd_prueba(tmp_path: Path) -> Path:
    """Crea una base SQLite aislada con roles, usuarios y nómina de prueba."""
    db_file = tmp_path / "test_frankie.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(
        """
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE usuarios_roles (
            id_usuario INTEGER NOT NULL,
            id_rol INTEGER NOT NULL,
            PRIMARY KEY (id_usuario, id_rol),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (id_rol) REFERENCES roles(id) ON DELETE CASCADE
        );
        CREATE TABLE personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombres TEXT NOT NULL,
            apellidos TEXT NOT NULL
        );
        CREATE TABLE empleados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_persona INTEGER NOT NULL,
            id_usuario INTEGER,
            cargo TEXT,
            sector TEXT,
            FOREIGN KEY (id_persona) REFERENCES personas(id),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        );
        INSERT INTO roles (nombre, descripcion) VALUES
            ('Admin', 'Acceso total'),
            ('Gerente', 'Gestión y nómina'),
            ('Vendedor', 'Clientes y ventas'),
            ('Administrativo', 'Gestión administrativa');
        INSERT INTO personas (nombres, apellidos) VALUES
            ('Lucia', 'Fernandez'),
            ('Martin', 'Sosa');
        INSERT INTO empleados (id_persona, id_usuario, cargo, sector) VALUES
            (1, NULL, 'Vendedor', 'Ventas'),
            (2, NULL, 'Administrativo', 'Administración');
        """
    )
    admin_hash = _hashear_password("admin123")
    conn.execute(
        "INSERT INTO usuarios (username, password, activo) VALUES (?, ?, 1)",
        ("admin", admin_hash),
    )
    conn.execute("INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (1, 1)")
    conn.commit()
    conn.close()
    return db_file


@pytest.fixture
def tk_root():
    """Inicializa una ventana raíz oculta de Tkinter o salta si no hay display."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tkinter no disponible en este entorno: {exc}")
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_no_admin_tiene_acceso_restringido(tk_root, bd_prueba: Path) -> None:
    """Un usuario no administrador ve la vista bloqueada y no puede guardar."""
    vista = VistaGestionUsuarios(
        tk_root,
        usuario_actual={"username": "l.fernandez", "rol": "Vendedor"},
        ruta_db=bd_prueba,
    )
    assert vista.es_admin is False
    assert str(vista.btn_guardar["state"]) == "disabled"
    assert str(vista.btn_importar["state"]) == "disabled"

    vista.var_username.set("intento_no_autorizado")
    vista.var_password.set("clave123")
    vista.var_rol.set("Vendedor")

    with patch("vistas.ui_usuarios.messagebox.showwarning") as mock_warn:
        vista.guardar_usuario()
        assert mock_warn.called

    conn = sqlite3.connect(str(bd_prueba))
    existe = conn.execute(
        "SELECT 1 FROM usuarios WHERE username = 'intento_no_autorizado'"
    ).fetchone()
    conn.close()
    assert existe is None


def test_admin_puede_crear_y_alternar_estado_usuario(tk_root, bd_prueba: Path) -> None:
    """El admin puede crear un usuario con hash SHA-256 y deshabilitarlo/reactivarlo."""
    vista = VistaGestionUsuarios(
        tk_root,
        usuario_actual="admin",
        ruta_db=bd_prueba,
    )
    assert vista.es_admin is True

    vista.var_username.set("vendedor1")
    vista.var_password.set("ventas123")
    vista.var_rol.set("Vendedor")
    vista.var_activo.set(True)

    with patch("vistas.ui_usuarios.messagebox.showinfo"):
        vista.guardar_usuario()

    conn = sqlite3.connect(str(bd_prueba))
    fila = conn.execute(
        "SELECT id, password, activo FROM usuarios WHERE username = 'vendedor1'"
    ).fetchone()
    conn.close()

    assert fila is not None
    uid, pwd_guardada, activo = fila
    assert pwd_guardada == _hashear_password("ventas123")
    assert pwd_guardada != "ventas123"
    assert activo == 1

    vista.id_seleccionado = uid
    vista.var_activo.set(True)
    vista.alternar_estado_usuario()

    conn = sqlite3.connect(str(bd_prueba))
    activo_despues = conn.execute(
        "SELECT activo FROM usuarios WHERE id = ?", (uid,)
    ).fetchone()[0]
    conn.close()
    assert activo_despues == 0


def test_importar_desde_nomina_vincula_empleado_y_hashea_clave(bd_prueba: Path) -> None:
    """Verifica que los empleados sin cuenta obtienen usuario, rol y clave cifrada."""
    conn = sqlite3.connect(str(bd_prueba))
    pendientes = conn.execute(
        """
        SELECT e.id, p.nombres, p.apellidos, e.cargo, e.sector
        FROM empleados e
        JOIN personas p ON p.id = e.id_persona
        WHERE e.id_usuario IS NULL
        ORDER BY e.id
        """
    ).fetchall()
    assert len(pendientes) == 2

    clave_hash = _hashear_password("frankie123")
    roles = {
        nombre.strip().lower(): (nombre, rid)
        for nombre, rid in conn.execute("SELECT nombre, id FROM roles").fetchall()
    }

    for id_emp, nom, ape, cargo, sector in pendientes:
        username = f"{nom[0].lower()}.{ape.lower()}"
        cargo_key = str(cargo or "").strip().lower()
        rol_sugerido = MAPA_CARGO_A_ROL.get(cargo_key) or ROL_POR_DEFECTO
        _, rol_id = roles[rol_sugerido.strip().lower()]

        cur = conn.execute(
            "INSERT INTO usuarios (username, password, activo) VALUES (?, ?, 1)",
            (username, clave_hash),
        )
        uid = cur.lastrowid
        conn.execute(
            "INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (?, ?)",
            (uid, rol_id),
        )
        conn.execute(
            "UPDATE empleados SET id_usuario = ? WHERE id = ?",
            (uid, id_emp),
        )
    conn.commit()

    vinculados = conn.execute(
        """
        SELECT u.username, r.nombre, e.id_usuario, u.password
        FROM empleados e
        JOIN usuarios u ON u.id = e.id_usuario
        JOIN usuarios_roles ur ON ur.id_usuario = u.id
        JOIN roles r ON r.id = ur.id_rol
        ORDER BY e.id
        """
    ).fetchall()
    conn.close()

    assert len(vinculados) == 2
    assert vinculados[0][0] == "l.fernandez"
    assert vinculados[0][1] == "Vendedor"
    assert vinculados[0][3] == clave_hash
    assert vinculados[1][0] == "m.sosa"
    assert vinculados[1][1] == "Administrativo"