"""
===============================================================================
MÓDULO DE PANEL PRINCIPAL (vistas/ui_panel.py)
===============================================================================
Orquestador visual principal con menú lateral, control RBAC y área de trabajo.
===============================================================================
"""

from typing import Any, Callable, Optional, Set
import tkinter as tk
from tkinter import messagebox, ttk

from controladores.controlador_core import ControladorCore
from vistas.estilos import (
    COLOR_TEXTO,
    FUENTE_BASE,
    FUENTE_TITULO,
    aplicar_estilos_base,
)

try:
    from vistas.ui_empleados import InterfazEmpleados
except ImportError:
    InterfazEmpleados = None

try:
    from vistas.ui_proveedores import InterfazProveedores
except ImportError:
    InterfazProveedores = None

try:
    from vistas.ui_inventario import InterfazInventario
except ImportError:
    InterfazInventario = None

try:
    from vistas.ui_haberes import InterfazHaberes
except ImportError:
    InterfazHaberes = None

try:
    from vistas.ui_clientes import InterfazClientes
except ImportError:
    InterfazClientes = None

try:
    from vistas.ui_facturacion import InterfazFacturacion
except ImportError:
    InterfazFacturacion = None

try:
    from vistas.ui_usuarios import VistaGestionUsuarios
except ImportError:
    VistaGestionUsuarios = None


def _normalizar_rol(nombre_rol: str) -> str:
    limpio = (nombre_rol or "").strip().lower()
    if limpio in {"admin", "administrador"}:
        return "admin"
    if limpio == "gerente":
        return "gerente"
    if limpio == "vendedor":
        return "vendedor"
    if limpio == "administrativo":
        return "administrativo"
    return limpio


def _obtener_roles_normalizados(usuario_actual: Any) -> Set[str]:
    roles: Set[str] = set()
    for rol in getattr(usuario_actual, "roles", None) or []:
        nombre = getattr(rol, "nombre", str(rol))
        norm = _normalizar_rol(nombre)
        if norm:
            roles.add(norm)
    username = str(getattr(usuario_actual, "username", "") or "").strip().lower()
    if username == "admin":
        roles.add("admin")
    return roles


