"""
===============================================================================
PRUEBAS UNITARIAS Y DE INTEGRACIÓN: MÓDULO HABERES (tests/test_haberes.py)
===============================================================================
Compatible con `unittest` y `pytest`.
Aisla SQLite y la carpeta de recibos en directorios temporales sin modificar
la base ni los comprobantes reales del proyecto.
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

from dominio.entidades_haberes import LiquidacionHaberes
from infraestructura.conexion import ConexionDB
from infraestructura.repo_haberes import RepositorioHaberes
from vistas.ui_haberes import InterfazHaberes

ESQUEMA_OFICIAL_HABERES = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_persona TEXT NOT NULL DEFAULT 'Fisica' CHECK (tipo_persona IN ('Fisica', 'Juridica')),
    nombres TEXT,
    apellidos TEXT,
    razon_social TEXT,
    tipo_documento TEXT NOT NULL DEFAULT 'CUIL' CHECK (tipo_documento IN ('DNI', 'CUIT', 'CUIL', 'Pasaporte')),
    nro_documento TEXT NOT NULL UNIQUE,
    telefono TEXT,
    email TEXT,
    domicilio TEXT,
    ciudad TEXT,
    provincia TEXT,
    codigo_postal TEXT
);

CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    legajo TEXT NOT NULL UNIQUE,
    cargo TEXT NOT NULL DEFAULT 'Empleado',
    sector TEXT NOT NULL DEFAULT 'Administración',
    tipo_vinculo TEXT NOT NULL DEFAULT 'Permanente',
    sueldo REAL NOT NULL DEFAULT 0.0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS liquidaciones_haberes (
    id_liquidacion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empleado INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    sueldo_basico REAL NOT NULL DEFAULT 0.0,
    total_remunerativo REAL NOT NULL DEFAULT 0.0,
    total_no_remunerativo REAL NOT NULL DEFAULT 0.0,
    total_descuentos REAL NOT NULL DEFAULT 0.0,
    neto_a_cobrar REAL NOT NULL DEFAULT 0.0,
    UNIQUE(id_empleado, periodo),
    FOREIGN KEY (id_empleado) REFERENCES empleados(id) ON DELETE CASCADE
);
"""


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestRepositorioHaberes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

        carpeta_db_temp = self.tmp_path / "db"
        carpeta_db_temp.mkdir(parents=True, exist_ok=True)
        self.db_temp = carpeta_db_temp / "frankie_gestor.db"

        with sqlite3.connect(self.db_temp) as conn:
            conn.executescript(ESQUEMA_OFICIAL_HABERES)

        original_init = ConexionDB.__init__
        db_objetivo = self.db_temp

        def _init_aislado(self_conexion, ruta_db=None):
            original_init(
                self_conexion,
                ruta_db if ruta_db is not None else db_objetivo,
            )

        self._patch_conexion = patch.object(ConexionDB, "__init__", _init_aislado)
        self._patch_conexion.start()
        self.repo = RepositorioHaberes()

    def tearDown(self) -> None:
        self._patch_conexion.stop()
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def _insertar_empleado(
        self,
        legajo: str = "L001",
        cuil: str = "20324567891",
        nombres: str = "Martín",
        apellidos: str = "Gómez",
        sueldo: float = 500000.0,
    ) -> int:
        with sqlite3.connect(self.db_temp) as conn:
            cur_p = conn.execute(
                """
                INSERT INTO personas (tipo_persona, nombres, apellidos, tipo_documento, nro_documento)
                VALUES ('Fisica', ?, ?, 'CUIL', ?)
                """,
                (nombres, apellidos, cuil),
            )
            id_persona = int(cur_p.lastrowid or 0)
            cur_e = conn.execute(
                """
                INSERT INTO empleados (id_persona, legajo, cargo, sector, tipo_vinculo, sueldo, activo)
                VALUES (?, ?, 'Analista', 'Administración', 'Permanente', ?, 1)
                """,
                (id_persona, legajo, sueldo),
            )
            conn.commit()
            return int(cur_e.lastrowid or 0)

    def test_calcular_liquidacion_persiste_y_actualiza_mismo_periodo(self) -> None:
        id_emp = self._insertar_empleado(sueldo=500000.0)

        primera = self.repo.calcular_liquidacion(
            id_empleado=id_emp,
            periodo="2026-11",
            basico=500000.0,
            antiguedad_anios=3,
            aplica_presentismo=True,
            horas_extra=0.0,
            feriados=0.0,
            ventas=0.0,
            adelanto=20000.0,
        )
        self.assertGreater(primera["remunerativo"], 500000.0)
        self.assertGreater(primera["descuentos"], 20000.0)
        self.assertGreater(primera["neto"], 0.0)

        # Recalcular el mismo empleado y período debe hacer UPSERT (1 sola fila)
        segunda = self.repo.calcular_liquidacion(
            id_empleado=id_emp,
            periodo="2026-11",
            basico=500000.0,
            antiguedad_anios=3,
            aplica_presentismo=True,
            horas_extra=0.0,
            feriados=0.0,
            ventas=100000.0,
            adelanto=0.0,
        )
        self.assertGreater(segunda["remunerativo"], primera["remunerativo"])

        listado = self.repo.listar_liquidaciones(id_empleado=id_emp)
        self.assertEqual(len(listado), 1)
        self.assertIsInstance(listado[0], LiquidacionHaberes)
        self.assertEqual(listado[0].periodo, "2026-11")
        self.assertAlmostEqual(
            listado[0].neto_a_cobrar, segunda["neto"], places=2
        )

    def test_guardar_y_listar_liquidaciones_multiples_empleados(self) -> None:
        id_emp1 = self._insertar_empleado(
            legajo="L010", cuil="20311222334", nombres="Ana", apellidos="Pérez"
        )
        id_emp2 = self._insertar_empleado(
            legajo="L020", cuil="27334445556", nombres="Luis", apellidos="Díaz"
        )

        liq1 = LiquidacionHaberes(
            id_empleado=id_emp1,
            periodo="2026-10",
            sueldo_basico=400000.0,
            total_remunerativo=440000.0,
            total_no_remunerativo=0.0,
            total_descuentos=85800.0,
            neto_a_cobrar=354200.0,
        )
        liq2 = LiquidacionHaberes(
            id_empleado=id_emp2,
            periodo="2026-10",
            sueldo_basico=450000.0,
            total_remunerativo=495000.0,
            total_no_remunerativo=0.0,
            total_descuentos=96525.0,
            neto_a_cobrar=398475.0,
        )

        id_guardado1 = self.repo.guardar_liquidacion(liq1)
        id_guardado2 = self.repo.guardar_liquidacion(liq2)
        self.assertGreater(id_guardado1, 0)
        self.assertGreater(id_guardado2, id_guardado1)

        todas = self.repo.listar_liquidaciones()
        self.assertEqual(len(todas), 2)

        solo_emp2 = self.repo.listar_liquidaciones(id_empleado=id_emp2)
        self.assertEqual(len(solo_emp2), 1)
        self.assertEqual(solo_emp2[0].id_empleado, id_emp2)


