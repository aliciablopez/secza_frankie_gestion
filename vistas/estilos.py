"""
===============================================================================
MÓDULO DE ESTILOS Y ACCESIBILIDAD GLOBAL (vistas/estilos.py)
===============================================================================
Centraliza variables de color, tipografía, valores por defecto y estilos de ttk
utilizando fuentes estándar del sistema en estilo normal (sin cursivas).
===============================================================================
"""

from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Final, Literal, Optional

# =============================================================================
# 1. VARIABLES DE COLOR, VALORES POR DEFECTO Y TIPOGRAFÍA (Paleta honeydew)
# =============================================================================
COLOR_FONDO: Final[str] = "honeydew"         # Fondo general de ventana y marcos base
COLOR_TARJETA: Final[str] = "lavenderblush"  # Fondo de contenedores tipo tarjeta (Card.TFrame)
COLOR_PRIMARIO: Final[str] = "yellowgreen"   # Fondo base de botones y elementos principales
COLOR_ACCENTO: Final[str] = "lightgreen"     # Resaltado al pasar el cursor / activar (hover/active)
COLOR_TEXTO: Final[str] = "black"            # Texto principal de alto contraste
COLOR_TEXTO_MUTED: Final[str] = "#556B2F"    # Texto secundario / notas (darkolivegreen)
COLOR_FOCO: Final[str] = "azure"             # Fondo al enfocar campos de entrada (focus)
COLOR_BORDE: Final[str] = "darkolivegreen"   # Bordes de contenedores y controles

# Valores por defecto configurables desde estilos.py
IVA_DEFECTO_PORC: Final[float] = 21.0
IMPUESTO_PROVINCIAL_DEFECTO_PORC: Final[float] = 0.0
PRECIO_LISTA_DEFECTO: Final[float] = 0.0
CARPETA_COMPROBANTES_DEFECTO: Final[Path] = Path("comprobantes")

TAMANIO_BASE: Final[int] = 12
TAMANIO_SUBTOTAL: Final[int] = 12
TAMANIO_TOTAL: Final[int] = 15
ALTO_FILA_TABLA: Final[int] = 28

FUENTE_PREFERIDA: Final[str] = "Segoe UI" if sys.platform.startswith("win") else "Arial"
FUENTE_RESPALDO: Final[str] = "Arial" if sys.platform.startswith("win") else "TkDefaultFont"

FUENTE_FAMILIA: str = FUENTE_PREFERIDA
FUENTE_BASE: Optional[tkfont.Font] = None
FUENTE_BOTON: Optional[tkfont.Font] = None
FUENTE_TITULO: Optional[tkfont.Font] = None
FUENTE_ENCABEZADO: Optional[tkfont.Font] = None
FUENTE_SUBTOTAL: Optional[tkfont.Font] = None
FUENTE_TOTAL: Optional[tkfont.Font] = None


def resolver_familia_fuente(root: tk.Misc) -> str:
    """
    Devuelve una familia estándar limpia (Segoe UI / Arial) evitando fuentes
    externas que puedan mapearse a variantes cursivas en Windows.
    """
    try:
        familias = list(tkfont.families(root))
    except Exception:
        return FUENTE_RESPALDO

    for candidata in (FUENTE_PREFERIDA, "Segoe UI", "Arial", "Tahoma", "Liberation Sans"):
        for nombre in familias:
            if nombre.lower() == candidata.lower():
                return nombre

    return FUENTE_RESPALDO


def _crear_o_actualizar_fuente(
    actual: Optional[tkfont.Font],
    root: tk.Misc,
    familia: str,
    tamano: int,
    peso: Literal["normal", "bold"] = "normal",
) -> tkfont.Font:
    """Crea o actualiza un objeto tkfont.Font garantizando slant='roman'."""
    if actual is None:
        return tkfont.Font(
            root=root,
            family=familia,
            size=tamano,
            weight=peso,
            slant="roman",
        )
    try:
        actual.configure(
            family=familia,
            size=tamano,
            weight=peso,
            slant="roman",
        )
        return actual
    except tk.TclError:
        return tkfont.Font(
            root=root,
            family=familia,
            size=tamano,
            weight=peso,
            slant="roman",
        )


def _sincronizar_fuentes_tk(root: tk.Misc, familia: str) -> None:
    """Sincroniza fuentes base nombradas de Tk en normal y sin cursivas."""
    for nombre_fuente in (
        "TkDefaultFont",
        "TkTextFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkIconFont",
        "TkTooltipFont",
    ):
        try:
            f = tkfont.nametofont(nombre_fuente, root=root)
            f.configure(
                family=familia,
                size=TAMANIO_BASE,
                weight="normal",
                slant="roman",
            )
        except Exception:
            continue


