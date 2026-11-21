"""
===============================================================================
MÓDULO DE INTERFAZ GRÁFICA: FACTURACIÓN EN 3 NIVELES (ui_facturacion.py)
===============================================================================
Componente `ttk.Frame` reutilizable para emitir facturas en 3 niveles:
1) Cabecera (Cliente activo, Vendedor activo, Condición de venta).
2) Detalle de ítems (Producto, Cantidad, Descuentos por tramo, Impuestos).
3) Totales, emisión transaccional con impacto en stock y comprobante HTML.
===============================================================================
"""

from datetime import datetime
from html import escape
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Literal, Optional, Tuple
import webbrowser

import config
from dominio.entidades_ventas import Cliente, Factura
from infraestructura.repo_ventas import RepositorioVentas

AnclaTreeview = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]


def _formatear_moneda(valor: float) -> str:
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class InterfazFacturacion(ttk.Frame):
    """Vista modular de facturación de 3 niveles con exportación HTML."""

    def __init__(self, parent: tk.Misc, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)

        self._clientes_map: Dict[str, Dict[str, Any]] = {}
        self._vendedores_map: Dict[str, Dict[str, Any]] = {}
        self._productos_map: Dict[str, Dict[str, Any]] = {}
        self._items_carrito: List[Dict[str, Any]] = []
        self._ultima_factura: Optional[Factura] = None

        self._var_cliente = tk.StringVar()
        self._var_info_cliente = tk.StringVar(value="Cliente: —")
        self._var_vendedor = tk.StringVar()

        condiciones_defecto = getattr(
            config,
            "CONDICIONES_VENTA",
            ["Efectivo", "Fidelidad", "Cuenta Corriente", "Tarjeta de Crédito"],
        )
        self._condiciones = list(condiciones_defecto)
        self._var_condicion = tk.StringVar(
            value=self._condiciones[0] if self._condiciones else "Efectivo"
        )

        self._var_producto = tk.StringVar()
        self._var_info_producto = tk.StringVar(value="Stock: — | Precio: —")
        self._var_cantidad = tk.StringVar(value="1")

        self._var_subtotal = tk.StringVar(value="$ 0,00")
        self._var_ajuste_cond = tk.StringVar(value="$ 0,00")
        self._var_imp_prov = tk.StringVar(value="$ 0,00")
        self._var_iva = tk.StringVar(value="$ 0,00")
        self._var_total = tk.StringVar(value="$ 0,00")

        self._construir_ui()
        self.refrescar_datos_base()

    def _construir_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ---------------------------------------------------------------------
        # NIVEL 1: CABECERA COMERCIAL
        # ---------------------------------------------------------------------
        frame_cabecera = ttk.LabelFrame(
            self, text="1. Cabecera de Factura", padding=(12, 8, 12, 10)
        )
        frame_cabecera.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        frame_cabecera.columnconfigure(1, weight=2)
        frame_cabecera.columnconfigure(3, weight=1)
        frame_cabecera.columnconfigure(5, weight=1)

        ttk.Label(frame_cabecera, text="Cliente *:").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=4
        )
        self._combo_cliente = ttk.Combobox(
            frame_cabecera,
            textvariable=self._var_cliente,
            state="readonly",
            width=34,
        )
        self._combo_cliente.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)
        self._combo_cliente.bind(
            "<<ComboboxSelected>>", lambda _e: self._actualizar_info_cliente()
        )

        ttk.Label(frame_cabecera, text="Vendedor *:").grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=4
        )
        self._combo_vendedor = ttk.Combobox(
            frame_cabecera,
            textvariable=self._var_vendedor,
            state="readonly",
            width=24,
        )
        self._combo_vendedor.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(frame_cabecera, text="Condición *:").grid(
            row=0, column=4, sticky="w", padx=(0, 6), pady=4
        )
        combo_cond = ttk.Combobox(
            frame_cabecera,
            textvariable=self._var_condicion,
            values=self._condiciones,
            state="readonly",
            width=20,
        )
        combo_cond.grid(row=0, column=5, sticky="ew", padx=(0, 8), pady=4)
        combo_cond.bind(
            "<<ComboboxSelected>>", lambda _e: self._recalcular_totales()
        )

        ttk.Button(
            frame_cabecera,
            text="Refrescar",
            command=self.refrescar_datos_base,
        ).grid(row=0, column=6, sticky="e", pady=4)

        ttk.Label(
            frame_cabecera,
            textvariable=self._var_info_cliente,
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(2, 0))

        # ---------------------------------------------------------------------
        # BARRA DE CARGA DE ÍTEM (NIVEL 2)
        # ---------------------------------------------------------------------
        frame_agregar = ttk.LabelFrame(
            self, text="Agregar Artículo al Detalle", padding=(12, 8, 12, 8)
        )
        frame_agregar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        frame_agregar.columnconfigure(1, weight=2)

        ttk.Label(frame_agregar, text="Producto:").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=4
        )
        self._combo_producto = ttk.Combobox(
            frame_agregar,
            textvariable=self._var_producto,
            state="readonly",
            width=40,
        )
        self._combo_producto.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)
        self._combo_producto.bind(
            "<<ComboboxSelected>>", lambda _e: self._actualizar_info_producto()
        )

        ttk.Label(frame_agregar, text="Cantidad:").grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=4
        )
        entry_cant = ttk.Entry(
            frame_agregar, textvariable=self._var_cantidad, width=8
        )
        entry_cant.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=4)
        entry_cant.bind("<Return>", lambda _e: self._agregar_item())

        ttk.Button(
            frame_agregar, text="Agregar Ítem", command=self._agregar_item
        ).grid(row=0, column=4, sticky="e", padx=(0, 6), pady=4)

        ttk.Button(
            frame_agregar, text="Quitar Ítem", command=self._quitar_item
        ).grid(row=0, column=5, sticky="e", padx=(0, 6), pady=4)

        ttk.Button(
            frame_agregar, text="Limpiar Detalle", command=self._limpiar_detalle
        ).grid(row=0, column=6, sticky="e", pady=4)

        ttk.Label(
            frame_agregar,
            textvariable=self._var_info_producto,
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(2, 0))

        # ---------------------------------------------------------------------
        # NIVEL 2: DETALLE DE FACTURA (TREEVIEW + SCROLLBARS EN GRID)
        # ---------------------------------------------------------------------
        frame_detalle = ttk.LabelFrame(
            self, text="2. Detalle de Ítems", padding=(12, 8, 12, 8)
        )
        frame_detalle.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))
        frame_detalle.columnconfigure(0, weight=1)
        frame_detalle.rowconfigure(0, weight=1)

        columnas = (
            "codigo",
            "descripcion",
            "cantidad",
            "precio_lista",
            "desc_cant",
            "subtotal_neto",
            "imp_prov",
            "iva",
            "subtotal_final",
        )
        self._tree = ttk.Treeview(
            frame_detalle, columns=columnas, show="headings", selectmode="browse"
        )
        config_cols: Dict[str, Tuple[str, int, AnclaTreeview]] = {
            "codigo": ("Código", 95, "w"),
            "descripcion": ("Descripción", 230, "w"),
            "cantidad": ("Cant.", 65, "center"),
            "precio_lista": ("P. Lista", 95, "e"),
            "desc_cant": ("Desc. Cant.", 85, "e"),
            "subtotal_neto": ("Neto", 100, "e"),
            "imp_prov": ("Imp. Prov.", 90, "e"),
            "iva": ("IVA", 90, "e"),
            "subtotal_final": ("Subtotal", 105, "e"),
        }
        for col, (titulo, ancho, ancla) in config_cols.items():
            self._tree.heading(col, text=titulo)
            self._tree.column(col, width=ancho, anchor=ancla)

        scroll_y = ttk.Scrollbar(
            frame_detalle, orient="vertical", command=self._tree.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_detalle, orient="horizontal", command=self._tree.xview
        )
        self._tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        # ---------------------------------------------------------------------
        # NIVEL 3: TOTALES, EMISIÓN Y EXPORTACIÓN HTML
        # ---------------------------------------------------------------------
        frame_totales = ttk.LabelFrame(
            self, text="3. Totales y Emisión", padding=(12, 8, 12, 10)
        )
        frame_totales.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        for col in range(5):
            frame_totales.columnconfigure(col, weight=1)

        ttk.Label(frame_totales, text="Subtotal ítems:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(frame_totales, textvariable=self._var_subtotal).grid(
            row=1, column=0, sticky="w"
        )

        ttk.Label(frame_totales, text="Ajuste condición:").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(frame_totales, textvariable=self._var_ajuste_cond).grid(
            row=1, column=1, sticky="w"
        )

        ttk.Label(frame_totales, text="Imp. Provincial:").grid(
            row=0, column=2, sticky="w"
        )
        ttk.Label(frame_totales, textvariable=self._var_imp_prov).grid(
            row=1, column=2, sticky="w"
        )

        ttk.Label(frame_totales, text="IVA:").grid(row=0, column=3, sticky="w")
        ttk.Label(frame_totales, textvariable=self._var_iva).grid(
            row=1, column=3, sticky="w"
        )

        ttk.Label(
            frame_totales, text="TOTAL:", font=("Segoe UI", 10, "bold")
        ).grid(row=0, column=4, sticky="e")
        ttk.Label(
            frame_totales,
            textvariable=self._var_total,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=1, column=4, sticky="e")

        frame_botones = ttk.Frame(frame_totales)
        frame_botones.grid(
            row=2, column=0, columnspan=5, sticky="ew", pady=(10, 0)
        )
        frame_botones.columnconfigure(2, weight=1)

        ttk.Button(
            frame_botones,
            text="Emitir Factura",
            command=self._emitir_factura,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        self._btn_exportar_html = ttk.Button(
            frame_botones,
            text="Exportar Comprobante HTML",
            command=self._exportar_comprobante_html,
            state="disabled",
        )
        self._btn_exportar_html.grid(row=0, column=1, sticky="w", padx=(0, 8))

        ttk.Button(
            frame_botones,
            text="Nueva Factura",
            command=self._nueva_factura,
        ).grid(row=0, column=3, sticky="e")

    # -------------------------------------------------------------------------
    # CARGA Y SELECCIÓN DE CATÁLOGOS
    # -------------------------------------------------------------------------
    def refrescar_datos_base(self) -> None:
        """Recarga clientes activos, vendedores activos y productos con stock."""
        try:
            clientes_data = RepositorioVentas.listar_clientes(
                incluir_inactivos=False
            )
            vendedores_data = RepositorioVentas.listar_vendedores_activos()
            productos_data = RepositorioVentas.listar_productos_venta()
        except Exception as exc:
            messagebox.showerror("Error al cargar datos", str(exc))
            return

        self._clientes_map.clear()
        etiquetas_clientes: List[str] = []
        for reg in clientes_data:
            cli: Cliente = reg["cliente"]
            marca_frec = " [FRECUENTE]" if reg.get("es_frecuente") else ""
            etiqueta = (
                f"#{cli.id_cliente} - {cli.nombre_completo} "
                f"({cli.nro_documento}){marca_frec}"
            )
            self._clientes_map[etiqueta] = reg
            etiquetas_clientes.append(etiqueta)

        self._combo_cliente["values"] = etiquetas_clientes
        if etiquetas_clientes and self._var_cliente.get() not in self._clientes_map:
            self._var_cliente.set(etiquetas_clientes[0])
        elif not etiquetas_clientes:
            self._var_cliente.set("")
        self._actualizar_info_cliente()

        self._vendedores_map.clear()
        etiquetas_vendedores: List[str] = []
        for vend in vendedores_data:
            etiqueta = (
                f"#{vend['id_empleado']} - Leg. {vend['legajo']} "
                f"| {str(vend['nombre_completo']).strip()}"
            )
            self._vendedores_map[etiqueta] = vend
            etiquetas_vendedores.append(etiqueta)

        self._combo_vendedor["values"] = etiquetas_vendedores
        if (
            etiquetas_vendedores
            and self._var_vendedor.get() not in self._vendedores_map
        ):
            self._var_vendedor.set(etiquetas_vendedores[0])
        elif not etiquetas_vendedores:
            self._var_vendedor.set("")

        self._productos_map.clear()
        etiquetas_productos: List[str] = []
        for prod in productos_data:
            precio_fmt = _formatear_moneda(float(prod["precio_venta"]))
            etiqueta = (
                f"[{prod['codigo']}] {prod['descripcion']} "
                f"(Stock: {prod['stock_actual']} | {precio_fmt})"
            )
            self._productos_map[etiqueta] = prod
            etiquetas_productos.append(etiqueta)

        self._combo_producto["values"] = etiquetas_productos
        if (
            etiquetas_productos
            and self._var_producto.get() not in self._productos_map
        ):
            self._var_producto.set(etiquetas_productos[0])
        elif not etiquetas_productos:
            self._var_producto.set("")
        self._actualizar_info_producto()

    def _actualizar_info_cliente(self) -> None:
        reg = self._clientes_map.get(self._var_cliente.get())
        if not reg:
            self._var_info_cliente.set("Cliente: sin seleccionar")
            return
        cli: Cliente = reg["cliente"]
        compras = int(reg.get("compras_mes", 0))
        estado_frec = (
            f"Cliente Frecuente ({compras} compras en el mes)"
            if reg.get("es_frecuente")
            else f"Cliente Estándar ({compras} compras en el mes)"
        )
        self._var_info_cliente.set(
            f"Cliente: {cli.nombre_completo} | Doc: {cli.nro_documento} | {estado_frec}"
        )

    def _actualizar_info_producto(self) -> None:
        prod = self._productos_map.get(self._var_producto.get())
        if not prod:
            self._var_info_producto.set("Stock: — | Precio: —")
            return
        precio = float(prod["precio_venta"])
        stock = int(prod["stock_actual"])
        self._var_info_producto.set(
            f"Stock disponible: {stock} u. | Precio de lista: {_formatear_moneda(precio)}"
        )

    # -------------------------------------------------------------------------
    # GESTIÓN DE ÍTEMS Y CÁLCULO DE TOTALES
    # -------------------------------------------------------------------------
    def _agregar_item(self) -> None:
        prod = self._productos_map.get(self._var_producto.get())
        if not prod:
            messagebox.showwarning("Producto requerido", "Seleccioná un producto.")
            return

        try:
            cantidad = int(self._var_cantidad.get().strip())
        except ValueError:
            messagebox.showwarning(
                "Cantidad inválida", "Ingresá un número entero mayor a 0."
            )
            return

        if cantidad <= 0:
            messagebox.showwarning(
                "Cantidad inválida", "La cantidad debe ser mayor a 0."
            )
            return

        id_prod = int(prod["id"])
        stock_disp = int(prod["stock_actual"])

        cant_acumulada = cantidad
        for item in self._items_carrito:
            if int(item["id_producto"]) == id_prod:
                cant_acumulada += int(item["cantidad"])
                break

        if cant_acumulada > stock_disp:
            messagebox.showwarning(
                "Stock insuficiente",
                f"No hay stock suficiente para '{prod['descripcion']}'. "
                f"Disponible: {stock_disp}, solicitado: {cant_acumulada}.",
            )
            return

        for item in self._items_carrito:
            if int(item["id_producto"]) == id_prod:
                item["cantidad"] = cant_acumulada
                break
        else:
            self._items_carrito.append(
                {
                    "id_producto": id_prod,
                    "codigo": str(prod["codigo"]),
                    "descripcion": str(prod["descripcion"]),
                    "cantidad": cantidad,
                    "precio_lista": float(prod["precio_venta"]),
                }
            )

        self._var_cantidad.set("1")
        self._recalcular_totales()

    def _quitar_item(self) -> None:
        seleccion = self._tree.selection()
        if not seleccion:
            messagebox.showinfo(
                "Selección requerida", "Seleccioná un renglón para quitar."
            )
            return
        idx = self._tree.index(seleccion[0])
        if 0 <= idx < len(self._items_carrito):
            self._items_carrito.pop(idx)
            self._recalcular_totales()

    def _limpiar_detalle(self) -> None:
        self._items_carrito.clear()
        self._recalcular_totales()

    def _recalcular_totales(self) -> None:
        for fila in self._tree.get_children():
            self._tree.delete(fila)

        try:
            calculo = RepositorioVentas.calcular_previsualizacion_factura(
                self._items_carrito, self._var_condicion.get()
            )
        except Exception as exc:
            messagebox.showerror("Error en cálculo", str(exc))
            return

        for det in calculo["detalles"]:
            self._tree.insert(
                "",
                "end",
                values=(
                    det.codigo_producto,
                    det.descripcion_producto,
                    det.cantidad,
                    _formatear_moneda(det.precio_lista),
                    f"{det.descuento_cantidad_pct * 100:.0f}%",
                    _formatear_moneda(det.subtotal_neto),
                    _formatear_moneda(det.impuesto_provincial),
                    _formatear_moneda(det.iva),
                    _formatear_moneda(det.subtotal_final),
                ),
            )

        self._var_subtotal.set(_formatear_moneda(float(calculo["subtotal_items"])))
        ajuste = float(calculo["ajuste_condicion_monto"])
        self._var_ajuste_cond.set(_formatear_moneda(-ajuste))
        self._var_imp_prov.set(
            _formatear_moneda(float(calculo["impuesto_provincial_total"]))
        )
        self._var_iva.set(_formatear_moneda(float(calculo["iva_total"])))
        self._var_total.set(_formatear_moneda(float(calculo["total"])))

    # -------------------------------------------------------------------------
    # EMISIÓN Y COMPROBANTE HTML
    # -------------------------------------------------------------------------
    def _emitir_factura(self) -> None:
        reg_cli = self._clientes_map.get(self._var_cliente.get())
        reg_vend = self._vendedores_map.get(self._var_vendedor.get())

        if not reg_cli:
            messagebox.showwarning("Cliente requerido", "Seleccioná un cliente.")
            return
        if not reg_vend:
            messagebox.showwarning(
                "Vendedor requerido", "Seleccioná un vendedor activo."
            )
            return
        if not self._items_carrito:
            messagebox.showwarning(
                "Sin artículos", "Agregá al menos un producto a la factura."
            )
            return

        cli: Cliente = reg_cli["cliente"]
        if cli.id_cliente is None:
            messagebox.showerror("Cliente inválido", "El cliente no tiene ID válido.")
            return

        id_vendedor = int(reg_vend["id_empleado"])
        condicion = self._var_condicion.get()

        try:
            factura = RepositorioVentas.emitir_factura(
                id_cliente=cli.id_cliente,
                id_vendedor=id_vendedor,
                condicion_venta=condicion,
                items_crudos=self._items_carrito,
            )
        except Exception as exc:
            messagebox.showerror("Error al emitir factura", str(exc))
            return

        self._ultima_factura = factura
        self._btn_exportar_html.configure(state="normal")

        messagebox.showinfo(
            "Factura emitida",
            f"Factura #{factura.id_factura} emitida correctamente.\n"
            f"Total: {_formatear_moneda(factura.total)}",
        )

        self._items_carrito.clear()
        self._recalcular_totales()
        self.refrescar_datos_base()

    def _nueva_factura(self) -> None:
        self._items_carrito.clear()
        self._ultima_factura = None
        self._btn_exportar_html.configure(state="disabled")
        self._var_cantidad.set("1")
        self._recalcular_totales()
        self.refrescar_datos_base()

    def _exportar_comprobante_html(self) -> None:
        if self._ultima_factura is None:
            messagebox.showinfo(
                "Comprobante no disponible",
                "Primero emití una factura para generar su comprobante HTML.",
            )
            return

        fac = self._ultima_factura
        nombre_cli = fac.cliente_nombre or f"Cliente #{fac.id_cliente}"
        doc_cli = fac.cliente_documento
        nombre_vend = fac.vendedor_nombre or f"Vendedor #{fac.id_vendedor}"

        filas_html = []
        for det in fac.detalles:
            filas_html.append(
                f"<tr>"
                f"<td>{escape(det.codigo_producto)}</td>"
                f"<td>{escape(det.descripcion_producto)}</td>"
                f"<td style='text-align:center'>{det.cantidad}</td>"
                f"<td style='text-align:right'>{_formatear_moneda(det.precio_lista)}</td>"
                f"<td style='text-align:right'>{det.descuento_cantidad_pct * 100:.0f}%</td>"
                f"<td style='text-align:right'>{_formatear_moneda(det.subtotal_final)}</td>"
                f"</tr>"
            )

        html_doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Factura #{fac.id_factura}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 28px; color: #222; }}
  h1 {{ margin-bottom: 4px; font-size: 20px; }}
  .meta {{ margin-bottom: 18px; font-size: 13px; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 8px; }}
  th {{ background: #f2f2f2; text-align: left; }}
  .totales {{ margin-top: 16px; width: 320px; margin-left: auto; font-size: 13px; }}
  .totales td {{ border: none; padding: 4px 6px; }}
  .total-final {{ font-weight: bold; font-size: 15px; border-top: 1px solid #333 !important; }}
  @media print {{ .no-print {{ display: none; }} }}
</style>
</head>
<body>
  <h1>Comprobante de Venta — Factura #{fac.id_factura}</h1>
  <div class="meta">
    <strong>Fecha:</strong> {escape(fac.fecha)}<br>
    <strong>Cliente:</strong> {escape(nombre_cli)} {escape(f"({doc_cli})" if doc_cli else "")}<br>
    <strong>Vendedor:</strong> {escape(nombre_vend)}<br>
    <strong>Condición de venta:</strong> {escape(fac.condicion_venta)}
  </div>
  <table>
    <thead>
      <tr>
        <th>Código</th>
        <th>Descripción</th>
        <th style="text-align:center">Cant.</th>
        <th style="text-align:right">P. Lista</th>
        <th style="text-align:right">Desc.</th>
        <th style="text-align:right">Subtotal</th>
      </tr>
    </thead>
    <tbody>
      {"".join(filas_html)}
    </tbody>
  </table>
  <table class="totales">
    <tr><td>Subtotal ítems:</td><td style="text-align:right">{_formatear_moneda(fac.subtotal_items)}</td></tr>
    <tr><td>Ajuste condición:</td><td style="text-align:right">{_formatear_moneda(-fac.ajuste_condicion_monto)}</td></tr>
    <tr><td>Imp. Provincial:</td><td style="text-align:right">{_formatear_moneda(fac.impuesto_provincial_total)}</td></tr>
    <tr><td>IVA:</td><td style="text-align:right">{_formatear_moneda(fac.iva_total)}</td></tr>
    <tr class="total-final"><td>TOTAL:</td><td style="text-align:right">{_formatear_moneda(fac.total)}</td></tr>
  </table>
  <p class="no-print" style="margin-top:20px;font-size:12px;color:#555;">
    Generado el {datetime.now().strftime("%Y-%m-%d %H:%M")} — Usá Ctrl+P / Imprimir para guardar como PDF.
  </p>
</body>
</html>
"""

        ruta_sugerida = f"factura_{fac.id_factura}.html"
        ruta_archivo = filedialog.asksaveasfilename(
            title="Guardar comprobante HTML",
            initialfile=ruta_sugerida,
            defaultextension=".html",
            filetypes=[("Archivo HTML", "*.html"), ("Todos los archivos", "*.*")],
        )
        if not ruta_archivo:
            return

        destino = Path(ruta_archivo)
        destino.write_text(html_doc, encoding="utf-8")

        if messagebox.askyesno(
            "Comprobante guardado",
            f"Comprobante guardado en:\n{destino}\n\n"
            "¿Deseás abrirlo en el navegador para imprimir o exportar a PDF?",
        ):
            webbrowser.open(destino.as_uri())


if __name__ == "__main__":
    ventana_prueba = tk.Tk()
    ventana_prueba.title("Prueba - Vista Facturación")
    ventana_prueba.geometry("1040x680")
    vista = InterfazFacturacion(ventana_prueba)
    vista.grid(row=0, column=0, sticky="nsew")
    ventana_prueba.columnconfigure(0, weight=1)
    ventana_prueba.rowconfigure(0, weight=1)
    ventana_prueba.mainloop()