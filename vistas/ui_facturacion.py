"""
===============================================================================
MÓDULO DE VISTAS: FACTURACIÓN Y VENTAS (vistas/ui_facturacion.py)
===============================================================================
Interfaz gráfica para la emisión de comprobantes de venta siguiendo el patrón
visual apilado del sistema:
- Medios de pago: Efectivo, Transferencia, Tarjeta de crédito.
- CRUD de ítems con "Agregar Ítem", "Modificar Producto" y "Quitar".
- Tabla de detalle centrada exclusivamente en productos.
- Bonificaciones, recargos e impuestos concentrados en Totales y Emisión con
  recálculo automático en tiempo real y botones visibles sin recorte.
- Tipografía 12 pt sin itálicas (slant='roman') y estilos globales.
===============================================================================
"""

from datetime import datetime
from typing import Any, cast, Dict, List, Literal, Optional, Tuple
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

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

MEDIOS_PAGO: Tuple[str, ...] = (
    "Efectivo",
    "Transferencia",
    "Tarjeta de crédito",
)


def _a_entero_o_cero(valor: Any) -> int:
    """Convierte a int de forma segura y tipada."""
    if valor is None or isinstance(valor, bool):
        return 0
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return 0
        try:
            return int(float(texto))
        except ValueError:
            return 0
    return 0


def _a_flotante_o_cero(valor: Any) -> float:
    """Convierte a float de forma segura y tipada."""
    if valor is None or isinstance(valor, bool):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        texto = valor.strip().replace(",", ".")
        if not texto:
            return 0.0
        try:
            return float(texto)
        except ValueError:
            return 0.0
    return 0.0


