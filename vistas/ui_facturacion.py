"""
===============================================================================
MÓDULO DE VISTAS: FACTURACIÓN Y VENTAS (vistas/ui_facturacion.py)
===============================================================================
Interfaz gráfica para la emisión de comprobantes de venta, selección de clientes,
vendedores y productos, con cálculo automático según medio de pago, resguardo
HTML en comprobantes/facturas, visualización emergente y exportación a PDF
para impresión sin exponer carpetas de comprobantes al vendedor.
===============================================================================
"""

from datetime import datetime
import html
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import config as app_config
from dominio.entidades_ventas import Factura
from infraestructura.conexion import ConexionDB
from infraestructura.repo_stock import RepositorioStock
from infraestructura.repo_ventas import RepositorioVentas
from vistas.estilos import (
    CARPETA_COMPROBANTES_DEFECTO,
    IMPUESTO_PROVINCIAL_DEFECTO_PORC,
    IVA_DEFECTO_PORC,
    PRECIO_LISTA_DEFECTO,
    aplicar_estilos_base,
)

MEDIOS_PAGO_FALLBACK: Tuple[str, ...] = (
    "Efectivo",
    "Transferencia",
    "Tarjeta de Crédito",
)

ROLES_VENDEDOR_VALIDOS: Tuple[str, ...] = (
    "vendedor",
    "empleado de ventas",
    "empleado_ventas",
    "ventas",
)


def _iva_defecto() -> float:
    raw = getattr(app_config, "IVA_POR_DEFECTO", IVA_DEFECTO_PORC)
    try:
        tasa = float(raw)
    except (TypeError, ValueError):
        tasa = IVA_DEFECTO_PORC
    return tasa / 100.0 if tasa > 1.0 else tasa


def _medios_pago() -> Tuple[str, ...]:
    medios = getattr(app_config, "MEDIOS_PAGO_PERMITIDOS", None)
    if isinstance(medios, (tuple, list)) and len(medios) > 0:
        return tuple(str(m) for m in medios)
    return MEDIOS_PAGO_FALLBACK


def _dir_facturas() -> Path:
    carpeta = getattr(app_config, "DIR_FACTURAS", None)
    if isinstance(carpeta, Path):
        return carpeta
    if isinstance(carpeta, str) and carpeta.strip():
        return Path(carpeta)
    return CARPETA_COMPROBANTES_DEFECTO / "facturas"


def _ajuste_medio(medio: str) -> Tuple[float, float]:
    raw_fn = getattr(app_config, "obtener_ajuste_medio_pago", None)
    fn = cast(Optional[Callable[[str], Tuple[float, float]]], raw_fn)
    if fn is not None:
        res = fn(medio)
        if isinstance(res, (tuple, list)) and len(res) >= 2:
            return float(res[0] or 0.0), float(res[1] or 0.0)
    clave = medio.strip().lower()
    if clave == "efectivo":
        return 10.0, 0.0
    if "crédito" in clave or "credito" in clave:
        return 0.0, 10.0
    return 0.0, 0.0


def _abrev_medio(medio: str) -> str:
    raw_fn = getattr(app_config, "obtener_abreviatura_medio_pago", None)
    fn = cast(Optional[Callable[[str], str]], raw_fn)
    if fn is not None:
        res = fn(medio)
        if isinstance(res, str) and res.strip():
            return res.strip()
    clave = medio.strip().lower()
    if clave == "efectivo":
        return "Ef."
    if "transferencia" in clave:
        return "Transf."
    if "crédito" in clave or "credito" in clave:
        return "T. Crédito"
    return medio.strip()


def _id_producto(prod: Any) -> int:
    raw = getattr(prod, "id_producto", None)
    if raw is None:
        raw = getattr(prod, "id", 0)
    return int(raw or 0)


def _stock_producto(prod: Any) -> int:
    raw = getattr(prod, "stock_actual", None)
    if raw is None:
        raw = getattr(prod, "stock", 0)
    return int(raw or 0)


def _precio_producto(prod: Any) -> float:
    raw = getattr(prod, "precio_venta", None)
    if raw is None:
        raw = getattr(prod, "precio_unitario", PRECIO_LISTA_DEFECTO)
    try:
        valor = float(raw if raw is not None else PRECIO_LISTA_DEFECTO)
    except (TypeError, ValueError):
        valor = PRECIO_LISTA_DEFECTO
    return round(valor, 2)


def _es_rol_vendedor(rol_o_cargo: Any) -> bool:
    texto = str(rol_o_cargo or "").strip().lower()
    if not texto:
        return False
    if any(excluido in texto for excluido in ("gerente", "admin")):
        return False
    return any(permitido in texto for permitido in ROLES_VENDEDOR_VALIDOS)


