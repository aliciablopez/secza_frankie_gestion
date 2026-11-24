"""
===============================================================================
MÓDULO DE VISTAS: FACTURACIÓN Y VENTAS (vistas/ui_facturacion.py)
===============================================================================
Interfaz gráfica para la emisión de comprobantes de venta siguiendo el patrón
visual apilado del sistema:
- Medios de pago: Efectivo, Transferencia, Tarjeta de crédito.
- CRUD de ítems con "Agregar Ítem", "Modificar Producto", "Actualizar" y "Quitar".
- Tabla de detalle centrada exclusivamente en productos.
- Bonificaciones, recargos e impuestos concentrados en Totales y Emisión con
  recálculo automático en tiempo real, control RBAC y botones visibles.
- Tipografía 12 pt sin itálicas (slant='roman') y estilos globales.
===============================================================================
"""

from typing import Any, cast, Dict, List, Literal, Optional, Set, Tuple
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

ROLES_EMISION_FACTURA: Set[str] = {"admin", "gerente", "vendedor"}


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
        self.puede_emitir_factura: bool = bool(roles_activos & ROLES_EMISION_FACTURA)

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
        self._ultimo_calculo_repo: Optional[Dict[str, Any]] = None
        self._actualizando_campos: bool = False

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
        self._aplicar_permisos_ui()
        self.cargar_datos_iniciales()
        self._recalcular_totales(desde_medio_pago=True)

    def _aplicar_permisos_ui(self) -> None:
        """Habilita o bloquea la emisión de facturas según el rol del usuario."""
        estado_emision = "normal" if self.puede_emitir_factura else "disabled"
        self.btn_emitir.config(state=estado_emision)

    def _conectar_recalculo_automatico(self) -> None:
        """Recalcula automáticamente cada vez que cambian medio de pago o porcentajes."""
        self.var_medio_pago.trace_add(
            "write", lambda *_args: self._recalcular_totales(desde_medio_pago=True)
        )
        for var in (
            self.var_bonificacion_pct,
            self.var_recargo_pct,
            self.var_impuesto_pct,
        ):
            var.trace_add(
                "write", lambda *_args: self._recalcular_totales(desde_medio_pago=False)
            )

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
        frame_form = ttk.LabelFrame(
            self, text=" Datos del Comprobante y Productos ", padding=10
        )
        frame_form.pack(fill="x", padx=4, pady=(0, 4))
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

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

        self.btn_actualizar_item = ttk.Button(
            frame_botones_item,
            text="Actualizar",
            command=self.actualizar_producto_seleccionado,
        )
        self.btn_actualizar_item.pack(side="left", padx=5)

        ttk.Button(
            frame_botones_item,
            text="Quitar",
            command=self.quitar_producto_seleccionado,
        ).pack(side="left", padx=5)

        frame_tabla = ttk.LabelFrame(
            self,
            text=" Detalle de Productos (Seleccione una fila para modificar, actualizar o quitar) ",
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

        frame_totales = ttk.LabelFrame(
            self, text=" Totales y Emisión ", padding=10
        )
        frame_totales.pack(fill="x", padx=4, pady=(0, 2))
        frame_totales.columnconfigure(1, weight=1)
        frame_totales.columnconfigure(3, weight=1)

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

        ttk.Label(
            frame_totales, text="TOTAL A PAGAR:", style="Subtitulo.TLabel"
        ).grid(row=2, column=0, sticky="w", padx=6, pady=(6, 2))
        ttk.Label(
            frame_totales, textvariable=self.var_total_final, style="Subtitulo.TLabel"
        ).grid(row=2, column=1, sticky="w", padx=6, pady=(6, 2))

        frame_emision = ttk.Frame(frame_totales)
        frame_emision.grid(row=2, column=2, columnspan=2, sticky="e", pady=(6, 2))

        self.btn_limpiar = ttk.Button(
            frame_emision,
            text="Limpiar",
            command=self.limpiar_comprobante,
        )
        self.btn_limpiar.pack(side="left", padx=4)

        self.btn_emitir = ttk.Button(
            frame_emision,
            text="Emitir Factura",
            command=self.emitir_factura,
        )
        self.btn_emitir.pack(side="left", padx=4)

        self.btn_imprimir = ttk.Button(
            frame_emision,
            text="Imprimir Factura",
            command=self.imprimir_factura,
        )
        self.btn_imprimir.pack(side="left", padx=4)

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
                nombre_fmt = (
                    f"{apellidos}, {nombres}".strip(", ") or f"Cliente #{id_cli}"
                )
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

        self._recargar_productos()

    def _recargar_productos(self) -> None:
        """Recarga el listado de productos y sus stocks actuales."""
        try:
            idx_previo = self.combo_productos.current()
            self.productos_disponibles = list(
                RepositorioVentas.listar_productos_venta()
            )
            etiquetas_prod: List[str] = []
            for prod in self.productos_disponibles:
                id_p = _a_entero_o_cero(prod.get("id"))
                cod_p = str(prod.get("codigo") or "").strip()
                desc_p = str(prod.get("descripcion") or f"Producto #{id_p}").strip()
                precio_p = _a_flotante_o_cero(prod.get("precio_venta"))
                etiquetas_prod.append(f"[{cod_p or id_p}] {desc_p} (${precio_p:,.2f})")
            self.combo_productos["values"] = etiquetas_prod
            if etiquetas_prod:
                pos = idx_previo if 0 <= idx_previo < len(etiquetas_prod) else 0
                self.combo_productos.current(pos)
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
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())
        self._refrescar_tabla_y_totales()

    def actualizar_producto_seleccionado(self) -> None:
        """Aplica los cambios del formulario al registro seleccionado de la tabla."""
        self.modificar_producto_seleccionado()

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

    def _construir_items_crudos(self) -> List[Dict[str, Any]]:
        return [
            {
                "id_producto": _a_entero_o_cero(it["id_producto"]),
                "codigo": str(it["codigo"]),
                "descripcion": str(it["descripcion"]),
                "cantidad": _a_entero_o_cero(it["cantidad"]),
                "precio_lista": _a_flotante_o_cero(it["precio_unitario"]),
                "descuento_pct": _a_flotante_o_cero(it["descuento_pct"]),
            }
            for it in self.items_factura
        ]

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

        self._recalcular_totales(desde_medio_pago=False)

    def _recalcular_totales(self, desde_medio_pago: bool = False) -> None:
        """
        Alinea la previsualización con RepositorioVentas.calcular_previsualizacion_factura
        y mantiene sincronizados los porcentajes y montos en pantalla.
        """
        if self._actualizando_campos:
            return

        medio_pago = self.var_medio_pago.get().strip() or MEDIOS_PAGO[0]
        if not self.items_factura:
            self._ultimo_calculo_repo = None
            self.var_subtotal_prod.set("$0.00")
            self.var_bonificacion_monto.set("-$0.00")
            self.var_recargo_monto.set("+$0.00")
            self.var_impuestos_monto.set("$0.00")
            self.var_total_final.set("$0.00")
            return

        try:
            calculo = RepositorioVentas.calcular_previsualizacion_factura(
                self._construir_items_crudos(),
                medio_pago,
            )
            self._ultimo_calculo_repo = calculo
            subtotal_prod = _a_flotante_o_cero(calculo.get("subtotal_items"))
            ajuste_cond = _a_flotante_o_cero(calculo.get("ajuste_condicion_monto"))
            imp_prov = _a_flotante_o_cero(calculo.get("impuesto_provincial_total"))
            iva_tot = _a_flotante_o_cero(calculo.get("iva_total"))
            total_repo = _a_flotante_o_cero(calculo.get("total"))

            if desde_medio_pago and subtotal_prod > 0:
                bonif_pct = round((max(0.0, ajuste_cond) / subtotal_prod) * 100.0, 2)
                recargo_pct = round(
                    (abs(min(0.0, ajuste_cond)) / subtotal_prod) * 100.0, 2
                )
                imp_pct = round(((imp_prov + iva_tot) / subtotal_prod) * 100.0, 2)
                self._actualizando_campos = True
                try:
                    self.var_bonificacion_pct.set(f"{bonif_pct:.2f}")
                    self.var_recargo_pct.set(f"{recargo_pct:.2f}")
                    self.var_impuesto_pct.set(f"{imp_pct:.2f}")
                finally:
                    self._actualizando_campos = False

            bonif_pct_ui = _a_flotante_o_cero(self.var_bonificacion_pct.get())
            recargo_pct_ui = _a_flotante_o_cero(self.var_recargo_pct.get())
            imp_pct_ui = _a_flotante_o_cero(self.var_impuesto_pct.get())

            bonif_monto = round(subtotal_prod * (bonif_pct_ui / 100.0), 2)
            recargo_monto = round(subtotal_prod * (recargo_pct_ui / 100.0), 2)
            base_imponible = max(0.0, subtotal_prod - bonif_monto + recargo_monto)
            impuestos_tot = round(base_imponible * (imp_pct_ui / 100.0), 2)

            if desde_medio_pago and total_repo > 0:
                bonif_monto = round(max(0.0, ajuste_cond), 2)
                recargo_monto = round(abs(min(0.0, ajuste_cond)), 2)
                impuestos_tot = round(imp_prov + iva_tot, 2)
                total_final = round(total_repo, 2)
            else:
                total_final = round(base_imponible + impuestos_tot, 2)

            self.var_subtotal_prod.set(f"${subtotal_prod:,.2f}")
            self.var_bonificacion_monto.set(f"-${bonif_monto:,.2f}")
            self.var_recargo_monto.set(f"+${recargo_monto:,.2f}")
            self.var_impuestos_monto.set(f"${impuestos_tot:,.2f}")
            self.var_total_final.set(f"${total_final:,.2f}")
        except Exception:
            self._ultimo_calculo_repo = None

    def _construir_texto_comprobante(self, nro_comprobante: str = "BORRADOR") -> str:
        """Genera un resumen legible del comprobante para vista previa / impresión."""
        lineas = [
            "FRANKIE GESTOR COMERCIAL - COMPROBANTE DE VENTA",
            f"Comprobante: {nro_comprobante}",
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
                f"Bonificación: {self.var_bonificacion_monto.get()}",
                f"Recargo: {self.var_recargo_monto.get()}",
                f"Impuestos: {self.var_impuestos_monto.get()}",
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

    def limpiar_comprobante(self) -> None:
        """Limpia el detalle de productos, campos de ítem y reinicia totales."""
        self.items_factura.clear()
        self.indice_item_edicion = None
        self._ultimo_calculo_repo = None
        self.var_cantidad.set("1")
        self.var_descuento_item.set("0.0")
        self._actualizando_campos = True
        try:
            self.var_bonificacion_pct.set("0.0")
            self.var_recargo_pct.set("0.0")
            self.var_impuesto_pct.set("21.0")
        finally:
            self._actualizando_campos = False
        self._refrescar_tabla_y_totales()

    def emitir_factura(self) -> None:
        """Valida selección y emite la factura a través de RepositorioVentas."""
        if not self.puede_emitir_factura:
            messagebox.showwarning(
                "Acceso restringido",
                "Tu rol actual no tiene permisos para emitir facturas.",
                parent=self,
            )
            return

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
                "Vendedor requerido", "Seleccioná un vendedor.", parent=self
            )
            return

        id_cliente = _a_entero_o_cero(self.clientes_disponibles[idx_cli].get("id"))
        vend_sel = self.vendedores_disponibles[idx_vend]
        id_vendedor = _a_entero_o_cero(
            vend_sel.get("id_empleado") or vend_sel.get("id")
        )
        medio_pago = self.var_medio_pago.get().strip() or MEDIOS_PAGO[0]
        items_crudos = self._construir_items_crudos()

        if not messagebox.askyesno(
            "Confirmar Emisión",
            f"¿Confirmás la emisión de la factura por {self.var_total_final.get()}?",
            parent=self,
        ):
            return

        try:
            resultado = RepositorioVentas.emitir_factura(
                id_cliente=id_cliente,
                id_vendedor=id_vendedor,
                condicion_venta=medio_pago,
                items_crudos=items_crudos,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al emitir factura",
                str(exc),
                parent=self,
            )
            return

        id_fact = getattr(resultado, "id_factura", None)
        nro_comp = f"FAC-{id_fact}" if id_fact is not None else "EMITIDA"

        self.ultimo_resumen_impresion = self._construir_texto_comprobante(
            nro_comprobante=nro_comp
        )
        self.limpiar_comprobante()
        self._recargar_productos()

        messagebox.showinfo(
            "Factura Emitida",
            f"Comprobante registrado correctamente ({nro_comp}).",
            parent=self,
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Facturación y Ventas")
    root.geometry("1150x740")
    InterfazFacturacion(root)
    root.mainloop()