class TestInterfazHaberesRBAC(unittest.TestCase):
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

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.carpeta_recibos_temp = Path(self._tmpdir.name) / "recibo_haberes"
        self.carpeta_recibos_temp.mkdir(parents=True, exist_ok=True)
        self._patch_recibos = patch(
            "vistas.ui_haberes._obtener_carpeta_recibos_haberes",
            return_value=self.carpeta_recibos_temp,
        )
        self._patch_recibos.start()

    def tearDown(self) -> None:
        self._patch_recibos.stop()
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def _crear_vista(self, usuario_actual=None) -> InterfazHaberes:
        empleado_demo = SimpleNamespace(
            id_empleado=1,
            legajo="L001",
            apellidos="Gómez",
            nombres="Martín",
            nro_documento="20324567891",
            cargo="Analista",
            sueldo=500000.0,
        )
        with (
            patch(
                "vistas.ui_haberes.RepositorioRRHH.listar_empleados",
                return_value=[empleado_demo],
            ),
            patch.object(
                RepositorioHaberes, "listar_liquidaciones", return_value=[]
            ),
        ):
            vista = InterfazHaberes(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_roles_habilitados_para_liquidar(self) -> None:
        for rol in ("Admin", "Gerente"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_liquidar)
                    self.assertEqual(
                        str(vista.btn_calcular_guardar["state"]), "normal"
                    )
                finally:
                    vista.destroy()

    def test_roles_no_habilitados_bloqueados_para_liquidar(self) -> None:
        for rol in ("Administrativo", "Vendedor"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertFalse(vista.puede_liquidar)
                    self.assertEqual(
                        str(vista.btn_calcular_guardar["state"]), "disabled"
                    )

                    with (
                        patch.object(
                            RepositorioHaberes, "calcular_liquidacion"
                        ) as mock_calc,
                        patch("vistas.ui_haberes.messagebox.showwarning") as mock_warn,
                    ):
                        vista._calcular_y_guardar()
                        mock_calc.assert_not_called()
                        mock_warn.assert_called_once()
                finally:
                    vista.destroy()


if __name__ == "__main__":
    unittest.main()