def _escapar_pdf(texto: str) -> str:
    limpio = texto.encode("latin-1", errors="replace").decode("latin-1")
    return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _exportar_pdf_desde_texto(lineas: List[str], ruta_pdf: Path) -> None:
    """
    Genera un archivo PDF válido con las líneas del comprobante sin requerir
    dependencias externas obligatorias.
    """
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)

    comandos: List[str] = ["BT", "/F1 10 Tf", "45 750 Td", "14 TL"]
    for idx, linea in enumerate(lineas):
        escapada = _escapar_pdf(linea)
        if idx == 0:
            comandos.append(f"({escapada}) Tj")
        else:
            comandos.append(f"T* ({escapada}) Tj")
    comandos.append("ET")
    stream_contenido = "\n".join(comandos).encode("latin-1", errors="replace")

    objetos: List[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream_contenido)} >>\nstream\n".encode("ascii")
            + stream_contenido
            + b"\nendstream\nendobj\n"
        ),
    ]

    salida = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = [0]
    for obj in objetos:
        offsets.append(len(salida))
        salida.extend(obj)

    pos_xref = len(salida)
    salida.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    salida.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        salida.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    salida.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{pos_xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    ruta_pdf.write_bytes(bytes(salida))


class InterfazFacturacion(ttk.Frame):
    """Vista modular para selección de clientes/vendedores/productos y facturación."""

    def __init__(self, parent: tk.Misc, usuario_actual: Any = None) -> None:
        super().__init__(parent)
        self.usuario_actual: Any = usuario_actual

        self.clientes_disponibles: List[Tuple[int, str]] = []
        self.vendedores_disponibles: List[Tuple[int, str]] = []
        self.productos_disponibles: List[Any] = []
        self.items_actuales: List[Dict[str, Any]] = []
        self.ultima_factura_emitida: Optional[Dict[str, Any]] = None
        self.ultima_ruta_html: Optional[Path] = None

        medios: Tuple[str, ...] = _medios_pago()
        tasa_iva: float = _iva_defecto()

        self.var_cliente = tk.StringVar()
        self.var_vendedor = tk.StringVar()
        self.var_medio_pago = tk.StringVar(value=medios[0])
        self.var_producto = tk.StringVar()
        self.var_cantidad = tk.StringVar(value="1")

        self.var_bonificacion_pct = tk.StringVar(value="0.0")
        self.var_recargo_pct = tk.StringVar(value="0.0")
        self.var_impuesto_pct = tk.StringVar(value=f"{tasa_iva * 100:.1f}")

        self.var_monto_bonificacion = tk.StringVar(value="0.00")
        self.var_monto_recargo = tk.StringVar(value="0.00")
        self.var_monto_impuestos = tk.StringVar(value="0.00")
        self.var_subtotal_productos = tk.StringVar(value="$0.00")
        self.var_subtotal_neto = tk.StringVar(value="$0.00")
        self.var_total_pagar = tk.StringVar(value="$0.00")

        self._construir_interfaz(medios)
        self._cargar_catalogos()
        self._al_cambiar_medio_pago()

    # =========================================================================
    # INTERFAZ GRÁFICA (GRID UNIFORME Y AJUSTE A PANTALLA)
    # =========================================================================
    def _construir_interfaz(self, medios: Tuple[str, ...]) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # 1. Datos del comprobante y productos
        frame_sup = ttk.LabelFrame(
            self,
            text=" Datos del Comprobante y Productos ",
            padding=8,
        )
        frame_sup.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 4))
        frame_sup.columnconfigure(1, weight=1, minsize=140)
        frame_sup.columnconfigure(3, weight=1, minsize=140)

        ttk.Label(frame_sup, text="Cliente *:").grid(
            row=0, column=0, sticky="w", pady=3, padx=(0, 4)
        )
        self.combo_cliente = ttk.Combobox(
            frame_sup,
            textvariable=self.var_cliente,
            state="readonly",
            width=24,
        )
        self.combo_cliente.grid(row=0, column=1, sticky="ew", pady=3, padx=(0, 10))

        ttk.Label(frame_sup, text="Vendedor *:").grid(
            row=0, column=2, sticky="w", pady=3, padx=(0, 4)
        )
        self.combo_vendedor = ttk.Combobox(
            frame_sup,
            textvariable=self.var_vendedor,
            state="readonly",
            width=24,
        )
        self.combo_vendedor.grid(row=0, column=3, sticky="ew", pady=3)

        ttk.Label(frame_sup, text="Medio de pago *:").grid(
            row=1, column=0, sticky="w", pady=3, padx=(0, 4)
        )
        self.combo_medio_pago = ttk.Combobox(
            frame_sup,
            textvariable=self.var_medio_pago,
            values=list(medios),
            state="readonly",
            width=24,
        )
        self.combo_medio_pago.grid(row=1, column=1, sticky="ew", pady=3, padx=(0, 10))
        self.combo_medio_pago.bind("<<ComboboxSelected>>", self._al_cambiar_medio_pago)

        ttk.Label(frame_sup, text="Producto *:").grid(
            row=1, column=2, sticky="w", pady=3, padx=(0, 4)
        )
        self.combo_producto = ttk.Combobox(
            frame_sup,
            textvariable=self.var_producto,
            state="readonly",
            width=28,
        )
        self.combo_producto.grid(row=1, column=3, sticky="ew", pady=3)

        ttk.Label(frame_sup, text="Cantidad *:").grid(
            row=2, column=0, sticky="w", pady=3, padx=(0, 4)
        )
        self.entry_cantidad = ttk.Entry(
            frame_sup, textvariable=self.var_cantidad, width=10
        )
        self.entry_cantidad.grid(row=2, column=1, sticky="w", pady=3, padx=(0, 10))

        self.lbl_info_medio = ttk.Label(frame_sup, text="", style="Muted.TLabel")
        self.lbl_info_medio.grid(row=2, column=2, columnspan=2, sticky="w", pady=3)

        frame_acciones_item = ttk.Frame(frame_sup)
        frame_acciones_item.grid(row=3, column=0, columnspan=4, sticky="e", pady=(6, 0))

        ttk.Button(
            frame_acciones_item, text="Agregar Ítem", command=self.agregar_item
        ).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(
            frame_acciones_item,
            text="Modificar Producto",
            command=self.modificar_item_seleccionado,
        ).grid(row=0, column=1, padx=4)
        ttk.Button(
            frame_acciones_item, text="Quitar", command=self.quitar_item_seleccionado
        ).grid(row=0, column=2, padx=(4, 0))

        # 2. Detalle de productos
        frame_detalle = ttk.LabelFrame(
            self,
            text=" Detalle de Productos (Seleccione una fila para modificar o quitar) ",
            padding=8,
        )
        frame_detalle.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        frame_detalle.columnconfigure(0, weight=1)
        frame_detalle.rowconfigure(0, weight=1)

        columnas = ("id", "codigo", "producto", "cantidad", "precio_unit", "total_item")
        self.tree = ttk.Treeview(
            frame_detalle,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=5,
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("codigo", text="Código")
        self.tree.heading("producto", text="Producto")
        self.tree.heading("cantidad", text="Cant.")
        self.tree.heading("precio_unit", text="Precio Unit.")
        self.tree.heading("total_item", text="Total por ítem")

        self.tree.column("id", width=48, minwidth=40, anchor="center", stretch=False)
        self.tree.column("codigo", width=85, minwidth=70, anchor="center", stretch=False)
        self.tree.column("producto", width=220, minwidth=140, anchor="w", stretch=True)
        self.tree.column("cantidad", width=65, minwidth=55, anchor="center", stretch=False)
        self.tree.column("precio_unit", width=110, minwidth=90, anchor="e", stretch=False)
        self.tree.column("total_item", width=120, minwidth=100, anchor="e", stretch=False)

        scroll_y = ttk.Scrollbar(frame_detalle, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(frame_detalle, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

        # 3. Totales y emisión
        frame_totales = ttk.LabelFrame(self, text=" Totales y Emisión ", padding=8)
        frame_totales.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        frame_totales.columnconfigure(2, weight=1)

        ttk.Label(frame_totales, text="Bonificación $").grid(
            row=0, column=0, sticky="w", pady=2, padx=(0, 8)
        )
        ttk.Entry(
            frame_totales,
            textvariable=self.var_monto_bonificacion,
            width=12,
            state="readonly",
            justify="right",
        ).grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(
            frame_totales, text="Subtotal productos:", style="Subtotal.TLabel"
        ).grid(row=0, column=3, sticky="e", pady=2, padx=(16, 8))
        ttk.Label(
            frame_totales, textvariable=self.var_subtotal_productos, style="Subtotal.TLabel"
        ).grid(row=0, column=4, sticky="e", pady=2)

        ttk.Label(frame_totales, text="Impuestos $").grid(
            row=1, column=0, sticky="w", pady=2, padx=(0, 8)
        )
        ttk.Entry(
            frame_totales,
            textvariable=self.var_monto_impuestos,
            width=12,
            state="readonly",
            justify="right",
        ).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(
            frame_totales, text="Subtotal (antes de impuestos):", style="Subtotal.TLabel"
        ).grid(row=1, column=3, sticky="e", pady=2, padx=(16, 8))
        ttk.Label(
            frame_totales, textvariable=self.var_subtotal_neto, style="Subtotal.TLabel"
        ).grid(row=1, column=4, sticky="e", pady=2)

        ttk.Label(frame_totales, text="Recargos $").grid(
            row=2, column=0, sticky="w", pady=2, padx=(0, 8)
        )
        ttk.Entry(
            frame_totales,
            textvariable=self.var_monto_recargo,
            width=12,
            state="readonly",
            justify="right",
        ).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frame_totales, text="TOTAL A PAGAR:", style="Total.TLabel").grid(
            row=2, column=3, sticky="e", pady=(4, 2), padx=(16, 8)
        )
        ttk.Label(frame_totales, textvariable=self.var_total_pagar, style="Total.TLabel").grid(
            row=2, column=4, sticky="e", pady=(4, 2)
        )

        frame_botones_emision = ttk.Frame(frame_totales)
        frame_botones_emision.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Button(
            frame_botones_emision, text="Emitir factura", command=self.emitir_factura
        ).grid(row=0, column=0)

    # =========================================================================
    # CARGA DE CATÁLOGOS
    # =========================================================================
    def _cargar_catalogos(self) -> None:
        self._cargar_clientes()
        self._cargar_vendedores()
        self._cargar_productos()

    def _cargar_clientes(self) -> None:
        self.clientes_disponibles = []
        try:
            with ConexionDB() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT c.id, p.apellidos, p.nombres
                    FROM clientes c
                    INNER JOIN personas p ON c.id_persona = p.id
                    WHERE COALESCE(c.activo, 1) = 1
                    ORDER BY p.apellidos ASC, p.nombres ASC
                    """
                )
                for row in cur.fetchall():
                    cid = int(row[0])
                    self.clientes_disponibles.append((cid, f"[{cid}] {row[1]}, {row[2]}"))
        except Exception as exc:
            messagebox.showerror(
                "Error", f"No se pudieron cargar los clientes: {exc}", parent=self
            )

        valores = [etq for _, etq in self.clientes_disponibles]
        self.combo_cliente["values"] = valores
        if valores and self.var_cliente.get() not in valores:
            self.combo_cliente.current(0)
        elif not valores:
            self.var_cliente.set("")

    def _cargar_vendedores(self) -> None:
        self.vendedores_disponibles = []
        try:
            with ConexionDB() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT e.id, p.apellidos, p.nombres, COALESCE(e.cargo, '')
                    FROM empleados e
                    INNER JOIN personas p ON e.id_persona = p.id
                    WHERE COALESCE(e.activo, 1) = 1
                    ORDER BY p.apellidos ASC, p.nombres ASC
                    """
                )
                for row in cur.fetchall():
                    if _es_rol_vendedor(row[3]):
                        vid = int(row[0])
                        self.vendedores_disponibles.append(
                            (vid, f"[{vid}] {row[1]}, {row[2]}")
                        )
        except Exception as exc:
            messagebox.showerror(
                "Error", f"No se pudieron cargar los vendedores: {exc}", parent=self
            )

        valores = [etq for _, etq in self.vendedores_disponibles]
        self.combo_vendedor["values"] = valores
        if valores and self.var_vendedor.get() not in valores:
            self.combo_vendedor.current(0)
        elif not valores:
            self.var_vendedor.set("")

    def _cargar_productos(self) -> None:
        try:
            repo_stock: Any = RepositorioStock
            raw_fn = getattr(repo_stock, "listar_productos", None)
            fn = cast(Optional[Callable[[], Any]], raw_fn)
            if fn is not None:
                raw_productos: Any = fn()
            else:
                raw_productos = repo_stock().listar_productos()
            lista_prod: List[Any] = (
                list(raw_productos) if isinstance(raw_productos, (list, tuple)) else []
            )
            self.productos_disponibles = [
                p for p in lista_prod if getattr(p, "activo", True)
            ]
        except Exception as exc:
            self.productos_disponibles = []
            messagebox.showerror(
                "Error", f"No se pudieron cargar los productos: {exc}", parent=self
            )

        valores = [
            f"[{getattr(p, 'codigo', '')}] {getattr(p, 'descripcion', '')} (${_precio_producto(p):,.2f})"
            for p in self.productos_disponibles
        ]
        self.combo_producto["values"] = valores
        if valores and self.var_producto.get() not in valores:
            self.combo_producto.current(0)

    # =========================================================================
    # LÓGICA DE MEDIO DE PAGO Y CÁLCULOS
    # =========================================================================
    def _al_cambiar_medio_pago(self, _event: Any = None) -> None:
        medio = self.var_medio_pago.get().strip()
        bonif_pct, recargo_pct = _ajuste_medio(medio)
        iva_pct = float(self.var_impuesto_pct.get() or IVA_DEFECTO_PORC)
        abrev = _abrev_medio(medio)

        self.var_bonificacion_pct.set(f"{bonif_pct:.1f}")
        self.var_recargo_pct.set(f"{recargo_pct:.1f}")

        if bonif_pct > 0:
            detalle_ajuste = f"Bonif. {bonif_pct:.0f}%"
        elif recargo_pct > 0:
            detalle_ajuste = f"Recargo {recargo_pct:.0f}%"
        else:
            detalle_ajuste = "Sin bonif./recargo 0%"

        self.lbl_info_medio.config(
            text=f"{detalle_ajuste} · IVA {iva_pct:.1f}% {abrev}"
        )
        self._recalcular_totales()

    def _obtener_totales_calculados(self) -> Dict[str, float]:
        subtotal_productos = round(
            sum(float(it["total_item"]) for it in self.items_actuales),
            2,
        )
        bonif_pct = float(self.var_bonificacion_pct.get() or 0.0)
        recargo_pct = float(self.var_recargo_pct.get() or 0.0)
        iva_pct = float(self.var_impuesto_pct.get() or IVA_DEFECTO_PORC)

        monto_bonificacion = round(subtotal_productos * (bonif_pct / 100.0), 2)
        monto_recargo = round(subtotal_productos * (recargo_pct / 100.0), 2)
        subtotal_neto = round(subtotal_productos - monto_bonificacion + monto_recargo, 2)
        monto_impuestos = round(subtotal_neto * (iva_pct / 100.0), 2)
        total_pagar = round(subtotal_neto + monto_impuestos, 2)

        return {
            "subtotal_productos": subtotal_productos,
            "bonificacion_pct": bonif_pct,
            "monto_bonificacion": monto_bonificacion,
            "recargo_pct": recargo_pct,
            "monto_recargo": monto_recargo,
            "subtotal_neto": subtotal_neto,
            "impuesto_pct": iva_pct,
            "monto_impuestos": monto_impuestos,
            "total_pagar": total_pagar,
        }

    def _recalcular_totales(self) -> None:
        tot = self._obtener_totales_calculados()
        self.var_subtotal_productos.set(f"${tot['subtotal_productos']:,.2f}")
        self.var_monto_bonificacion.set(f"{tot['monto_bonificacion']:,.2f}")
        self.var_monto_recargo.set(f"{tot['monto_recargo']:,.2f}")
        self.var_subtotal_neto.set(f"${tot['subtotal_neto']:,.2f}")
        self.var_monto_impuestos.set(f"{tot['monto_impuestos']:,.2f}")
        self.var_total_pagar.set(f"${tot['total_pagar']:,.2f}")

    # =========================================================================
    # GESTIÓN DE ÍTEMS EN EL DETALLE
    # =========================================================================
    def _obtener_producto_seleccionado_combo(self) -> Optional[Any]:
        idx = self.combo_producto.current()
        if idx < 0 or idx >= len(self.productos_disponibles):
            return None
        return self.productos_disponibles[idx]

    def _validar_cantidad(self) -> Optional[int]:
        try:
            cant = int(self.var_cantidad.get().strip())
            if cant <= 0:
                raise ValueError
            return cant
        except ValueError:
            messagebox.showerror(
                "Cantidad inválida",
                "Ingrese una cantidad entera mayor a cero.",
                parent=self,
            )
            return None

    def agregar_item(self) -> None:
        prod = self._obtener_producto_seleccionado_combo()
        if prod is None:
            messagebox.showwarning(
                "Producto requerido", "Seleccione un producto válido.", parent=self
            )
            return

        cantidad = self._validar_cantidad()
        if cantidad is None:
            return

        pid = _id_producto(prod)
        stock_disp = _stock_producto(prod)
        existente = next(
            (it for it in self.items_actuales if int(it["id_producto"]) == pid),
            None,
        )
        cantidad_total = cantidad + (int(existente["cantidad"]) if existente else 0)
        if cantidad_total > stock_disp:
            messagebox.showwarning(
                "Stock insuficiente",
                f"Stock disponible para '{getattr(prod, 'descripcion', '')}': {stock_disp} unidades.",
                parent=self,
            )
            return

        precio_unit = _precio_producto(prod)
        if existente is not None:
            existente["cantidad"] = cantidad_total
            existente["precio_unitario"] = precio_unit
            existente["total_item"] = round(cantidad_total * precio_unit, 2)
        else:
            self.items_actuales.append(
                {
                    "id_producto": pid,
                    "codigo": str(getattr(prod, "codigo", "")),
                    "descripcion": str(getattr(prod, "descripcion", "")),
                    "cantidad": cantidad,
                    "precio_unitario": precio_unit,
                    "total_item": round(cantidad * precio_unit, 2),
                }
            )

        self.var_cantidad.set("1")
        self._refrescar_tabla_detalles()

    def modificar_item_seleccionado(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(
                "Sin selección",
                "Seleccione una fila de la tabla para modificar.",
                parent=self,
            )
            return

        idx_fila = self.tree.index(sel[0])
        if idx_fila < 0 or idx_fila >= len(self.items_actuales):
            return

        prod = self._obtener_producto_seleccionado_combo()
        if prod is None:
            messagebox.showwarning(
                "Producto requerido", "Seleccione un producto válido.", parent=self
            )
            return

        cantidad = self._validar_cantidad()
        if cantidad is None:
            return

        stock_disp = _stock_producto(prod)
        if cantidad > stock_disp:
            messagebox.showwarning(
                "Stock insuficiente",
                f"Stock disponible para '{getattr(prod, 'descripcion', '')}': {stock_disp} unidades.",
                parent=self,
            )
            return

        precio_unit = _precio_producto(prod)
        self.items_actuales[idx_fila] = {
            "id_producto": _id_producto(prod),
            "codigo": str(getattr(prod, "codigo", "")),
            "descripcion": str(getattr(prod, "descripcion", "")),
            "cantidad": cantidad,
            "precio_unitario": precio_unit,
            "total_item": round(cantidad * precio_unit, 2),
        }
        self._refrescar_tabla_detalles()

    def quitar_item_seleccionado(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(
                "Sin selección",
                "Seleccione una fila de la tabla para quitar.",
                parent=self,
            )
            return

        idx_fila = self.tree.index(sel[0])
        if 0 <= idx_fila < len(self.items_actuales):
            self.items_actuales.pop(idx_fila)
            self._refrescar_tabla_detalles()

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx_fila = self.tree.index(sel[0])
        if idx_fila < 0 or idx_fila >= len(self.items_actuales):
            return

        item = self.items_actuales[idx_fila]
        self.var_cantidad.set(str(item["cantidad"]))
        for idx_prod, prod in enumerate(self.productos_disponibles):
            if _id_producto(prod) == int(item["id_producto"]):
                self.combo_producto.current(idx_prod)
                break

    def _refrescar_tabla_detalles(self) -> None:
        for fila in self.tree.get_children():
            self.tree.delete(fila)

        for item in self.items_actuales:
            self.tree.insert(
                "",
                "end",
                values=(
                    item["id_producto"],
                    item["codigo"],
                    item["descripcion"],
                    item["cantidad"],
                    f"${float(item['precio_unitario']):,.2f}",
                    f"${float(item['total_item']):,.2f}",
                ),
            )

        self._recalcular_totales()

    # =========================================================================
    # EMISIÓN, VISUALIZACIÓN EMERGENTE E IMPRESIÓN EN PDF
    # =========================================================================
    def _obtener_id_cliente_seleccionado(self) -> Optional[int]:
        idx = self.combo_cliente.current()
        if idx < 0 or idx >= len(self.clientes_disponibles):
            return None
        return int(self.clientes_disponibles[idx][0])

    def _obtener_id_vendedor_seleccionado(self) -> Optional[int]:
        idx = self.combo_vendedor.current()
        if idx < 0 or idx >= len(self.vendedores_disponibles):
            return None
        return int(self.vendedores_disponibles[idx][0])

    def _persistir_factura_en_repo(
        self,
        id_cliente: int,
        id_vendedor: int,
        medio_pago: str,
        items_crudos: List[Dict[str, Any]],
    ) -> Factura:
        return RepositorioVentas.emitir_factura(
            id_cliente=id_cliente,
            id_vendedor=id_vendedor,
            condicion_venta=medio_pago,
            items_crudos=items_crudos,
        )

    def _obtener_carpeta_comprobante(self, subcarpeta: str = "facturas") -> Path:
        if subcarpeta == "facturas":
            return _dir_facturas()
        base_dir = _dir_facturas().parent
        return base_dir / subcarpeta

    def _formatear_comprobante_html(self, datos: Dict[str, Any]) -> str:
        tot = datos["totales"]
        filas_html: List[str] = []
        for it in datos["items"]:
            filas_html.append(
                "<tr>"
                f"<td>{html.escape(str(it['codigo']))}</td>"
                f"<td>{html.escape(str(it['descripcion']))}</td>"
                f"<td class='num'>{int(it['cantidad'])}</td>"
                f"<td class='num'>${float(it['precio_unitario']):,.2f}</td>"
                f"<td class='num'>${float(it['total_item']):,.2f}</td>"
                "</tr>"
            )

        return (
            "<!DOCTYPE html>\n"
            "<html lang='es'>\n"
            "<head>\n"
            "<meta charset='utf-8'>\n"
            f"<title>Factura #{html.escape(str(datos['id_factura']))}</title>\n"
            "<style>\n"
            "body { font-family: Arial, sans-serif; color: #111; margin: 28px; }\n"
            "h1 { font-size: 18px; margin-bottom: 6px; }\n"
            ".meta { margin-bottom: 16px; line-height: 1.5; }\n"
            "table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }\n"
            "th, td { border: 1px solid #556B2F; padding: 6px 8px; }\n"
            "th { background: #9ACD32; text-align: left; }\n"
            ".num { text-align: right; }\n"
            ".totales { width: 360px; margin-left: auto; }\n"
            ".totales td { border: none; padding: 4px 6px; }\n"
            ".total-final { font-size: 15px; font-weight: bold; border-top: 1px solid #111 !important; }\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"<h1>Frankie Gestor Comercial - Factura #{html.escape(str(datos['id_factura']))}</h1>\n"
            "<div class='meta'>\n"
            f"<div>Fecha: {html.escape(str(datos['fecha']))}</div>\n"
            f"<div>Cliente: {html.escape(str(datos['cliente']))}</div>\n"
            f"<div>Vendedor: {html.escape(str(datos['vendedor']))}</div>\n"
            f"<div>Medio de pago: {html.escape(str(datos['medio_pago']))} ({html.escape(str(datos['medio_pago_abrev']))})</div>\n"
            "</div>\n"
            "<table>\n"
            "<thead><tr><th>Código</th><th>Producto</th><th>Cant.</th><th>Precio Unit.</th><th>Total</th></tr></thead>\n"
            f"<tbody>{''.join(filas_html)}</tbody>\n"
            "</table>\n"
            "<table class='totales'>\n"
            f"<tr><td>Subtotal productos:</td><td class='num'>${tot['subtotal_productos']:,.2f}</td></tr>\n"
            f"<tr><td>Bonificación {tot['bonificacion_pct']:.1f}%:</td><td class='num'>{tot['monto_bonificacion']:,.2f}</td></tr>\n"
            f"<tr><td>Recargos {tot['recargo_pct']:.1f}%:</td><td class='num'>{tot['monto_recargo']:,.2f}</td></tr>\n"
            f"<tr><td>Subtotal antes de impuestos:</td><td class='num'>${tot['subtotal_neto']:,.2f}</td></tr>\n"
            f"<tr><td>Impuestos {tot['impuesto_pct']:.1f}%:</td><td class='num'>{tot['monto_impuestos']:,.2f}</td></tr>\n"
            f"<tr class='total-final'><td>TOTAL A PAGAR:</td><td class='num'>${tot['total_pagar']:,.2f}</td></tr>\n"
            "</table>\n"
            "</body>\n"
            "</html>\n"
        )

    def _formatear_comprobante_lineas_pdf(self, datos: Dict[str, Any]) -> List[str]:
        tot = datos["totales"]
        lineas = [
            f"FRANKIE GESTOR COMERCIAL - FACTURA #{datos['id_factura']}",
            f"Fecha: {datos['fecha']}   Medio: {datos['medio_pago']} ({datos['medio_pago_abrev']})",
            f"Cliente: {datos['cliente']}",
            f"Vendedor: {datos['vendedor']}",
            "----------------------------------------------------------------",
            "Codigo      Producto                      Cant   P.Unit      Total",
            "----------------------------------------------------------------",
        ]
        for it in datos["items"]:
            cod = str(it["codigo"])[:10]
            desc = str(it["descripcion"])[:26]
            lineas.append(
                f"{cod:<11} {desc:<27} {int(it['cantidad']):>4} "
                f"{float(it['precio_unitario']):>9,.2f} {float(it['total_item']):>10,.2f}"
            )
        lineas.extend(
            [
                "----------------------------------------------------------------",
                f"Subtotal productos:            ${tot['subtotal_productos']:>12,.2f}",
                f"Bonificacion ({tot['bonificacion_pct']:.1f}%):          {tot['monto_bonificacion']:>12,.2f}",
                f"Recargos ({tot['recargo_pct']:.1f}%):              {tot['monto_recargo']:>12,.2f}",
                f"Subtotal antes de impuestos:   ${tot['subtotal_neto']:>12,.2f}",
                f"Impuestos ({tot['impuesto_pct']:.1f}%):               {tot['monto_impuestos']:>12,.2f}",
                f"TOTAL A PAGAR:                 ${tot['total_pagar']:>12,.2f}",
            ]
        )
        return lineas

    def _formatear_vista_previa_texto(self, datos: Dict[str, Any]) -> str:
        return "\n".join(self._formatear_comprobante_lineas_pdf(datos))

    def _guardar_resguardo_html(self, datos: Dict[str, Any]) -> Optional[Path]:
        carpeta = self._obtener_carpeta_comprobante("facturas")
        carpeta.mkdir(parents=True, exist_ok=True)
        base_nombre = str(datos.get("base_nombre") or f"factura_{datos['id_factura']}")
        ruta_html = carpeta / f"{base_nombre}.html"
        ruta_html.write_text(self._formatear_comprobante_html(datos), encoding="utf-8")
        self.ultima_ruta_html = ruta_html
        return ruta_html

    def _generar_pdf_en_resguardo(self, datos: Dict[str, Any]) -> Path:
        carpeta = self._obtener_carpeta_comprobante("facturas")
        carpeta.mkdir(parents=True, exist_ok=True)
        base_nombre = str(datos.get("base_nombre") or f"factura_{datos['id_factura']}")
        ruta_html = self.ultima_ruta_html or (carpeta / f"{base_nombre}.html")
        if not ruta_html.exists():
            ruta_html.write_text(
                self._formatear_comprobante_html(datos), encoding="utf-8"
            )
            self.ultima_ruta_html = ruta_html

        ruta_pdf = carpeta / f"{base_nombre}.pdf"
        _exportar_pdf_desde_texto(
            self._formatear_comprobante_lineas_pdf(datos),
            ruta_pdf,
        )
        return ruta_pdf

    def emitir_factura(self) -> None:
        if not self.items_actuales:
            messagebox.showwarning(
                "Sin ítems",
                "Agregue al menos un producto antes de emitir la factura.",
                parent=self,
            )
            return

        id_cliente = self._obtener_id_cliente_seleccionado()
        id_vendedor = self._obtener_id_vendedor_seleccionado()
        if id_cliente is None or id_vendedor is None:
            messagebox.showwarning(
                "Datos incompletos",
                "Seleccione un cliente activo y un vendedor válidos.",
                parent=self,
            )
            return

        medio_pago = self.var_medio_pago.get().strip() or "Efectivo"
        abrev_medio = _abrev_medio(medio_pago)
        tot = self._obtener_totales_calculados()

        items_crudos: List[Dict[str, Any]] = [
            {
                "id_producto": int(it["id_producto"]),
                "codigo": str(it["codigo"]),
                "descripcion": str(it["descripcion"]),
                "cantidad": int(it["cantidad"]),
                "precio_lista": float(it["precio_unitario"]),
            }
            for it in self.items_actuales
        ]

        try:
            factura_guardada = self._persistir_factura_en_repo(
                id_cliente=int(id_cliente),
                id_vendedor=int(id_vendedor),
                medio_pago=medio_pago,
                items_crudos=items_crudos,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al Emitir",
                f"No se pudo emitir la factura: {exc}",
                parent=self,
            )
            return

        nro_factura = (
            factura_guardada.id_factura
            if factura_guardada.id_factura is not None
            else 0
        )

        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_nombre = f"factura_{nro_factura}_{sello}" if nro_factura else f"factura_{sello}"

        datos_factura: Dict[str, Any] = {
            "id_factura": nro_factura,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "cliente": factura_guardada.cliente_nombre or self.var_cliente.get(),
            "vendedor": factura_guardada.vendedor_nombre or self.var_vendedor.get(),
            "medio_pago": medio_pago,
            "medio_pago_abrev": abrev_medio,
            "items": [dict(it) for it in self.items_actuales],
            "totales": tot,
            "base_nombre": base_nombre,
        }
        self.ultima_factura_emitida = datos_factura

        try:
            self._guardar_resguardo_html(datos_factura)
        except OSError:
            self.ultima_ruta_html = None

        messagebox.showinfo(
            "Factura Emitida",
            (
                f"Factura #{nro_factura} emitida y guardada correctamente.\n"
                f"Total a pagar: ${tot['total_pagar']:,.2f}"
            ),
            parent=self,
        )

        self.abrir_ventana_impresion(conservar_factura=True)

    def abrir_ventana_impresion(self, conservar_factura: bool = True) -> None:
        datos = self.ultima_factura_emitida
        if datos is None:
            messagebox.showinfo(
                "Sin factura emitida",
                "Primero emita una factura para visualizarla e imprimirla en PDF.",
                parent=self,
            )
            return

        ventana = tk.Toplevel(self)
        ventana.title(f"Comprobante - Factura #{datos['id_factura']}")
        ventana.geometry("680x440")
        ventana.transient(self.winfo_toplevel())
        ventana.grab_set()
        ventana.columnconfigure(0, weight=1)
        ventana.rowconfigure(0, weight=1)

        marco = ttk.Frame(ventana, padding=10)
        marco.grid(row=0, column=0, sticky="nsew")
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(0, weight=1)

        texto = tk.Text(
            marco,
            wrap="none",
            font=("Courier New", 10),
            state="normal",
        )
        texto.grid(row=0, column=0, sticky="nsew")
        texto.insert("1.0", self._formatear_vista_previa_texto(datos))
        texto.configure(state="disabled")

        scroll_y = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
        scroll_x = ttk.Scrollbar(marco, orient="horizontal", command=texto.xview)
        texto.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        frame_pie = ttk.Frame(marco)
        frame_pie.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def _imprimir_y_finalizar() -> None:
            try:
                self._generar_pdf_en_resguardo(datos)
            except OSError as exc:
                messagebox.showerror(
                    "Error al Imprimir PDF",
                    f"No se pudo generar el PDF de la factura: {exc}",
                    parent=ventana,
                )
                return

            messagebox.showinfo(
                "PDF Generado",
                f"Factura #{datos['id_factura']} exportada a PDF correctamente.",
                parent=ventana,
            )
            ventana.destroy()
            self._finalizar_ciclo_emision(limpiar_todo=not conservar_factura)

        def _cerrar_sin_pdf() -> None:
            ventana.destroy()
            self._finalizar_ciclo_emision(limpiar_todo=not conservar_factura)

        ttk.Button(
            frame_pie, text="Imprimir PDF", command=_imprimir_y_finalizar
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(frame_pie, text="Cerrar", command=_cerrar_sin_pdf).grid(
            row=0, column=1
        )

    def _finalizar_ciclo_emision(self, limpiar_todo: bool = False) -> None:
        self.items_actuales = []
        if limpiar_todo:
            self.ultima_factura_emitida = None
            self.ultima_ruta_html