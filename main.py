"""
===============================================================================
PUNTO DE ENTRADA PRINCIPAL: SISTEMA FRANKIE (main.py)
===============================================================================
Garantiza las rutas del proyecto, verifica la conexión a la base de datos,
aplica los estilos globales y cede el control de navegación a ControladorSesion.
===============================================================================
"""

from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

DIR_ACTUAL = Path(__file__).resolve().parent
if str(DIR_ACTUAL) not in sys.path:
    sys.path.insert(0, str(DIR_ACTUAL))

from controladores.controlador_sesion import ControladorSesion
from infraestructura.conexion import ConexionDB
from vistas.estilos import aplicar_estilos_base


def _verificar_base_datos(root: tk.Tk) -> bool:
    """
    Verifica que la base de datos SQLite sea accesible y responda correctamente.
    Retorna True si está operativa, o False si ocurre un error.
    """
    try:
        with ConexionDB() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return True
    except Exception as exc:
        messagebox.showerror(
            "Error de Base de Datos",
            f"No se pudo inicializar o verificar la base de datos:\n{exc}",
            parent=root,
        )
        return False


def main() -> None:
    """Punto de entrada único de la aplicación."""
    root = tk.Tk()
    aplicar_estilos_base(root)

    if not _verificar_base_datos(root):
        root.destroy()
        return

    controlador = ControladorSesion(root)
    controlador.mostrar_login()

    root.mainloop()


if __name__ == "__main__":
    main()