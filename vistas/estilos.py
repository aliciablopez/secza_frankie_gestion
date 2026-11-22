"""
===============================================================================
MÓDULO DE ESTILOS Y ACCESIBILIDAD GLOBAL (vistas/estilos.py)
===============================================================================
Centraliza variables de color y tipografía junto con los estilos de ttk,
incluyendo carga de fuentes estáticas desde assets/fuentes/ y detección de familia.
===============================================================================
"""

import ctypes
from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

# =============================================================================
# 1. VARIABLES DE COLOR Y FUENTE (equivalentes a variables CSS)
# =============================================================================
COLOR_FONDO = "honeydew"         # Fondo general de ventana y marcos base
COLOR_TARJETA = "lavenderblush"  # Fondo de contenedores tipo tarjeta (Card.TFrame)
COLOR_PRIMARIO = "yellowgreen"   # Fondo base de botones y elementos principales
COLOR_ACCENTO = "lightgreen"     # Resaltado al pasar el cursor / activar (hover/active)
COLOR_TEXTO = "black"            # Texto principal de alto contraste
COLOR_TEXTO_MUTED = "#556B2F"    # Texto secundario / notas (darkolivegreen)
COLOR_FOCO = "azure"             # Fondo al enfocar campos de entrada (focus)
COLOR_BORDE = "darkolivegreen"   # Bordes de contenedores y controles

TAMANIO_BASE = 12
ALTO_FILA_TABLA = 34

FUENTE_PREFERIDA = "Atkinson Hyperlegible"
FUENTE_RESPALDO = "Segoe UI" if sys.platform.startswith("win") else "TkDefaultFont"

FUENTE_FAMILIA = FUENTE_PREFERIDA
FUENTE_BASE = (FUENTE_FAMILIA, TAMANIO_BASE, "normal")
FUENTE_BOTON = (FUENTE_FAMILIA, TAMANIO_BASE, "normal")
FUENTE_TITULO = (FUENTE_FAMILIA, TAMANIO_BASE, "bold")
FUENTE_ENCABEZADO = (FUENTE_FAMILIA, TAMANIO_BASE, "bold")

_FUENTES_CARGADAS = False


def _obtener_carpeta_fuentes() -> Path:
    """Devuelve la ruta absoluta hacia assets/fuentes/."""
    ruta_base = Path(__file__).resolve().parents[1]
    return ruta_base / "assets" / "fuentes"


def cargar_fuentes_locales() -> None:
    """
    Intenta registrar los archivos .ttf estáticos de assets/fuentes/
    para el proceso actual sin requerir instalación manual previa.
    """
    global _FUENTES_CARGADAS
    if _FUENTES_CARGADAS:
        return

    carpeta_fuentes = _obtener_carpeta_fuentes()
    if not carpeta_fuentes.exists() or not carpeta_fuentes.is_dir():
        _FUENTES_CARGADAS = True
        return

    archivos_ttf = sorted(carpeta_fuentes.glob("*.ttf"))
    if not archivos_ttf:
        _FUENTES_CARGADAS = True
        return

    if sys.platform.startswith("win"):
        # FR_PRIVATE = 0x10: disponible solo para este proceso mientras siga abierto
        fr_private = 0x10
        gdi32 = getattr(ctypes, "windll", None)
        if gdi32 is not None and hasattr(gdi32, "gdi32"):
            add_font = gdi32.gdi32.AddFontResourceExW
            for archivo in archivos_ttf:
                try:
                    add_font(str(archivo), fr_private, 0)
                except Exception:
                    continue

    _FUENTES_CARGADAS = True


def resolver_familia_fuente(root: tk.Misc) -> str:
    """
    Detecta si 'Atkinson Hyperlegible' (o una coincidencia cercana) está disponible
    en Tk; si no lo está, devuelve una familia de respaldo segura.
    """
    cargar_fuentes_locales()

    try:
        familias = list(tkfont.families(root))
    except Exception:
        return FUENTE_RESPALDO

    for nombre in familias:
        if nombre.lower() == FUENTE_PREFERIDA.lower():
            return nombre

    for nombre in familias:
        if "atkinson hyperlegible" in nombre.lower() and "next" not in nombre.lower():
            return nombre

    for nombre in familias:
        if "atkinson" in nombre.lower():
            return nombre

    return FUENTE_RESPALDO


def _actualizar_fuentes_globales(familia: str) -> None:
    """Actualiza las constantes de fuente con la familia resuelta."""
    global FUENTE_FAMILIA, FUENTE_BASE, FUENTE_BOTON, FUENTE_TITULO, FUENTE_ENCABEZADO
    FUENTE_FAMILIA = familia
    FUENTE_BASE = (FUENTE_FAMILIA, TAMANIO_BASE, "normal")
    FUENTE_BOTON = (FUENTE_FAMILIA, TAMANIO_BASE, "normal")
    FUENTE_TITULO = (FUENTE_FAMILIA, TAMANIO_BASE, "bold")
    FUENTE_ENCABEZADO = (FUENTE_FAMILIA, TAMANIO_BASE, "bold")


def _sincronizar_fuentes_tk(root: tk.Misc) -> None:
    """Asegura que las fuentes base de Tk no usen cursivas (slant='roman')."""
    for nombre_fuente in (
        "TkDefaultFont",
        "TkTextFont",
        "TkMenuFont",
        "TkHeadingFont",
    ):
        try:
            f = tkfont.nametofont(nombre_fuente, root=root)
            f.configure(
                family=FUENTE_FAMILIA,
                size=TAMANIO_BASE,
                weight="bold" if nombre_fuente == "TkHeadingFont" else "normal",
                slant="roman",
            )
        except Exception:
            continue


def aplicar_estilos_base(root: tk.Misc) -> None:
    """
    Aplica la hoja de estilos global de ttk sobre la ventana o contenedor raíz.
    """
    familia_activa = resolver_familia_fuente(root)
    _actualizar_fuentes_globales(familia_activa)
    _sincronizar_fuentes_tk(root)

    style = ttk.Style(root)
    style.theme_use("clam")

    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=COLOR_FONDO)

    # Estilo base heredado por los widgets ttk
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
        padding=6,
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
        padding=4,
    )
    style.configure(
        "TCheckbutton",
        background=COLOR_FONDO,
        foreground=COLOR_TEXTO,
        font=FUENTE_BASE,
    )

    # Botones (TButton): 12 pt sin negrita ni cursiva
    style.configure(
        "TButton",
        font=FUENTE_BOTON,
        padding=(12, 8),
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

    # Tablas (Treeview)
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
        padding=8,
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_ACCENTO)],
        foreground=[("selected", COLOR_TEXTO)],
    )
    root.option_add("*TCombobox*Listbox.font", FUENTE_BASE)