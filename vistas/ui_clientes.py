"""
===============================================================================
MÓDULO DE VISTAS: INTERFAZ DE CLIENTES (vistas/ui_clientes.py)
===============================================================================
Alta, Listado, Edición y Baja/Reactivación Lógica de clientes (Persona Física).
- Botonera alineada al patrón del sistema: Guardar, Limpiar, Deshabilitar.
- Tabla limpia (sin Consumidor Final ni Frecuente; esos datos van a facturación).
- Orden alfabético por Apellido y Nombre.
- Tipografía 12 pt sin itálicas en etiquetas, campos de texto, botones y tabla.
- Control de permisos por rol: Admin, Gerente y Administrativo pueden editar;
  Vendedor consulta y selecciona.
===============================================================================
"""

from typing import Any, cast, Dict, List, Literal, Optional, Set, Tuple
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from dominio.entidades_ventas import Cliente
from infraestructura.repo_ventas import RepositorioVentas

try:
    from vistas.ui_estilos import aplicar_estilos_base
except ImportError:
    try:
        from vistas.estilos import aplicar_estilos_base
    except ImportError:
        aplicar_estilos_base = None

TAMANIO_FUENTE = 12
ALTO_FILA_TABLA = 34
AnchorTk = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
ROLES_EDICION_CLIENTES: Set[str] = {"admin", "gerente", "administrativo"}


def _normalizar_rol(nombre_rol: str) -> str:
    """Normaliza el nombre del rol para comparaciones consistentes."""
    limpio = (nombre_rol or "").strip().lower()
    if limpio in {"admin", "administrador"}:
        return "admin"
    if limpio == "gerente":
        return "gerente"
    if limpio == "administrativo":
        return "administrativo"
    if limpio == "vendedor":
        return "vendedor"
    return limpio


def _obtener_roles_normalizados(usuario_actual: Any) -> Set[str]:
    """Extrae los roles normalizados desde usuario_actual.roles."""
    roles: Set[str] = set()
    for rol in getattr(usuario_actual, "roles", None) or []:
        nombre = getattr(rol, "nombre", str(rol))
        norm = _normalizar_rol(nombre)
        if norm:
            roles.add(norm)
    return roles


