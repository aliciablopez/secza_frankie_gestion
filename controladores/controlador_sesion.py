"""
===============================================================================
MÓDULO DE CONTROLADORES: SESIÓN Y NAVEGACIÓN (controladores/controlador_sesion.py)
===============================================================================
Coordina la autenticación con el repositorio core y el cambio de vistas
sobre la ventana principal de la aplicación.
===============================================================================
"""

from typing import Optional
import tkinter as tk

from infraestructura.repo_core import RepoCore
from vistas.estilos import COLOR_FONDO, aplicar_estilos_base
from vistas.ui_login import VentanaLogin
from vistas.ui_panel import PanelPrincipal


class ControladorSesion:
    """Gestiona el ciclo de autenticación y el cambio entre login y panel."""

    def __init__(self, root: tk.Misc, repo: Optional[RepoCore] = None) -> None:
        self.root = root
        self.repo = repo if repo is not None else RepoCore()
        self.usuario_actual: Optional[object] = None

    def mostrar_login(self) -> None:
        """Configura la ventana para el inicio de sesión y monta VentanaLogin."""
        self.usuario_actual = None
        self._limpiar_ventana()

        aplicar_estilos_base(self.root)

        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.configure(bg=COLOR_FONDO)
            self.root.minsize(0, 0)
            self.root.columnconfigure(0, weight=0)
            self.root.columnconfigure(1, weight=0)
            self.root.rowconfigure(0, weight=0)
            self.root.title("Frankie - Iniciar Sesión")
            self.root.geometry("420x350")
            self.root.resizable(False, False)

        VentanaLogin(
            self.root,
            on_autenticar=self._autenticar,
            on_login_exitoso=self.mostrar_panel_principal,
        )

    def mostrar_panel_principal(self, usuario: object) -> None:
        """Configura la ventana para el Panel Principal tras autenticar."""
        self.usuario_actual = usuario
        self._limpiar_ventana()

        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.resizable(True, True)
            self.root.columnconfigure(0, weight=0)
            self.root.columnconfigure(1, weight=1)
            self.root.rowconfigure(0, weight=1)

        PanelPrincipal(
            self.root,
            usuario_actual=usuario,
            on_cerrar_sesion=self.mostrar_login,
        )

    def _autenticar(self, username: str, password: str) -> Optional[object]:
        return self.repo.autenticar(username, password)

    def _limpiar_ventana(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()