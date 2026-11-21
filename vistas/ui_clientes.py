"""
===============================================================================
MÓDULO DE INTERFAZ GRÁFICA: GESTIÓN DE CLIENTES (src/vistas/ui_clientes.py)
===============================================================================
Componente `ttk.Frame` reutilizable para el CRUD de clientes (personas físicas
con prefijo 20 o 27), búsqueda en vivo, filtro de inactivos, activación/
desactivación lógica y visualización de cliente frecuente.
===============================================================================
"""

from datetime import datetime
from typing import Any, Dict, Optional
import tkinter as tk
from tkinter import messagebox, ttk

from dominio.entidades_ventas import (
    Cliente,
    es_documento_persona_fisica_valido,
    limpiar_documento,
)
from infraestructura.repo_ventas import RepositorioVentas


def formatear_documento_cliente(doc_raw: str) -> str:
    """Formatea CUIL/CUIT de 11 dígitos como XX-XXXXXXXX-X o devuelve dígitos."""
    digitos = limpiar_documento(doc_raw)
    if len(digitos) == 11:
        return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"
    return digitos


class InterfazClientes(ttk.Frame):
    """Vista modular para administrar clientes (exclusivamente personas físicas)."""

    TIPOS_DOC_FISICA = ("CUIL", "CUIT", "DNI", "Pasaporte")

    def __init__(self, parent: tk.Misc, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self._id_cliente_edicion: Optional[int] = None
        self._id_persona_edicion: Optional[int] = None
        self._registros_visibles: Dict[str, Dict[str, Any]] = {}

        self._var_tipo_doc = tk.StringVar(value="CUIL")
        self._var_nro_doc = tk.StringVar()
        self._var_nombres = tk.StringVar()
        self._var_apellidos = tk.StringVar()
        self._var_telefono = tk.StringVar()
        self._var_email = tk.StringVar()
        self._var_domicilio = tk.StringVar()
        self._var_ciudad = tk.StringVar()
        self._var_provincia = tk.StringVar()
        self._var_cp = tk.StringVar()
        self._var_activo = tk.BooleanVar(value=True)

        self._var_busqueda = tk.StringVar()
        self._var_incluir_inactivos = tk.BooleanVar(value=False)

        self._construir_ui()
        self._refrescar_listado()

    def _construir_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Encabezado
        frame_header = ttk.Frame(self, padding=(12, 10, 12, 4))
        frame_header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            frame_header,
            text="Gestión de Clientes (Personas Físicas — Prefijos 20 / 27)",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        periodo_actual = datetime.now().strftime("%Y-%m")
        ttk.Label(
            frame_header,
            text=f"Período frecuente: {periodo_actual}",
        ).pack(side="right")

        # Formulario superior
        frame_form = ttk.LabelFrame(
            self, text="Datos del Cliente", padding=(12, 8, 12, 10)
        )
        frame_form.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        for col in (1, 3, 5):
            frame_form.columnconfigure(col, weight=1)

        # Fila 0: Tipo Doc, Nro Doc, Nombres, Apellidos
        ttk.Label(frame_form, text="Tipo Doc:").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=4
        )
        combo_tipo = ttk.Combobox(
            frame_form,
            textvariable=self._var_tipo_doc,
            values=self.TIPOS_DOC_FISICA,
            state="readonly",
            width=12,
        )
        combo_tipo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=4)

        ttk.Label(frame_form, text="CUIL/CUIT/DNI *:").grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_nro_doc, width=22).grid(
            row=0, column=3, sticky="ew", padx=(0, 12), pady=4
        )

        ttk.Label(frame_form, text="Nombres *:").grid(
            row=0, column=4, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_nombres, width=24).grid(
            row=0, column=5, sticky="ew", pady=4
        )

        # Fila 1: Apellidos, Teléfono, Email
        ttk.Label(frame_form, text="Apellidos *:").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_apellidos, width=22).grid(
            row=1, column=1, sticky="ew", padx=(0, 12), pady=4
        )

        ttk.Label(frame_form, text="Teléfono:").grid(
            row=1, column=2, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_telefono, width=20).grid(
            row=1, column=3, sticky="ew", padx=(0, 12), pady=4
        )

        ttk.Label(frame_form, text="Email:").grid(
            row=1, column=4, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_email, width=24).grid(
            row=1, column=5, sticky="ew", pady=4
        )

        # Fila 2: Domicilio, Ciudad, Provincia / CP
        ttk.Label(frame_form, text="Domicilio:").grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_domicilio, width=24).grid(
            row=2, column=1, sticky="ew", padx=(0, 12), pady=4
        )

        ttk.Label(frame_form, text="Ciudad:").grid(
            row=2, column=2, sticky="w", padx=(0, 6), pady=4
        )
        ttk.Entry(frame_form, textvariable=self._var_ciudad, width=20).grid(
            row=2, column=3, sticky="ew", padx=(0, 12), pady=4
        )

        frame_prov_cp = ttk.Frame(frame_form)
        frame_prov_cp.grid(row=2, column=4, columnspan=2, sticky="ew", pady=4)
        frame_prov_cp.columnconfigure(1, weight=1)
        ttk.Label(frame_prov_cp, text="Provincia:").grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )
        ttk.Entry(frame_prov_cp, textvariable=self._var_provincia, width=16).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Label(frame_prov_cp, text="CP:").grid(
            row=0, column=2, sticky="w", padx=(0, 4)
        )
        ttk.Entry(frame_prov_cp, textvariable=self._var_cp, width=8).grid(
            row=0, column=3, sticky="w"
        )

        # Fila 3: Estado y botonera de formulario
        frame_acciones_form = ttk.Frame(frame_form)
        frame_acciones_form.grid(
            row=3, column=0, columnspan=6, sticky="ew", pady=(8, 0)
        )

        ttk.Checkbutton(
            frame_acciones_form,
            text="Cliente activo",
            variable=self._var_activo,
        ).pack(side="left", padx=(0, 16))

        ttk.Button(
            frame_acciones_form,
            text="Guardar Cliente",
            command=self._guardar_cliente,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            frame_acciones_form,
            text="Limpiar / Nuevo",
            command=self._limpiar_formulario,
        ).pack(side="left", padx=(0, 6))

        self._btn_toggle_estado = ttk.Button(
            frame_acciones_form,
            text="Desactivar / Activar",
            command=self._alternar_estado_seleccionado,
        )
        self._btn_toggle_estado.pack(side="right")

        # Bloque inferior: búsqueda, filtros y grilla con scrollbars en grid
        frame_lista = ttk.LabelFrame(
            self, text="Padrón de Clientes", padding=(12, 8, 12, 12)
        )
        frame_lista.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        frame_lista.columnconfigure(0, weight=1)
        frame_lista.rowconfigure(1, weight=1)

        frame_filtros = ttk.Frame(frame_lista)
        frame_filtros.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame_filtros.columnconfigure(1, weight=1)

        ttk.Label(frame_filtros, text="Buscar:").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        entry_buscar = ttk.Entry(frame_filtros, textvariable=self._var_busqueda)
        entry_buscar.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        entry_buscar.bind("<KeyRelease>", lambda _e: self._refrescar_listado())

        ttk.Checkbutton(
            frame_filtros,
            text="Mostrar inactivos",
            variable=self._var_incluir_inactivos,
            command=self._refrescar_listado,
        ).grid(row=0, column=2, sticky="e", padx=(0, 8))

        ttk.Button(
            frame_filtros,
            text="Actualizar",
            command=self._refrescar_listado,
        ).grid(row=0, column=3, sticky="e")

        # Contenedor exclusivo para Treeview + scrollbars via grid
        frame_grid = ttk.Frame(frame_lista)
        frame_grid.grid(row=1, column=0, sticky="nsew")
        frame_grid.columnconfigure(0, weight=1)
        frame_grid.rowconfigure(0, weight=1)

        columnas = (
            "id",
            "documento",
            "nombre",
            "telefono",
            "email",
            "compras_mes",
            "frecuente",
            "estado",
        )
        self._tree = ttk.Treeview(
            frame_grid, columns=columnas, show="headings", selectmode="browse"
        )
        encabezados = {
            "id": ("ID", 55),
            "documento": ("Documento", 135),
            "nombre": ("Apellido y Nombre", 220),
            "telefono": ("Teléfono", 120),
            "email": ("Email", 190),
            "compras_mes": ("Compras/Mes", 95),
            "frecuente": ("Frecuente", 95),
            "estado": ("Estado", 85),
        }
        for col, (titulo, ancho) in encabezados.items():
            self._tree.heading(col, text=titulo)
            ancor = (
                "center"
                if col in ("id", "compras_mes", "frecuente", "estado")
                else "w"
            )
            self._tree.column(col, width=ancho, anchor=ancor)

        scroll_y = ttk.Scrollbar(
            frame_grid, orient="vertical", command=self._tree.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_grid, orient="horizontal", command=self._tree.xview
        )
        self._tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<<TreeviewSelect>>", self._cargar_seleccion_en_formulario)

    def _limpiar_formulario(self) -> None:
        self._id_cliente_edicion = None
        self._id_persona_edicion = None
        self._var_tipo_doc.set("CUIL")
        self._var_nro_doc.set("")
        self._var_nombres.set("")
        self._var_apellidos.set("")
        self._var_telefono.set("")
        self._var_email.set("")
        self._var_domicilio.set("")
        self._var_ciudad.set("")
        self._var_provincia.set("")
        self._var_cp.set("")
        self._var_activo.set(True)
        self._tree.selection_remove(self._tree.selection())

    def _guardar_cliente(self) -> None:
        nro_doc = self._var_nro_doc.get().strip()
        nombres = self._var_nombres.get().strip()
        apellidos = self._var_apellidos.get().strip()

        if not nro_doc or not nombres or not apellidos:
            messagebox.showwarning(
                "Datos incompletos",
                "Completá Documento (prefijo 20 o 27), Nombres y Apellidos.",
            )
            return

        if not es_documento_persona_fisica_valido(nro_doc):
            messagebox.showwarning(
                "Documento no válido para Persona Física",
                "Para clientes (Persona Física) ingresá un CUIL/CUIT de 11 dígitos "
                "comenzado con 20 o 27, o un DNI válido.",
            )
            return

        cliente = Cliente(
            id_cliente=self._id_cliente_edicion,
            id_persona=self._id_persona_edicion,
            tipo_documento=self._var_tipo_doc.get().strip(),
            nro_documento=limpiar_documento(nro_doc),
            nombres=nombres,
            apellidos=apellidos,
            telefono=self._var_telefono.get().strip(),
            email=self._var_email.get().strip(),
            domicilio=self._var_domicilio.get().strip(),
            ciudad=self._var_ciudad.get().strip(),
            provincia=self._var_provincia.get().strip(),
            codigo_postal=self._var_cp.get().strip(),
            activo=bool(self._var_activo.get()),
        )

        try:
            RepositorioVentas.guardar_cliente(cliente)
            messagebox.showinfo(
                "Guardado",
                "Cliente guardado correctamente en el padrón.",
            )
            self._limpiar_formulario()
            self._refrescar_listado()
        except Exception as exc:
            messagebox.showerror("Error al guardar cliente", str(exc))

    def _cargar_seleccion_en_formulario(self, _event: Any = None) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            return
        item_id = seleccion[0]
        data = self._registros_visibles.get(item_id)
        if not data:
            return

        cli: Cliente = data["cliente"]
        self._id_cliente_edicion = cli.id_cliente
        self._id_persona_edicion = cli.id_persona
        self._var_tipo_doc.set(
            cli.tipo_documento.capitalize()
            if cli.tipo_documento.lower() == "pasaporte"
            else cli.tipo_documento.upper()
        )
        self._var_nro_doc.set(formatear_documento_cliente(cli.nro_documento))
        self._var_nombres.set(cli.nombres)
        self._var_apellidos.set(cli.apellidos)
        self._var_telefono.set(cli.telefono)
        self._var_email.set(cli.email)
        self._var_domicilio.set(cli.domicilio)
        self._var_ciudad.set(cli.ciudad)
        self._var_provincia.set(cli.provincia)
        self._var_cp.set(cli.codigo_postal)
        self._var_activo.set(cli.activo)

    def _alternar_estado_seleccionado(self) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            messagebox.showinfo(
                "Selección requerida",
                "Seleccioná un cliente en la tabla para activar o desactivar.",
            )
            return

        data = self._registros_visibles.get(seleccion[0])
        if not data:
            return
        cli: Cliente = data["cliente"]
        if cli.id_cliente is None:
            return

        nuevo_estado = not cli.activo
        accion = "activar" if nuevo_estado else "desactivar"
        if not messagebox.askyesno(
            "Confirmar cambio de estado",
            f"¿Deseás {accion} a '{cli.nombre_completo}'?",
        ):
            return

        try:
            RepositorioVentas.cambiar_estado_cliente(cli.id_cliente, nuevo_estado)
            self._limpiar_formulario()
            self._refrescar_listado()
        except Exception as exc:
            messagebox.showerror("Error al actualizar estado", str(exc))

    def _refrescar_listado(self) -> None:
        for fila in self._tree.get_children():
            self._tree.delete(fila)
        self._registros_visibles.clear()

        try:
            filas = RepositorioVentas.listar_clientes(
                criterio_busqueda=self._var_busqueda.get(),
                incluir_inactivos=bool(self._var_incluir_inactivos.get()),
            )
        except Exception as exc:
            messagebox.showerror("Error al listar clientes", str(exc))
            return

        for reg in filas:
            cli: Cliente = reg["cliente"]
            compras_mes: int = int(reg["compras_mes"])
            es_frecuente: bool = bool(reg["es_frecuente"])
            iid = self._tree.insert(
                "",
                "end",
                values=(
                    cli.id_cliente,
                    formatear_documento_cliente(cli.nro_documento),
                    cli.nombre_completo,
                    cli.telefono,
                    cli.email,
                    compras_mes,
                    "Sí" if es_frecuente else "No",
                    "Activo" if cli.activo else "Inactivo",
                ),
            )
            self._registros_visibles[iid] = reg


if __name__ == "__main__":
    ventana_prueba = tk.Tk()
    ventana_prueba.title("Prueba - Vista Clientes")
    ventana_prueba.geometry("980x620")
    vista = InterfazClientes(ventana_prueba)
    vista.pack(fill="both", expand=True)
    ventana_prueba.mainloop()