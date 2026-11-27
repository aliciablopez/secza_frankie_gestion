"""
===============================================================================
MÓDULO DE VISTAS: VENTANA DE LOGIN (vistas/ui_login.py)
===============================================================================
Interfaz de inicio de sesión desacoplada de la navegación posterior.
===============================================================================
"""

from typing import Callable, Optional
import tkinter as tk
from tkinter import messagebox, ttk

from vistas.estilos import COLOR_FONDO, aplicar_estilos_base


class VentanaLogin:
    """
    Formulario de inicio de sesión del Sistema Frankie.
    Delega la autenticación y la navegación a un callback externo.
    """

    def __init__(
        self,
        root: tk.Misc,
        on_autenticar: Callable[[str, str], Optional[object]],
        on_login_exitoso: Callable[[object], None],
    ) -> None:
        self.root = root
        self.on_autenticar = on_autenticar
        self.on_login_exitoso = on_login_exitoso

        aplicar_estilos_base(self.root)
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.configure(bg=COLOR_FONDO)

        self.var_usuario = tk.StringVar()
        self.var_password = tk.StringVar()
        self.btn_login: Optional[ttk.Button] = None

        self._crear_interfaz()

    def _crear_interfaz(self) -> None:
        contenedor = ttk.Frame(self.root, padding=24)
        contenedor.pack(fill="both", expand=True)

        lbl_titulo = ttk.Label(
            contenedor,
            text="SISTEMA FRANKIE",
            style="Subtitulo.TLabel",
        )
        lbl_titulo.pack(pady=(8, 4))

        lbl_subtitulo = ttk.Label(
            contenedor,
            text="Ingrese sus credenciales de acceso",
            style="Muted.TLabel",
        )
        lbl_subtitulo.pack(pady=(0, 20))

        ttk.Label(contenedor, text="Usuario:").pack(anchor="w", pady=(0, 4))
        entry_user = ttk.Entry(contenedor, textvariable=self.var_usuario, width=32)
        entry_user.pack(pady=(0, 12), fill="x", ipady=3)

        ttk.Label(contenedor, text="Contraseña:").pack(anchor="w", pady=(0, 4))
        entry_pass = ttk.Entry(
            contenedor,
            textvariable=self.var_password,
            show="*",
            width=32,
        )
        entry_pass.pack(pady=(0, 20), fill="x", ipady=3)

        entry_user.bind("<Return>", lambda _event: entry_pass.focus_set())
        entry_pass.bind("<Return>", lambda _event: self.intentar_login())
        entry_user.focus_set()

        self.btn_login = ttk.Button(
            contenedor,
            text="Ingresar al Sistema",
            command=self.intentar_login,
        )
        self.btn_login.pack(fill="x", ipady=6)

    def intentar_login(self) -> None:
        """Valida campos mínimos y solicita autenticación al controlador."""
        username = self.var_usuario.get().strip()
        password = self.var_password.get()

        if not username or not password.strip():
            messagebox.showwarning(
                "Campos incompletos",
                "Por favor, ingrese usuario y contraseña.",
                parent=self.root,
            )
            return

        if self.btn_login is not None:
            self.btn_login.state(["disabled"])

        try:
            usuario_valido = self.on_autenticar(username, password)
        except (RuntimeError, ValueError, OSError) as exc:
            messagebox.showerror(
                "Error de conexión",
                f"No se pudo verificar la autenticación: {exc}",
                parent=self.root,
            )
            return
        finally:
            if self.btn_login is not None and self.btn_login.winfo_exists():
                self.btn_login.state(["!disabled"])

        if usuario_valido:
            nombre = getattr(usuario_valido, "username", username)
            messagebox.showinfo(
                "Acceso concedido",
                f"¡Bienvenido/a, {nombre}!",
                parent=self.root,
            )
            self.var_password.set("")
            self.on_login_exitoso(usuario_valido)
        else:
            messagebox.showerror(
                "Acceso denegado",
                "Usuario o contraseña incorrectos.",
                parent=self.root,
            )
            self.var_password.set("")