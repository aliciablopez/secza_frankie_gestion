"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO 2 - RRHH Y HABERES (tests/test_rrhh.py)
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

# Raíz del proyecto (donde están dominio/, infraestructura/, controladores/, vistas/)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from dominio.entidades_haberes import LiquidacionHaberes
from dominio.entidades_persona import limpiar_documento
from dominio.entidades_rrhh import Empleado
from infraestructura.conexion import ConexionDB
from infraestructura.repo_haberes import RepositorioHaberes
from infraestructura.repo_rrhh import RepositorioRRHH
from vistas.ui_empleados import InterfazEmpleados

ESQUEMA_OFICIAL_RRHH_HABERES = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS usuarios_roles (
    id_usuario INTEGER NOT NULL,
    id_rol INTEGER NOT NULL,
    PRIMARY KEY (id_usuario, id_rol),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (id_rol) REFERENCES roles(id) ON DELETE CASCADE
);

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
    codigo_postal TEXT,
    CONSTRAINT chk_tipo_persona CHECK (
        (tipo_persona = 'Fisica' AND nombres IS NOT NULL AND apellidos IS NOT NULL AND razon_social IS NULL) OR
        (tipo_persona = 'Juridica' AND razon_social IS NOT NULL AND nombres IS NULL AND apellidos IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    id_usuario INTEGER UNIQUE,
    legajo TEXT NOT NULL UNIQUE,
    cargo TEXT NOT NULL DEFAULT 'Vendedor' CHECK (cargo IN (
        'Vendedor',
        'Administrativo',
        'Gerente',
        'Admin'
    )),
    sector TEXT NOT NULL DEFAULT 'Ventas' CHECK (sector IN (
        'Ventas',
        'Gestión',
        'Staff',
        'Compras',
        'Administración'
    )),
    tipo_vinculo TEXT NOT NULL DEFAULT 'Contratado' CHECK (tipo_vinculo IN (
        'Contratado',
        'Propietario',
        'Pasante',
        'Permanente'
    )),
    sueldo REAL NOT NULL DEFAULT 0.0 CHECK (sueldo >= 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS liquidaciones_haberes (
    id_liquidacion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empleado INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    sueldo_basico REAL NOT NULL CHECK (sueldo_basico >= 0),
    total_remunerativo REAL NOT NULL CHECK (total_remunerativo >= 0),
    total_no_remunerativo REAL NOT NULL DEFAULT 0.0 CHECK (total_no_remunerativo >= 0),
    total_descuentos REAL NOT NULL CHECK (total_descuentos >= 0),
    neto_a_cobrar REAL NOT NULL CHECK (neto_a_cobrar >= 0),
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_empleado, periodo),
    FOREIGN KEY (id_empleado) REFERENCES empleados(id) ON DELETE RESTRICT
);
"""


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestModuloRRHHYHaberes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        with sqlite3.connect(self.db_temp) as conn:
            conn.executescript(ESQUEMA_OFICIAL_RRHH_HABERES)

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

    def test_limpiar_documento_y_entidad_empleado(self) -> None:
        self.assertEqual(limpiar_documento("20-35123456-9"), "20351234569")

        emp = Empleado(
            nro_documento="20-35123456-9",
            nombres="Ana",
            apellidos="Gomez",
            legajo="E001",
            cargo="Administrativo",
            sector="Administración",
            tipo_vinculo="Permanente",
        )
        emp.sueldo = 500000.0
        self.assertEqual(emp.nro_documento, "20351234569")
        self.assertEqual(emp.obtener_nombre_completo(), "Gomez, Ana")
        self.assertTrue(emp.es_permanente)
        self.assertFalse(emp.requiere_factura)
        self.assertAlmostEqual(emp.sueldo, 500000.0, places=2)

    def test_calculo_totales_en_entidad_liquidacion(self) -> None:
        liq = LiquidacionHaberes(
            id_empleado=1,
            periodo="2026-11",
            sueldo_basico=400000.0,
            presentismo_monto=33320.0,
            jubilacion=47665.2,
            adelantos=10000.0,
        )
        liq.calcular_totales()
        self.assertAlmostEqual(liq.total_remunerativo, 433320.0, places=2)
        self.assertAlmostEqual(liq.total_descuentos, 57665.2, places=2)
        self.assertAlmostEqual(liq.neto_a_cobrar, 375654.8, places=2)
        self.assertEqual(liq.periodo_formateado, "Mes 11 / Año 2026")

    def test_crear_actualizar_listar_y_baja_logica_empleado(self) -> None:
        emp1 = Empleado(
            nro_documento="30112233",
            nombres="Lucas",
            apellidos="Perez",
            legajo="",
            cargo="Vendedor",
            sector="Ventas",
            tipo_vinculo="Contratado",
        )
        self.assertTrue(RepositorioRRHH.crear_empleado(emp1))
        assert emp1.id_empleado is not None
        id_emp1: int = int(emp1.id_empleado)
        self.assertEqual(emp1.legajo, "E001")

        emp2 = Empleado(
            nro_documento="33445566",
            nombres="Sofia",
            apellidos="Diaz",
            legajo="",
            cargo="Gerente",
            sector="Gestión",
            tipo_vinculo="Permanente",
        )
        self.assertTrue(RepositorioRRHH.crear_empleado(emp2))
        assert emp2.id_empleado is not None
        id_emp2: int = int(emp2.id_empleado)
        self.assertEqual(emp2.legajo, "E002")

        emp1.cargo = "Administrativo"
        emp1.sector = "Administración"
        self.assertTrue(RepositorioRRHH.guardar_empleado(emp1))
        actualizado = RepositorioRRHH.obtener_empleado_por_id(id_emp1)
        self.assertIsNotNone(actualizado)
        assert actualizado is not None
        self.assertEqual(actualizado.cargo, "Administrativo")
        self.assertGreaterEqual(actualizado.sueldo, 0.0)

        self.assertTrue(RepositorioRRHH.cambiar_estado_empleado(id_emp1, False))
        activos = RepositorioRRHH.listar_empleados(incluir_inactivos=False)
        todos = RepositorioRRHH.listar_empleados(incluir_inactivos=True)
        self.assertEqual(len(activos), 1)
        self.assertEqual(len(todos), 2)

        busqueda = RepositorioRRHH.listar_empleados(criterio_busqueda="Sofia")
        self.assertEqual(len(busqueda), 1)
        self.assertEqual(busqueda[0].id_empleado, id_emp2)

    def test_calcular_upsert_guardar_y_listar_liquidacion_en_repo(self) -> None:
        emp = Empleado(
            nro_documento="35998877",
            nombres="Martin",
            apellidos="Lopez",
            legajo="",
        )
        emp.sueldo = 500000.0
        RepositorioRRHH.crear_empleado(emp)
        assert emp.id_empleado is not None
        id_emp: int = int(emp.id_empleado)

        repo_hab = RepositorioHaberes()
        resultado = repo_hab.calcular_liquidacion(
            id_empleado=id_emp,
            periodo="2026-11",
            basico=500000.0,
            antiguedad_anios=2,
            aplica_presentismo=False,
            adelanto=20000.0,
        )
        self.assertGreater(resultado["remunerativo"], 500000.0)
        self.assertGreater(resultado["neto"], 0.0)

        # Recalcular mismo empleado y período actualiza sin duplicar fila
        resultado_actualizado = repo_hab.calcular_liquidacion(
            id_empleado=id_emp,
            periodo="2026-11",
            basico=520000.0,
            antiguedad_anios=2,
            aplica_presentismo=False,
            adelanto=20000.0,
        )
        self.assertGreater(
            resultado_actualizado["remunerativo"], resultado["remunerativo"]
        )

        historial_nov = repo_hab.listar_liquidaciones(id_empleado=id_emp)
        liq_nov = [item for item in historial_nov if item.periodo == "2026-11"]
        self.assertEqual(len(liq_nov), 1)
        self.assertAlmostEqual(liq_nov[0].sueldo_basico, 520000.0, places=2)

        nueva_liq = LiquidacionHaberes(
            id_empleado=id_emp,
            periodo="2026-12",
            sueldo_basico=550000.0,
            total_remunerativo=550000.0,
            total_descuentos=90000.0,
            neto_a_cobrar=460000.0,
        )
        liq_id = repo_hab.guardar_liquidacion(nueva_liq)
        assert liq_id is not None
        id_liq: int = int(liq_id)
        self.assertGreater(id_liq, 0)
        self.assertEqual(len(repo_hab.listar_liquidaciones(id_empleado=id_emp)), 2)


class TestInterfazEmpleadosRBAC(unittest.TestCase):
    """Pruebas de permisos RBAC en InterfazEmpleados."""

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

    def _crear_vista(self, usuario_actual=None) -> InterfazEmpleados:
        with (
            patch.object(RepositorioRRHH, "listar_empleados", return_value=[]),
            patch.object(
                RepositorioRRHH, "generar_siguiente_legajo", return_value="E001"
            ),
        ):
            vista = InterfazEmpleados(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_administrativo_y_vendedor_bloqueados(self) -> None:
        for rol in ("Administrativo", "Vendedor"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertFalse(vista.puede_gestionar_empleados)
                    self.assertEqual(str(vista.btn_guardar["state"]), "disabled")
                    self.assertEqual(str(vista.btn_editar["state"]), "disabled")
                    self.assertEqual(str(vista.btn_estado["state"]), "disabled")

                    with (
                        patch.object(RepositorioRRHH, "crear_empleado") as mock_crear,
                        patch(
                            "vistas.ui_empleados.messagebox.showwarning"
                        ) as mock_warn,
                    ):
                        vista.txt_nombres.insert(0, "Ana")
                        vista.txt_apellidos.insert(0, "Pérez")
                        vista.txt_documento.insert(0, "20123456789")
                        vista._guardar_empleado()

                        mock_crear.assert_not_called()
                        mock_warn.assert_called_once()
                finally:
                    vista.destroy()

    def test_admin_y_gerente_habilitados(self) -> None:
        for rol in ("Admin", "Gerente"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_gestionar_empleados)
                    self.assertEqual(str(vista.btn_guardar["state"]), "normal")
                    self.assertEqual(str(vista.btn_editar["state"]), "normal")
                    self.assertEqual(str(vista.btn_estado["state"]), "normal")
                finally:
                    vista.destroy()


if __name__ == "__main__":
    unittest.main()