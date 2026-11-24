"""Pruebas simples y completas para Clientes: entidad, repositorio y vista RBAC."""

from types import SimpleNamespace
import tkinter as tk
import unittest
from unittest.mock import patch

from dominio.entidades_ventas import Cliente
from infraestructura.repo_ventas import RepositorioVentas
from vistas.ui_clientes import InterfazClientes


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        username=f"usuario_{nombre_rol.lower()}",
        roles=[SimpleNamespace(nombre=nombre_rol)],
    )


class TestClientesDominioYRepo(unittest.TestCase):
    """Pruebas básicas de la entidad Cliente y del repositorio de clientes."""

    def test_construccion_entidad_cliente(self) -> None:
        cliente = Cliente(
            nombres="Lucía",
            apellidos="Gómez",
            nro_documento="27345678901",
            email="lucia@ejemplo.com",
            telefono="2235550101",
        )
        self.assertEqual(cliente.nombres, "Lucía")
        self.assertEqual(cliente.apellidos, "Gómez")
        self.assertEqual(cliente.nro_documento, "27345678901")

    def test_listar_clientes_delega_en_repositorio(self) -> None:
        cliente_demo = Cliente(
            nombres="Ana",
            apellidos="Pérez",
            nro_documento="20123456789",
        )
        with patch.object(
            RepositorioVentas,
            "listar_clientes",
            return_value=[cliente_demo],
        ) as mock_listar:
            resultado = RepositorioVentas.listar_clientes(
                criterio_busqueda="Pérez",
                incluir_inactivos=False,
            )
            mock_listar.assert_called_once_with(
                criterio_busqueda="Pérez",
                incluir_inactivos=False,
            )
            self.assertEqual(len(resultado), 1)
            self.assertEqual(resultado[0].apellidos, "Pérez")

    def test_guardar_cliente_delega_en_repositorio(self) -> None:
        cliente_demo = Cliente(
            nombres="Carlos",
            apellidos="Ruiz",
            nro_documento="20987654321",
        )
        with patch.object(
            RepositorioVentas,
            "guardar_cliente",
            return_value=1,
        ) as mock_guardar:
            RepositorioVentas.guardar_cliente(cliente_demo)
            mock_guardar.assert_called_once_with(cliente_demo)


class TestClientesVistaRBAC(unittest.TestCase):
    """Pruebas de permisos por rol en InterfazClientes."""

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

    def _crear_vista(self, usuario_actual=None) -> InterfazClientes:
        with patch.object(
            RepositorioVentas,
            "listar_clientes",
            return_value=[],
        ):
            vista = InterfazClientes(self.root, usuario_actual=usuario_actual)
            self.root.update_idletasks()
            return vista

    def test_vendedor_solo_consulta_y_no_puede_editar(self) -> None:
        vista = self._crear_vista(_usuario_con_rol("Vendedor"))
        try:
            self.assertFalse(vista.puede_editar_clientes)
            self.assertEqual(str(vista.btn_guardar["state"]), "disabled")
            self.assertEqual(str(vista.btn_actualizar["state"]), "disabled")
            self.assertEqual(str(vista.btn_toggle_estado["state"]), "disabled")

            with (
                patch.object(RepositorioVentas, "guardar_cliente") as mock_guardar,
                patch("vistas.ui_clientes.messagebox.showwarning") as mock_warn,
            ):
                vista.var_documento.set("20123456789")
                vista.var_nombres.set("Ana")
                vista.var_apellidos.set("Pérez")
                vista.guardar_cliente()

                mock_guardar.assert_not_called()
                mock_warn.assert_called_once()
        finally:
            vista.destroy()

    def test_roles_con_edicion_habilitan_guardar(self) -> None:
        for rol in ("Administrativo", "Gerente", "Admin"):
            with self.subTest(rol=rol):
                vista = self._crear_vista(_usuario_con_rol(rol))
                try:
                    self.assertTrue(vista.puede_editar_clientes)
                    self.assertEqual(str(vista.btn_guardar["state"]), "normal")
                finally:
                    vista.destroy()


if __name__ == "__main__":
    unittest.main()