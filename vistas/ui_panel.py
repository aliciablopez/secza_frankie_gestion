"""
===============================================================================
MÓDULO DE PANEL PRINCIPAL (vistas/ui_panel.py)
===============================================================================
Orquestador visual principal con menú lateral, control RBAC y área de trabajo.
===============================================================================
"""

from typing import Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox, ttk

from controladores.controlador_core import ControladorCore
from vistas.estilos import COLOR_TEXTO, FUENTE_BASE, aplicar_estilos_base

# Importaciones seguras de las vistas modulares del sistema
try:
    from vistas.ui_empleados import InterfazEmpleados
except ImportError:
    try:
        from src.vistas.ui_empleados import InterfazEmpleados
    except ImportError:
        InterfazEmpleados = None

try:
    from vistas.ui_proveedores import InterfazProveedores
except ImportError:
    try:
        from src.vistas.ui_proveedores import InterfazProveedores
    except ImportError:
        InterfazProveedores = None

try:
    from vistas.ui_inventario import InterfazInventario
except ImportError:
    try:
        from src.vistas.ui_inventario import InterfazInventario
    except ImportError:
        InterfazInventario = None

try:
    from vistas.ui_haberes import InterfazHaberes
except ImportError:
    try:
        from src.vistas.ui_haberes import InterfazHaberes
    except ImportError:
        InterfazHaberes = None

try:
    from vistas.ui_clientes import InterfazClientes
except ImportError:
    try:
        from src.vistas.ui_clientes import InterfazClientes
    except ImportError:
        InterfazClientes = None


class PanelPrincipal:
    """
    Ventana contenedora principal del sistema bajo arquitectura de menú lateral.
    """

    def __init__(
        self,
        root: tk.Misc,
        usuario_actual: Any,
        on_cerrar_sesion: Optional[Callable[[], None]] = None,
        orquestador: Optional[ControladorCore] = None,
    ) -> None:
        self.root = root
        self.usuario_actual = usuario_actual
        self.on_cerrar_sesion = on_cerrar_sesion
        self.orquestador = orquestador if orquestador is not None else ControladorCore()

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
            nombres_roles=[r.nombre for r in roles],
        )

    def _dibujar_interfaz(
        self,
        username: str,
        roles_txt: str,
        nombres_roles: list[str],
    ) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # =======================================================
        # MENÚ LATERAL (Izquierda)
        # =======================================================
        self.frame_menu = ttk.Frame(self.root, width=260, padding=12)
        self.frame_menu.grid(row=0, column=0, sticky="ns")
        self.frame_menu.grid_propagate(False)

        lbl_menu = ttk.Label(
            self.frame_menu,
            text="MENÚ PRINCIPAL",
            style="Subtitulo.TLabel",
        )
        lbl_menu.pack(pady=(10, 4), anchor="w")

        lbl_usuario = ttk.Label(
            self.frame_menu,
            text=f"{username} · {roles_txt}",
            style="Muted.TLabel",
            wraplength=230,
        )
        lbl_usuario.pack(pady=(0, 12), anchor="w")

        es_admin = "Administrador" in nombres_roles

        # Botones de Navegación Modular (12 pt sin negrita desde estilos.py)
        btn_rrhh = ttk.Button(
            self.frame_menu,
            text="👥 Padrón Empleados",
            command=self.abrir_modulo_rrhh,
        )
        btn_rrhh.pack(fill="x", pady=4)

        btn_haberes = ttk.Button(
            self.frame_menu,
            text="💰 Liquidación Haberes",
            command=self.abrir_modulo_haberes,
        )
        btn_haberes.pack(fill="x", pady=4)

        btn_proveedores = ttk.Button(
            self.frame_menu,
            text="🏭 Padrón Proveedores",
            command=self.abrir_modulo_proveedores,
        )
        btn_proveedores.pack(fill="x", pady=4)

        btn_inventario = ttk.Button(
            self.frame_menu,
            text="📦 Control de Stock",
            command=self.abrir_modulo_inventario,
        )
        btn_inventario.pack(fill="x", pady=4)

        btn_clientes = ttk.Button(
            self.frame_menu,
            text="🧑‍🤝‍🧑 Padrón Clientes",
            command=self.abrir_modulo_clientes,
        )
        btn_clientes.pack(fill="x", pady=4)

        ttk.Separator(self.frame_menu, orient="horizontal").pack(fill="x", pady=12)

        # Cerrar Sesión antes de Backup Sistema
        btn_salir = ttk.Button(
            self.frame_menu,
            text="🚪 Cerrar Sesión",
            command=self.cerrar_sesion,
        )
        btn_salir.pack(fill="x", pady=4)

        if es_admin:
            ttk.Separator(self.frame_menu, orient="horizontal").pack(fill="x", pady=12)
            btn_backup = ttk.Button(
                self.frame_menu,
                text="💾 Backup Sistema",
                command=self.ejecutar_backup,
            )
            btn_backup.pack(fill="x", pady=4)

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
            style="Subtitulo.TLabel",
            justify="center",
        ).pack(pady=(0, 8))

        ttk.Label(
            tarjeta_bienvenida,
            text="Seleccione una opción del menú lateral para comenzar.",
            style="Muted.TLabel",
            justify="center",
        ).pack()

    def limpiar_area_central(self) -> None:
        """Elimina la vista activa anterior."""
        for widget in self.frame_contenido.winfo_children():
            widget.destroy()
        self.pantalla_actual = None

    def gestionar_apertura(self, clase_vista: Any, mensaje_fallback: str) -> None:
        """Monta la vista seleccionada en el área central o muestra un aviso."""
        self.limpiar_area_central()
        if clase_vista is not None:
            try:
                vista = clase_vista(self.frame_contenido)
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

    def abrir_modulo_clientes(self) -> None:
        """Abre el módulo de clientes."""
        self.gestionar_apertura(
            InterfazClientes,
            "Módulo de Clientes no disponible.",
        )

    def ejecutar_backup(self) -> None:
        """Solicita al controlador core la generación de un respaldo del sistema."""
        try:
            resultado = self.orquestador.ejecutar_backup()
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
            "Cerrar Sesión",
            "¿Está seguro de que desea cerrar la sesión actual?",
            parent=self.root,
        ):
            if self.on_cerrar_sesion is not None:
                self.on_cerrar_sesion()
            elif isinstance(self.root, (tk.Tk, tk.Toplevel)):
                self.root.destroy()