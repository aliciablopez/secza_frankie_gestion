"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO FACTURACIÓN Y VENTAS (tests/test_ventas.py)
===============================================================================
Compatible con `unittest` y `pytest`.
Aisla SQLite en un directorio temporal sin modificar la base real del proyecto.
Nota de diseño de prueba: el esquema temporal de test no define triggers SQLite
sobre `facturas_detalles`, validando directamente el flujo de `RepositorioVentas`
y los permisos RBAC de `InterfazFacturacion`.
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

from dominio.entidades_ventas import Cliente, limpiar_documento
from infraestructura.conexion import ConexionDB
from infraestructura.repo_ventas import RepositorioVentas
from vistas.ui_facturacion import InterfazFacturacion

ESQUEMA_OFICIAL_VENTAS = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_persona TEXT NOT NULL CHECK (tipo_persona IN ('Fisica', 'Juridica')),
    nombres TEXT,
    apellidos TEXT,
    razon_social TEXT,
    tipo_documento TEXT NOT NULL CHECK (tipo_documento IN ('DNI', 'CUIT', 'CUIL', 'Pasaporte')),
    nro_documento TEXT NOT NULL UNIQUE,
    telefono TEXT,
    email TEXT,
    domicilio TEXT,
    ciudad TEXT,
    provincia TEXT,
    codigo_postal TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    fecha_alta TEXT DEFAULT CURRENT_TIMESTAMP,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    legajo TEXT NOT NULL UNIQUE,
    cargo TEXT NOT NULL DEFAULT 'Vendedor',
    sector TEXT NOT NULL DEFAULT 'Ventas',
    tipo_vinculo TEXT NOT NULL DEFAULT 'Permanente',
    sueldo REAL NOT NULL DEFAULT 0.0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    categoria TEXT,
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 0,
    precio_venta REAL NOT NULL DEFAULT 0.0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    id_vendedor INTEGER NOT NULL,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    total REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_vendedor) REFERENCES empleados(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS facturas_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_factura INTEGER NOT NULL,
    id_producto INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario REAL NOT NULL,
    descuento_porcentaje REAL NOT NULL DEFAULT 0.0,
    subtotal REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (id_factura) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id) ON DELETE RESTRICT
);
"""


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestModuloVentasYFacturacion(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        with sqlite3.connect(self.db_temp) as conn:
            conn.executescript(ESQUEMA_OFICIAL_VENTAS)

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

    def _poblar_vendedor_y_producto(
        self,
        legajo: str = "E001",
        cuil_vendedor: str = "20301112223",
        nombre_vendedor: str = "Carlos",
        apellido_vendedor: str = "Sosa",
        codigo_prod: str = "P001",
        desc_prod: str = "Teclado Mecánico",
        stock: int = 20,
        precio: float = 10000.0,
    ) -> tuple[int, int]:
        with sqlite3.connect(self.db_temp) as conn:
            cur_p = conn.execute(
                """
                INSERT INTO personas (tipo_persona, nombres, apellidos, tipo_documento, nro_documento)
                VALUES ('Fisica', ?, ?, 'CUIL', ?)
                """,
                (nombre_vendedor, apellido_vendedor, limpiar_documento(cuil_vendedor)),
            )
            id_persona_v = int(cur_p.lastrowid or 0)
            cur_e = conn.execute(
                """
                INSERT INTO empleados (id_persona, legajo, cargo, sector, tipo_vinculo, activo)
                VALUES (?, ?, 'Vendedor', 'Ventas', 'Permanente', 1)
                """,
                (id_persona_v, legajo),
            )
            id_vendedor = int(cur_e.lastrowid or 0)

            cur_pr = conn.execute(
                """
                INSERT INTO productos (codigo, descripcion, categoria, stock_actual, stock_minimo, precio_venta, activo)
                VALUES (?, ?, 'Periféricos', ?, 2, ?, 1)
                """,
                (codigo_prod, desc_prod, stock, precio),
            )
            id_producto = int(cur_pr.lastrowid or 0)
            conn.commit()
        return id_vendedor, id_producto

    def test_crud_cliente_y_cliente_frecuente(self) -> None:
        cli = Cliente(
            nro_documento="27-34567890-4",
            nombres="Lucía",
            apellidos="Méndez",
            tipo_documento="CUIT",
        )
        self.assertTrue(RepositorioVentas.guardar_cliente(cli))
        assert cli.id_cliente is not None
        id_cli: int = int(cli.id_cliente)

        id_vend, id_prod = self._poblar_vendedor_y_producto()
        items = [
            {
                "id_producto": id_prod,
                "codigo": "P001",
                "descripcion": "Teclado Mecánico",
                "cantidad": 1,
                "precio_lista": 10000.0,
            }
        ]

        with patch(
            "infraestructura.repo_ventas.config.MINIMO_COMPRAS_CLIENTE_FRECUENTE",
            2,
            create=True,
        ):
            for _ in range(2):
                RepositorioVentas.emitir_factura(id_cli, id_vend, "Efectivo", items)

            listado = RepositorioVentas.listar_clientes(criterio_busqueda="Méndez")
            self.assertEqual(len(listado), 1)
            self.assertEqual(listado[0]["compras_mes"], 2)
            self.assertTrue(listado[0]["es_frecuente"])

        self.assertTrue(RepositorioVentas.cambiar_estado_cliente(id_cli, False))
        self.assertEqual(
            len(RepositorioVentas.listar_clientes(incluir_inactivos=False)), 0
        )
        self.assertEqual(
            len(RepositorioVentas.listar_clientes(incluir_inactivos=True)), 1
        )

    def test_emision_factura_descuenta_stock_y_calcula_comisiones(self) -> None:
        cli = Cliente(
            nro_documento="27-29888777-6",
            nombres="Sofía",
            apellidos="Ríos",
            tipo_documento="CUIT",
        )
        RepositorioVentas.guardar_cliente(cli)
        assert cli.id_cliente is not None
        id_cli: int = int(cli.id_cliente)

        id_vend, id_prod = self._poblar_vendedor_y_producto(stock=15, precio=10000.0)
        items = [
            {
                "id_producto": id_prod,
                "codigo": "P001",
                "descripcion": "Teclado Mecánico",
                "cantidad": 5,
                "precio_lista": 10000.0,
            }
        ]

        factura = RepositorioVentas.emitir_factura(id_cli, id_vend, "Efectivo", items)
        self.assertIsNotNone(factura.id_factura)
        self.assertGreater(factura.total, 0.0)

        with sqlite3.connect(self.db_temp) as conn:
            fila = conn.execute(
                "SELECT stock_actual FROM productos WHERE id = ?", (id_prod,)
            ).fetchone()
        assert fila is not None
        self.assertEqual(int(fila[0]), 10)

        periodo_actual = factura.fecha[:7]
        comisiones = RepositorioVentas.calcular_comisiones_periodo(periodo_actual)
        self.assertIn(id_vend, comisiones)
        self.assertAlmostEqual(
            comisiones[id_vend]["ventas_mes"], factura.total, places=2
        )
        self.assertGreater(comisiones[id_vend]["bono_mejor_vendedor"], 0.0)


class TestInterfazFacturacionRBAC(unittest.TestCase):
    """Pruebas de permisos RBAC en InterfazFacturacion."""

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

    def _crear_vista(self, usuario_actual=None) -> InterfazFacturacion:
        with (
            patch.object(RepositorioVentas, "listar_clientes", return_value=[]),
            patch.object(
                RepositorioVentas, "listar_vendedores_activos", return_value=[]
            ),
            patch.object(
                RepositorioVentas, "listar_productos_venta", return_value=[]
            ),
        ):
            vista = InterfazFacturacion(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_roles_habilitados_para_emitir_factura(self) -> None:
        for rol in ("Admin", "Gerente", "Vendedor"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_emitir_factura)
                    self.assertEqual(str(vista.btn_emitir["state"]), "normal")
                finally:
                    vista.destroy()

    def test_rol_no_habilitado_bloqueado_para_emitir_factura(self) -> None:
        vista = self._crear_vista(_usuario_con_rol("Administrativo"))
        try:
            self.assertFalse(vista.puede_emitir_factura)
            self.assertEqual(str(vista.btn_emitir["state"]), "disabled")

            with (
                patch.object(RepositorioVentas, "emitir_factura") as mock_emitir,
                patch("vistas.ui_facturacion.messagebox.showwarning") as mock_warn,
            ):
                vista.items_factura.append(
                    {
                        "id_producto": 1,
                        "codigo": "P001",
                        "descripcion": "Item prueba",
                        "cantidad": 1,
                        "precio_unitario": 100.0,
                        "descuento_pct": 0.0,
                        "subtotal": 100.0,
                    }
                )
                vista.emitir_factura()
                mock_emitir.assert_not_called()
                mock_warn.assert_called_once()
        finally:
            vista.destroy()


if __name__ == "__main__":
    unittest.main()