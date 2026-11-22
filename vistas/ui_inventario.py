"""
===============================================================================
MÓDULO DE INTERFAZ DE USUARIO: CONTROL DE INVENTARIO Y STOCK (vistas/ui_inventario.py)
===============================================================================
Permite administrar el inventario de productos, actualizar existencias/datos,
ajustar stock y visualizar alertas de reposición.
- Patrón visual apilado: formulario arriba, tabla abajo.
- Botonera estándar: Guardar, Actualizar, Limpiar, Deshabilitar.
- Tipografía 12 pt sin itálicas (slant='roman').
===============================================================================
"""

from typing import Any, cast, Dict, List, Literal, Optional, Tuple
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from dominio.entidades_stock import Producto, calcular_precio_venta_sugerido
from infraestructura.repo_stock import RepositorioStock

try:
    from infraestructura.repo_proveedores import RepositorioProveedores
except ImportError:
    RepositorioProveedores = None

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


def _a_entero_opcional(valor: Any) -> Optional[int]:
    """Convierte a int de forma segura, o devuelve None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return None
        try:
            return int(float(texto))
        except ValueError:
            return None
    return None


def _a_entero_o_cero(valor: Any) -> int:
    """Convierte a int de forma segura, o devuelve 0."""
    convertido = _a_entero_opcional(valor)
    return convertido if convertido is not None else 0


def _a_flotante_o_cero(valor: Any) -> float:
    """Convierte a float de forma segura, o devuelve 0.0."""
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


class InterfazInventario(ttk.Frame):
    """Vista modular para gestión de inventario y stock con patrón apilado."""

    def __init__(self, parent: tk.Misc, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self.winfo_toplevel())
            except Exception:
                pass

        self.pack(fill="both", expand=True, padx=10, pady=10)
        self.repo = RepositorioStock()

        self.producto_seleccionado_id: Optional[int] = None
        self.producto_activo: bool = True
        self.proveedores_map: Dict[str, int] = {}
        self.proveedores_por_id: Dict[int, str] = {}
        self.productos_cache: Dict[str, Producto] = {}

        self.var_proveedor = tk.StringVar()
        self.var_codigo = tk.StringVar()
        self.var_descripcion = tk.StringVar()
        self.var_categoria = tk.StringVar()
        self.var_stock = tk.StringVar(value="75")
        self.var_minimo = tk.StringVar(value="75")
        self.var_costo = tk.StringVar(value="0.00")
        self.var_precio = tk.StringVar(value="0.00")
        self.var_ubicacion = tk.StringVar()

        self.var_busqueda = tk.StringVar()
        self.var_solo_alertas = tk.BooleanVar(value=False)

        self._construir_interfaz()
        self._configurar_fuentes()
        self.cargar_proveedores()
        self.cargar_datos()

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
            self, text=" Datos del Producto y Stock ", padding=15
        )
        frame_form.pack(fill="x", padx=5, pady=5)
        frame_form.columnconfigure(1, weight=1)
        frame_form.columnconfigure(3, weight=1)

        # Fila 0: Código | Descripción
        ttk.Label(frame_form, text="Código *:").grid(
            row=0, column=0, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_codigo).grid(
            row=0, column=1, sticky="ew", padx=6, pady=5
        )

        ttk.Label(frame_form, text="Descripción *:").grid(
            row=0, column=2, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_descripcion).grid(
            row=0, column=3, sticky="ew", padx=6, pady=5
        )

        # Fila 1: Proveedor | Categoría
        ttk.Label(frame_form, text="Proveedor *:").grid(
            row=1, column=0, sticky="w", padx=6, pady=5
        )
        self.combo_proveedor = ttk.Combobox(
            frame_form,
            textvariable=self.var_proveedor,
            state="readonly",
        )
        self.combo_proveedor.grid(row=1, column=1, sticky="ew", padx=6, pady=5)

        ttk.Label(frame_form, text="Categoría:").grid(
            row=1, column=2, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_categoria).grid(
            row=1, column=3, sticky="ew", padx=6, pady=5
        )

        # Fila 2: Stock Actual | Stock Mínimo
        ttk.Label(frame_form, text="Stock Actual:").grid(
            row=2, column=0, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_stock).grid(
            row=2, column=1, sticky="ew", padx=6, pady=5
        )

        ttk.Label(frame_form, text="Stock Mínimo:").grid(
            row=2, column=2, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_minimo).grid(
            row=2, column=3, sticky="ew", padx=6, pady=5
        )

        # Fila 3: Precio Costo | Precio Venta
        ttk.Label(frame_form, text="Precio Costo ($):").grid(
            row=3, column=0, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_costo).grid(
            row=3, column=1, sticky="ew", padx=6, pady=5
        )

        ttk.Label(frame_form, text="Precio Venta ($):").grid(
            row=3, column=2, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_precio).grid(
            row=3, column=3, sticky="ew", padx=6, pady=5
        )

        # Fila 4: Ubicación | Botonera
        ttk.Label(frame_form, text="Ubicación:").grid(
            row=4, column=0, sticky="w", padx=6, pady=5
        )
        ttk.Entry(frame_form, textvariable=self.var_ubicacion).grid(
            row=4, column=1, sticky="ew", padx=6, pady=5
        )

        frame_botones = ttk.Frame(frame_form)
        frame_botones.grid(row=4, column=2, columnspan=2, sticky="e", padx=6, pady=5)

        self.btn_guardar = ttk.Button(
            frame_botones,
            text="Guardar",
            command=self.guardar_producto,
        )
        self.btn_guardar.pack(side="left", padx=4)

        self.btn_actualizar = ttk.Button(
            frame_botones,
            text="Actualizar",
            command=self.actualizar_producto,
            state="disabled",
        )
        self.btn_actualizar.pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="Limpiar",
            command=self.limpiar_formulario,
        ).pack(side="left", padx=4)

        self.btn_toggle_estado = ttk.Button(
            frame_botones,
            text="Deshabilitar",
            command=self.toggle_estado_producto,
            state="disabled",
        )
        self.btn_toggle_estado.pack(side="left", padx=4)

        # 2. Tabla inferior apilada: Catálogo de Productos
        frame_tabla = ttk.LabelFrame(
            self,
            text=" Catálogo de Productos y Stock (Seleccione una fila para actualizar) ",
            padding=15,
        )
        frame_tabla.pack(fill="both", expand=True, padx=5, pady=5)

        frame_filtro = ttk.Frame(frame_tabla)
        frame_filtro.pack(fill="x", pady=(0, 8))

        ttk.Label(frame_filtro, text="Buscar:").pack(side="left", padx=(0, 6))
        entry_buscar = ttk.Entry(frame_filtro, textvariable=self.var_busqueda)
        entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry_buscar.bind("<KeyRelease>", lambda _e: self.cargar_datos())

        ttk.Checkbutton(
            frame_filtro,
            text="Solo Alertas de Stock Mínimo",
            variable=self.var_solo_alertas,
            command=self.cargar_datos,
        ).pack(side="right")

        frame_grilla = ttk.Frame(frame_tabla)
        frame_grilla.pack(fill="both", expand=True)
        frame_grilla.rowconfigure(0, weight=1)
        frame_grilla.rowconfigure(1, weight=0)
        frame_grilla.columnconfigure(0, weight=1)
        frame_grilla.columnconfigure(1, weight=0)

        columnas = (
            "id",
            "codigo",
            "descripcion",
            "categoria",
            "stock",
            "minimo",
            "precio",
            "ubicacion",
            "proveedor",
        )
        self.tabla_prod = ttk.Treeview(
            frame_grilla,
            columns=columnas,
            show="headings",
            selectmode="browse",
            height=7,
        )

        encabezados: Dict[str, Tuple[str, int, AnchorTk]] = {
            "id": ("ID", 55, "center"),
            "codigo": ("Código", 105, "center"),
            "descripcion": ("Descripción", 240, "w"),
            "categoria": ("Categoría", 120, "w"),
            "stock": ("Stock Actual", 95, "center"),
            "minimo": ("Stock Mín.", 95, "center"),
            "precio": ("Precio Venta", 120, "e"),
            "ubicacion": ("Ubicación", 110, "center"),
            "proveedor": ("Proveedor", 180, "w"),
        }
        for col, (titulo, ancho, ancla) in encabezados.items():
            self.tabla_prod.heading(col, text=titulo)
            self.tabla_prod.column(col, width=ancho, anchor=cast(AnchorTk, ancla))

        self.tabla_prod.tag_configure("bajo_stock", background="#fdecea")

        scroll_y = ttk.Scrollbar(
            frame_grilla, orient="vertical", command=self.tabla_prod.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_grilla, orient="horizontal", command=self.tabla_prod.xview
        )
        self.tabla_prod.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tabla_prod.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self.tabla_prod.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def cargar_proveedores(self) -> None:
        """Carga proveedores activos desde el repositorio correspondiente."""
        self.proveedores_map.clear()
        self.proveedores_por_id.clear()
        try:
            if RepositorioProveedores is not None and hasattr(
                RepositorioProveedores, "listar_proveedores"
            ):
                raw_provs = RepositorioProveedores.listar_proveedores()
            else:
                raw_provs = self.repo.listar_proveedores_activos()

            etiquetas: List[str] = []
            for prov in raw_provs:
                if isinstance(prov, dict):
                    id_p = _a_entero_o_cero(
                        prov.get("id_proveedor") or prov.get("id")
                    )
                    nombre_p = str(
                        prov.get("razon_social")
                        or prov.get("nombre_comercial")
                        or f"Proveedor #{id_p}"
                    ).strip()
                else:
                    id_p = _a_entero_o_cero(
                        getattr(prov, "id_proveedor", None) or getattr(prov, "id", 0)
                    )
                    nombre_p = str(
                        getattr(prov, "razon_social", None)
                        or getattr(prov, "nombre_comercial", None)
                        or f"Proveedor #{id_p}"
                    ).strip()

                if id_p <= 0:
                    continue
                etiqueta = f"{id_p} - {nombre_p}"
                self.proveedores_map[etiqueta] = id_p
                self.proveedores_por_id[id_p] = nombre_p
                etiquetas.append(etiqueta)

            self.combo_proveedor["values"] = etiquetas
            if etiquetas and not self.var_proveedor.get():
                self.combo_proveedor.current(0)
        except Exception as exc:
            messagebox.showerror(
                "Error al cargar proveedores", str(exc), parent=self
            )

    def cargar_datos(self) -> None:
        """Carga los productos del catálogo aplicando filtro de búsqueda y alerta."""
        for fila in self.tabla_prod.get_children():
            self.tabla_prod.delete(fila)
        self.productos_cache.clear()

        try:
            productos = self.repo.listar_productos(
                criterio_busqueda=self.var_busqueda.get().strip(),
                solo_stock_bajo=bool(self.var_solo_alertas.get()),
                incluir_inactivos=False,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al cargar inventario", str(exc), parent=self
            )
            return

        for prod in productos:
            if not bool(getattr(prod, "activo", True)):
                continue

            id_prod = _a_entero_o_cero(getattr(prod, "id_producto", None))
            codigo = str(getattr(prod, "codigo", "") or "").strip()
            desc = str(getattr(prod, "descripcion", "") or "").strip()
            cat = str(getattr(prod, "categoria", "") or "").strip()
            id_prov = _a_entero_o_cero(getattr(prod, "id_proveedor", 0))
            prov_nom = str(
                getattr(prod, "proveedor_nombre", "")
                or self.proveedores_por_id.get(id_prov, "")
                or "N/A"
            ).strip()

            stock_act = _a_entero_o_cero(getattr(prod, "stock_actual", 0))
            stock_min = _a_entero_o_cero(getattr(prod, "stock_minimo", 75))
            precio_vta = _a_flotante_o_cero(getattr(prod, "precio_venta", 0.0))
            ubic = str(getattr(prod, "ubicacion", "") or "").strip()

            tags = ("bajo_stock",) if stock_act <= stock_min else ()
            iid = self.tabla_prod.insert(
                "",
                "end",
                values=(
                    id_prod or "-",
                    codigo or "-",
                    desc or "-",
                    cat or "-",
                    stock_act,
                    stock_min,
                    f"${precio_vta:,.2f}",
                    ubic or "-",
                    prov_nom,
                ),
                tags=tags,
            )
            self.productos_cache[iid] = prod

    def _construir_producto_desde_formulario(
        self, id_producto: Optional[int], activo: bool
    ) -> Optional[Producto]:
        """Valida los campos y construye una instancia de Producto."""
        codigo = self.var_codigo.get().strip()
        descripcion = self.var_descripcion.get().strip()
        if not codigo or not descripcion:
            messagebox.showwarning(
                "Datos incompletos",
                "Completá al menos Código y Descripción del producto.",
                parent=self,
            )
            return None

        sel_prov = self.var_proveedor.get().strip()
        id_prov = self.proveedores_map.get(sel_prov)
        if not id_prov and self.proveedores_map:
            id_prov = next(iter(self.proveedores_map.values()))
        if not id_prov:
            messagebox.showwarning(
                "Proveedor requerido",
                "Seleccioná o registrá un proveedor antes de guardar productos.",
                parent=self,
            )
            return None

        stock_act = _a_entero_o_cero(self.var_stock.get())
        stock_min = _a_entero_o_cero(self.var_minimo.get()) or 75
        precio_costo = _a_flotante_o_cero(self.var_costo.get())
        precio_venta = _a_flotante_o_cero(self.var_precio.get())
        if precio_venta <= 0.0 and precio_costo > 0.0:
            precio_venta = calcular_precio_venta_sugerido(precio_costo)

        return Producto(
            id_producto=id_producto,
            codigo=codigo,
            descripcion=descripcion,
            categoria=self.var_categoria.get().strip(),
            id_proveedor=id_prov,
            stock_actual=stock_act,
            stock_minimo=stock_min,
            precio_costo=precio_costo,
            precio_venta=precio_venta,
            ubicacion=self.var_ubicacion.get().strip(),
            activo=activo,
        )

    def guardar_producto(self) -> None:
        """Registra un nuevo producto en el inventario."""
        prod = self._construir_producto_desde_formulario(
            id_producto=None, activo=True
        )
        if prod is None:
            return

        try:
            self.repo.guardar_producto(prod)
            self.limpiar_formulario()
            self.cargar_datos()
            messagebox.showinfo(
                "Guardado",
                "Producto registrado correctamente.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al guardar producto", str(exc), parent=self
            )

    def actualizar_producto(self) -> None:
        """Actualiza el producto seleccionado en la tabla conservando su ID."""
        if self.producto_seleccionado_id is None:
            messagebox.showwarning(
                "Sin selección",
                "Seleccioná un producto de la tabla para actualizar.",
                parent=self,
            )
            return

        prod = self._construir_producto_desde_formulario(
            id_producto=self.producto_seleccionado_id,
            activo=self.producto_activo,
        )
        if prod is None:
            return

        try:
            self.repo.guardar_producto(prod)
            self.limpiar_formulario()
            self.cargar_datos()
            messagebox.showinfo(
                "Actualizado",
                "Producto y stock actualizados correctamente.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Error al actualizar producto", str(exc), parent=self
            )

    def toggle_estado_producto(self) -> None:
        """Deshabilita o reactiva el producto seleccionado."""
        if self.producto_seleccionado_id is None:
            return

        nuevo_estado = not self.producto_activo
        accion = "reactivar" if nuevo_estado else "deshabilitar"
        if not messagebox.askyesno(
            "Confirmar cambio de estado",
            f"¿Deseás {accion} el producto '{self.var_descripcion.get().strip()}'?",
            parent=self,
        ):
            return

        try:
            self.repo.cambiar_estado_producto(
                self.producto_seleccionado_id, nuevo_estado
            )
            self.limpiar_formulario()
            self.cargar_datos()
        except Exception as exc:
            messagebox.showerror(
                "Error al cambiar estado", str(exc), parent=self
            )

    def limpiar_formulario(self) -> None:
        """Limpia los campos y restablece el estado de selección."""
        self.producto_seleccionado_id = None
        self.producto_activo = True
        self.var_codigo.set("")
        self.var_descripcion.set("")
        self.var_categoria.set("")
        self.var_stock.set("75")
        self.var_minimo.set("75")
        self.var_costo.set("0.00")
        self.var_precio.set("0.00")
        self.var_ubicacion.set("")
        if self.combo_proveedor["values"]:
            self.combo_proveedor.current(0)
        self.btn_guardar.config(state="normal")
        self.btn_actualizar.config(state="disabled")
        self.btn_toggle_estado.config(text="Deshabilitar", state="disabled")
        if self.tabla_prod.selection():
            self.tabla_prod.selection_remove(self.tabla_prod.selection())

    def _al_seleccionar_fila(self, _event: Any = None) -> None:
        """Carga los datos de la fila seleccionada en el formulario para actualizar."""
        seleccion = self.tabla_prod.selection()
        if not seleccion:
            return
        prod = self.productos_cache.get(seleccion[0])
        if prod is None:
            return

        self.producto_seleccionado_id = _a_entero_opcional(
            getattr(prod, "id_producto", None)
        )
        self.producto_activo = bool(getattr(prod, "activo", True))

        self.var_codigo.set(str(getattr(prod, "codigo", "") or ""))
        self.var_descripcion.set(str(getattr(prod, "descripcion", "") or ""))
        self.var_categoria.set(str(getattr(prod, "categoria", "") or ""))
        self.var_stock.set(str(_a_entero_o_cero(getattr(prod, "stock_actual", 0))))
        self.var_minimo.set(str(_a_entero_o_cero(getattr(prod, "stock_minimo", 75))))
        self.var_costo.set(
            f"{_a_flotante_o_cero(getattr(prod, 'precio_costo', 0.0)):.2f}"
        )
        self.var_precio.set(
            f"{_a_flotante_o_cero(getattr(prod, 'precio_venta', 0.0)):.2f}"
        )
        self.var_ubicacion.set(str(getattr(prod, "ubicacion", "") or ""))

        id_prov = _a_entero_o_cero(getattr(prod, "id_proveedor", 0))
        for etiqueta, p_id in self.proveedores_map.items():
            if p_id == id_prov:
                self.var_proveedor.set(etiqueta)
                break

        self.btn_actualizar.config(state="normal")
        self.btn_toggle_estado.config(
            state="normal",
            text="Reactivar" if not self.producto_activo else "Deshabilitar",
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Inventario y Gestión de Stock")
    root.geometry("1180x740")
    InterfazInventario(root)
    root.mainloop()