from contextlib import closing
from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from infraestructura.conexion import ConexionDB


logger = logging.getLogger(__name__)


class OrquestadorCore:
    """
    Controlador del Módulo Core.
    Aplica las reglas de negocio y orquesta las acciones entre la Interfaz y la Infraestructura.
    """

    def ejecutar_backup(self) -> str:
        """
        Realiza una copia de seguridad en caliente (Hot Backup) de la base de datos.
        Devuelve un mensaje de éxito o de error para que la Vista lo muestre.
        """
        # 1. Calculamos las rutas de forma segura usando pathlib.
        # Si está en secza_frankie/controladores/orquestador_core.py, parents[1] es la raíz del proyecto.
        ruta_base = Path(__file__).resolve().parents[1]
        ruta_db_origen = ruta_base / "db" / "frankie_gestor.db"
        carpeta_backups = ruta_base / "db" / "backups"

        if not ruta_db_origen.exists():
            return f"Error crítico al generar backup: no se encontró la base de datos en {ruta_db_origen}"

        carpeta_backups.mkdir(parents=True, exist_ok=True)

        # 2. Generamos un nombre único con fecha, hora y microsegundos para evitar colisiones.
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        nombre_archivo = f"respaldo_frankie_{fecha_str}.db"
        ruta_db_destino = carpeta_backups / nombre_archivo

        try:
            # 3. Lógica de Hot Backup nativa de SQLite (segura contra bloqueos).
            with ConexionDB() as db_origen:
                with closing(sqlite3.connect(ruta_db_destino)) as db_destino:
                    with db_destino:
                        db_origen.backup(db_destino)

            return f"Backup exitoso.\nArchivo generado: {nombre_archivo}"

        except Exception as e:
            logger.exception("Error crítico al generar backup")
            return f"Error crítico al generar backup: {e}"


# ===================================================================================
# ⚠️ CÓMO DEBEN ARMAR SUS CONTROLADORES:
# ===================================================================================
#
# Cuando creen orquestador_rrhh.py y orquestador_ventas.py, sigan estas reglas:
#
# 1. EL CONTROLADOR ES EL CEREBRO: La Vista (Tkinter) es tonta, solo hace clics.
#    El Repositorio (SQLite) es tonto, solo guarda datos. El Controlador es el único
#    que piensa. Si hay que calcular un descuento o validar si un CUIT es correcto,
#    SE HACE ACÁ.
#
# 2. CERO TKINTER: Está totalmente prohibido importar 'tkinter' o 'messagebox'
#    en esta carpeta. Fíjense que esta función devuelve un texto (str). Es la
#    interfaz (ui_panel.py) la que va a agarrar este texto y decidirá si lo muestra
#    en un cartelito verde o rojo.
#
# 3. FLUJO DE TRABAJO:
#    Vista captura clic -> Llama al Controlador -> Controlador hace los cálculos
#    -> Controlador llama al Repositorio para guardar -> Devuelve respuesta a Vista.
# ===================================================================================