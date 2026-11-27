"""
===============================================================================
VISTA DE GESTIÓN DE USUARIOS (vistas/ui_usuarios.py)
===============================================================================
Administra credenciales, roles y estado de usuarios sobre el esquema SQLite
(`usuarios`, `roles`, `usuarios_roles` y enlace opcional con `empleados`/`personas`),
aplicando los estilos globales del proyecto y restringiendo lectura/edición a `admin`.
Incluye usuarios base por rol para pruebas/presentación, importación limpia desde
la nómina de personal y eliminación de registros duplicados/fantasma.
===============================================================================
"""

import hashlib
from os import PathLike
from pathlib import Path
import re
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

RutaEntrada = Optional[Union[str, PathLike[str]]]

ROLES_PERMITIDOS: Tuple[str, ...] = (
    "Admin",
    "Gerente",
    "Vendedor",
    "Administrativo",
)

ROL_POR_DEFECTO = "Vendedor"
PASSWORD_ADMIN_INICIAL = "admin123"

# (username, password_plano, nombre, apellido, rol)
USUARIOS_BASE_DEMO: Tuple[Tuple[str, str, str, str, str], ...] = (
    ("admin", PASSWORD_ADMIN_INICIAL, "Admin", "Sistema", "Admin"),
    ("gerente", "gerente", "Nombre Gerente", "Gerente", "Gerente"),
    ("vendedor", "vendedor", "Nombre Vendedor", "Vendedor", "Vendedor"),
    (
        "administrativo",
        "administrativo",
        "Nombre Administrativo",
        "Administrativo",
        "Administrativo",
    ),
)

