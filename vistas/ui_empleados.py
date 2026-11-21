"""
===============================================================================
MÓDULO DE VISTAS: INTERFAZ DE EMPLEADOS (vistas/ui_empleados.py)
===============================================================================
Gestión completa del padrón de personal: Alta, Listado, Edición y Baja Lógica.
Sincronizado con CARGOS, SECTORES y TIPOS_VINCULO de dominio/entidades_rrhh.py.
===============================================================================
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Optional

from dominio.entidades_rrhh import CARGOS, SECTORES, TIPOS_VINCULO, Empleado
from infraestructura.repo_rrhh import RepositorioRRHH

try:
    from vistas.ui_estilos import aplicar_estilos_base
except ImportError:
    try:
        from vistas.estilos import aplicar_estilos_base
    except ImportError:
        aplicar_estilos_base = None


def _cargo_por_defecto() -> str:
    """Devuelve un cargo válido inicial compatible con CARGOS."""
    if "Vendedor" in CARGOS:
        return "Vendedor"
    return CARGOS[0] if CARGOS else "Vendedor"


def _sector_por_defecto() -> str:
    """Devuelve un sector válido inicial compatible con SECTORES."""
    if "Ventas" in SECTORES:
        return "Ventas"
    return SECTORES[0] if SECTORES else "Ventas"


def _vinculo_por_defecto() -> str:
    """Devuelve un tipo de vínculo válido inicial compatible con TIPOS_VINCULO."""
    if "Contratado" in TIPOS_VINCULO:
        return "Contratado"
    return TIPOS_VINCULO[0] if TIPOS_VINCULO else "Contratado"


class InterfazEmpleados(ttk.Frame):
    """Panel de control y gestión del padrón de empleados (Módulo de RR. HH.)."""

    def __init__(self, parent):
        super().__init__(parent)
        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self)
            except Exception:
                pass

        self.pack(fill="both", expand=True, padx=10, pady=10)

        # Estado de selección y caché local para edición rápida
        self.empleado_seleccionado_id: Optional[int] = None
        self.persona_seleccionada_id: Optional[int] = None
        self.empleado_estado_activo: bool = True
        self.empleados_cache: Dict[str, Empleado] = {}

        # Variables de control del formulario (terna homogénea por defecto)
        self.var_legajo = tk.StringVar()
        self.var_documento = tk.StringVar()
        self.var_nombres = tk.StringVar()
        self.var_apellidos = tk.StringVar()
        self.var_cargo = tk.StringVar(value=_cargo_por_defecto())
        self.var_sector = tk.StringVar(value=_sector_por_defecto())
        self.var_vinculo = tk.StringVar(value=_vinculo_por_defecto())
        self.var_sueldo = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_telefono = tk.StringVar()

        self.var_busqueda = tk.StringVar()
        self.var_mostrar_inactivos = tk.BooleanVar(value=False)

        self._construir_interfaz()
        self.sugerir_legajo()
        self.cargar_tabla_empleados()

    def _construir_interfaz(self):
        # 1. Formulario de Datos
        frame_form = ttk.LabelFrame(self, text=" Datos del Empleado ", padding=15)
        frame_form.pack(fill="x", padx=5, pady=5)
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

        # Fila 0: Legajo y CUIL
        ttk.Label(frame_form, text="Legajo:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        entry_legajo = ttk.Entry(
            frame_form, textvariable=self.var_legajo, width=15, state="readonly"
        )
        entry_legajo.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frame_form, text="CUIL (11 dígitos) *:").grid(
            row=0, column=2, sticky="w", padx=5, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_documento, width=22).grid(
            row=0, column=3, sticky="w", padx=5, pady=5
        )

        # Fila 1: Nombres y Apellidos
        ttk.Label(frame_form, text="Nombres *:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame_form, textvariable=self.var_nombres, width=25).grid(
            row=1, column=1, sticky="ew", padx=5, pady=5
        )

        ttk.Label(frame_form, text="Apellidos *:").grid(
            row=1, column=2, sticky="w", padx=5, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_apellidos, width=25).grid(
            row=1, column=3, sticky="ew", padx=5, pady=5
        )

        # Fila 2: Cargo y Sector
        ttk.Label(frame_form, text="Cargo *:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.combo_cargo = ttk.Combobox(
            frame_form,
            textvariable=self.var_cargo,
            state="readonly",
            values=CARGOS,
        )
        self.combo_cargo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(frame_form, text="Sector *:").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        self.combo_sector = ttk.Combobox(
            frame_form,
            textvariable=self.var_sector,
            state="readonly",
            values=SECTORES,
        )
        self.combo_sector.grid(row=2, column=3, sticky="ew", padx=5, pady=5)

        # Fila 3: Vínculo y Sueldo
        ttk.Label(frame_form, text="Vínculo *:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.combo_vinculo = ttk.Combobox(
            frame_form,
            textvariable=self.var_vinculo,
            state="readonly",
            values=TIPOS_VINCULO,
        )
        self.combo_vinculo.grid(row=3, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(frame_form, text="Sueldo Base ($) *:").grid(
            row=3, column=2, sticky="w", padx=5, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_sueldo, width=22).grid(
            row=3, column=3, sticky="w", padx=5, pady=5
        )

        # Fila 4: Contacto
        ttk.Label(frame_form, text="Email *:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame_form, textvariable=self.var_email, width=25).grid(
            row=4, column=1, sticky="ew", padx=5, pady=5
        )

        ttk.Label(frame_form, text="Teléfono:").grid(row=4, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame_form, textvariable=self.var_telefono, width=22).grid(
            row=4, column=3, sticky="w", padx=5, pady=5
        )

        # Botonera del Formulario
        frame_botones = ttk.Frame(frame_form)
        frame_botones.grid(row=5, column=0, columnspan=4, sticky="e", pady=10)

        ttk.Button(
            frame_botones, text="Limpiar / Nuevo", command=self.limpiar_formulario
        ).pack(side="left", padx=5)

        self.btn_toggle_estado = ttk.Button(
            frame_botones,
            text="Deshabilitar",
            command=self.toggle_estado_empleado,
            state="disabled",
        )
        self.btn_toggle_estado.pack(side="left", padx=5)

        self.btn_guardar = ttk.Button(
            frame_botones, text="Guardar Empleado", command=self.guardar_empleado
        )
        self.btn_guardar.pack(side="left", padx=5)

        # 2. Sección de Listado (Tabla Treeview)
        frame_tabla = ttk.LabelFrame(
            self,
            text=" Padrón de Personal Registrado (Seleccione una fila para editar o deshabilitar) ",
            padding=15,
        )
        frame_tabla.pack(fill="both", expand=True, padx=5, pady=5)

        # Filtro de Búsqueda
        frame_busqueda = ttk.Frame(frame_tabla)
        frame_busqueda.pack(fill="x", pady=(0, 8))

        ttk.Label(frame_busqueda, text="Buscar empleado:").pack(side="left", padx=(0, 5))
        entry_buscar = ttk.Entry(frame_busqueda, textvariable=self.var_busqueda)
        entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry_buscar.bind("<KeyRelease>", lambda _e: self.cargar_tabla_empleados())

        chk_inactivos = ttk.Checkbutton(
            frame_busqueda,
            text="Mostrar inactivos",
            variable=self.var_mostrar_inactivos,
            command=self.cargar_tabla_empleados,
        )
        chk_inactivos.pack(side="right")

        # Contenedor exclusivo de Tabla + Barras de Desplazamiento
        frame_grilla = ttk.Frame(frame_tabla)
        frame_grilla.pack(fill="both", expand=True)
        frame_grilla.rowconfigure(0, weight=1)
        frame_grilla.columnconfigure(0, weight=1)

        columnas = (
            "id",
            "legajo",
            "nombre",
            "documento",
            "cargo",
            "sector",
            "vinculo",
            "sueldo",
            "email",
            "telefono",
            "estado",
        )
        self.tabla = ttk.Treeview(frame_grilla, columns=columnas, show="headings", height=8)

        self.tabla.heading("id", text="ID")
        self.tabla.heading("legajo", text="Legajo")
        self.tabla.heading("nombre", text="Nombre Completo")
        self.tabla.heading("documento", text="CUIL")
        self.tabla.heading("cargo", text="Cargo")
        self.tabla.heading("sector", text="Sector")
        self.tabla.heading("vinculo", text="Vínculo")
        self.tabla.heading("sueldo", text="Sueldo Base")
        self.tabla.heading("email", text="Email")
        self.tabla.heading("telefono", text="Teléfono")
        self.tabla.heading("estado", text="Estado")

        self.tabla.column("id", width=35, anchor="center")
        self.tabla.column("legajo", width=70, anchor="center")
        self.tabla.column("nombre", width=140, anchor="w")
        self.tabla.column("documento", width=105, anchor="center")
        self.tabla.column("cargo", width=105, anchor="w")
        self.tabla.column("sector", width=95, anchor="w")
        self.tabla.column("vinculo", width=95, anchor="w")
        self.tabla.column("sueldo", width=85, anchor="e")
        self.tabla.column("email", width=130, anchor="w")
        self.tabla.column("telefono", width=90, anchor="center")
        self.tabla.column("estado", width=65, anchor="center")

        scroll_y = ttk.Scrollbar(frame_grilla, orient="vertical", command=self.tabla.yview)
        scroll_x = ttk.Scrollbar(frame_grilla, orient="horizontal", command=self.tabla.xview)
        self.tabla.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tabla.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def sugerir_legajo(self):
        """Asigna automáticamente el siguiente legajo disponible."""
        try:
            siguiente = RepositorioRRHH.generar_siguiente_legajo()
            self.var_legajo.set(siguiente)
        except Exception:
            self.var_legajo.set("E001")

    def cargar_tabla_empleados(self):
        """Carga y filtra los registros en la tabla, guardando sus objetos en caché."""
        for row in self.tabla.get_children():
            self.tabla.delete(row)

        self.empleados_cache.clear()
        criterio = self.var_busqueda.get().strip()
        incluir_inactivos = self.var_mostrar_inactivos.get()

        try:
            empleados = RepositorioRRHH.listar_empleados(
                criterio_busqueda=criterio, incluir_inactivos=incluir_inactivos
            )
            for emp in empleados:
                if emp.id_empleado is not None:
                    self.empleados_cache[str(emp.id_empleado)] = emp
                estado_str = "Activo" if getattr(emp, "activo", True) else "Inactivo"
                vinculo_str = getattr(emp, "tipo_vinculo", "Contratado") or "Contratado"
                self.tabla.insert(
                    "",
                    "end",
                    values=(
                        emp.id_empleado,
                        emp.legajo,
                        f"{emp.apellidos}, {emp.nombres}",
                        emp.nro_documento,
                        emp.cargo,
                        emp.sector,
                        vinculo_str,
                        f"$ {emp.sueldo:,.2f}" if emp.sueldo else "$ 0.00",
                        emp.email or "-",
                        emp.telefono or "-",
                        estado_str,
                    ),
                )
        except Exception as e:
            messagebox.showwarning(
                "Aviso al Cargar Empleados",
                f"No se pudo cargar la tabla de empleados: {e}",
                parent=self,
            )

    def guardar_empleado(self):
        """Valida y persiste el empleado (Alta o Modificación)."""
        doc = "".join(c for c in self.var_documento.get() if c.isdigit())
        nombres = self.var_nombres.get().strip()
        apellidos = self.var_apellidos.get().strip()
        cargo = self.var_cargo.get().strip()
        sector = self.var_sector.get().strip()
        vinculo = self.var_vinculo.get().strip()
        sueldo_txt = self.var_sueldo.get().strip().replace(",", ".")
        email = self.var_email.get().strip()
        telefono = self.var_telefono.get().strip()

        if not all([doc, nombres, apellidos, cargo, sector, vinculo, sueldo_txt, email]):
            messagebox.showwarning(
                "Campos Incompletos",
                "Por favor, complete todos los campos obligatorios marcados con (*).",
                parent=self,
            )
            return

        if len(doc) != 11:
            messagebox.showwarning(
                "CUIL Inválido",
                "El CUIL del empleado debe tener exactamente 11 dígitos numéricos.",
                parent=self,
            )
            return

        try:
            sueldo = float(sueldo_txt)
        except ValueError:
            messagebox.showerror(
                "Error de Formato",
                "El sueldo base debe ser un valor numérico.",
                parent=self,
            )
            return

        if sueldo < 0:
            messagebox.showwarning(
                "Valor Inválido",
                "El sueldo base no puede ser negativo.",
                parent=self,
            )
            return

        legajo = self.var_legajo.get().strip()

        empleado = Empleado(
            id_empleado=self.empleado_seleccionado_id,
            id_persona=self.persona_seleccionada_id,
            nro_documento=doc,
            tipo_documento="CUIL",
            nombres=nombres,
            apellidos=apellidos,
            legajo=legajo,
            cargo=cargo,
            sector=sector,
            tipo_vinculo=vinculo,
            sueldo=sueldo,
            email=email,
            telefono=telefono,
            activo=self.empleado_estado_activo,
        )

        try:
            es_edicion = self.empleado_seleccionado_id is not None
            exito = RepositorioRRHH.guardar_empleado(empleado)

            if exito:
                mensaje = (
                    "¡Datos del empleado actualizados correctamente!"
                    if es_edicion
                    else "¡Empleado registrado correctamente!"
                )
                messagebox.showinfo("Éxito", mensaje, parent=self)
                self.limpiar_formulario()
                self.cargar_tabla_empleados()
            else:
                messagebox.showerror(
                    "Error",
                    "No se pudo guardar el registro del empleado.",
                    parent=self,
                )
        except Exception as e:
            messagebox.showerror(
                "Error Crítico",
                f"Ocurrió un error al persistir los datos: {e}",
                parent=self,
            )

    def toggle_estado_empleado(self):
        """Ejecuta la baja o reactivación lógica del empleado seleccionado."""
        if not self.empleado_seleccionado_id:
            return

        nuevo_estado = not self.empleado_estado_activo
        accion = "reactivar" if nuevo_estado else "deshabilitar"
        participio = "reactivado" if nuevo_estado else "deshabilitado"

        confirmado = messagebox.askyesno(
            "Confirmar Acción",
            f"¿Está seguro de que desea {accion} al empleado con legajo {self.var_legajo.get()}?",
            parent=self,
        )
        if not confirmado:
            return

        try:
            exito = RepositorioRRHH.cambiar_estado_empleado(
                self.empleado_seleccionado_id, nuevo_estado
            )
            if exito:
                messagebox.showinfo(
                    "Estado Actualizado",
                    f"El empleado ha sido {participio} correctamente.",
                    parent=self,
                )
                self.limpiar_formulario()
                self.cargar_tabla_empleados()
            else:
                messagebox.showerror(
                    "Error",
                    f"No se pudo {accion} al empleado.",
                    parent=self,
                )
        except Exception as e:
            messagebox.showerror(
                "Error Crítico",
                f"Error al cambiar el estado del empleado: {e}",
                parent=self,
            )

    def limpiar_formulario(self):
        """Restablece el formulario a su estado inicial para un nuevo ingreso."""
        self.empleado_seleccionado_id = None
        self.persona_seleccionada_id = None
        self.empleado_estado_activo = True
        self.var_documento.set("")
        self.var_nombres.set("")
        self.var_apellidos.set("")
        self.var_sueldo.set("")
        self.var_email.set("")
        self.var_telefono.set("")
        self.var_cargo.set(_cargo_por_defecto())
        self.var_sector.set(_sector_por_defecto())
        self.var_vinculo.set(_vinculo_por_defecto())
        self.btn_guardar.config(text="Guardar Empleado")
        self.btn_toggle_estado.config(text="Deshabilitar", state="disabled")
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())
        self.sugerir_legajo()

    def _al_seleccionar_fila(self, _event=None):
        """Vuelca todos los datos del empleado seleccionado hacia el formulario y habilita su gestión."""
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        valores = self.tabla.item(seleccion[0], "values")
        if not valores:
            return

        id_emp_str = str(valores[0])
        emp = self.empleados_cache.get(id_emp_str)
        if not emp:
            return

        self.empleado_seleccionado_id = emp.id_empleado
        self.persona_seleccionada_id = emp.id_persona
        self.empleado_estado_activo = bool(getattr(emp, "activo", True))

        self.var_legajo.set(emp.legajo or "")
        self.var_documento.set(emp.nro_documento or "")
        self.var_nombres.set(emp.nombres or "")
        self.var_apellidos.set(emp.apellidos or "")
        self.var_cargo.set(emp.cargo or _cargo_por_defecto())
        self.var_sector.set(emp.sector or _sector_por_defecto())
        self.var_vinculo.set(
            getattr(emp, "tipo_vinculo", _vinculo_por_defecto()) or _vinculo_por_defecto()
        )
        self.var_sueldo.set(str(emp.sueldo if emp.sueldo is not None else ""))
        self.var_email.set(emp.email or "")
        self.var_telefono.set(emp.telefono or "")

        self.btn_guardar.config(text="Actualizar Empleado")
        self.btn_toggle_estado.config(
            state="normal",
            text="Deshabilitar" if self.empleado_estado_activo else "Reactivar",
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Padrón de Empleados")
    root.geometry("1050x680")
    InterfazEmpleados(root)
    root.mainloop()