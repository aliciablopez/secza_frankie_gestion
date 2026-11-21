"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO 1 - CORE Y SEGURIDAD (tests/test_core.py)
===============================================================================
Compatible con `unittest` y `pytest`.
Aisla la base de datos en un directorio temporal para no tocar la BD real.
===============================================================================
"""

from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

# Raíz del proyecto (donde están dominio/, infraestructura/, controladores/, vistas/)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from controladores.controlador_core import ControladorCore
from dominio.entidades_core import Rol, Usuario
from infraestructura.conexion import ConexionDB
from infraestructura.repo_core import RepoCore


class TestModuloCore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        db_origen = self._localizar_db_original()
        if db_origen is not None:
            shutil.copy2(db_origen, self.db_temp)
        else:
            hash_admin = RepoCore._hashear_password("admin123")
            with sqlite3.connect(self.db_temp) as conn:
                conn.executescript(
                    f"""
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT NOT NULL UNIQUE,
                        descripcion TEXT DEFAULT ''
                    );
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        activo INTEGER NOT NULL DEFAULT 1
                    );
                    CREATE TABLE IF NOT EXISTS usuarios_roles (
                        id_usuario INTEGER NOT NULL,
                        id_rol INTEGER NOT NULL,
                        PRIMARY KEY (id_usuario, id_rol),
                        FOREIGN KEY (id_usuario) REFERENCES usuarios(id),
                        FOREIGN KEY (id_rol) REFERENCES roles(id)
                    );
                    INSERT OR IGNORE INTO roles (nombre, descripcion)
                    VALUES ('Administrador', 'Acceso total');
                    INSERT OR IGNORE INTO usuarios (username, password, activo)
                    VALUES ('admin', '{hash_admin}', 1);
                    INSERT OR IGNORE INTO usuarios_roles (id_usuario, id_rol)
                    SELECT u.id, r.id FROM usuarios u, roles r
                    WHERE u.username = 'admin' AND r.nombre = 'Administrador';
                    """
                )

        self._patches = []
        original_init = ConexionDB.__init__
        db_objetivo = self.db_temp

        def _init_aislado(self_conexion, ruta_db=None):
            original_init(
                self_conexion,
                ruta_db if ruta_db is not None else db_objetivo,
            )

        p_init = patch.object(ConexionDB, "__init__", _init_aislado)
        p_init.start()
        self._patches.append(p_init)

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._tmpdir.cleanup()

    @staticmethod
    def _localizar_db_original() -> Path | None:
        candidatos = [
            RAIZ_PROYECTO / "db" / "frankie_gestor.db",
            RAIZ_PROYECTO / "db" / "frankie.db",
            RAIZ_PROYECTO / "frankie_gestor.db",
            RAIZ_PROYECTO / "frankie.db",
        ]
        for ruta in candidatos:
            if ruta.exists() and ruta.is_file():
                return ruta
        return None

    def test_gestor_contexto_conexion_y_pragmas(self) -> None:
        """Verifica que ConexionDB abra una conexión válida, active FKs y cierre al salir."""
        gestor = ConexionDB(self.db_temp)

        with gestor as conn:
            self.assertIsInstance(conn, sqlite3.Connection)
            self.assertIs(conn.row_factory, sqlite3.Row)
            fk_activa = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            self.assertEqual(fk_activa, 1)

        self.assertIsNone(gestor.conexion)

    def test_creacion_usuario_y_rol(self) -> None:
        """Verifica que Usuario y Rol se instancien y asocien correctamente."""
        usuario = Usuario(id_usuario=99, username="test_user", password_hash="hashfalso123")
        rol = Rol(id_rol=1, nombre="Gerente")
        usuario.agregar_rol(rol)

        self.assertEqual(usuario.username, "test_user")
        self.assertEqual(len(usuario.roles), 1)
        self.assertEqual(usuario.roles[0].nombre, "Gerente")

    def test_hashing_password(self) -> None:
        """Verifica que el algoritmo SHA-256 devuelva un hex digest de 64 caracteres."""
        hash_result = RepoCore._hashear_password("admin123")
        self.assertIsInstance(hash_result, str)
        self.assertEqual(len(hash_result), 64)

    def test_autenticacion_exitosa(self) -> None:
        """Verifica autenticación de 'admin' y carga de su rol Administrador."""
        usuario = RepoCore.autenticar_usuario("admin", "admin123")

        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.username, "admin")
        roles_nombres = [r.nombre for r in usuario.roles]
        self.assertIn("Administrador", roles_nombres)

    def test_autenticacion_adaptador_ui(self) -> None:
        """Verifica que el método adaptador autenticar() funcione igual que autenticar_usuario()."""
        usuario = RepoCore.autenticar("admin", "admin123")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.username, "admin")

    def test_autenticacion_fallida(self) -> None:
        """Verifica que el sistema rechace credenciales inválidas."""
        usuario = RepoCore.autenticar_usuario("admin", "clave_equivocada")
        self.assertIsNone(usuario)

    def test_ejecucion_backup(self) -> None:
        """Verifica que ControladorCore cree el respaldo en el directorio aislado."""
        controlador = ControladorCore(ruta_base=self.tmp_path)
        resultado = controlador.ejecutar_backup()

        self.assertIsInstance(resultado, str)
        self.assertIn("exitoso", resultado.lower())

        carpeta_backups = self.tmp_path / "db" / "backups"
        self.assertTrue(carpeta_backups.exists())
        archivos_respaldo = list(carpeta_backups.glob("respaldo_frankie_*.db"))
        self.assertEqual(len(archivos_respaldo), 1)
        self.assertGreater(archivos_respaldo[0].stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()