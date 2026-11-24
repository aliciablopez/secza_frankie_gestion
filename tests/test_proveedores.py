"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO PROVEEDORES (tests/test_proveedores.py)
===============================================================================
Compatible con `unittest` y `pytest`.
Aisla SQLite en un directorio temporal sin modificar la base real del proyecto.
===============================================================================
"""

import gc
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import tkinter as tk
import unittest
from unittest.mock import patch
import warnings

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from dominio.entidades_proveedores import Proveedor, RUBROS_PROVEEDOR
from infraestructura.conexion import ConexionDB
from infraestructura.repo_proveedores import RepositorioProveedores
from vistas.ui_proveedores import InterfazProveedores

ESQUEMA_OFICIAL_PROVEEDORES = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_persona TEXT NOT NULL DEFAULT 'Juridica' CHECK (tipo_persona IN ('Fisica', 'Juridica')),
    nombres TEXT,
    apellidos TEXT,
    razon_social TEXT,
    tipo_documento TEXT NOT NULL DEFAULT 'CUIT' CHECK (tipo_documento IN ('DNI', 'CUIT', 'CUIL', 'Pasaporte')),
    nro_documento TEXT NOT NULL UNIQUE,
    telefono TEXT,
    email TEXT,
    domicilio TEXT,
    ciudad TEXT,
    provincia TEXT,
    codigo_postal TEXT
);

CREATE TABLE IF NOT EXISTS proveedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    rubro TEXT,
    contacto_secundario TEXT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);
"""


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestRepositorioProveedores(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        with sqlite3.connect(self.db_temp) as conn:
            conn.executescript(ESQUEMA_OFICIAL_PROVEEDORES)

        original_init = ConexionDB.__init__
        db_objetivo = self.db_temp

        def _init_aislado(self_conexion, ruta_db=None):
            original_init(
                self_conexion,
                ruta_db if ruta_db is not None else db_objetivo,
            )

        self._patch_conexion = patch.object(ConexionDB, "__init__", _init_aislado)
        self._patch_conexion.start()

    def tearDown(self) -> None:
        self._patch_conexion.stop()
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_alta_edicion_filtros_y_estado_proveedor(self) -> None:
        rubro_1 = RUBROS_PROVEEDOR[0]
        rubro_2 = RUBROS_PROVEEDOR[1] if len(RUBROS_PROVEEDOR) > 1 else RUBROS_PROVEEDOR[0]

        prov1 = Proveedor(
            cuit="30-71234567-9",
            razon_social="Bijou del Mar S.R.L.",
            rubro=rubro_1,
            contacto="Lucía Ferreyra",
            telefono="2235550101",
            email="ventas@bijoudelmar.com.ar",
            domicilio="Güemes 1234",
            activo=True,
        )
        prov2 = Proveedor(
            cuit="30709988776",
            razon_social="Cueros Atlántico S.A.",
            rubro=rubro_2,
            contacto="Carlos Sosa",
            telefono="2235550202",
            email="info@cuerosatlantico.com.ar",
            domicilio="Colón 456",
            activo=True,
        )

        self.assertTrue(RepositorioProveedores.guardar_proveedor(prov1))
        self.assertTrue(RepositorioProveedores.guardar_proveedor(prov2))
        self.assertEqual(prov1.cuit, "30712345679")
        self.assertIsNotNone(prov1.id_proveedor)
        assert prov1.id_proveedor is not None

        # Filtro por búsqueda y rubro
        buscados = RepositorioProveedores.listar_proveedores(criterio_busqueda="Bijou")
        self.assertEqual(len(buscados), 1)
        self.assertEqual(buscados[0].razon_social, "Bijou del Mar S.R.L.")

        por_rubro = RepositorioProveedores.listar_proveedores(rubro_filtro=rubro_2)
        self.assertEqual(len(por_rubro), 1)
        self.assertEqual(por_rubro[0].cuit, "30709988776")

        # Edición conservando ID
        prov1.razon_social = "Bijou del Mar Mayorista S.R.L."
        prov1.telefono = "2235550999"
        self.assertTrue(RepositorioProveedores.guardar_proveedor(prov1))
        editados = RepositorioProveedores.listar_proveedores(criterio_busqueda="Mayorista")
        self.assertEqual(len(editados), 1)
        self.assertEqual(editados[0].telefono, "2235550999")

        # Baja y reactivación lógica
        self.assertTrue(
            RepositorioProveedores.cambiar_estado_proveedor(prov1.id_proveedor, False)
        )
        self.assertEqual(
            len(RepositorioProveedores.listar_proveedores(incluir_inactivos=False)), 1
        )
        self.assertEqual(
            len(RepositorioProveedores.listar_proveedores(incluir_inactivos=True)), 2
        )

        self.assertTrue(
            RepositorioProveedores.cambiar_estado_proveedor(prov1.id_proveedor, True)
        )
        self.assertEqual(
            len(RepositorioProveedores.listar_proveedores(incluir_inactivos=False)), 2
        )

    def test_rechaza_cuit_invalido_para_proveedor(self) -> None:
        prov_invalido = Proveedor(
            cuit="20301112223",
            razon_social="Persona Física No Válida",
            rubro=RUBROS_PROVEEDOR[0],
            activo=True,
        )
        with self.assertRaises(ValueError):
            RepositorioProveedores.guardar_proveedor(prov_invalido)


class TestInterfazProveedoresRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk no disponible en este entorno: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "root") and cls.root.winfo_exists():
            cls.root.destroy()

    def _crear_vista(self, usuario_actual=None) -> InterfazProveedores:
        with patch.object(
            RepositorioProveedores, "listar_proveedores", return_value=[]
        ):
            vista = InterfazProveedores(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_roles_habilitados_para_gestionar_proveedores(self) -> None:
        for rol in ("Admin", "Gerente"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_gestionar_proveedores)
                    self.assertEqual(str(vista.btn_guardar["state"]), "normal")
                finally:
                    vista.destroy()

    def test_roles_no_habilitados_bloqueados_para_gestionar_proveedores(self) -> None:
        for rol in ("Administrativo", "Vendedor"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertFalse(vista.puede_gestionar_proveedores)
                    self.assertEqual(str(vista.btn_guardar["state"]), "disabled")

                    with (
                        patch.object(
                            RepositorioProveedores, "guardar_proveedor"
                        ) as mock_guardar,
                        patch.object(
                            RepositorioProveedores, "cambiar_estado_proveedor"
                        ) as mock_estado,
                        patch("vistas.ui_proveedores.messagebox.showwarning") as mock_warn,
                    ):
                        vista.var_cuit.set("30712345679")
                        vista.var_razon_social.set("Proveedor Bloqueado")
                        vista.guardar_proveedor()
                        mock_guardar.assert_not_called()
                        mock_warn.assert_called_once()

                        vista.proveedor_seleccionado_id = 1
                        vista.toggle_estado_proveedor()
                        mock_estado.assert_not_called()
                finally:
                    vista.destroy()


if __name__ == "__main__":
    unittest.main()