def aplicar_estilos_base(root: tk.Misc) -> None:
    """
    Aplica la hoja de estilos global de ttk sobre la ventana o contenedor raíz.
    """
    global FUENTE_FAMILIA
    global FUENTE_BASE, FUENTE_BOTON, FUENTE_TITULO, FUENTE_ENCABEZADO
    global FUENTE_SUBTOTAL, FUENTE_TOTAL

    familia_activa = resolver_familia_fuente(root)
    FUENTE_FAMILIA = familia_activa

    FUENTE_BASE = _crear_o_actualizar_fuente(
        FUENTE_BASE, root, familia_activa, TAMANIO_BASE, "normal"
    )
    FUENTE_BOTON = _crear_o_actualizar_fuente(
        FUENTE_BOTON, root, familia_activa, TAMANIO_BASE, "normal"
    )
    FUENTE_TITULO = _crear_o_actualizar_fuente(
        FUENTE_TITULO, root, familia_activa, TAMANIO_BASE, "normal"
    )
    FUENTE_ENCABEZADO = _crear_o_actualizar_fuente(
        FUENTE_ENCABEZADO, root, familia_activa, TAMANIO_BASE, "normal"
    )
    FUENTE_SUBTOTAL = _crear_o_actualizar_fuente(
        FUENTE_SUBTOTAL, root, familia_activa, TAMANIO_SUBTOTAL, "bold"
    )
    FUENTE_TOTAL = _crear_o_actualizar_fuente(
        FUENTE_TOTAL, root, familia_activa, TAMANIO_TOTAL, "bold"
    )

    _sincronizar_fuentes_tk(root, familia_activa)

    style = ttk.Style(root)
    style.theme_use("clam")

    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=COLOR_FONDO)

    style.configure(
        ".",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
    )

    # Contenedores y marcos
    style.configure("TFrame", background=COLOR_FONDO)
    style.configure("Card.TFrame", background=COLOR_TARJETA, relief="flat")
    style.configure(
        "TLabelframe",
        background=COLOR_FONDO,
        borderwidth=1,
        relief="solid",
        bordercolor=COLOR_BORDE,
    )
    style.configure(
        "TLabelframe.Label",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_TITULO,
    )

    # Etiquetas de texto
    style.configure(
        "TLabel",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
    )
    style.configure(
        "Subtitulo.TLabel",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_TITULO,
    )
    style.configure(
        "Subtotal.TLabel",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_SUBTOTAL,
    )
    style.configure(
        "Total.TLabel",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_TOTAL,
    )
    style.configure(
        "Muted.TLabel",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO_MUTED,
        font=FUENTE_BASE,
    )

    # Campos de entrada, combos y checks
    style.configure(
        "TEntry",
        fieldbackground="white",
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
        padding=4,
    )
    style.map(
        "TEntry",
        fieldbackground=[
            ("focus", COLOR_FOCO),
            ("disabled", COLOR_FONDO),
        ],
        foreground=[
            ("disabled", COLOR_TEXTO_MUTED),
        ],
        bordercolor=[
            ("focus", COLOR_BORDE),
        ],
    )
    style.configure(
        "TCombobox",
        fieldbackground="white",
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
        padding=3,
    )
    style.configure(
        "TCheckbutton",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
    )

    # Botones (TButton): 12pt normal, sin cursiva
    style.configure(
        "TButton",
        font=FUENTE_BOTON,
        padding=(9, 5),
        background=COLOR_PRIMARIO,
        foreground=COLOR_TEXTO,
        borderwidth=1,
        bordercolor=COLOR_BORDE,
    )
    style.map(
        "TButton",
        background=[
            ("active", COLOR_ACCENTO),
            ("disabled", "gainsboro"),
        ],
        foreground=[
            ("active", COLOR_TEXTO),
            ("disabled", COLOR_TEXTO_MUTED),
        ],
        bordercolor=[
            ("focus", COLOR_TEXTO),
            ("active", COLOR_BORDE),
            ("disabled", COLOR_TEXTO_MUTED),
        ],
    )

    # Tablas (Treeview): encabezados y filas en 12pt normal, sin cursiva
    style.configure(
        "Treeview",
        background="white",
        fieldbackground="white",
        foreground=COLOR_TEXTO,
        rowheight=ALTO_FILA_TABLA,
        font=FUENTE_BASE,
    )
    style.configure(
        "Treeview.Heading",
        font=FUENTE_ENCABEZADO,
        background=COLOR_PRIMARIO,
        foreground=COLOR_TEXTO,
        padding=5,
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_ACCENTO)],
        foreground=[("selected", COLOR_TEXTO)],
    )