MAPA_CARGO_A_ROL: Dict[str, str] = {
    "admin": "Admin",
    "administrador": "Admin",
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
        try:
            from vistas import ui_estilos as estilos  # pylint: disable=import-outside-toplevel
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
ROLES_ADMIN = {"admin", "administrador"}
RUTA_DB_POR_DEFECTO: Path = (
    Path(__file__).resolve().parent.parent / "db" / "frankie_gestor.db"
)


def _normalizar_rol_canonico(rol_raw: str) -> str:
    limpio = (rol_raw or "").strip().lower()
    if limpio in ROLES_ADMIN:
        return "Admin"
    if limpio == "gerente":
        return "Gerente"
    if limpio == "vendedor":
        return "Vendedor"
    if limpio == "administrativo":
        return "Administrativo"
    return ROL_POR_DEFECTO


def _normalizar_persona_clave(nombres: str, apellidos: str) -> str:
    """Normaliza nombre y apellido para detectar duplicados de una misma persona."""
    limpio = f"{nombres or ''} {apellidos or ''}".strip().lower()
    return " ".join(
        p for p in re.sub(r"[^a-z0-9áéíóúüñ]+", " ", limpio).split() if p
    )


def _username_base_sin_sufijo(username: str) -> str:
    """Quita sufijos numéricos finales tipo 'f.fulanitez2' -> 'f.fulanitez'."""
    limpio = (username or "").strip().lower()
    if limpio in {"admin", "gerente", "vendedor", "administrativo"}:
        return limpio
    return re.sub(r"\d+$", "", limpio)


def _hashear_password(password_plano: str) -> str:
    """Genera hash SHA-256 en hexadecimal compatible con la base del proyecto."""
    return hashlib.sha256(password_plano.encode("utf-8")).hexdigest()


def _credenciales_por_rol(rol_nombre: str) -> Tuple[str, str]:
    """Devuelve (usuario_base, password_plano) según el rol."""
    canonico = _normalizar_rol_canonico(rol_nombre)
    if canonico == "Admin":
        return ("admin", PASSWORD_ADMIN_INICIAL)
    clave = canonico.lower()
    return (clave, clave)


def _inferir_nombre_apellido_desde_username(username: str) -> Tuple[str, str]:
    """Intenta inferir nombre y apellido básicos a partir de un username."""
    limpio = re.sub(r"\d+$", "", (username or "").strip())
    if not limpio:
        return "", ""
    if limpio.lower() in {"admin", "gerente", "vendedor", "administrativo"}:
        rol_cap = limpio.capitalize()
        return f"Nombre {rol_cap}", rol_cap
    if "." in limpio:
        parte_nom, parte_ape = limpio.split(".", 1)
        nom = parte_nom.capitalize() if len(parte_nom) > 1 else parte_nom.upper()
        ape = parte_ape.capitalize()
        return nom, ape
    return limpio.capitalize(), ""


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
        username = (
            str(usuario_actual.get("username") or usuario_actual.get("usuario") or "")
            .strip()
            .lower()
        )
        rol = str(usuario_actual.get("rol") or "").strip().lower()
        roles = {str(r).strip().lower() for r in (usuario_actual.get("roles") or [])}
        return username == "admin" or rol in ROLES_ADMIN or bool(roles & ROLES_ADMIN)

    username_attr = (
        str(
            getattr(usuario_actual, "username", "")
            or getattr(usuario_actual, "usuario", "")
        )
        .strip()
        .lower()
    )
    rol_attr = str(getattr(usuario_actual, "rol", "") or "").strip().lower()
    roles_attr = {
        str(getattr(r, "nombre", r)).strip().lower()
        for r in (getattr(usuario_actual, "roles", None) or [])
    }
    return (
        username_attr == "admin"
        or rol_attr in ROLES_ADMIN
        or bool(roles_attr & ROLES_ADMIN)
    )


def _sugerir_username(nombres: str, apellidos: str) -> str:
    """Construye el username base limpio a partir de nombre y apellido."""
    partes_nom = [
        p
        for p in "".join(ch if ch.isalnum() else " " for ch in nombres.lower()).split()
        if p
    ]
    partes_ape = [
        p
        for p in "".join(ch if ch.isalnum() else " " for ch in apellidos.lower()).split()
        if p
    ]

    inicial = partes_nom[0][0] if partes_nom else "u"
    apellido = partes_ape[0] if partes_ape else "empleado"
    return f"{inicial}.{apellido}"


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
        self.iid_a_usuario: Dict[str, int] = {}
        # (id_usuario, username, password_demo, nombre, apellido, rol_nombre, activo)
        self.registros_cache: List[Tuple[int, str, str, str, str, str, int]] = []

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
        self.btn_limpiar: ttk.Button
        self.btn_toggle_estado: ttk.Button
        self.btn_eliminar: ttk.Button
        self.btn_importar: ttk.Button
        self.var_buscar: tk.StringVar
        self.entry_buscar: ttk.Entry
        self.tree: ttk.Treeview

        self._aplicar_estilos()
        self._asegurar_bd()
        self._construir_interfaz()
        self._cargar_roles()
        self._asegurar_usuarios_base_demo()
        self._cargar_usuarios()
        self._aplicar_politica_acceso()
        self._sincronizar_credenciales_por_rol(
            actualizar_usuario=self.id_seleccionado is None
        )

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
            cols_usuarios = {
                row[1] for row in conn.execute("PRAGMA table_info(usuarios)").fetchall()
            }
            if "nombres" not in cols_usuarios:
                conn.execute("ALTER TABLE usuarios ADD COLUMN nombres TEXT DEFAULT ''")
            if "apellidos" not in cols_usuarios:
                conn.execute("ALTER TABLE usuarios ADD COLUMN apellidos TEXT DEFAULT ''")

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.ruta_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _asegurar_usuarios_base_demo(self) -> None:
        """Crea un usuario base por rol para pruebas rápidas si aún no existen."""
        with self._conectar() as conn:
            for username, pwd_plano, nombre, apellido, rol_canonico in USUARIOS_BASE_DEMO:
                rol_id = self._asegurar_rol_id(conn, rol_canonico)
                pwd_hash = _hashear_password(pwd_plano)
                conn.execute(
                    "INSERT OR IGNORE INTO usuarios (username, password, activo, nombres, apellidos) "
                    "VALUES (?, ?, 1, ?, ?)",
                    (username, pwd_hash, nombre, apellido),
                )
                row = conn.execute(
                    "SELECT id FROM usuarios WHERE LOWER(username) = LOWER(?)",
                    (username,),
                ).fetchone()
                if row:
                    uid = int(row[0])
                    conn.execute(
                        "UPDATE usuarios SET "
                        "nombres = CASE WHEN COALESCE(TRIM(nombres), '') = '' THEN ? ELSE nombres END, "
                        "apellidos = CASE WHEN COALESCE(TRIM(apellidos), '') = '' THEN ? ELSE apellidos END "
                        "WHERE id = ?",
                        (nombre, apellido, uid),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO usuarios_roles (id_usuario, id_rol) VALUES (?, ?)",
                        (uid, rol_id),
                    )

    def _construir_interfaz(self) -> None:
        # 1. Cabecera
        frame_cabecera = ttk.Frame(self, padding=(4, 2))
        frame_cabecera.pack(fill="x", side="top")

        ttk.Label(
            frame_cabecera,
            text=TITULO_CABECERA,
            font=("Atkinson Hyperlegible", 14, "bold"),
        ).pack(side="left")

        self.lbl_estado_acceso = ttk.Label(frame_cabecera, text="")
        self.lbl_estado_acceso.pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(4, 6))

        # 2. Formulario superior (patrón apilado)
        frame_form = ttk.LabelFrame(self, text="Datos del usuario", padding=10)
        frame_form.pack(fill="x", side="top")

        for col in range(6):
            frame_form.columnconfigure(col, weight=1 if col in (1, 3, 5) else 0)

        ttk.Label(frame_form, text="Nombre").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=4
        )
        self.var_nombres = tk.StringVar()
        self.entry_nombres = ttk.Entry(frame_form, textvariable=self.var_nombres)
        self.entry_nombres.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Apellido").grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=4
        )
        self.var_apellidos = tk.StringVar()
        self.entry_apellidos = ttk.Entry(frame_form, textvariable=self.var_apellidos)
        self.entry_apellidos.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Usuario *").grid(
            row=0, column=4, sticky="w", padx=(0, 6), pady=4
        )
        self.var_username = tk.StringVar()
        self.entry_username = ttk.Entry(frame_form, textvariable=self.var_username)
        self.entry_username.grid(row=0, column=5, sticky="ew", pady=4)

        ttk.Label(frame_form, text="Contraseña").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=4
        )
        self.var_password = tk.StringVar()
        self.entry_password = ttk.Entry(
            frame_form, textvariable=self.var_password, state="readonly"
        )
        self.entry_password.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="Rol *").grid(
            row=1, column=2, sticky="w", padx=(0, 6), pady=4
        )
        self.var_rol = tk.StringVar(value=ROL_POR_DEFECTO)
        self.combo_rol = ttk.Combobox(
            frame_form, textvariable=self.var_rol, state="readonly"
        )
        self.combo_rol.grid(row=1, column=3, sticky="ew", padx=(0, 12), pady=4)
        self.combo_rol.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._sincronizar_credenciales_por_rol(
                actualizar_usuario=(self.id_seleccionado is None)
            ),
        )

        self.var_activo = tk.BooleanVar(value=True)
        self.chk_activo = ttk.Checkbutton(
            frame_form, text="Usuario activo", variable=self.var_activo
        )
        self.chk_activo.grid(row=1, column=4, columnspan=2, sticky="w", pady=4)

        # Botonera: Guardar, Limpiar, Deshabilitar, Eliminar + Importar
        frame_acciones = ttk.Frame(frame_form)
        frame_acciones.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 2))

        self.btn_guardar = ttk.Button(
            frame_acciones, text="Guardar", command=self.guardar_usuario
        )
        self.btn_guardar.pack(side="left", padx=(0, 8))

        self.btn_limpiar = ttk.Button(
            frame_acciones, text="Limpiar", command=self.limpiar_formulario
        )
        self.btn_limpiar.pack(side="left", padx=(0, 8))

        self.btn_toggle_estado = ttk.Button(
            frame_acciones,
            text="Deshabilitar",
            command=self.alternar_estado_usuario,
        )
        self.btn_toggle_estado.pack(side="left", padx=(0, 8))

        self.btn_eliminar = ttk.Button(
            frame_acciones,
            text="Eliminar",
            command=self.eliminar_usuario,
        )
        self.btn_eliminar.pack(side="left", padx=(0, 8))

        self.btn_importar = ttk.Button(
            frame_acciones,
            text="Importar",
            command=self.abrir_modal_importar_nomina,
        )
        self.btn_importar.pack(side="left")

        # 3. Tabla inferior con filtro de búsqueda y barras de desplazamiento V y H
        frame_tabla = ttk.LabelFrame(self, text="Padrón de usuarios", padding=10)
        frame_tabla.pack(fill="both", expand=True, side="top", pady=(8, 0))

        frame_filtro = ttk.Frame(frame_tabla)
        frame_filtro.pack(fill="x", side="top", pady=(0, 6))

        ttk.Label(frame_filtro, text="Buscar:").pack(side="left", padx=(0, 6))
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._refrescar_tabla())
        self.entry_buscar = ttk.Entry(frame_filtro, textvariable=self.var_buscar, width=32)
        self.entry_buscar.pack(side="left")

        frame_grid = ttk.Frame(frame_tabla)
        frame_grid.pack(fill="both", expand=True, side="top")
        frame_grid.columnconfigure(0, weight=1)
        frame_grid.columnconfigure(1, weight=0)
        frame_grid.rowconfigure(0, weight=1)
        frame_grid.rowconfigure(1, weight=0)

        columnas = (
            "usuario",
            "contrasena",
            "nombre",
            "apellido",
            "rol",
            "estado",
        )
        self.tree = ttk.Treeview(
            frame_grid,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=8,
        )
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("contrasena", text="Contraseña")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("apellido", text="Apellido")
        self.tree.heading("rol", text="Rol")
        self.tree.heading("estado", text="Estado")

        self.tree.column("usuario", width=150, anchor="w", stretch=False)
        self.tree.column("contrasena", width=150, anchor="w", stretch=False)
        self.tree.column("nombre", width=180, anchor="w", stretch=False)
        self.tree.column("apellido", width=180, anchor="w", stretch=False)
        self.tree.column("rol", width=150, anchor="w", stretch=False)
        self.tree.column("estado", width=110, anchor="center", stretch=False)

        scroll_v = ttk.Scrollbar(frame_grid, orient="vertical", command=self.tree.yview)
        scroll_h = ttk.Scrollbar(frame_grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_v.set, xscrollcommand=scroll_h.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_v.grid(row=0, column=1, sticky="ns")
        scroll_h.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def _sincronizar_credenciales_por_rol(self, actualizar_usuario: bool = False) -> None:
        """Sincroniza usuario y contraseña según el rol seleccionado (sin tocar admin)."""
        rol_canonico = _normalizar_rol_canonico(self.var_rol.get() or ROL_POR_DEFECTO)
        user_sugerido, pwd_plano = _credenciales_por_rol(rol_canonico)

        if self.id_seleccionado is not None and rol_canonico == "Admin":
            self.var_password.set(PASSWORD_ADMIN_INICIAL)
        else:
            self.var_password.set(pwd_plano)

        if actualizar_usuario:
            self.var_username.set(user_sugerido)

    def _aplicar_politica_acceso(self) -> None:
        if self.es_admin:
            self.lbl_estado_acceso.configure(text="Acceso: Admin (lectura y edición)")
            estado_campos = "normal"
            estado_combo = "readonly"
            estado_botones = "normal"
        else:
            self.lbl_estado_acceso.configure(
                text="Acceso restringido: solo 'admin' puede ver y editar"
            )
            estado_campos = "disabled"
            estado_combo = "disabled"
            estado_botones = "disabled"

        for widget in (self.entry_nombres, self.entry_apellidos, self.entry_username):
            widget.configure(state=estado_campos)
        self.entry_password.configure(state="readonly")
        self.combo_rol.configure(state=estado_combo)
        self.chk_activo.configure(state=estado_botones)
        for btn in (
            self.btn_guardar,
            self.btn_limpiar,
            self.btn_toggle_estado,
            self.btn_eliminar,
            self.btn_importar,
        ):
            btn.configure(state=estado_botones)

    def _cargar_roles(self) -> None:
        descripciones_oficiales = {
            "Admin": "Control total del sistema",
            "Gerente": "Gestión operativa y CRUD",
            "Vendedor": "Operación comercial y ventas",
            "Administrativo": "Gestión administrativa y soporte",
        }
        self.mapa_roles.clear()
        with self._conectar() as conn:
            for rol_nombre in ROLES_PERMITIDOS:
                conn.execute(
                    "INSERT OR IGNORE INTO roles (nombre, descripcion) VALUES (?, ?)",
                    (rol_nombre, descripciones_oficiales.get(rol_nombre, rol_nombre)),
                )
            filas = conn.execute("SELECT id, nombre FROM roles ORDER BY id").fetchall()

        valores_combo: List[str] = []
        for rol_id, nombre in filas:
            canonico = _normalizar_rol_canonico(str(nombre))
            self.mapa_roles[canonico.lower()] = int(rol_id)
            if canonico in ROLES_PERMITIDOS and canonico not in valores_combo:
                valores_combo.append(canonico)

        for rol_nombre in ROLES_PERMITIDOS:
            if rol_nombre not in valores_combo:
                valores_combo.append(rol_nombre)

        self.combo_rol.configure(values=tuple(valores_combo))
        if not self.var_rol.get():
            self.var_rol.set(ROL_POR_DEFECTO)

    def _cargar_usuarios(self) -> None:
        self.registros_cache.clear()
        with self._conectar() as conn:
            cols_usuarios = {
                row[1] for row in conn.execute("PRAGMA table_info(usuarios)").fetchall()
            }
            tiene_nombres = "nombres" in cols_usuarios
            tiene_apellidos = "apellidos" in cols_usuarios

            select_expr = (
                "u.id, u.username, COALESCE(r.nombre, ''), "
                f"{'COALESCE(u.nombres, \"\")' if tiene_nombres else '\"\"'}, "
                f"{'COALESCE(u.apellidos, \"\")' if tiene_apellidos else '\"\"'}, "
                "COALESCE(u.activo, 1)"
            )
            query = (
                f"SELECT {select_expr} "
                "FROM usuarios u "
                "LEFT JOIN usuarios_roles ur ON ur.id_usuario = u.id "
                "LEFT JOIN roles r ON r.id = ur.id_rol "
                "ORDER BY u.id"
            )
            filas = conn.execute(query).fetchall()

        vistos_ids: Set[int] = set()
        for fila in filas:
            uid = int(fila[0])
            if uid in vistos_ids:
                continue
            vistos_ids.add(uid)

            username = str(fila[1] or "")
            rol_canonico = _normalizar_rol_canonico(str(fila[2] or ROL_POR_DEFECTO))
            _, pwd_demo = _credenciales_por_rol(rol_canonico)
            nombre = str(fila[3] or "").strip()
            apellido = str(fila[4] or "").strip()
            if not nombre and not apellido:
                nombre, apellido = _inferir_nombre_apellido_desde_username(username)
            activo = int(fila[5] if fila[5] is not None else 1)

            self.registros_cache.append(
                (uid, username, pwd_demo, nombre, apellido, rol_canonico, activo)
            )

        self._refrescar_tabla()

    def _refrescar_tabla(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.iid_a_usuario.clear()

        if not self.es_admin:
            return

        criterio = (self.var_buscar.get() or "").strip().lower()
        for uid, username, pwd_demo, nombre, apellido, rol, activo in self.registros_cache:
            if criterio and criterio not in " ".join(
                (username, pwd_demo, nombre, apellido, rol)
            ).lower():
                continue
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    username,
                    pwd_demo,
                    nombre or "-",
                    apellido or "-",
                    rol,
                    "Activo" if activo else "Inactivo",
                ),
            )
            self.iid_a_usuario[iid] = uid

    def _asegurar_rol_id(self, conn: sqlite3.Connection, rol_nombre: str) -> int:
        canonico = _normalizar_rol_canonico(rol_nombre)
        clave = canonico.lower()
        if clave in self.mapa_roles:
            return self.mapa_roles[clave]

        conn.execute(
            "INSERT OR IGNORE INTO roles (nombre, descripcion) VALUES (?, ?)",
            (canonico, canonico),
        )
        row = conn.execute(
            "SELECT id FROM roles WHERE LOWER(nombre) = LOWER(?)", (canonico,)
        ).fetchone()
        rol_id = int(row[0]) if row else 1
        self.mapa_roles[clave] = rol_id
        return rol_id

    def guardar_usuario(self) -> None:
        """Crea o actualiza un usuario aplicando credenciales por rol (sin tocar admin)."""
        if not self.es_admin:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo 'admin' puede administrar usuarios.",
                parent=self,
            )
            return

        rol_canonico = _normalizar_rol_canonico(self.var_rol.get() or ROL_POR_DEFECTO)
        user_sugerido, pwd_plano = _credenciales_por_rol(rol_canonico)

        username = (self.var_username.get() or "").strip() or user_sugerido
        nombres = (self.var_nombres.get() or "").strip()
        apellidos = (self.var_apellidos.get() or "").strip()
        activo_int = 1 if self.var_activo.get() else 0

        if not username:
            messagebox.showwarning(
                "Dato obligatorio", "Ingresá el nombre de usuario.", parent=self
            )
            return

        es_admin_objetivo = rol_canonico == "Admin" or username.lower() == "admin"

        try:
            with self._conectar() as conn:
                cols_usuarios = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(usuarios)").fetchall()
                }
                rol_id = self._asegurar_rol_id(conn, rol_canonico)

                if self.id_seleccionado is None:
                    password_hash = _hashear_password(pwd_plano)
                    campos = ["username", "password", "activo"]
                    valores: List[Any] = [username, password_hash, activo_int]
                    if "nombres" in cols_usuarios:
                        campos.append("nombres")
                        valores.append(nombres)
                    if "apellidos" in cols_usuarios:
                        campos.append("apellidos")
                        valores.append(apellidos)

                    placeholders = ", ".join("?" for _ in campos)
                    cur = conn.execute(
                        f"INSERT INTO usuarios ({', '.join(campos)}) VALUES ({placeholders})",
                        valores,
                    )
                    usuario_id = int(cur.lastrowid or 0)
                    conn.execute(
                        "INSERT OR REPLACE INTO usuarios_roles (id_usuario, id_rol) VALUES (?, ?)",
                        (usuario_id, rol_id),
                    )
                    msg = f"Usuario '{username}' creado (rol: {rol_canonico})."
                else:
                    usuario_id = self.id_seleccionado
                    sets = ["username = ?", "activo = ?"]
                    params: List[Any] = [username, activo_int]

                    if "nombres" in cols_usuarios:
                        sets.append("nombres = ?")
                        params.append(nombres)
                    if "apellidos" in cols_usuarios:
                        sets.append("apellidos = ?")
                        params.append(apellidos)

                    # La contraseña de admin no se modifica al editar
                    if not es_admin_objetivo:
                        sets.append("password = ?")
                        params.append(_hashear_password(pwd_plano))

                    params.append(usuario_id)
                    conn.execute(
                        f"UPDATE usuarios SET {', '.join(sets)} WHERE id = ?",
                        params,
                    )
                    conn.execute(
                        "DELETE FROM usuarios_roles WHERE id_usuario = ?",
                        (usuario_id,),
                    )
                    conn.execute(
                        "INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (?, ?)",
                        (usuario_id, rol_id),
                    )
                    msg = f"Usuario '{username}' actualizado (rol: {rol_canonico})."

            self.limpiar_formulario()
            self._cargar_usuarios()
            messagebox.showinfo("Éxito", msg, parent=self)
        except sqlite3.IntegrityError as exc:
            messagebox.showerror(
                "Error de integridad",
                f"No se pudo guardar el usuario (posible duplicado): {exc}",
                parent=self,
            )
        except sqlite3.Error as exc:
            messagebox.showerror("Error de base de datos", str(exc), parent=self)

    def alternar_estado_usuario(self) -> None:
        """Activa o deshabilita el usuario seleccionado."""
        if not self.es_admin:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo 'admin' puede cambiar el estado de usuarios.",
                parent=self,
            )
            return

        if self.id_seleccionado is None:
            messagebox.showwarning(
                "Sin selección", "Seleccioná un usuario de la tabla.", parent=self
            )
            return

        username = (self.var_username.get() or "").strip()
        nuevo_estado = 0 if self.var_activo.get() else 1
        accion = "deshabilitar" if nuevo_estado == 0 else "habilitar"

        if not messagebox.askyesno(
            "Confirmar",
            f"¿Deseás {accion} al usuario '{username}'?",
            parent=self,
        ):
            return

        try:
            with self._conectar() as conn:
                conn.execute(
                    "UPDATE usuarios SET activo = ? WHERE id = ?",
                    (nuevo_estado, self.id_seleccionado),
                )
            self.limpiar_formulario()
            self._cargar_usuarios()
        except sqlite3.Error as exc:
            messagebox.showerror("Error de base de datos", str(exc), parent=self)

    def eliminar_usuario(self) -> None:
        """Elimina definitivamente el usuario seleccionado de la base de datos."""
        if not self.es_admin:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo 'admin' puede eliminar usuarios.",
                parent=self,
            )
            return

        if self.id_seleccionado is None:
            messagebox.showwarning(
                "Sin selección",
                "Seleccioná un usuario de la tabla para eliminar.",
                parent=self,
            )
            return

        username = (self.var_username.get() or "").strip()
        if username.lower() == "admin":
            messagebox.showwarning(
                "Acción protegida",
                "No se puede eliminar el usuario 'admin'.",
                parent=self,
            )
            return

        if not messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Deseás eliminar definitivamente al usuario '{username}'?",
            parent=self,
        ):
            return

        try:
            with self._conectar() as conn:
                conn.execute(
                    "DELETE FROM usuarios_roles WHERE id_usuario = ?",
                    (self.id_seleccionado,),
                )
                conn.execute(
                    "DELETE FROM usuarios WHERE id = ?",
                    (self.id_seleccionado,),
                )
            self.limpiar_formulario()
            self._cargar_usuarios()
            messagebox.showinfo(
                "Eliminado", f"Usuario '{username}' eliminado.", parent=self
            )
        except sqlite3.Error as exc:
            messagebox.showerror("Error de base de datos", str(exc), parent=self)

    def limpiar_formulario(self) -> None:
        """Limpia los campos y restablece el formulario a modo alta."""
        self.id_seleccionado = None
        self.var_nombres.set("")
        self.var_apellidos.set("")
        self.var_rol.set(ROL_POR_DEFECTO)
        self.var_activo.set(True)
        self.btn_toggle_estado.configure(text="Deshabilitar")
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self._sincronizar_credenciales_por_rol(actualizar_usuario=True)

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        """Carga el usuario seleccionado y completa nombre, apellido y contraseña."""
        if not self.es_admin:
            return
        seleccion = self.tree.selection()
        if not seleccion:
            return

        uid = self.iid_a_usuario.get(seleccion[0])
        if uid is None:
            return

        registro = next((r for r in self.registros_cache if r[0] == uid), None)
        if registro is None:
            return

        _, username, pwd_demo, nombre, apellido, rol_canonico, activo = registro
        self.id_seleccionado = uid
        self.var_username.set(username)
        self.var_password.set(pwd_demo)
        self.var_nombres.set(nombre)
        self.var_apellidos.set(apellido)
        self.var_rol.set(rol_canonico)
        self.var_activo.set(bool(activo))
        self.btn_toggle_estado.configure(
            text="Deshabilitar" if bool(activo) else "Habilitar"
        )

    def abrir_modal_importar_nomina(self) -> None:
        """Importa empleados válidos sin duplicar usuarios existentes ni variantes."""
        if not self.es_admin:
            return

        usernames_existentes: Set[str] = {
            r[1].strip().lower() for r in self.registros_cache if r[1].strip()
        }
        bases_existentes: Set[str] = {
            _username_base_sin_sufijo(u) for u in usernames_existentes
        }
        personas_existentes: Set[str] = set()

        for _, u, _, nom, ape, _, _ in self.registros_cache:
            clave_per = _normalizar_persona_clave(nom, ape)
            if clave_per:
                personas_existentes.add(clave_per)
            inf_nom, inf_ape = _inferir_nombre_apellido_desde_username(u)
            clave_inf = _normalizar_persona_clave(inf_nom, inf_ape)
            if clave_inf:
                personas_existentes.add(clave_inf)

        candidatos: List[Tuple[str, str, str, str]] = []
        vistos_lote: Set[str] = set()

        try:
            with self._conectar() as conn:
                tablas = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "empleados" in tablas:
                    cols_emp = {
                        row[1]
                        for row in conn.execute("PRAGMA table_info(empleados)").fetchall()
                    }
                    tiene_personas = "personas" in tablas and "id_persona" in cols_emp
                    sel_nom = (
                        "p.nombres"
                        if tiene_personas
                        else ("e.nombres" if "nombres" in cols_emp else "''")
                    )
                    sel_ape = (
                        "p.apellidos"
                        if tiene_personas
                        else ("e.apellidos" if "apellidos" in cols_emp else "''")
                    )
                    sel_cargo = "e.cargo" if "cargo" in cols_emp else "''"
                    sel_sector = "e.sector" if "sector" in cols_emp else "''"
                    join_per = (
                        "LEFT JOIN personas p ON p.id = e.id_persona"
                        if tiene_personas
                        else ""
                    )
                    where_act = (
                        "WHERE COALESCE(e.activo, 1) = 1" if "activo" in cols_emp else ""
                    )

                    rows = conn.execute(
                        f"SELECT COALESCE({sel_nom}, ''), COALESCE({sel_ape}, ''), "
                        f"COALESCE({sel_cargo}, ''), COALESCE({sel_sector}, '') "
                        f"FROM empleados e {join_per} {where_act}"
                    ).fetchall()

                    for nom, ape, cargo, sector in rows:
                        nom_s = str(nom or "").strip()
                        ape_s = str(ape or "").strip()
                        clave_per = _normalizar_persona_clave(nom_s, ape_s)
                        if not clave_per:
                            continue
                        if clave_per in personas_existentes or clave_per in vistos_lote:
                            continue

                        user_sug = _sugerir_username(nom_s, ape_s)
                        base_sug = _username_base_sin_sufijo(user_sug)
                        if (
                            user_sug.lower() in usernames_existentes
                            or base_sug in bases_existentes
                        ):
                            continue

                        rol_sugerido = _normalizar_rol_canonico(
                            MAPA_CARGO_A_ROL.get(str(cargo).strip().lower())
                            or MAPA_SECTOR_A_ROL.get(str(sector).strip().lower())
                            or ROL_POR_DEFECTO
                        )
                        vistos_lote.add(clave_per)
                        usernames_existentes.add(user_sug.lower())
                        bases_existentes.add(base_sug)
                        candidatos.append((user_sug, rol_sugerido, nom_s, ape_s))
        except sqlite3.Error:
            candidatos = []

        if not candidatos:
            messagebox.showinfo(
                "Importar nómina",
                "No se encontraron empleados nuevos para importar.",
                parent=self,
            )
            return

        importados = 0
        try:
            with self._conectar() as conn:
                cols_usuarios = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(usuarios)").fetchall()
                }
                for user_sug, rol_sugerido, nom, ape in candidatos:
                    rol_id = self._asegurar_rol_id(conn, rol_sugerido)
                    _, pwd_plano = _credenciales_por_rol(rol_sugerido)
                    pwd_hash = _hashear_password(pwd_plano)
                    campos = ["username", "password", "activo"]
                    vals: List[Any] = [user_sug, pwd_hash, 1]
                    if "nombres" in cols_usuarios:
                        campos.append("nombres")
                        vals.append(nom)
                    if "apellidos" in cols_usuarios:
                        campos.append("apellidos")
                        vals.append(ape)
                    cur = conn.execute(
                        f"INSERT OR IGNORE INTO usuarios ({', '.join(campos)}) "
                        f"VALUES ({', '.join('?' for _ in campos)})",
                        vals,
                    )
                    if cur.rowcount and cur.lastrowid:
                        conn.execute(
                            "INSERT OR IGNORE INTO usuarios_roles (id_usuario, id_rol) VALUES (?, ?)",
                            (int(cur.lastrowid), rol_id),
                        )
                        importados += 1
            self._cargar_usuarios()
            messagebox.showinfo(
                "Importación completada",
                f"Se importaron {importados} usuario(s) desde la nómina.",
                parent=self,
            )
        except sqlite3.Error as exc:
            messagebox.showerror("Error al importar", str(exc), parent=self)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor Comercial - Usuarios")
    root.geometry("1160x740")
    VistaGestionUsuarios(root, usuario_actual="admin").pack(fill="both", expand=True)
    root.mainloop()