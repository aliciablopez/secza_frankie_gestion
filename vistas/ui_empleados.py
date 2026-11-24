
"""
===============================================================================
MÓDULO DE INTERFAZ DE USUARIO: CAPA DE PRESENTACIÓN DE EMPLEADOS (vistas/ui_empleados.py)
===============================================================================
Permite administrar legajos, datos fiscales, cargos, contratos y visualizar
separadamente los apellidos y nombres del personal, con control RBAC por rol.
===============================================================================
"""

from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, List, Optional, Set

# Garantizar que la raíz del proyecto esté en sys.path
DIR_ACTUAL = Path(__file__).resolve().parent
RAIZ_PROYECTO = DIR_ACTUAL.parent

for path in (DIR_ACTUAL, RAIZ_PROYECTO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dominio.entidades_persona import limpiar_documento
from dominio.entidades_rrhh import CARGOS, Empleado, SECTORES, TIPOS_VINCULO
from infraestructura.repo_rrhh import RepositorioRRHH

try:
    from vistas.estilos import COLOR_TEXTO_MUTED, aplicar_estilos_base
except ImportError:
    try:
        from vistas.ui_estilos import COLOR_TEXTO_MUTED, aplicar_estilos_base
    except ImportError:
        COLOR_TEXTO_MUTED = "#556B2F"
        aplicar_estilos_base = None

ROLES_GESTION_EMPLEADOS: Set[str] = {"admin", "gerente"}
SECTORES_DISPONIBLES: List[str] = [
    s for s in SECTORES if str(s).strip().lower() != "compras"
] or list(SECTORES)


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


def formatear_cuit(cuit_limpio: str) -> str:
    """Convierte una cadena de 11 dígitos al formato de presentación XX-XXXXXXXX-X."""
    cuit_digits = "".join(filter(str.isdigit, cuit_limpio or ""))
    if len(cuit_digits) == 11:
        return f"{cuit_digits[:2]}-{cuit_digits[2:10]}-{cuit_digits[10]}"
    return cuit_limpio


def _documento_duplicado(
    cuit_limpio: str, id_persona_actual: Optional[int] = None
) -> bool:
    """Verifica si ya existe otro empleado con el mismo número de documento."""
    for emp in RepositorioRRHH.listar_empleados(incluir_inactivos=True):
        doc_emp = limpiar_documento(getattr(emp, "nro_documento", "") or "")
        if doc_emp and doc_emp == cuit_limpio:
            id_per_emp = getattr(emp, "id_persona", None)
            if id_persona_actual is None or id_per_emp != id_persona_actual:
                return True
    return False


class InterfazEmpleados(ttk.Frame):
    """Componente principal de Interfaz Gráfica para el Módulo de Recursos Humanos."""

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
        self.puede_gestionar_empleados: bool = bool(
            roles_activos & ROLES_GESTION_EMPLEADOS
        )

        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self.winfo_toplevel())
            except Exception:
                pass

        self.empleado_edicion_id: Optional[int] = None
        self.persona_edicion_id: Optional[int] = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)

        self._crear_encabezado()
        self._crear_panel_formulario()
        self._crear_panel_tabla()
        self._aplicar_permisos_ui()
        self._cargar_tabla()
        self._actualizar_legajo_sugerido()

    def _aplicar_permisos_ui(self) -> None:
        """Habilita o bloquea las acciones de RRHH según el rol activo."""
        estado_escritura = "normal" if self.puede_gestionar_empleados else "disabled"
        self.btn_guardar.config(state=estado_escritura)
        self.btn_actualizar.config(state=estado_escritura)
        self.btn_deshabilitar.config(state=estado_escritura)

    def _crear_encabezado(self) -> None:
        frame_top = ttk.Frame(self)
        frame_top.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        lbl_titulo = ttk.Label(
            frame_top,
            text="Gestión de Recursos Humanos",
            style="Subtitulo.TLabel",
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ttk.Label(
            frame_top,
            text="Administración de legajos, datos fiscales, cargos y contratos",
            style="Muted.TLabel",
        )
        lbl_subtitulo.pack(anchor="w")

    def _crear_panel_formulario(self) -> None:
        self.frame_form = ttk.LabelFrame(self, text=" Datos del Empleado ")
        self.frame_form.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_form.columnconfigure((1, 3), weight=1)

        # Row 0: Nombres y Apellidos
        ttk.Label(self.frame_form, text="Nombres:").grid(
            row=0, column=0, padx=10, pady=4, sticky="w"
        )
        self.txt_nombres = ttk.Entry(self.frame_form)
        self.txt_nombres.grid(row=0, column=1, padx=10, pady=4, sticky="ew")

        ttk.Label(self.frame_form, text="Apellidos:").grid(
            row=0, column=2, padx=10, pady=4, sticky="w"
        )
        self.txt_apellidos = ttk.Entry(self.frame_form)
        self.txt_apellidos.grid(row=0, column=3, padx=10, pady=4, sticky="ew")

        # Row 1: CUIT y Legajo
        ttk.Label(self.frame_form, text="CUIT (11 dígitos):").grid(
            row=1, column=0, padx=10, pady=4, sticky="w"
        )
        self.txt_documento = ttk.Entry(self.frame_form)
        self.txt_documento.grid(row=1, column=1, padx=10, pady=4, sticky="ew")

        ttk.Label(self.frame_form, text="Legajo:").grid(
            row=1, column=2, padx=10, pady=4, sticky="w"
        )
        self.txt_legajo = ttk.Entry(self.frame_form)
        self.txt_legajo.grid(row=1, column=3, padx=10, pady=4, sticky="ew")

        # Row 2: Cargo y Sector
        ttk.Label(self.frame_form, text="Cargo:").grid(
            row=2, column=0, padx=10, pady=4, sticky="w"
        )
        self.cmb_cargo = ttk.Combobox(self.frame_form, values=CARGOS, state="readonly")
        default_cargo = "Vendedor" if "Vendedor" in CARGOS else CARGOS[0]
        self.cmb_cargo.set(default_cargo)
        self.cmb_cargo.grid(row=2, column=1, padx=10, pady=4, sticky="ew")

        ttk.Label(self.frame_form, text="Sector:").grid(
            row=2, column=2, padx=10, pady=4, sticky="w"
        )
        self.cmb_sector = ttk.Combobox(
            self.frame_form, values=SECTORES_DISPONIBLES, state="readonly"
        )
        default_sector = (
            "Ventas" if "Ventas" in SECTORES_DISPONIBLES else SECTORES_DISPONIBLES[0]
        )
        self.cmb_sector.set(default_sector)
        self.cmb_sector.grid(row=2, column=3, padx=10, pady=4, sticky="ew")

        # Row 3: Tipo de Vínculo y Sueldo Base
        ttk.Label(self.frame_form, text="Vínculo Laboral:").grid(
            row=3, column=0, padx=10, pady=4, sticky="w"
        )
        self.cmb_vinculo = ttk.Combobox(
            self.frame_form, values=TIPOS_VINCULO, state="readonly"
        )
        default_vinculo = (
            "Contratado" if "Contratado" in TIPOS_VINCULO else TIPOS_VINCULO[0]
        )
        self.cmb_vinculo.set(default_vinculo)
        self.cmb_vinculo.grid(row=3, column=1, padx=10, pady=4, sticky="ew")

        ttk.Label(self.frame_form, text="Sueldo Base ($):").grid(
            row=3, column=2, padx=10, pady=4, sticky="w"
        )
        self.txt_sueldo = ttk.Entry(self.frame_form)
        self.txt_sueldo.grid(row=3, column=3, padx=10, pady=4, sticky="ew")

        # Row 4: Teléfono y Email
        ttk.Label(self.frame_form, text="Teléfono:").grid(
            row=4, column=0, padx=10, pady=4, sticky="w"
        )
        self.txt_telefono = ttk.Entry(self.frame_form)
        self.txt_telefono.grid(row=4, column=1, padx=10, pady=4, sticky="ew")

        ttk.Label(self.frame_form, text="Email:").grid(
            row=4, column=2, padx=10, pady=4, sticky="w"
        )
        self.txt_email = ttk.Entry(self.frame_form)
        self.txt_email.grid(row=4, column=3, padx=10, pady=4, sticky="ew")

        # Row 5: Botonera en orden Guardar, Actualizar, Limpiar, Deshabilitar
        frame_botones = ttk.Frame(self.frame_form)
        frame_botones.grid(row=5, column=0, columnspan=4, pady=10, sticky="w")

        self.btn_guardar = ttk.Button(
            frame_botones,
            text="Guardar",
            command=self._guardar_empleado,
        )
        self.btn_guardar.pack(side="left", padx=(10, 5))

        self.btn_actualizar = ttk.Button(
            frame_botones,
            text="Actualizar",
            command=self._cargar_seleccion_formulario,
        )
        self.btn_actualizar.pack(side="left", padx=5)

        self.btn_limpiar = ttk.Button(
            frame_botones,
            text="Limpiar",
            command=self._limpiar_formulario,
        )
        self.btn_limpiar.pack(side="left", padx=5)

        self.btn_deshabilitar = ttk.Button(
            frame_botones,
            text="Deshabilitar",
            command=self._alternar_estado_empleado,
        )
        self.btn_deshabilitar.pack(side="left", padx=5)

    def _crear_panel_tabla(self) -> None:
        frame_tabla = ttk.LabelFrame(self, text=" Nómina de Personal ")
        frame_tabla.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="nsew")
        frame_tabla.columnconfigure(0, weight=1)
        frame_tabla.rowconfigure(1, weight=1)

        frame_filtro = ttk.Frame(frame_tabla)
        frame_filtro.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        ttk.Label(frame_filtro, text="Buscar:").pack(side="left", padx=(0, 5))
        self.txt_buscar = ttk.Entry(frame_filtro)
        self.txt_buscar.pack(side="left", fill="x", expand=True, padx=5)
        self.txt_buscar.bind("<KeyRelease>", self._al_buscar_tecla)

        self.var_inactivos = tk.BooleanVar(value=False)
        self.chk_inactivos = ttk.Checkbutton(
            frame_filtro,
            text="Mostrar Inactivos",
            variable=self.var_inactivos,
            command=self._cargar_tabla,
        )
        self.chk_inactivos.pack(side="right", padx=10)

        columnas = (
            "id",
            "legajo",
            "cuit",
            "apellidos",
            "nombres",
            "cargo",
            "sector",
            "vinculo",
            "sueldo",
            "estado",
        )
        self.tabla = ttk.Treeview(
            frame_tabla, columns=columnas, show="headings", height=6
        )

        self.tabla.heading("id", text="ID")
        self.tabla.heading("legajo", text="Legajo")
        self.tabla.heading("cuit", text="CUIT")
        self.tabla.heading("apellidos", text="Apellidos")
        self.tabla.heading("nombres", text="Nombres")
        self.tabla.heading("cargo", text="Cargo")
        self.tabla.heading("sector", text="Sector")
        self.tabla.heading("vinculo", text="Vínculo")
        self.tabla.heading("sueldo", text="Sueldo Base")
        self.tabla.heading("estado", text="Estado")

        self.tabla.column("id", width=50, anchor="center", stretch=False)
        self.tabla.column("legajo", width=90, anchor="center", stretch=False)
        self.tabla.column("cuit", width=130, anchor="center", stretch=False)
        self.tabla.column("apellidos", width=150, anchor="w", stretch=False)
        self.tabla.column("nombres", width=150, anchor="w", stretch=False)
        self.tabla.column("cargo", width=130, anchor="w", stretch=False)
        self.tabla.column("sector", width=110, anchor="w", stretch=False)
        self.tabla.column("vinculo", width=110, anchor="center", stretch=False)
        self.tabla.column("sueldo", width=110, anchor="e", stretch=False)
        self.tabla.column("estado", width=90, anchor="center", stretch=False)

        scrollbar_y = ttk.Scrollbar(
            frame_tabla, orient="vertical", command=self.tabla.yview
        )
        scrollbar_x = ttk.Scrollbar(
            frame_tabla, orient="horizontal", command=self.tabla.xview
        )
        self.tabla.configure(
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )

        self.tabla.grid(row=1, column=0, padx=(10, 0), pady=(5, 0), sticky="nsew")
        scrollbar_y.grid(row=1, column=1, padx=(0, 10), pady=(5, 0), sticky="ns")
        scrollbar_x.grid(row=2, column=0, padx=(10, 0), pady=(0, 8), sticky="ew")

        self.tabla.bind("<Double-1>", self._al_doble_click_tabla)
        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            self.btn_deshabilitar.configure(text="Deshabilitar")
            return
        valores = self.tabla.item(seleccion[0], "values")
        if len(valores) >= 10:
            estado_actual = valores[9]
            self.btn_deshabilitar.configure(
                text="Habilitar" if estado_actual != "Activo" else "Deshabilitar"
            )

    def _actualizar_legajo_sugerido(self) -> None:
        self.txt_legajo.config(state="normal")
        self.txt_legajo.delete(0, "end")
        if self.empleado_edicion_id is None:
            siguiente = RepositorioRRHH.generar_siguiente_legajo()
            self.txt_legajo.insert(0, siguiente)
        self.txt_legajo.config(state="disabled")

    def _al_buscar_tecla(self, _event: Any) -> None:
        self._cargar_tabla()

    def _cargar_tabla(self) -> None:
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        criterio = self.txt_buscar.get().strip() if hasattr(self, "txt_buscar") else ""
        incluir_inactivos = (
            self.var_inactivos.get() if hasattr(self, "var_inactivos") else False
        )

        empleados: list[Empleado] = RepositorioRRHH.listar_empleados(
            criterio_busqueda=criterio,
            incluir_inactivos=incluir_inactivos,
        )

        for emp in empleados:
            estado_txt = "Activo" if emp.activo else "Inactivo"
            cuit_formateado = formatear_cuit(emp.nro_documento)
            sueldo_val = float(getattr(emp, "sueldo", 0.0) or 0.0)

            self.tabla.insert(
                "",
                "end",
                values=(
                    emp.id_empleado,
                    emp.legajo,
                    cuit_formateado,
                    emp.apellidos or "",
                    emp.nombres or "",
                    emp.cargo,
                    emp.sector,
                    getattr(emp, "tipo_vinculo", "Contratado"),
                    f"$ {sueldo_val:,.2f}",
                    estado_txt,
                ),
            )

        self._al_seleccionar_fila()

    def _limpiar_formulario(self) -> None:
        self.empleado_edicion_id = None
        self.persona_edicion_id = None
        self.txt_nombres.delete(0, "end")
        self.txt_apellidos.delete(0, "end")
        self.txt_documento.delete(0, "end")
        self.txt_sueldo.delete(0, "end")
        self.txt_telefono.delete(0, "end")
        self.txt_email.delete(0, "end")

        default_cargo = "Vendedor" if "Vendedor" in CARGOS else CARGOS[0]
        default_sector = (
            "Ventas" if "Ventas" in SECTORES_DISPONIBLES else SECTORES_DISPONIBLES[0]
        )
        default_vinculo = (
            "Contratado" if "Contratado" in TIPOS_VINCULO else TIPOS_VINCULO[0]
        )

        self.cmb_cargo.set(default_cargo)
        self.cmb_sector.set(default_sector)
        self.cmb_vinculo.set(default_vinculo)
        self.btn_guardar.configure(text="Guardar")

        self._actualizar_legajo_sugerido()
        self._aplicar_permisos_ui()

    def _guardar_empleado(self) -> None:
        if not self.puede_gestionar_empleados:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo Admin o Gerente pueden agregar o modificar empleados.",
                parent=self,
            )
            return

        nombres = self.txt_nombres.get().strip()
        apellidos = self.txt_apellidos.get().strip()
        cuit_raw = self.txt_documento.get().strip()
        cuit_limpio = limpiar_documento(cuit_raw)

        self.txt_legajo.config(state="normal")
        legajo = self.txt_legajo.get().strip()
        self.txt_legajo.config(state="disabled")

        sueldo_str = self.txt_sueldo.get().strip()

        if not nombres or not apellidos:
            messagebox.showwarning("Atención", "Nombres y Apellidos son obligatorios.")
            return

        if not cuit_limpio or len(cuit_limpio) != 11 or not cuit_limpio.isdigit():
            messagebox.showwarning(
                "Atención", "Ingrese un CUIT válido de 11 dígitos numéricos."
            )
            return

        if _documento_duplicado(cuit_limpio, id_persona_actual=self.persona_edicion_id):
            messagebox.showerror(
                "Error",
                f"El CUIT '{formatear_cuit(cuit_limpio)}' ya está registrado.",
            )
            return

        sueldo_override: Optional[float] = None
        if sueldo_str:
            try:
                sueldo_override = float(sueldo_str)
            except ValueError:
                messagebox.showerror(
                    "Error", "El sueldo debe ser un valor numérico decimal válido."
                )
                return

        emp = Empleado(
            nro_documento=cuit_limpio,
            nombres=nombres,
            legajo=legajo,
            cargo=self.cmb_cargo.get(),
            sector=self.cmb_sector.get(),
            tipo_vinculo=self.cmb_vinculo.get(),
            apellidos=apellidos,
            telefono=self.txt_telefono.get().strip(),
            email=self.txt_email.get().strip(),
            id_empleado=self.empleado_edicion_id,
            id_persona=self.persona_edicion_id,
        )
        if sueldo_override is not None:
            emp.sueldo = sueldo_override

        if self.empleado_edicion_id:
            exito = RepositorioRRHH.actualizar_empleado(emp)
            msg = "Empleado actualizado correctamente."
        else:
            exito = RepositorioRRHH.crear_empleado(emp)
            msg = "Empleado registrado con éxito."

        if exito:
            messagebox.showinfo("Éxito", msg)
            self._limpiar_formulario()
            self._cargar_tabla()
        else:
            messagebox.showerror(
                "Error", "Ocurrió un fallo en la operación de base de datos."
            )

    def _cargar_seleccion_formulario(self) -> None:
        if not self.puede_gestionar_empleados:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo Admin o Gerente pueden editar empleados.",
                parent=self,
            )
            return

        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning(
                "Atención", "Seleccione un empleado de la lista para actualizar."
            )
            return

        valores = self.tabla.item(seleccion[0], "values")
        id_empleado = int(valores[0])

        empleados = RepositorioRRHH.listar_empleados(incluir_inactivos=True)
        emp_sel = next((e for e in empleados if e.id_empleado == id_empleado), None)

        if emp_sel:
            id_per = emp_sel.id_persona
            self._limpiar_formulario()
            self.empleado_edicion_id = emp_sel.id_empleado
            self.persona_edicion_id = id_per
            self.txt_nombres.insert(0, emp_sel.nombres or "")
            self.txt_apellidos.insert(0, emp_sel.apellidos or "")
            self.txt_documento.insert(0, emp_sel.nro_documento or "")

            self.txt_legajo.config(state="normal")
            self.txt_legajo.delete(0, "end")
            self.txt_legajo.insert(0, emp_sel.legajo or "")
            self.txt_legajo.config(state="disabled")

            sueldo_actual = float(getattr(emp_sel, "sueldo", 0.0) or 0.0)
            self.txt_sueldo.insert(0, str(sueldo_actual))
            self.txt_telefono.insert(0, emp_sel.telefono or "")
            self.txt_email.insert(0, emp_sel.email or "")

            if emp_sel.cargo in CARGOS:
                self.cmb_cargo.set(emp_sel.cargo)
            if emp_sel.sector in SECTORES_DISPONIBLES:
                self.cmb_sector.set(emp_sel.sector)
            vinculo_actual = getattr(emp_sel, "tipo_vinculo", "")
            if vinculo_actual in TIPOS_VINCULO:
                self.cmb_vinculo.set(vinculo_actual)

            self.btn_guardar.configure(text="Guardar")
            self._aplicar_permisos_ui()

    def _al_doble_click_tabla(self, _event: Any) -> None:
        if self.puede_gestionar_empleados:
            self._cargar_seleccion_formulario()

    def _alternar_estado_empleado(self) -> None:
        if not self.puede_gestionar_empleados:
            messagebox.showwarning(
                "Acceso restringido",
                "Solo Admin o Gerente pueden cambiar el estado de empleados.",
                parent=self,
            )
            return

        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning(
                "Atención", "Seleccione un empleado para cambiar su estado."
            )
            return

        valores = self.tabla.item(seleccion[0], "values")
        id_empleado = int(valores[0])
        estado_actual = valores[9]

        nuevo_estado: bool = estado_actual != "Activo"
        accion_str = "desactivar" if not nuevo_estado else "activar"

        if messagebox.askyesno(
            "Confirmar", f"¿Desea {accion_str} al empleado seleccionado?"
        ):
            if RepositorioRRHH.cambiar_estado_empleado(id_empleado, nuevo_estado):
                messagebox.showinfo("Éxito", f"Empleado {accion_str}do correctamente.")
                self._cargar_tabla()
            else:
                messagebox.showerror(
                    "Error", "No se pudo cambiar el estado en la base de datos."
                )
