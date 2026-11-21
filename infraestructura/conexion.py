"""
===============================================================================
MÓDULO DE INFRAESTRUCTURA: CONEXIÓN A LA BASE DE DATOS (infraestructura/conexion.py)
===============================================================================
Centraliza la ruta de la base de datos en '<raíz>/db/frankie_gestor.db',
activa las claves foráneas y gestiona las transacciones mediante contexto.
===============================================================================
"""

from pathlib import Path
import sqlite3
from typing import Optional


class ConexionDB:
    """
    Gestor de contexto transaccional para la base de datos SQLite del Sistema Frankie.
    """

    RAIZ_PROYECTO: Path = Path(__file__).resolve().parent.parent
    RUTA_DB_DEFECTO: Path = RAIZ_PROYECTO / "db" / "frankie_gestor.db"

    def __init__(self, ruta_db: Optional[Path | str] = None) -> None:
        if ruta_db is not None:
            self.ruta_db = Path(ruta_db)
        else:
            self.ruta_db = self.RUTA_DB_DEFECTO
        self.conexion: Optional[sqlite3.Connection] = None

    def _localizar_esquema(self) -> Optional[Path]:
        """Busca esquema.sql en '<raíz>/db/esquema.sql' o '<raíz>/esquema.sql'."""
        candidatos = [
            self.RAIZ_PROYECTO / "db" / "esquema.sql",
            self.RAIZ_PROYECTO / "esquema.sql",
        ]
        for ruta in candidatos:
            if ruta.exists() and ruta.is_file():
                return ruta
        return None

    def _asegurar_esquema_si_vacia(self, conn: sqlite3.Connection) -> None:
        """Aplica esquema.sql si la base aún no tiene la tabla 'usuarios'."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios';"
        )
        if cursor.fetchone() is None:
            ruta_esquema = self._localizar_esquema()
            if ruta_esquema is not None:
                script_sql = ruta_esquema.read_text(encoding="utf-8")
                conn.executescript(script_sql)

    def __enter__(self) -> sqlite3.Connection:
        self.ruta_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.ruta_db), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        self._asegurar_esquema_si_vacia(conn)

        self.conexion = conn
        return conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conexion is not None:
            try:
                if exc_type is not None:
                    self.conexion.rollback()
                else:
                    self.conexion.commit()
            finally:
                self.conexion.close()
                self.conexion = None