class PanelPrincipal:
    """
    Ventana contenedora principal del sistema bajo arquitectura de menú lateral.
    """

    def __init__(
        self,
        root: tk.Misc,
        usuario_actual: Any,
        on_cerrar_sesion: Optional[Callable[[], None]] = None,
        controlador: Optional[ControladorCore] = None,
    ) -> None:
        self.root = root
        self.usuario_actual = usuario_actual
        self.on_cerrar_sesion = on_cerrar_sesion
        self.controlador = controlador if controlador is not None else ControladorCore()

        aplicar_estilos_base(self.root)

        roles = getattr(self.usuario_actual, "roles", []) or []
        roles_txt = ", ".join(r.nombre for r in roles) if roles else "Sin Roles"
        username = getattr(self.usuario_actual, "username", "Usuario")

        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title(f"Frankie Gestor Comercial - {username} [{roles_txt}]")
            self.root.geometry("1150x750")
            self.root.minsize(950, 650)

        self.pantalla_actual: Optional[tk.Misc] = None
        self._dibujar_interfaz(
            username=username,
            roles_txt=roles_txt,
        )

    def _dibujar_interfaz(
        self,
        username: str,
        roles_txt: str,
    ) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # =======================================================
        # MENÚ LATERAL (Izquierda)
        # =======================================================
        self.frame_menu = ttk.Frame(self.root, width=220, padding=12)
        self.frame_menu.grid(row=0, column=0, sticky="ns")
        self.frame_menu.grid_propagate(False)

        lbl_menu = ttk.Label(
            self.frame_menu,
            text="MENÚ",
            style="Subtitulo.TLabel",
        )
        lbl_menu.pack(pady=(10, 4), anchor="w")

        lbl_usuario = ttk.Label(
            self.frame_menu,
            text=f"{username} · {roles_txt}",
            style="Muted.TLabel",
            wraplength=190,
        )
        lbl_usuario.pack(pady=(0, 12), anchor="w")

        roles_norm = _obtener_roles_normalizados(self.usuario_actual)
        es_admin = "admin" in roles_norm

        btn_clientes = ttk.Button(
            self.frame_menu,
            text="Clientes",
            command=self.abrir_modulo_clientes,
        )
        btn_clientes.pack(fill="x", pady=4)

        btn_facturacion = ttk.Button(
            self.frame_menu,
            text="Facturación",
            command=self.abrir_modulo_facturacion,
        )
        btn_facturacion.pack(fill="x", pady=4)

        btn_personal = ttk.Button(
            self.frame_menu,
            text="Personal",
            command=self.abrir_modulo_rrhh,
        )
        btn_personal.pack(fill="x", pady=4)

        btn_haberes = ttk.Button(
            self.frame_menu,
            text="Haberes",
            command=self.abrir_modulo_haberes,
        )
        btn_haberes.pack(fill="x", pady=4)

        btn_proveedores = ttk.Button(
            self.frame_menu,
            text="Proveedores",
            command=self.abrir_modulo_proveedores,
        )
        btn_proveedores.pack(fill="x", pady=4)

        btn_inventario = ttk.Button(
            self.frame_menu,
            text="Inventario",
            command=self.abrir_modulo_inventario,
        )
        btn_inventario.pack(fill="x", pady=4)

        if es_admin:
            ttk.Separator(self.frame_menu, orient="horizontal").pack(fill="x", pady=10)
            btn_backup = ttk.Button(
                self.frame_menu,
                text="Backup",
                command=self.ejecutar_backup,
            )
            btn_backup.pack(fill="x", pady=4)

            btn_usuarios = ttk.Button(
                self.frame_menu,
                text="Usuarios",
                command=self.abrir_modulo_usuarios,
            )
            btn_usuarios.pack(fill="x", pady=4)

        ttk.Separator(self.frame_menu, orient="horizontal").pack(fill="x", pady=10)

        btn_salir = ttk.Button(
            self.frame_menu,
            text="Salir",
            command=self.cerrar_sesion,
        )
        btn_salir.pack(fill="x", pady=4)

        # =======================================================
        # ÁREA DE TRABAJO CENTRAL (Derecha)
        # =======================================================
        self.frame_contenido = ttk.Frame(self.root, padding=16)
        self.frame_contenido.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)

        tarjeta_bienvenida = ttk.Frame(
            self.frame_contenido,
            style="Card.TFrame",
            padding=28,
        )
        tarjeta_bienvenida.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            tarjeta_bienvenida,
            text=f"Bienvenido/a al Sistema Frankie, {username}",
            font=FUENTE_TITULO,
            justify="center",
        ).pack(pady=(0, 8))

        ttk.Label(
            tarjeta_bienvenida,
            text="Seleccione una opción del menú lateral para comenzar.",
            font=FUENTE_BASE,
            justify="center",
        ).pack()

    def limpiar_area_central(self) -> None:
        """Elimina la vista activa anterior."""
        for widget in self.frame_contenido.winfo_children():
            widget.destroy()
        self.pantalla_actual = None

    def _instanciar_vista(self, clase_vista: Any) -> Any:
        """Intenta pasar usuario_actual a la vista; si no lo acepta, hace fallback."""
        try:
            return clase_vista(self.frame_contenido, usuario_actual=self.usuario_actual)
        except TypeError:
            return clase_vista(self.frame_contenido)

    def gestionar_apertura(self, clase_vista: Any, mensaje_fallback: str) -> None:
        """Monta la vista seleccionada en el área central o muestra un aviso."""
        self.limpiar_area_central()
        if clase_vista is not None:
            try:
                vista = self._instanciar_vista(clase_vista)
                if hasattr(vista, "pack"):
                    vista.pack(fill="both", expand=True)
                elif hasattr(vista, "grid"):
                    vista.grid(row=0, column=0, sticky="nsew")
                self.pantalla_actual = vista
            except Exception as exc:
                self.mostrar_mensaje_estado(f"Error al cargar la vista: {exc}")
        else:
            self.mostrar_mensaje_estado(mensaje_fallback)

    def mostrar_mensaje_estado(self, texto: str) -> None:
        """Muestra una tarjeta centrada con un mensaje informativo o de estado."""
        tarjeta = ttk.Frame(self.frame_contenido, style="Card.TFrame", padding=24)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        lbl = ttk.Label(
            tarjeta,
            text=texto,
            foreground=COLOR_TEXTO,
            font=FUENTE_BASE,
            justify="center",
            wraplength=520,
        )
        lbl.pack()
        self.pantalla_actual = tarjeta

    def abrir_modulo_clientes(self) -> None:
        """Abre el módulo de clientes."""
        self.gestionar_apertura(
            InterfazClientes,
            "Módulo de Clientes no disponible.",
        )

    def abrir_modulo_facturacion(self) -> None:
        """Abre el módulo de facturación."""
        self.gestionar_apertura(
            InterfazFacturacion,
            "Módulo de Facturación no disponible.",
        )

    def abrir_modulo_rrhh(self) -> None:
        """Abre el módulo de empleados."""
        self.gestionar_apertura(InterfazEmpleados, "Módulo de Empleados no disponible.")

    def abrir_modulo_haberes(self) -> None:
        """Abre el módulo de liquidación de haberes."""
        self.gestionar_apertura(
            InterfazHaberes,
            "Módulo de Liquidación de Haberes no disponible.",
        )

    def abrir_modulo_proveedores(self) -> None:
        """Abre el módulo de proveedores."""
        self.gestionar_apertura(
            InterfazProveedores,
            "Módulo de Proveedores no disponible.",
        )

    def abrir_modulo_inventario(self) -> None:
        """Abre el módulo de inventario y control de stock."""
        self.gestionar_apertura(
            InterfazInventario,
            "Módulo de Inventario no disponible.",
        )

    def abrir_modulo_usuarios(self) -> None:
        """Abre el módulo de gestión de usuarios (restringido a admin)."""
        roles_norm = _obtener_roles_normalizados(self.usuario_actual)
        if "admin" not in roles_norm:
            self.mostrar_mensaje_estado("Acceso restringido: solo 'admin' puede administrar usuarios.")
            return
        self.gestionar_apertura(
            VistaGestionUsuarios,
            "Módulo de Usuarios no disponible.",
        )

    def ejecutar_backup(self) -> None:
        """Solicita al controlador core la generación de un respaldo del sistema."""
        try:
            resultado = self.controlador.ejecutar_backup()
        except Exception as exc:
            messagebox.showerror(
                "Error de Backup",
                f"No se pudo completar el backup: {exc}",
                parent=self.root,
            )
            return

        if "exitoso" in str(resultado).lower():
            messagebox.showinfo("Backup Completado", str(resultado), parent=self.root)
        else:
            messagebox.showerror("Error de Backup", str(resultado), parent=self.root)

    def cerrar_sesion(self) -> None:
        """Confirma el cierre de sesión y delega el retorno al login."""
        if messagebox.askyesno(
            "Salir",
            "¿Está seguro de que desea cerrar la sesión actual?",
            parent=self.root,
        ):
            if self.on_cerrar_sesion is not None:
                self.on_cerrar_sesion()
            elif isinstance(self.root, (tk.Tk, tk.Toplevel)):
                self.root.destroy()