class InterfazFacturacion(ttk.Frame):
    """Vista modular para emisión de facturas con patrón visual apilado."""

    def __init__(self, parent: tk.Misc, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self.winfo_toplevel())
            except Exception:
                pass

        self.pack(fill="both", expand=True, padx=8, pady=6)

        self.clientes_disponibles: List[Dict[str, Any]] = []
        self.vendedores_disponibles: List[Dict[str, Any]] = []
        self.productos_disponibles: List[Dict[str, Any]] = []
        self.items_factura: List[Dict[str, Any]] = []
        self.indice_item_edicion: Optional[int] = None
        self.item_id_por_fila: Dict[str, int] = {}
        self.ultimo_resumen_impresion: Optional[str] = None

        self.var_cliente = tk.StringVar()
        self.var_vendedor = tk.StringVar()
        self.var_medio_pago = tk.StringVar(value=MEDIOS_PAGO[0])

        self.var_producto = tk.StringVar()
        self.var_cantidad = tk.StringVar(value="1")
        self.var_descuento_item = tk.StringVar(value="0.0")

        self.var_bonificacion_pct = tk.StringVar(value="0.0")
        self.var_recargo_pct = tk.StringVar(value="0.0")
        self.var_impuesto_pct = tk.StringVar(value="21.0")

        self.var_subtotal_prod = tk.StringVar(value="$0.00")
        self.var_bonificacion_monto = tk.StringVar(value="-$0.00")
        self.var_recargo_monto = tk.StringVar(value="+$0.00")
        self.var_impuestos_monto = tk.StringVar(value="$0.00")
        self.var_total_final = tk.StringVar(value="$0.00")

        self._construir_interfaz()
        self._configurar_fuentes()
        self._conectar_recalculo_automatico()
        self.cargar_datos_iniciales()
        self._recalcular_totales()

    def _conectar_recalculo_automatico(self) -> None:
        """Recalcula automáticamente cada vez que cambian los porcentajes."""
        for var in (
            self.var_bonificacion_pct,
            self.var_recargo_pct,
            self.var_impuesto_pct,
        ):
            var.trace_add("write", lambda *_args: self._recalcular_totales())

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
        # 1. Bloque superior: Comprobante y carga/edición de producto (2 columnas)
        frame_form = ttk.LabelFrame(
            self, text=" Datos del Comprobante y Productos ", padding=10
        )
        frame_form.pack(fill="x", padx=4, pady=(0, 4))
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

        # Fila 0: Cliente | Vendedor
        ttk.Label(frame_form, text="Cliente *:").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        self.combo_clientes = ttk.Combobox(
            frame_form,
            textvariable=self.var_cliente,
            state="readonly",
        )
        self.combo_clientes.grid(row=0, column=1, sticky="ew", padx=6, pady=3)

        ttk.Label(frame_form, text="Vendedor *:").grid(
            row=0, column=2, sticky="w", padx=6, pady=3
        )
        self.combo_vendedores = ttk.Combobox(
            frame_form,
            textvariable=self.var_vendedor,
            state="readonly",
        )
        self.combo_vendedores.grid(row=0, column=3, sticky="ew", padx=6, pady=3)

        # Fila 1: Medio de pago | Producto
        ttk.Label(frame_form, text="Medio de pago *:").grid(
            row=1, column=0, sticky="w", padx=6, pady=3
        )
        self.combo_medio_pago = ttk.Combobox(
            frame_form,
            textvariable=self.var_medio_pago,
            state="readonly",
            values=MEDIOS_PAGO,
        )
        self.combo_medio_pago.grid(row=1, column=1, sticky="ew", padx=6, pady=3)

        ttk.Label(frame_form, text="Producto *:").grid(
            row=1, column=2, sticky="w", padx=6, pady=3
        )
        self.combo_productos = ttk.Combobox(
            frame_form,
            textvariable=self.var_producto,
            state="readonly",
        )
        self.combo_productos.grid(row=1, column=3, sticky="ew", padx=6, pady=3)

        # Fila 2: Cantidad | Desc. ítem (%)
        ttk.Label(frame_form, text="Cantidad *:").grid(
            row=2, column=0, sticky="w", padx=6, pady=3
        )
        ttk.Entry(frame_form, textvariable=self.var_cantidad).grid(
            row=2, column=1, sticky="ew", padx=6, pady=3
        )

        ttk.Label(frame_form, text="Desc. ítem (%):").grid(
            row=2, column=2, sticky="w", padx=6, pady=3
        )
        ttk.Entry(frame_form, textvariable=self.var_descuento_item).grid(
            row=2, column=3, sticky="ew", padx=6, pady=3
        )

        # Fila 3: Botonera de ítems
        frame_botones_item = ttk.Frame(frame_form)
        frame_botones_item.grid(row=3, column=0, columnspan=4, sticky="e", pady=(4, 0))

        ttk.Button(
            frame_botones_item,
            text="Agregar Ítem",
            command=self.agregar_producto,
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botones_item,
            text="Modificar Producto",
            command=self.modificar_producto_seleccionado,
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botones_item,
            text="Quitar",
            command=self.quitar_producto_seleccionado,
        ).pack(side="left", padx=5)

        # 2. Bloque central: Tabla exclusiva de productos (proporción compacta)
        frame_tabla = ttk.LabelFrame(
            self,
            text=" Detalle de Productos (Seleccione una fila para modificar o quitar) ",
            padding=10,
        )
        frame_tabla.pack(fill="x", padx=4, pady=(0, 4))

        frame_grilla = ttk.Frame(frame_tabla)
        frame_grilla.pack(fill="x")
        frame_grilla.columnconfigure(0, weight=1)
        frame_grilla.columnconfigure(1, weight=0)

        columnas = ("id_prod", "codigo", "producto", "cantidad", "precio_unit", "subtotal")
        self.tabla = ttk.Treeview(
            frame_grilla,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=3,
        )

        encabezados: Dict[str, Tuple[str, int, AnchorTk]] = {
            "id_prod": ("ID", 70, "center"),
            "codigo": ("Código", 130, "center"),
            "producto": ("Producto", 320, "w"),
            "cantidad": ("Cant.", 90, "center"),
            "precio_unit": ("Precio Unit.", 135, "e"),
            "subtotal": ("Subtotal", 145, "e"),
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

        self.tabla.grid(row=0, column=0, sticky="ew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

        # 3. Bloque inferior: Totales y Emisión (sin filas repetidas + botones visibles)
        frame_totales = ttk.LabelFrame(
            self, text=" Totales y Emisión ", padding=10
        )
        frame_totales.pack(fill="x", padx=4, pady=(0, 2))
        frame_totales.columnconfigure(1, weight=1)
        frame_totales.columnconfigure(3, weight=1)

        # Fila 0: Bonificación (% y monto en la misma fila) | Recargo (% y monto en la misma fila)
        frame_bonif = ttk.Frame(frame_totales)
        frame_bonif.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=2)
        ttk.Label(frame_bonif, text="Bonificación (%):").pack(side="left", padx=(0, 6))
        ttk.Entry(
            frame_bonif, textvariable=self.var_bonificacion_pct, width=8
        ).pack(side="left", padx=(0, 8))
        ttk.Label(frame_bonif, textvariable=self.var_bonificacion_monto).pack(
            side="left"
        )

        frame_recargo = ttk.Frame(frame_totales)
        frame_recargo.grid(row=0, column=2, columnspan=2, sticky="ew", padx=6, pady=2)
        ttk.Label(frame_recargo, text="Recargo (%):").pack(side="left", padx=(0, 6))
        ttk.Entry(
            frame_recargo, textvariable=self.var_recargo_pct, width=8
        ).pack(side="left", padx=(0, 8))
        ttk.Label(frame_recargo, textvariable=self.var_recargo_monto).pack(
            side="left"
        )

        # Fila 1: Impuestos (% y monto en la misma fila) | Subtotal productos
        frame_imp = ttk.Frame(frame_totales)
        frame_imp.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=2)
        ttk.Label(frame_imp, text="Impuestos (%):").pack(side="left", padx=(0, 6))
        ttk.Entry(
            frame_imp, textvariable=self.var_impuesto_pct, width=8
        ).pack(side="left", padx=(0, 8))
        ttk.Label(frame_imp, textvariable=self.var_impuestos_monto).pack(
            side="left"
        )

        ttk.Label(frame_totales, text="Subtotal productos:").grid(
            row=1, column=2, sticky="w", padx=6, pady=2
        )
        ttk.Label(frame_totales, textvariable=self.var_subtotal_prod).grid(
            row=1, column=3, sticky="e", padx=6, pady=2
        )

        # Fila 2: TOTAL A PAGAR + Botonera de emisión siempre visible
        ttk.Label(
            frame_totales, text="TOTAL A PAGAR:", style="Subtitulo.TLabel"
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(6, 2))
        ttk.Label(
            frame_totales, textvariable=self.var_total_final, style="Subtitulo.TLabel"
        ).grid(row=2, column=1, sticky="w", padx=6, pady=(6, 2))

        frame_emision = ttk.Frame(frame_totales)
        frame_emision.grid(row=2, column=2, columnspan=2, sticky="e", pady=(6, 2))

        ttk.Button(
            frame_emision,
            text="Limpiar",
            command=self.limpiar_comprobante,
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_emision,
            text="Emitir Factura",
            command=self.emitir_factura,
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_emision,
            text="Imprimir Factura",
            command=self.imprimir_factura,
        ).pack(side="left", padx=4)

    def cargar_datos_iniciales(self) -> None:
        """Carga clientes, vendedores activos y productos disponibles."""
        try:
            raw_clientes = RepositorioVentas.listar_clientes(incluir_inactivos=False)
            self.clientes_disponibles = []
            etiquetas_cli: List[str] = []
            for item in raw_clientes:
                cli = (
                    item["cliente"]
                    if isinstance(item, dict) and "cliente" in item
                    else item
                )
                id_cli = _a_entero_o_cero(
                    getattr(cli, "id_cliente", None) or getattr(cli, "id", 0)
                )
                apellidos = str(
                    getattr(cli, "apellidos", "")
                    or getattr(cli, "apellido", "")
                    or ""
                ).strip()
                nombres = str(
                    getattr(cli, "nombres", "")
                    or getattr(cli, "nombre", "")
                    or ""
                ).strip()
                nombre_fmt = f"{apellidos}, {nombres}".strip(", ") or f"Cliente #{id_cli}"
                es_frec = (
                    bool(item.get("es_frecuente", False))
                    if isinstance(item, dict)
                    else False
                )
                self.clientes_disponibles.append(
                    {
                        "id": id_cli,
                        "etiqueta": f"[{id_cli}] {nombre_fmt}",
                        "es_frecuente": es_frec,
                    }
                )
                etiquetas_cli.append(f"[{id_cli}] {nombre_fmt}")

            self.combo_clientes["values"] = etiquetas_cli
            if etiquetas_cli:
                self.combo_clientes.current(0)
        except Exception as exc:
            messagebox.showerror("Error al cargar clientes", str(exc), parent=self)

        try:
            self.vendedores_disponibles = list(
                RepositorioVentas.listar_vendedores_activos()
            )
            etiquetas_vend: List[str] = []
            for vend in self.vendedores_disponibles:
                id_v = _a_entero_o_cero(vend.get("id_empleado") or vend.get("id"))
                nombre_v = str(
                    vend.get("nombre_completo") or f"Vendedor #{id_v}"
                ).strip()
                etiquetas_vend.append(f"[{id_v}] {nombre_v}")
            self.combo_vendedores["values"] = etiquetas_vend
            if etiquetas_vend:
                self.combo_vendedores.current(0)
        except Exception as exc:
            messagebox.showerror("Error al cargar vendedores", str(exc), parent=self)

        try:
            self.productos_disponibles = list(RepositorioVentas.listar_productos_venta())
            etiquetas_prod: List[str] = []
            for prod in self.productos_disponibles:
                id_p = _a_entero_o_cero(prod.get("id"))
                cod_p = str(prod.get("codigo") or "").strip()
                desc_p = str(prod.get("descripcion") or f"Producto #{id_p}").strip()
                precio_p = _a_flotante_o_cero(prod.get("precio_venta"))
                etiquetas_prod.append(f"[{cod_p or id_p}] {desc_p} (${precio_p:,.2f})")
            self.combo_productos["values"] = etiquetas_prod
            if etiquetas_prod:
                self.combo_productos.current(0)
        except Exception as exc:
            messagebox.showerror("Error al cargar productos", str(exc), parent=self)

    def _leer_item_formulario(self) -> Optional[Dict[str, Any]]:
        """Valida y arma un ítem de producto a partir de los campos del formulario."""
        idx_prod = self.combo_productos.current()
        if idx_prod < 0 or idx_prod >= len(self.productos_disponibles):
            messagebox.showwarning(
                "Producto requerido", "Seleccioná un producto.", parent=self
            )
            return None

        prod = self.productos_disponibles[idx_prod]
        id_prod = _a_entero_o_cero(prod.get("id"))
        codigo = str(prod.get("codigo") or "").strip()
        descripcion = str(prod.get("descripcion") or "").strip()
        precio_unit = _a_flotante_o_cero(prod.get("precio_venta"))
        stock_disp = _a_entero_o_cero(prod.get("stock_actual"))

        try:
            cantidad = int(self.var_cantidad.get().strip())
            if cantidad <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning(
                "Cantidad inválida",
                "Ingresá una cantidad entera mayor a cero.",
                parent=self,
            )
            return None

        if stock_disp > 0 and cantidad > stock_disp:
            messagebox.showwarning(
                "Stock insuficiente",
                f"Stock disponible para '{descripcion}': {stock_disp}.",
                parent=self,
            )
            return None

        desc_pct = _a_flotante_o_cero(self.var_descuento_item.get())
        if desc_pct < 0.0 or desc_pct > 100.0:
            messagebox.showwarning(
                "Descuento inválido",
                "El descuento del ítem debe estar entre 0% y 100%.",
                parent=self,
            )
            return None

        subtotal = round(cantidad * precio_unit * (1.0 - desc_pct / 100.0), 2)
        return {
            "id_producto": id_prod,
            "codigo": codigo or str(id_prod),
            "descripcion": descripcion,
            "cantidad": cantidad,
            "precio_unitario": precio_unit,
            "descuento_pct": desc_pct,
            "subtotal": subtotal,
        }

    def agregar_producto(self) -> None:
        """Agrega o acumula un producto en el detalle de la factura."""
        nuevo = self._leer_item_formulario()
        if nuevo is None:
            return

        for existente in self.items_factura:
            if existente["id_producto"] == nuevo["id_producto"]:
                nueva_cant = _a_entero_o_cero(existente["cantidad"]) + _a_entero_o_cero(
                    nuevo["cantidad"]
                )
                precio_u = _a_flotante_o_cero(existente["precio_unitario"])
                desc_u = _a_flotante_o_cero(nuevo["descuento_pct"])
                existente["cantidad"] = nueva_cant
                existente["descuento_pct"] = desc_u
                existente["subtotal"] = round(
                    nueva_cant * precio_u * (1.0 - desc_u / 100.0), 2
                )
                self.indice_item_edicion = None
                self._refrescar_tabla_y_totales()
                return

        self.items_factura.append(nuevo)
        self.indice_item_edicion = None
        self._refrescar_tabla_y_totales()

    def modificar_producto_seleccionado(self) -> None:
        """Actualiza los datos del producto seleccionado en la tabla."""
        idx_objetivo = self.indice_item_edicion
        if idx_objetivo is None:
            seleccion = self.tabla.selection()
            if seleccion:
                idx_objetivo = self.item_id_por_fila.get(seleccion[0])

        if idx_objetivo is None or not (0 <= idx_objetivo < len(self.items_factura)):
            messagebox.showwarning(
                "Sin selección",
                "Seleccioná un producto de la tabla para modificarlo.",
                parent=self,
            )
            return

        actualizado = self._leer_item_formulario()
        if actualizado is None:
            return

        self.items_factura[idx_objetivo] = actualizado
        self.indice_item_edicion = None
        self._refrescar_tabla_y_totales()

    def quitar_producto_seleccionado(self) -> None:
        """Elimina el producto seleccionado de la tabla."""
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = self.item_id_por_fila.get(seleccion[0])
        if idx is not None and 0 <= idx < len(self.items_factura):
            del self.items_factura[idx]
            self.indice_item_edicion = None
            self._refrescar_tabla_y_totales()

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        """Carga el producto seleccionado en el formulario para editarlo."""
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = self.item_id_por_fila.get(seleccion[0])
        if idx is None or not (0 <= idx < len(self.items_factura)):
            return

        item = self.items_factura[idx]
        self.indice_item_edicion = idx
        self.var_cantidad.set(str(item["cantidad"]))
        self.var_descuento_item.set(str(item["descuento_pct"]))

        for pos, prod in enumerate(self.productos_disponibles):
            if _a_entero_o_cero(prod.get("id")) == _a_entero_o_cero(
                item["id_producto"]
            ):
                self.combo_productos.current(pos)
                break

    def _refrescar_tabla_y_totales(self) -> None:
        """Refresca la tabla exclusiva de productos y recalcula totales."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.item_id_por_fila.clear()

        for idx, item in enumerate(self.items_factura):
            precio_u = _a_flotante_o_cero(item["precio_unitario"])
            subtotal = _a_flotante_o_cero(item["subtotal"])
            iid = self.tabla.insert(
                "",
                "end",
                values=(
                    item["id_producto"],
                    item["codigo"],
                    item["descripcion"],
                    item["cantidad"],
                    f"${precio_u:,.2f}",
                    f"${subtotal:,.2f}",
                ),
            )
            self.item_id_por_fila[iid] = idx

        self._recalcular_totales()

    def _recalcular_totales(self) -> None:
        """Calcula subtotal de productos, bonificaciones, recargos, impuestos y total."""
        subtotal_prod = sum(
            _a_flotante_o_cero(it.get("subtotal")) for it in self.items_factura
        )
        bonif_pct = max(0.0, _a_flotante_o_cero(self.var_bonificacion_pct.get()))
        recargo_pct = max(0.0, _a_flotante_o_cero(self.var_recargo_pct.get()))
        imp_pct = max(0.0, _a_flotante_o_cero(self.var_impuesto_pct.get()))

        bonif_monto = subtotal_prod * (bonif_pct / 100.0)
        recargo_monto = subtotal_prod * (recargo_pct / 100.0)
        base_neta = max(0.0, subtotal_prod - bonif_monto + recargo_monto)
        impuestos_monto = base_neta * (imp_pct / 100.0)
        total_final = base_neta + impuestos_monto

        self.var_subtotal_prod.set(f"${subtotal_prod:,.2f}")
        self.var_bonificacion_monto.set(f"-${bonif_monto:,.2f}")
        self.var_recargo_monto.set(f"+${recargo_monto:,.2f}")
        self.var_impuestos_monto.set(f"${impuestos_monto:,.2f}")
        self.var_total_final.set(f"${total_final:,.2f}")

    def _construir_texto_comprobante(self, nro_comprobante: str = "BORRADOR") -> str:
        """Genera un resumen legible del comprobante para vista previa / impresión."""
        lineas = [
            "FRANKIE GESTOR COMERCIAL - COMPROBANTE DE VENTA",
            f"Comprobante: {nro_comprobante} | Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Cliente: {self.var_cliente.get() or '-'}",
            f"Vendedor: {self.var_vendedor.get() or '-'}",
            f"Medio de pago: {self.var_medio_pago.get() or MEDIOS_PAGO[0]}",
            "-" * 52,
        ]
        for it in self.items_factura:
            lineas.append(
                f"[{it['codigo']}] {it['descripcion']} x{it['cantidad']} -> "
                f"${_a_flotante_o_cero(it['subtotal']):,.2f}"
            )
        lineas.extend(
            [
                "-" * 52,
                f"Subtotal productos: {self.var_subtotal_prod.get()}",
                f"Bonificación ({self.var_bonificacion_pct.get()}%): {self.var_bonificacion_monto.get()}",
                f"Recargo ({self.var_recargo_pct.get()}%): {self.var_recargo_monto.get()}",
                f"Impuestos ({self.var_impuesto_pct.get()}%): {self.var_impuestos_monto.get()}",
                f"TOTAL A PAGAR: {self.var_total_final.get()}",
            ]
        )
        return "\n".join(lineas)

    def imprimir_factura(self) -> None:
        """Muestra la vista previa imprimible del último comprobante o del actual."""
        texto = self.ultimo_resumen_impresion or self._construir_texto_comprobante()
        if not self.items_factura and self.ultimo_resumen_impresion is None:
            messagebox.showwarning(
                "Sin datos",
                "Agregá productos o emití una factura para imprimir.",
                parent=self,
            )
            return

        ventana = tk.Toplevel(self)
        ventana.title("Vista Previa de Factura")
        ventana.geometry("560x420")
        txt = tk.Text(ventana, wrap="word", padx=12, pady=12)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", texto)
        txt.configure(state="disabled")

    def emitir_factura(self) -> None:
        """Valida selección y emite la factura a través de RepositorioVentas."""
        if not self.items_factura:
            messagebox.showwarning(
                "Sin productos",
                "Agregá al menos un producto al detalle antes de emitir.",
                parent=self,
            )
            return

        idx_cli = self.combo_clientes.current()
        idx_vend = self.combo_vendedores.current()
        if idx_cli < 0 or idx_cli >= len(self.clientes_disponibles):
            messagebox.showwarning(
                "Cliente requerido", "Seleccioná un cliente.", parent=self
            )
            return
        if idx_vend < 0 or idx_vend >= len(self.vendedores_disponibles):
            messagebox.showwarning(
                "Vendedor requerido", "Seleccioná un vendedor activo.", parent=self
            )
            return

        id_cliente = _a_entero_o_cero(self.clientes_disponibles[idx_cli]["id"])
        vend = self.vendedores_disponibles[idx_vend]
        id_vendedor = _a_entero_o_cero(vend.get("id_empleado") or vend.get("id"))
        medio_pago = self.var_medio_pago.get().strip() or MEDIOS_PAGO[0]

        subtotal_prod = sum(
            _a_flotante_o_cero(it.get("subtotal")) for it in self.items_factura
        )
        bonif_pct = max(0.0, _a_flotante_o_cero(self.var_bonificacion_pct.get()))
        recargo_pct = max(0.0, _a_flotante_o_cero(self.var_recargo_pct.get()))
        imp_pct = max(0.0, _a_flotante_o_cero(self.var_impuesto_pct.get()))

        bonif_monto = subtotal_prod * (bonif_pct / 100.0)
        recargo_monto = subtotal_prod * (recargo_pct / 100.0)
        base_neta = max(0.0, subtotal_prod - bonif_monto + recargo_monto)
        impuestos_monto = base_neta * (imp_pct / 100.0)
        total_final = round(base_neta + impuestos_monto, 2)

        items_crudos = [
            {
                "id_producto": _a_entero_o_cero(it["id_producto"]),
                "codigo": str(it["codigo"]),
                "descripcion": str(it["descripcion"]),
                "cantidad": _a_entero_o_cero(it["cantidad"]),
                "precio_lista": _a_flotante_o_cero(it["precio_unitario"]),
                "descuento": _a_flotante_o_cero(it["descuento_pct"]),
                "medio_pago": medio_pago,
            }
            for it in self.items_factura
        ]

        try:
            factura = RepositorioVentas.emitir_factura(
                id_cliente,
                id_vendedor,
                medio_pago,
                items_crudos,
            )
            nro_fac = str(
                getattr(factura, "id_factura", None)
                or getattr(factura, "id", None)
                or "OK"
            )
            self.ultimo_resumen_impresion = self._construir_texto_comprobante(
                f"#{nro_fac}"
            )
            messagebox.showinfo(
                "Factura emitida",
                f"Comprobante #{nro_fac} emitido correctamente.\n"
                f"Medio de pago: {medio_pago}\n"
                f"Total: ${total_final:,.2f}",
                parent=self,
            )
            self.limpiar_comprobante()
            self.cargar_datos_iniciales()
        except Exception as exc:
            messagebox.showerror("Error al emitir factura", str(exc), parent=self)

    def limpiar_comprobante(self) -> None:
        """Reinicia los ítems, totales y campos de edición del comprobante."""
        self.items_factura.clear()
        self.indice_item_edicion = None
        self.var_cantidad.set("1")
        self.var_descuento_item.set("0.0")
        self.var_bonificacion_pct.set("0.0")
        self.var_recargo_pct.set("0.0")
        self._refrescar_tabla_y_totales()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Facturación")
    root.geometry("1180x760")
    InterfazFacturacion(root)
    root.mainloop()