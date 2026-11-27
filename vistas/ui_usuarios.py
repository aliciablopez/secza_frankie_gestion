"""
===============================================================================
VISTA DE GESTIÓN DE USUARIOS (vistas/ui_usuarios.py)
===============================================================================
Administra credenciales, roles y estado de usuarios sobre el esquema SQLite
(`usuarios`, `roles`, `usuarios_roles` y enlace opcional con `empleados`/`personas`),
aplicando los estilos globales del proyecto y restringiendo lectura/edición a `admin`.
Incluye importación asistida de usuarios desde la nómina de personal.
===============================================================================
"""

import hashlib
from os import PathLike
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

RutaEntrada = Optional[Union[str, PathLike[str]]]

ROLES_PERMITIDOS: Tuple[str, ...] = (
    "Admin",
    "Gerente",
    "Vendedor",
    "Administrativo",
)

ROL_POR_DEFECTO = "Vendedor"

MAPA_CARGO_A_ROL: Dict[str, str] = {
    "admin": "Admin",
    "gerente": "Gerente",
    "vendedor": "Vendedor",
    "administrativo": "Administrativo",
}

MAPA_SECTOR_A_ROL: Dict[str, str] = {
    "ventas": "Vendedor",
    "administración": "Administrativo",
    "administracion": "Administrativo",
    "gestión": "Gerente",
    "gestion": "Gerente",
}


def _cargar_funciones_db() -> Tuple[
    Optional[Callable[[Optional[str]], Path]],
    Optional[Callable[[Optional[str]], Path]],
    Optional[Callable[..., None]],
]:
    """Importa funciones de inicializar_db si están disponibles en el entorno."""
    try:
        from inicializar_db import (  # pylint: disable=import-outside-toplevel
            inicializar_base_datos,
            localizar_db,
            localizar_esquema,
        )

        return localizar_db, localizar_esquema, inicializar_base_datos
    except ImportError:
        return None, None, None


def _cargar_aplicador_estilos() -> Optional[Callable[[tk.Misc], Any]]:
    """Localiza el aplicador de estilos de vistas.estilos si existe."""
    try:
        from vistas import estilos  # pylint: disable=import-outside-toplevel
    except ImportError:
        return None

    for nombre_fn in ("aplicar_estilos_base", "aplicar_estilos", "configurar_estilos"):
        candidato = getattr(estilos, nombre_fn, None)
        if callable(candidato):
            return candidato
    return None


_LOCALIZAR_DB, _LOCALIZAR_ESQUEMA, _INICIALIZAR_BASE_DATOS = _cargar_funciones_db()
_APLICAR_ESTILOS_FN = _cargar_aplicador_estilos()

TITULO_CABECERA = "Gestión de usuarios"
ROLES_ADMIN = {"admin"}
RUTA_DB_POR_DEFECTO: Path = Path(__file__).resolve().parent.parent / "db" / "frankie_gestor.db"


def _hashear_password(password_plano: str) -> str:
    """Genera hash SHA-256 en hexadecimal compatible con la base del proyecto."""
    return hashlib.sha256(password_plano.encode("utf-8")).hexdigest()


def _resolver_ruta_db(ruta_db: RutaEntrada = None) -> Path:
    """Resuelve la ruta de la base de datos SQLite del proyecto."""
    if ruta_db is not None:
        return Path(ruta_db).resolve()
    if _LOCALIZAR_DB is not None:
        return _LOCALIZAR_DB(None)
    return RUTA_DB_POR_DEFECTO.resolve()


def _es_usuario_admin(usuario_actual: Any) -> bool:
    """Determina si el usuario activo tiene permisos de administrador."""
    if usuario_actual is None:
        return False
    if isinstance(usuario_actual, str):
        return usuario_actual.strip().lower() in ROLES_ADMIN
    if isinstance(usuario_actual, dict):
        username = str(
            usuario_actual.get("username") or usuario_actual.get("usuario") or ""
        ).strip().lower()
        rol = str(usuario_actual.get("rol") or "").strip().lower()
        roles = {str(r).strip().lower() for r in (usuario_actual.get("roles") or [])}
        return username == "admin" or rol in ROLES_ADMIN or bool(roles & ROLES_ADMIN)

    username_attr = str(
        getattr(usuario_actual, "username", "") or getattr(usuario_actual, "usuario", "")
    ).strip().lower()
    rol_attr = str(getattr(usuario_actual, "rol", "") or "").strip().lower()
    roles_attr = {str(r).strip().lower() for r in (getattr(usuario_actual, "roles", None) or [])}
    return username_attr == "admin" or rol_attr in ROLES_ADMIN or bool(roles_attr & ROLES_ADMIN)


