"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO INVENTARIO (tests/test_inventario.py)
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

from dominio.entidades_stock import Producto
from infraestructura.conexion import ConexionDB
from infraestructura.repo_stock import RepositorioStock
from vistas.ui_inventario import InterfazInventario

ESQUEMA_OFICIAL_INVENTARIO = """
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

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    categoria TEXT,
    id_proveedor INTEGER NOT NULL,
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 75,
    precio_costo REAL NOT NULL DEFAULT 0.0,
    precio_venta REAL NOT NULL DEFAULT 0.0,
    ubicacion TEXT,
    vencimiento TEXT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id) ON DELETE RESTRICT
);
"""


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestRepositorioStock(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        with sqlite3.connect(self.db_temp) as conn:
            conn.executescript(ESQUEMA_OFICIAL_INVENTARIO)

        original_init = ConexionDB.__init__
        db_objetivo = self.db_temp

        def _init_aislado(self_conexion, ruta_db=None):
            original_init(
                self_conexion,
                ruta_db if ruta_db is not None else db_objetivo,
            )

        self._patch_conexion = patch.object(ConexionDB, "__init__", _init_aislado)
        self._patch_conexion.start()
        self.id_proveedor = self._insertar_proveedor()

    def tearDown(self) -> None:
        self._patch_conexion.stop()
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def _insertar_proveedor(
        self,
        cuit: str = "30711223349",
        razon_social: str = "Distribuidora Sur S.A.",
    ) -> int:
        with sqlite3.connect(self.db_temp) as conn:
            cur_p = conn.execute(
                """
                INSERT INTO personas (tipo_persona, razon_social, tipo_documento, nro_documento)
                VALUES ('Juridica', ?, 'CUIT', ?)
                """,
                (razon_social, cuit),
            )
            id_persona = int(cur_p.lastrowid or 0)
            cur_pv = conn.execute(
                """
                INSERT INTO proveedores (id_persona, rubro, activo)
                VALUES (?, 'Mayorista', 1)
                """,
                (id_persona,),
            )
            conn.commit()
            return int(cur_pv.lastrowid or 0)

    def test_alta_edicion_filtros_y_estado_producto(self) -> None:
        prod_bajo = Producto(
            codigo="INV-001",
            descripcion="Mouse Inalámbrico",
            categoria="Periféricos",
            id_proveedor=self.id_proveedor,
            stock_actual=20,
            stock_minimo=75,
            precio_costo=5000.0,
            precio_venta=8000.0,
            ubicacion="Estante A1",
            activo=True,
        )
        prod_ok = Producto(
            codigo="INV-002",
            descripcion="Monitor LED 24",
            categoria="Pantallas",
            id_proveedor=self.id_proveedor,
            stock_actual=120,
            stock_minimo=75,
            precio_costo=90000.0,
            precio_venta=135000.0,
            ubicacion="Depósito B2",
            activo=True,
        )

        self.assertTrue(RepositorioStock.guardar_producto(prod_bajo))
        self.assertTrue(RepositorioStock.guardar_producto(prod_ok))
        self.assertIsNotNone(prod_bajo.id_producto)
        assert prod_bajo.id_producto is not None

        # Código duplicado en alta debe fallar
        duplicado = Producto(
            codigo="INV-001",
            descripcion="Duplicado",
            id_proveedor=self.id_proveedor,
            precio_costo=0.0,
            precio_venta=0.0,
        )
        with self.assertRaises(ValueError):
            RepositorioStock.guardar_producto(duplicado)

        # Filtro de stock bajo
        bajos = RepositorioStock.listar_productos(solo_stock_bajo=True)
        self.assertEqual(len(bajos), 1)
        self.assertEqual(bajos[0].codigo, "INV-001")

        # Filtro por búsqueda
        busqueda = RepositorioStock.listar_productos(criterio_busqueda="Monitor")
        self.assertEqual(len(busqueda), 1)
        self.assertEqual(busqueda[0].codigo, "INV-002")

        # Edición conservando ID
        prod_bajo.descripcion = "Mouse Inalámbrico RGB"
        prod_bajo.stock_actual = 85
        self.assertTrue(RepositorioStock.guardar_producto(prod_bajo))
        self.assertEqual(
            len(RepositorioStock.listar_productos(solo_stock_bajo=True)), 0
        )

        # Baja lógica y reactivación
        self.assertTrue(
            RepositorioStock.cambiar_estado_producto(prod_bajo.id_producto, False)
        )
        self.assertEqual(
            len(RepositorioStock.listar_productos(incluir_inactivos=False)), 1
        )
        self.assertEqual(
            len(RepositorioStock.listar_productos(incluir_inactivos=True)), 2
        )

        self.assertTrue(
            RepositorioStock.cambiar_estado_producto(prod_bajo.id_producto, True)
        )
        self.assertEqual(
            len(RepositorioStock.listar_productos(incluir_inactivos=False)), 2
        )

    def test_ajustar_stock_valido_y_rechazo_negativo(self) -> None:
        prod = Producto(
            codigo="INV-010",
            descripcion="Cable HDMI 2m",
            id_proveedor=self.id_proveedor,
            stock_actual=10,
            stock_minimo=5,
            precio_costo=2000.0,
            precio_venta=3500.0,
        )
        RepositorioStock.guardar_producto(prod)
        assert prod.id_producto is not None

        nuevo_subido = RepositorioStock.ajustar_stock(prod.id_producto, 5)
        self.assertEqual(nuevo_subido, 15)

        nuevo_bajado = RepositorioStock.ajustar_stock(prod.id_producto, -8)
        self.assertEqual(nuevo_bajado, 7)

        with self.assertRaises(ValueError):
            RepositorioStock.ajustar_stock(prod.id_producto, -20)


class TestInterfazInventarioRBAC(unittest.TestCase):
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

    def _crear_vista(self, usuario_actual=None) -> InterfazInventario:
        with (
            patch.object(
                RepositorioStock, "listar_proveedores_activos", return_value=[]
            ),
            patch.object(RepositorioStock, "listar_productos", return_value=[]),
        ):
            vista = InterfazInventario(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_roles_habilitados_para_gestionar_inventario(self) -> None:
        for rol in ("Admin", "Gerente"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_gestionar_inventario)
                    self.assertEqual(str(vista.btn_guardar["state"]), "normal")
                finally:
                    vista.destroy()

    def test_roles_no_habilitados_bloqueados_para_gestionar_inventario(self) -> None:
        for rol in ("Administrativo", "Vendedor"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertFalse(vista.puede_gestionar_inventario)
                    self.assertEqual(str(vista.btn_guardar["state"]), "disabled")

                    with (
                        patch.object(
                            RepositorioStock, "guardar_producto"
                        ) as mock_guardar,
                        patch.object(
                            RepositorioStock, "cambiar_estado_producto"
                        ) as mock_estado,
                        patch("vistas.ui_inventario.messagebox.showwarning") as mock_warn,
                    ):
                        vista.var_codigo.set("INV-999")
                        vista.var_descripcion.set("Producto Bloqueado")
                        vista.guardar_producto()
                        mock_guardar.assert_not_called()
                        mock_warn.assert_called_once()

                        vista.producto_seleccionado_id = 1
                        vista.toggle_estado_producto()
                        mock_estado.assert_not_called()
                finally:
                    vista.destroy()


if __name__ == "__main__":
    unittest.main()