"""
===============================================================================
MÓDULO DE VISTAS: PROVEEDORES (vistas/ui_proveedores.py)
===============================================================================
Alta, Listado, Edición y Baja/Reactivación Lógica de proveedores
(Persona Jurídica, CUIT prefijo 30, rubro, contacto, teléfono, email y
domicilio), usando la denominación unificada "Proveedores".
Incluye control RBAC para operaciones de escritura y cambio de estado.
===============================================================================
"""

from typing import Any, cast, Dict, Literal, Optional, Set, Tuple
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from dominio.entidades_proveedores import Proveedor, RUBROS_PROVEEDOR
from infraestructura.repo_proveedores import RepositorioProveedores

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

ROLES_GESTION_PROVEEDORES: Set[str] = {"admin", "gerente"}


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
    return roles


def _a_entero_opcional(valor: Any) -> Optional[int]:
    """Convierte a int de forma segura, o devuelve None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        try:
            return int(float(texto))
        except ValueError:
            return None
    return None


class InterfazProveedores(ttk.Frame):
    """Vista modular para gestionar Proveedores con patrón visual apilado."""

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
        self.puede_gestionar_proveedores: bool = (
            True
            if usuario_actual is None
            else bool(roles_activos & ROLES_GESTION_PROVEEDORES)
        )

        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self.winfo_toplevel())
            except Exception:
                pass

        self.pack(fill="both", expand=True, padx=10, pady=10)

        self.proveedor_seleccionado_id: Optional[int] = None
        self.persona_seleccionada_id: Optional[int] = None
        self.proveedor_activo: bool = True
        self.proveedores_cache: Dict[str, Proveedor] = {}

        self.var_cuit = tk.StringVar()
        self.var_razon_social = tk.StringVar()
        self.var_rubro = tk.StringVar(
            value=RUBROS_PROVEEDOR[0] if RUBROS_PROVEEDOR else ""
        )
        self.var_contacto = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_domicilio = tk.StringVar()

        self.var_busqueda = tk.StringVar()
        self.var_rubro_filtro = tk.StringVar(value="Todos")
        self.var_mostrar_inactivos = tk.BooleanVar(value=False)

        self._construir_interfaz()
        self._configurar_fuentes()
        self._aplicar_permisos_ui()
        self.cargar_tabla_proveedores()

    def _aplicar_permisos_ui(self) -> None:
        """Habilita o bloquea acciones de escritura según el rol del usuario."""
        estado_escritura = "normal" if self.puede_gestionar_proveedores else "disabled"
        self.btn_guardar.config(state=estado_escritura)
        if not self.puede_gestionar_proveedores:
            self.btn_toggle_estado.config(state="disabled")
        elif self.proveedor_seleccionado_id is None:
            self.btn_toggle_estado.config(state="disabled")

    def _configurar_fuentes(self) -> None:
        """Fuerza 12 pt sin itálicas (slant='roman') en fuentes Tk, entradas y ttk."""
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

    def _construir_interfaz(self) -> None:
        # 1. Formulario superior apilado (2 columnas)
        frame_form = ttk.LabelFrame(
            self, text=" Datos de Proveedores ", padding=15
        )
        frame_form.pack(fill="x", padx=5, pady=5)
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

        # Fila 0: CUIT | Razón Social
        ttk.Label(frame_form, text="CUIT (30-...) *:").grid(
            row=0, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_cuit).grid(
            row=0, column=1, sticky="ew", padx=6, pady=6
        )

        ttk.Label(frame_form, text="Razón Social *:").grid(
            row=0, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_razon_social).grid(
            row=0, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 1: Rubro | Contacto
        ttk.Label(frame_form, text="Rubro *:").grid(
            row=1, column=0, sticky="w", padx=6, pady=6
        )
        self.combo_rubro = ttk.Combobox(
            frame_form,
            textvariable=self.var_rubro,
            state="readonly",
            values=tuple(RUBROS_PROVEEDOR),
        )
        self.combo_rubro.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(frame_form, text="Contacto:").grid(
            row=1, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_contacto).grid(
            row=1, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 2: Teléfono | Email
        ttk.Label(frame_form, text="Teléfono:").grid(
            row=2, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_telefono).grid(
            row=2, column=1, sticky="ew", padx=6, pady=6
        )

        ttk.Label(frame_form, text="Email:").grid(
            row=2, column=2, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_email).grid(
            row=2, column=3, sticky="ew", padx=6, pady=6
        )

        # Fila 3: Domicilio | Botonera
        ttk.Label(frame_form, text="Domicilio:").grid(
            row=3, column=0, sticky="w", padx=6, pady=6
        )
        ttk.Entry(frame_form, textvariable=self.var_domicilio).grid(
            row=3, column=1, sticky="ew", padx=6, pady=6
        )

        frame_botones = ttk.Frame(frame_form)
        frame_botones.grid(row=3, column=2, columnspan=2, sticky="e", padx=6, pady=6)

        self.btn_guardar = ttk.Button(
            frame_botones,
            text="Guardar",
            command=self.guardar_proveedor,
        )
        self.btn_guardar.pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="Limpiar",
            command=self.limpiar_formulario,
        ).pack(side="left", padx=4)

        self.btn_toggle_estado = ttk.Button(
            frame_botones,
            text="Deshabilitar",
            command=self.toggle_estado_proveedor,
            state="disabled",
        )
        self.btn_toggle_estado.pack(side="left", padx=4)

        # 2. Tabla inferior apilada: Proveedores
        frame_tabla = ttk.LabelFrame(
            self,
            text=" Proveedores (Seleccione una fila para editar o cambiar estado) ",
            padding=15,
        )
        frame_tabla.pack(fill="both", expand=True, padx=5, pady=5)

        frame_filtros = ttk.Frame(frame_tabla)
        frame_filtros.pack(fill="x", pady=(0, 8))

        ttk.Label(frame_filtros, text="Buscar:").pack(side="left", padx=(0, 6))
        entry_buscar = ttk.Entry(frame_filtros, textvariable=self.var_busqueda)
        entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry_buscar.bind("<KeyRelease>", lambda _e: self.cargar_tabla_proveedores())

        ttk.Label(frame_filtros, text="Rubro:").pack(side="left", padx=(0, 4))
        combo_filtro_rubro = ttk.Combobox(
            frame_filtros,
            textvariable=self.var_rubro_filtro,
            state="readonly",
            values=("Todos", *RUBROS_PROVEEDOR),
            width=18,
        )
        combo_filtro_rubro.pack(side="left", padx=(0, 10))
        combo_filtro_rubro.bind(
            "<<ComboboxSelected>>", lambda _e: self.cargar_tabla_proveedores()
        )

        ttk.Checkbutton(
            frame_filtros,
            text="Mostrar inactivos",
            variable=self.var_mostrar_inactivos,
            command=self.cargar_tabla_proveedores,
        ).pack(side="right")

        frame_grilla = ttk.Frame(frame_tabla)
        frame_grilla.pack(fill="both", expand=True)
        frame_grilla.rowconfigure(0, weight=1)
        frame_grilla.rowconfigure(1, weight=0)
        frame_grilla.columnconfigure(0, weight=1)
        frame_grilla.columnconfigure(1, weight=0)

        columnas = (
            "id",
            "cuit",
            "razon_social",
            "rubro",
            "contacto",
            "telefono",
            "email",
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
            "id": ("ID", 55, "center"),
            "cuit": ("CUIT", 145, "center"),
            "razon_social": ("Razón Social", 240, "w"),
            "rubro": ("Rubro", 150, "w"),
            "contacto": ("Contacto", 170, "w"),
            "telefono": ("Teléfono", 140, "center"),
            "email": ("Email", 210, "w"),
            "estado": ("Estado", 100, "center"),
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

    def cargar_tabla_proveedores(self) -> None:
        """Carga los proveedores aplicando búsqueda, filtro de rubro y estado."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.proveedores_cache.clear()

        try:
            proveedores = RepositorioProveedores.listar_proveedores(
                criterio_busqueda=self.var_busqueda.get().strip(),
                rubro_filtro=self.var_rubro_filtro.get().strip(),
                incluir_inactivos=bool(self.var_mostrar_inactivos.get()),
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al cargar proveedores", str(exc), parent=self
            )
            return

        for prov in proveedores:
            id_prov = _a_entero_opcional(getattr(prov, "id_proveedor", None))
            activo = bool(getattr(prov, "activo", True))
            iid = self.tabla.insert(
                "",
                "end",
                values=(
                    id_prov if id_prov is not None else "-",
                    str(getattr(prov, "cuit", "") or "-"),
                    str(getattr(prov, "razon_social", "") or "-"),
                    str(getattr(prov, "rubro", "") or "-"),
                    str(getattr(prov, "contacto", "") or "-"),
                    str(getattr(prov, "telefono", "") or "-"),
                    str(getattr(prov, "email", "") or "-"),
                    "Activo" if activo else "Inactivo",
                ),
            )
            self.proveedores_cache[iid] = prov

    def _construir_entidad_proveedor(
        self,
        id_proveedor: Optional[int],
        id_persona: Optional[int],
        activo: bool,
    ) -> Proveedor:
        """Construye la entidad Proveedor a partir de los campos del formulario."""
        return Proveedor(
            id_proveedor=id_proveedor,
            id_persona=id_persona,
            cuit=self.var_cuit.get().strip(),
            razon_social=self.var_razon_social.get().strip(),
            rubro=self.var_rubro.get().strip(),
            contacto=self.var_contacto.get().strip(),
            telefono=self.var_telefono.get().strip(),
            email=self.var_email.get().strip(),
            domicilio=self.var_domicilio.get().strip(),
            activo=activo,
        )

    def guardar_proveedor(self) -> None:
        """Registra un nuevo proveedor o actualiza el seleccionado y refresca la tabla."""
        if not self.puede_gestionar_proveedores:
            messagebox.showwarning(
                "Acceso restringido",
                "Tu rol actual no tiene permisos para registrar o modificar proveedores.",
                parent=self,
            )
            return

        es_edicion = self.proveedor_seleccionado_id is not None
        prov = self._construir_entidad_proveedor(
            id_proveedor=self.proveedor_seleccionado_id,
            id_persona=self.persona_seleccionada_id,
            activo=self.proveedor_activo if es_edicion else True,
        )
        try:
            RepositorioProveedores.guardar_proveedor(prov)
            self.limpiar_formulario()
            self.cargar_tabla_proveedores()
            messagebox.showinfo(
                "Guardado",
                "Proveedor actualizado correctamente."
                if es_edicion
                else "Proveedor registrado correctamente.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al guardar proveedor", str(exc), parent=self
            )

    def toggle_estado_proveedor(self) -> None:
        """Activa o desactiva lógicamente al proveedor seleccionado."""
        if not self.puede_gestionar_proveedores:
            messagebox.showwarning(
                "Acceso restringido",
                "Tu rol actual no tiene permisos para cambiar el estado de proveedores.",
                parent=self,
            )
            return

        if self.proveedor_seleccionado_id is None:
            return

        nuevo_estado = not self.proveedor_activo
        accion = "reactivar" if nuevo_estado else "deshabilitar"
        if not messagebox.askyesno(
            "Confirmar cambio de estado",
            f"¿Deseás {accion} al proveedor '{self.var_razon_social.get().strip()}'?",
            parent=self,
        ):
            return

        try:
            RepositorioProveedores.cambiar_estado_proveedor(
                self.proveedor_seleccionado_id, nuevo_estado
            )
            self.limpiar_formulario()
            self.cargar_tabla_proveedores()
        except Exception as exc:
            messagebox.showerror(
                "Error al cambiar estado", str(exc), parent=self
            )

    def limpiar_formulario(self) -> None:
        """Restablece el formulario para un nuevo proveedor."""
        self.proveedor_seleccionado_id = None
        self.persona_seleccionada_id = None
        self.proveedor_activo = True
        self.var_cuit.set("")
        self.var_razon_social.set("")
        if RUBROS_PROVEEDOR:
            self.var_rubro.set(RUBROS_PROVEEDOR[0])
        self.var_contacto.set("")
        self.var_telefono.set("")
        self.var_email.set("")
        self.var_domicilio.set("")
        self.btn_guardar.config(
            state="normal" if self.puede_gestionar_proveedores else "disabled"
        )
        self.btn_toggle_estado.config(text="Deshabilitar", state="disabled")
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        """Carga el proveedor seleccionado en el formulario."""
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        prov = self.proveedores_cache.get(seleccion[0])
        if prov is None:
            return

        self.proveedor_seleccionado_id = _a_entero_opcional(
            getattr(prov, "id_proveedor", None)
        )
        self.persona_seleccionada_id = _a_entero_opcional(
            getattr(prov, "id_persona", None)
        )
        self.proveedor_activo = bool(getattr(prov, "activo", True))

        self.var_cuit.set(str(getattr(prov, "cuit", "") or ""))
        self.var_razon_social.set(str(getattr(prov, "razon_social", "") or ""))
        rubro_val = str(getattr(prov, "rubro", "") or "")
        if rubro_val in RUBROS_PROVEEDOR:
            self.var_rubro.set(rubro_val)
        elif RUBROS_PROVEEDOR:
            self.var_rubro.set(RUBROS_PROVEEDOR[0])
        self.var_contacto.set(str(getattr(prov, "contacto", "") or ""))
        self.var_telefono.set(str(getattr(prov, "telefono", "") or ""))
        self.var_email.set(str(getattr(prov, "email", "") or ""))
        self.var_domicilio.set(str(getattr(prov, "domicilio", "") or ""))

        estado_btn = "normal" if self.puede_gestionar_proveedores else "disabled"
        self.btn_toggle_estado.config(
            state=estado_btn,
            text="Reactivar" if not self.proveedor_activo else "Deshabilitar",
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor Comercial - Proveedores")
    root.geometry("1180x740")
    InterfazProveedores(root)
    root.mainloop()