def _sugerir_username(nombres: str, apellidos: str, existentes: set[str]) -> str:
    """Construye un username único y limpio a partir de nombre y apellido."""
    partes_nom = [p for p in "".join(ch if ch.isalnum() else " " for ch in nombres.lower()).split() if p]
    partes_ape = [p for p in "".join(ch if ch.isalnum() else " " for ch in apellidos.lower()).split() if p]

    inicial = partes_nom[0][0] if partes_nom else "u"
    apellido = partes_ape[0] if partes_ape else "empleado"
    base = f"{inicial}.{apellido}"
    if base not in existentes:
        return base

    contador = 2
    while f"{base}{contador}" in existentes:
        contador += 1
    return f"{base}{contador}"


class VistaGestionUsuarios(ttk.Frame):
    """Vista modular de gestión de usuarios con patrón apilado y estilos del proyecto."""

    def __init__(
        self,
        parent: tk.Misc,
        usuario_actual: Any = None,
        ruta_db: RutaEntrada = None,
    ) -> None:
        super().__init__(parent, padding=10)
        self.usuario_actual = usuario_actual
        self.ruta_db: Path = _resolver_ruta_db(ruta_db)
        self.es_admin = _es_usuario_admin(usuario_actual)

        self.id_seleccionado: Optional[int] = None
        self.mapa_roles: Dict[str, int] = {}
        # (id_usuario, username, rol_nombre, nombres, apellidos, activo)
        self.registros_cache: List[Tuple[int, str, str, str, str, int]] = []

        self.lbl_estado_acceso: ttk.Label
        self.var_nombres: tk.StringVar
        self.entry_nombres: ttk.Entry
        self.var_apellidos: tk.StringVar
        self.entry_apellidos: ttk.Entry
        self.var_username: tk.StringVar
        self.entry_username: ttk.Entry
        self.var_password: tk.StringVar
        self.entry_password: ttk.Entry
        self.var_rol: tk.StringVar
        self.combo_rol: ttk.Combobox
        self.var_activo: tk.BooleanVar
        self.chk_activo: ttk.Checkbutton
        self.btn_guardar: ttk.Button
        self.btn_actualizar: ttk.Button
        self.btn_limpiar: ttk.Button
        self.btn_toggle_estado: ttk.Button
        self.btn_importar: ttk.Button
        self.var_buscar: tk.StringVar
        self.entry_buscar: ttk.Entry
        self.tree: ttk.Treeview

        self._aplicar_estilos()
        self._asegurar_bd()
        self._construir_interfaz()
        self._cargar_roles()
        self._cargar_usuarios()
        self._aplicar_politica_acceso()

    def _aplicar_estilos(self) -> None:
        if _APLICAR_ESTILOS_FN is not None:
            try:
                _APLICAR_ESTILOS_FN(self.winfo_toplevel())
            except tk.TclError:
                pass

    def _asegurar_bd(self) -> None:
        if _INICIALIZAR_BASE_DATOS is not None and _LOCALIZAR_ESQUEMA is not None:
            try:
                esquema = _LOCALIZAR_ESQUEMA(None)
                _INICIALIZAR_BASE_DATOS(
                    ruta_db=self.ruta_db,
                    ruta_esquema=esquema,
                    reiniciar=False,
                )
                return
            except (OSError, sqlite3.Error):
                pass
        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    descripcion TEXT
                );
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    activo INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS usuarios_roles (
                    id_usuario INTEGER NOT NULL,
                    id_rol INTEGER NOT NULL,
                    PRIMARY KEY (id_usuario, id_rol),
                    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE,
                    FOREIGN KEY (id_rol) REFERENCES roles(id) ON DELETE CASCADE
                );
                """
            )

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.ruta_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _construir_interfaz(self) -> None:
        # 1. Cabecera
        frame_cabecera = ttk.Frame(self, padding=(4, 4))
        frame_cabecera.pack(fill="x", side="top")

        ttk.Label(
            frame_cabecera,
            text=TITULO_CABECERA,
            font=("Atkinson Hyperlegible", 14, "bold"),
        ).pack(side="left")

        self.lbl_estado_acceso = ttk.Label(frame_cabecera, text="")
        self.lbl_estado_acceso.pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(4, 8))

        # 2. Formulario superior (patrón apilado)
        frame_form = ttk.LabelFrame(self, text="Datos del usuario", padding=12)
        frame_form.pack(fill="x", side="top")

        for col in range(6):
            frame_form.columnconfigure(col, weight=1 if col in (1, 3, 5) else 0)

        ttk.Label(frame_form, text="Nombres").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.var_nombres = tk.StringVar()
        self.entry_nombres = ttk.Entry(frame_form, textvariable=self.var_nombres)
        self.entry_nombres.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Apellidos").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.var_apellidos = tk.StringVar()
        self.entry_apellidos = ttk.Entry(frame_form, textvariable=self.var_apellidos)
        self.entry_apellidos.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Usuario (Login) *").grid(row=0, column=4, sticky="w", padx=(0, 6), pady=4)
        self.var_username = tk.StringVar()
        self.entry_username = ttk.Entry(frame_form, textvariable=self.var_username)
        self.entry_username.grid(row=0, column=5, sticky="ew", pady=4)

        ttk.Label(frame_form, text="Contraseña").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        self.var_password = tk.StringVar()
        self.entry_password = ttk.Entry(frame_form, textvariable=self.var_password, show="*")
        self.entry_password.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Rol Asignado *").grid(row=1, column=2, sticky="w", padx=(0, 6), pady=4)
        self.var_rol = tk.StringVar()
        self.combo_rol = ttk.Combobox(frame_form, textvariable=self.var_rol, state="readonly")
        self.combo_rol.grid(row=1, column=3, sticky="ew", padx=(0, 12), pady=4)

        self.var_activo = tk.BooleanVar(value=True)
        self.chk_activo = ttk.Checkbutton(frame_form, text="Usuario activo", variable=self.var_activo)
        self.chk_activo.grid(row=1, column=4, columnspan=2, sticky="w", pady=4)

        # Botonera CRUD estándar + Importar desde nómina
        frame_acciones = ttk.Frame(frame_form)
        frame_acciones.grid(row=2, column=0, columnspan=6, sticky="w", pady=(10, 2))

        self.btn_guardar = ttk.Button(frame_acciones, text="Guardar", command=self.guardar_usuario)
        self.btn_guardar.pack(side="left", padx=(0, 8))

        self.btn_actualizar = ttk.Button(frame_acciones, text="Actualizar", command=self.actualizar_usuario)
        self.btn_actualizar.pack(side="left", padx=(0, 8))

        self.btn_limpiar = ttk.Button(frame_acciones, text="Limpiar", command=self.limpiar_formulario)
        self.btn_limpiar.pack(side="left", padx=(0, 8))

        self.btn_toggle_estado = ttk.Button(
            frame_acciones,
            text="Deshabilitar",
            command=self.alternar_estado_usuario,
        )
        self.btn_toggle_estado.pack(side="left", padx=(0, 8))

        self.btn_importar = ttk.Button(
            frame_acciones,
            text="Importar",
            command=self.abrir_modal_importar_nomina,
        )
        self.btn_importar.pack(side="left")

        # 3. Tabla inferior con filtro de búsqueda y barras de desplazamiento V y H
        frame_tabla = ttk.LabelFrame(self, text="Usuarios registrados", padding=10)
        frame_tabla.pack(fill="both", expand=True, side="top", pady=(10, 0))

        frame_filtro = ttk.Frame(frame_tabla)
        frame_filtro.pack(fill="x", side="top", pady=(0, 8))

        ttk.Label(frame_filtro, text="Buscar:").pack(side="left", padx=(0, 6))
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._refrescar_tabla())
        self.entry_buscar = ttk.Entry(frame_filtro, textvariable=self.var_buscar, width=32)
        self.entry_buscar.pack(side="left")

        frame_grid = ttk.Frame(frame_tabla)
        frame_grid.pack(fill="both", expand=True, side="top")
        frame_grid.columnconfigure(0, weight=1)
        frame_grid.rowconfigure(0, weight=1)

        columnas = ("usuario", "rol", "nombres", "apellidos", "estado")
        self.tree = ttk.Treeview(frame_grid, columns=columnas, show="headings", selectmode="browse")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("rol", text="Rol del Sistema")
        self.tree.heading("nombres", text="Nombres")
        self.tree.heading("apellidos", text="Apellidos")
        self.tree.heading("estado", text="Estado")

        self.tree.column("usuario", width=150, anchor="w", stretch=False)
        self.tree.column("rol", width=180, anchor="w", stretch=False)
        self.tree.column("nombres", width=180, anchor="w", stretch=False)
        self.tree.column("apellidos", width=180, anchor="w", stretch=False)
        self.tree.column("estado", width=110, anchor="center", stretch=False)

        scroll_v = ttk.Scrollbar(frame_grid, orient="vertical", command=self.tree.yview)
        scroll_h = ttk.Scrollbar(frame_grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_v.set, xscrollcommand=scroll_h.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_v.grid(row=0, column=1, sticky="ns")
        scroll_h.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def _aplicar_politica_acceso(self) -> None:
        if self.es_admin:
            self.lbl_estado_acceso.configure(text="Acceso: Admin (lectura y edición)")
            estado_campos = "normal"
            estado_combo = "readonly"
            estado_botones = "normal"
        else:
            self.lbl_estado_acceso.configure(text="Acceso restringido: solo 'admin' puede ver y editar")
            estado_campos = "disabled"
            estado_combo = "disabled"
            estado_botones = "disabled"

        for widget in (self.entry_nombres, self.entry_apellidos, self.entry_username, self.entry_password):
            widget.configure(state=estado_campos)
        self.combo_rol.configure(state=estado_combo)
        self.chk_activo.configure(state=estado_botones)
        for btn in (
            self.btn_guardar,
            self.btn_actualizar,
            self.btn_limpiar,
            self.btn_toggle_estado,
            self.btn_importar,
        ):
            btn.configure(state=estado_botones)

    def _cargar_roles(self) -> None:
        descripciones_oficiales = {
            "Admin": "Control total del sistema",
            "Gerente": "Gestión operativa y CRUD",
        }