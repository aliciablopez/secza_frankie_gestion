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

    def __init__(self, ruta_base: Path | None = None) -> None:
        self.ruta_base = ruta_base or Path(__file__).resolve().parents[1]

    def ejecutar_backup(self) -> str:
        """
        Realiza una copia de seguridad en caliente (Hot Backup) de la base de datos.
        Devuelve un mensaje de éxito o de error para que la Vista lo muestre.
        """
        ruta_db_origen = self.ruta_base / "db" / "frankie_gestor.db"
        carpeta_backups = self.ruta_base / "db" / "backups"

        if not ruta_db_origen.exists() or not ruta_db_origen.is_file():
            return (
                f"Error crítico al generar backup: no se encontró la base de datos "
                f"en {ruta_db_origen}"
            )

        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        nombre_archivo = f"respaldo_frankie_{fecha_str}.db"
        ruta_db_destino = carpeta_backups / nombre_archivo

        try:
            carpeta_backups.mkdir(parents=True, exist_ok=True)

            with ConexionDB() as db_origen:
                if not isinstance(db_origen, sqlite3.Connection) or not hasattr(db_origen, "backup"):
                    raise TypeError("La conexión de origen no soporta backup nativo de SQLite.")

                with closing(sqlite3.connect(ruta_db_destino)) as db_destino:
                    with db_destino:
                        db_origen.backup(db_destino)

            if not ruta_db_destino.exists() or ruta_db_destino.stat().st_size == 0:
                if ruta_db_destino.exists():
                    ruta_db_destino.unlink(missing_ok=True)
                return "Error crítico al generar backup: el archivo de respaldo quedó vacío."

            return f"Backup exitoso.\nArchivo generado: {nombre_archivo}"

        except Exception as exc:
            if ruta_db_destino.exists():
                ruta_db_destino.unlink(missing_ok=True)
            logger.exception("Error crítico al generar backup")
            return f"Error crítico al generar backup: {exc}"


ControladorCore = OrquestadorCore