def _a_entero_opcional(valor: Any) -> Optional[int]:
    """Convierte a int de forma segura y tipada, o devuelve None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        try:
            return int(texto)
        except ValueError:
            return None
    return None


def _a_entero_o_cero(valor: Any) -> int:
    """Convierte a int de forma segura y tipada, o devuelve 0."""
    convertido = _a_entero_opcional(valor)
    return convertido if convertido is not None else 0


def _clave_alfabetica_fila(fila_info: Dict[str, Any]) -> Tuple[str, str, str]:
    """Clave de ordenamiento alfabético por Apellidos, Nombres y documento."""
    cli: Cliente = fila_info["cliente"]
    apellidos = str(
        getattr(cli, "apellidos", "") or getattr(cli, "apellido", "") or ""
    ).strip().lower()
    nombres = str(
        getattr(cli, "nombres", "") or getattr(cli, "nombre", "") or ""
    ).strip().lower()
    doc = str(
        getattr(cli, "nro_documento", "")
        or getattr(cli, "cuit_cliente", "")
        or getattr(cli, "dni", "")
        or ""
    ).strip().lower()
    return (apellidos, nombres, doc)


class InterfazClientes(ttk.Frame):
    """Vista modular para administrar el padrón de clientes (Persona Física)."""

    def __init__(
        self,
        parent: tk.Misc,
        usuario_actual: Any = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, *args, **kwargs)
        self.usuario_actual = usuario_actual
        roles_activos = _obtener_roles_normalizados(usuario_actual)
        self.puede_editar_clientes: bool = bool(
            roles_activos & ROLES_EDICION_CLIENTES
        )

        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self.winfo_toplevel())
            except Exception:
                pass

        self.pack(fill="both", expand=True, padx=10, pady=10)

        self.cliente_seleccionado_id: Optional[int] = None
        self.persona_seleccionada_id: Optional[int] = None
        self.cliente_estado_activo: bool = True
        self.cliente_es_frecuente_actual: bool = False
        self.clientes_cache: Dict[str, Dict[str, Any]] = {}

        self.var_documento = tk.StringVar()
        self.var_nombres = tk.StringVar()
        self.var_apellidos = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_direccion = tk.StringVar()

        self.var_busqueda = tk.StringVar()
        self.var_mostrar_inactivos = tk.BooleanVar(value=False)

        self._construir_interfaz()
        self._configurar_fuentes()
        self._aplicar_permisos_botonera(tiene_seleccion=False)
        self.cargar_tabla_clientes()

    def _configurar_fuentes(self) -> None:
        """
        Fuerza 12 pt sin itálicas (slant='roman') en fuentes Tk, campos de texto
        y estilos ttk sin alterar los colores configurados.
        """
        top = self.winfo_toplevel()
        base_font = tkfont.nametofont("TkDefaultFont", root=top)
        familia_actual = base_font.actual().get("family") or "Segoe UI"
        if "italic" in str(base_font.actual().get("slant", "")).lower():
            familia_actual = "Segoe UI"

        fuente_normal = (familia_actual, TAMANIO_FUENTE, "normal")
        fuente_encabezado = (familia_actual, TAMANIO_FUENTE, "bold")

        for nombre_fuente in tkfont.names(root=top):
            try:
                f = tkfont.nametofont(nombre_fuente, root=top)
                peso = (
                    "bold"
                    if nombre_fuente == "TkHeadingFont"
                    else f.actual().get("weight", "normal")
                )
                f.configure(
                    family=familia_actual,
                    size=TAMANIO_FUENTE,
                    weight=peso,
                    slant="roman",
                )
            except Exception:
                continue

        estilo = ttk.Style(top)
        estilo.configure(".", font=fuente_normal)
        estilo.configure("TLabel", font=fuente_normal)
        estilo.configure("Subtitulo.TLabel", font=fuente_encabezado)
        estilo.configure("Muted.TLabel", font=fuente_normal)
        estilo.configure("TButton", font=fuente_normal)
        estilo.configure("TCheckbutton", font=fuente_normal)
        estilo.configure("TEntry", font=fuente_normal)
        estilo.configure("TCombobox", font=fuente_normal)
        estilo.configure("TLabelframe.Label", font=fuente_encabezado)
        estilo.configure(
            "Treeview",
            font=fuente_normal,
            rowheight=ALTO_FILA_TABLA,
        )
        estilo.configure(
            "Treeview.Heading",
            font=fuente_encabezado,
        )

        top.option_add("*Font", fuente_normal)
        top.option_add("*Entry.font", fuente_normal)
        top.option_add("*TEntry*Font", fuente_normal)
        top.option_add("*TCombobox*Listbox.font", fuente_normal)

        self._aplicar_fuente_recursiva(self, fuente_normal)

    def _aplicar_fuente_recursiva(
        self, widget: tk.Misc, fuente: Tuple[str, int, str]
    ) -> None:
        """Asegura fuente normal sin itálica en widgets Entry / Text de Tk si existen."""
        for hijo in widget.winfo_children():
            if isinstance(hijo, (tk.Entry, tk.Text)):
                try:
                    hijo.configure(font=fuente)
                except Exception:
                    pass
            if isinstance(hijo, tk.Misc):
                self._aplicar_fuente_recursiva(hijo, fuente)

    def _aplicar_permisos_botonera(self, tiene_seleccion: bool) -> None:
        """Habilita o bloquea acciones de escritura según el rol del usuario."""
        if not self.puede_editar_clientes:
            self.btn_guardar.config(state="disabled")
            self.btn_toggle_estado.config(
                text="Reactivar" if not self.cliente_estado_activo else "Deshabilitar",
                state="disabled",
            )
            return

        self.btn_guardar.config(state="normal")
        if tiene_seleccion:
            self.btn_toggle_estado.config(
                state="normal",
                text="Reactivar" if not self.cliente_estado_activo else "Deshabilitar",
            )
        else:
            self.btn_toggle_estado.config(text="Deshabilitar", state="disabled")

    def _construir_interfaz(self) -> None:
        # 1. Formulario de Datos (2 columnas)
        frame_form = ttk.LabelFrame(self, text=" Datos del Cliente ", padding=15)
        frame_form.pack(fill="x", padx=5, pady=5)
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

        # Fila 0: DNI / CUIT | Teléfono
        ttk.Label(frame_form, text="DNI / CUIT *:").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_documento).grid(
            row=0, column=1, sticky="ew", padx=6, pady=6
        )

        ttk.Label(frame_form, text="Teléfono:").grid(
            row=0, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_telefono).grid(
            row=0, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 1: Nombres | Apellidos
        ttk.Label(frame_form, text="Nombres *:").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_nombres).grid(
            row=1, column=1, sticky="ew", padx=6, pady=6
        )

        ttk.Label(frame_form, text="Apellidos *:").grid(
            row=1, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_apellidos).grid(
            row=1, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 2: Email | Dirección
        ttk.Label(frame_form, text="Email:").grid(
            row=2, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_email).grid(
            row=2, column=1, sticky="ew", padx=6, pady=6
        )

        ttk.Label(frame_form, text="Dirección:").grid(
            row=2, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_direccion).grid(
            row=2, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 3: Botonera (Guardar, Limpiar, Deshabilitar)
        frame_botones = ttk.Frame(frame_form)
        frame_botones.grid(row=3, column=0, columnspan=4, sticky="e", pady=(10, 4))

        self.btn_guardar = ttk.Button(
            frame_botones,
            text="Guardar",
            command=self.guardar_cliente,
        )
        self.btn_guardar.pack(side="left", padx=6)

        ttk.Button(
            frame_botones,
            text="Limpiar",
            command=self.limpiar_formulario,
        ).pack(side="left", padx=6)

        self.btn_toggle_estado = ttk.Button(
            frame_botones,
            text="Deshabilitar",
            command=self.toggle_estado_cliente,
            state="disabled",
        )
        self.btn_toggle_estado.pack(side="left", padx=6)

        # 2. Listado (Tabla Treeview limpia y ordenada alfabéticamente)
        frame_tabla = ttk.LabelFrame(
            self,
            text=" Padrón de Clientes Registrados (Seleccione una fila para consultar o gestionar) ",
            padding=15,
        )
        frame_tabla.pack(fill="both", expand=True, padx=5, pady=5)

        frame_busqueda = ttk.Frame(frame_tabla)
        frame_busqueda.pack(fill="x", pady=(0, 8))

        ttk.Label(frame_busqueda, text="Buscar cliente:").pack(side="left", padx=(0, 6))
        entry_buscar = ttk.Entry(frame_busqueda, textvariable=self.var_busqueda)
        entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry_buscar.bind("<KeyRelease>", lambda _e: self.cargar_tabla_clientes())

        ttk.Checkbutton(
            frame_busqueda,
            text="Mostrar inactivos",
            variable=self.var_mostrar_inactivos,
            command=self.cargar_tabla_clientes,
        ).pack(side="right")

        frame_grilla = ttk.Frame(frame_tabla)
        frame_grilla.pack(fill="both", expand=True)
        frame_grilla.rowconfigure(0, weight=1)
        frame_grilla.rowconfigure(1, weight=0)
        frame_grilla.columnconfigure(0, weight=1)
        frame_grilla.columnconfigure(1, weight=0)

        columnas = (
            "id",
            "documento",
            "nombre_completo",
            "telefono",
            "email",
            "direccion",
            "estado",
        )
        self.tabla = ttk.Treeview(
            frame_grilla,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=8,
        )

        encabezados: Dict[str, Tuple[str, int, AnchorTk]] = {
            "id": ("ID", 60, "center"),
            "documento": ("DNI / CUIT", 155, "center"),
            "nombre_completo": ("Apellido y Nombre", 250, "w"),
            "telefono": ("Teléfono", 150, "center"),
            "email": ("Email", 220, "w"),
            "direccion": ("Dirección", 240, "w"),
            "estado": ("Estado", 105, "center"),
        }
        for col, (titulo, ancho, ancla) in encabezados.items():
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, anchor=cast(AnchorTk, ancla))

        scroll_y = ttk.Scrollbar(
            frame_grilla, orient="vertical", command=self.tabla.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_grilla, orient="horizontal", command=self.tabla.xview
        )
        self.tabla.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tabla.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def _obtener_registros_desde_repo(self) -> List[Dict[str, Any]]:
        """Consulta clientes en RepositorioVentas y normaliza la estructura."""
        criterio = self.var_busqueda.get().strip()
        incluir_inactivos = bool(self.var_mostrar_inactivos.get())

        raw_items = RepositorioVentas.listar_clientes(
            criterio_busqueda=criterio,
            incluir_inactivos=incluir_inactivos,
        )

        normalizados: List[Dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, dict) and "cliente" in item:
                normalizados.append(
                    {
                        "cliente": item["cliente"],
                        "compras_mes": _a_entero_o_cero(item.get("compras_mes", 0)),
                        "es_frecuente": bool(item.get("es_frecuente", False)),
                    }
                )
            elif isinstance(item, Cliente):
                normalizados.append(
                    {
                        "cliente": item,
                        "compras_mes": 0,
                        "es_frecuente": False,
                    }
                )
        return normalizados

    def cargar_tabla_clientes(self) -> None:
        """Carga, filtra y ordena alfabéticamente los clientes en la tabla."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.clientes_cache.clear()

        try:
            registros = self._obtener_registros_desde_repo()
        except Exception as exc:
            messagebox.showerror(
                "Error al listar clientes",
                str(exc),
                parent=self,
            )
            return

        registros_ordenados = sorted(registros, key=_clave_alfabetica_fila)
        mostrar_inactivos = bool(self.var_mostrar_inactivos.get())

        for reg in registros_ordenados:
            cli: Cliente = reg["cliente"]
            activo = bool(getattr(cli, "activo", True))
            if not mostrar_inactivos and not activo:
                continue

            doc = str(
                getattr(cli, "nro_documento", "")
                or getattr(cli, "cuit_cliente", "")
                or getattr(cli, "dni", "")
                or ""
            )
            apellidos = str(
                getattr(cli, "apellidos", "") or getattr(cli, "apellido", "") or ""
            )
            nombres = str(
                getattr(cli, "nombres", "") or getattr(cli, "nombre", "") or ""
            )
            nombre_completo = f"{apellidos}, {nombres}".strip(", ") or "-"
            telefono = str(getattr(cli, "telefono", "") or "")
            email = str(getattr(cli, "email", "") or "")
            direccion = str(
                getattr(cli, "domicilio", "") or getattr(cli, "direccion", "") or ""
            )

            id_cli = getattr(cli, "id_cliente", None)
            if id_cli is None:
                id_cli = getattr(cli, "id", "")

            iid = self.tabla.insert(
                "",
                "end",
                values=(
                    id_cli if id_cli is not None else "-",
                    doc or "-",
                    nombre_completo,
                    telefono or "-",
                    email or "-",
                    direccion or "-",
                    "Activo" if activo else "Inactivo",
                ),
            )
            self.clientes_cache[iid] = reg

    def _construir_entidad_cliente(
        self,
        id_cliente: Optional[int],
        id_persona: Optional[int],
        activo: bool,
    ) -> Optional[Cliente]:
        """Valida los campos del formulario y construye la entidad Cliente."""
        doc = self.var_documento.get().strip()
        nombres = self.var_nombres.get().strip()
        apellidos = self.var_apellidos.get().strip()

        if not doc or not nombres or not apellidos:
            messagebox.showwarning(
                "Datos incompletos",
                "Completá DNI / CUIT, Nombres y Apellidos.",
                parent=self,
            )
            return None

        direccion = self.var_direccion.get().strip()
        telefono = self.var_telefono.get().strip()
        email = self.var_email.get().strip()

        cliente = Cliente(
            nombres=nombres,
            apellidos=apellidos,
            nro_documento=doc,
            email=email,
            telefono=telefono,
            id_cliente=id_cliente,
            id_persona=id_persona,
        )
        setattr(cliente, "cuit_cliente", doc)
        setattr(cliente, "domicilio", direccion)
        setattr(cliente, "activo", activo)
        return cliente

    def guardar_cliente(self) -> None:
        """Registra un nuevo cliente o actualiza uno existente y refresca el padrón."""
        if not self.puede_editar_clientes:
            messagebox.showwarning(
                "Acceso restringido",
                "Su rol solo permite consultar y seleccionar clientes.",
                parent=self,
            )
            return

        es_edicion = self.cliente_seleccionado_id is not None
        id_cliente_objetivo = self.cliente_seleccionado_id
        id_persona_objetivo = self.persona_seleccionada_id if es_edicion else None
        estado_objetivo = self.cliente_estado_activo if es_edicion else True

        cliente = self._construir_entidad_cliente(
            id_cliente=id_cliente_objetivo,
            id_persona=id_persona_objetivo,
            activo=estado_objetivo,
        )
        if cliente is None:
            return

        try:
            resultado = RepositorioVentas.guardar_cliente(cliente)
            id_guardado = _a_entero_opcional(
                getattr(cliente, "id_cliente", None)
            )
            if id_guardado is None and isinstance(resultado, Cliente):
                id_guardado = _a_entero_opcional(getattr(resultado, "id_cliente", None))
            if id_guardado is None:
                id_guardado = _a_entero_opcional(resultado)

            if not es_edicion:
                self.var_mostrar_inactivos.set(False)
                self.var_busqueda.set("")

            self.limpiar_formulario()
            self.cargar_tabla_clientes()

            if es_edicion:
                detalle_id = f" (ID #{id_guardado})" if id_guardado is not None else ""
                messagebox.showinfo(
                    "Guardado",
                    f"Cliente actualizado correctamente{detalle_id}.",
                    parent=self,
                )
            else:
                detalle_id = f" (ID #{id_guardado})" if id_guardado is not None else ""
                messagebox.showinfo(
                    "Guardado",
                    f"Cliente registrado correctamente{detalle_id}.",
                    parent=self,
                )
        except Exception as exc:
            messagebox.showerror(
                "Error al guardar cliente",
                str(exc),
                parent=self,
            )

    def toggle_estado_cliente(self) -> None:
        """Activa o desactiva lógicamente al cliente seleccionado."""
        if not self.puede_editar_clientes:
            messagebox.showwarning(
                "Acceso restringido",
                "Su rol solo permite consultar y seleccionar clientes.",
                parent=self,
            )
            return

        if self.cliente_seleccionado_id is None:
            return

        nuevo_estado = not self.cliente_estado_activo
        accion = "reactivar" if nuevo_estado else "deshabilitar"
        nombre_ref = (
            f"{self.var_apellidos.get().strip()}, {self.var_nombres.get().strip()}".strip(", ")
            or f"ID #{self.cliente_seleccionado_id}"
        )
        if not messagebox.askyesno(
            "Confirmar cambio de estado",
            f"¿Deseás {accion} al cliente '{nombre_ref}'?",
            parent=self,
        ):
            return

        try:
            RepositorioVentas.cambiar_estado_cliente(
                self.cliente_seleccionado_id, nuevo_estado
            )
            self.limpiar_formulario()
            self.cargar_tabla_clientes()
            messagebox.showinfo(
                "Estado actualizado",
                f"Cliente {'reactivado' if nuevo_estado else 'deshabilitado'} correctamente.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al actualizar estado",
                str(exc),
                parent=self,
            )

    def limpiar_formulario(self) -> None:
        """Restablece el formulario para un nuevo cliente."""
        self.cliente_seleccionado_id = None
        self.persona_seleccionada_id = None
        self.cliente_estado_activo = True
        self.cliente_es_frecuente_actual = False
        self.var_documento.set("")
        self.var_nombres.set("")
        self.var_apellidos.set("")
        self.var_telefono.set("")
        self.var_email.set("")
        self.var_direccion.set("")
        self._aplicar_permisos_botonera(tiene_seleccion=False)
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        """Carga el cliente seleccionado en el formulario."""
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        reg = self.clientes_cache.get(seleccion[0])
        if not reg:
            return

        cli: Cliente = reg["cliente"]
        self.cliente_seleccionado_id = _a_entero_opcional(
            getattr(cli, "id_cliente", None)
        )
        self.persona_seleccionada_id = _a_entero_opcional(
            getattr(cli, "id_persona", None)
        )
        self.cliente_estado_activo = bool(getattr(cli, "activo", True))
        self.cliente_es_frecuente_actual = bool(reg.get("es_frecuente", False))

        doc = str(
            getattr(cli, "nro_documento", "")
            or getattr(cli, "cuit_cliente", "")
            or getattr(cli, "dni", "")
            or ""
        )
        nombres = str(
            getattr(cli, "nombres", "") or getattr(cli, "nombre", "") or ""
        )
        apellidos = str(
            getattr(cli, "apellidos", "") or getattr(cli, "apellido", "") or ""
        )
        direccion = str(
            getattr(cli, "domicilio", "") or getattr(cli, "direccion", "") or ""
        )

        self.var_documento.set(doc)
        self.var_nombres.set(nombres)
        self.var_apellidos.set(apellidos)
        self.var_telefono.set(str(getattr(cli, "telefono", "") or ""))
        self.var_email.set(str(getattr(cli, "email", "") or ""))
        self.var_direccion.set(direccion)

        self._aplicar_permisos_botonera(tiene_seleccion=True)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Gestión Clientes")
    root.geometry("1180x740")
    InterfazClientes(root)
    root.mainloop()