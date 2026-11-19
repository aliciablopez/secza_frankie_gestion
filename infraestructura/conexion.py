"""
Módulo de Infraestructura: Conexión Centralizada a SQLite
Gestiona la apertura transaccional, activación de claves foráneas y cierre seguro
de la base de datos 'db/frankie_gestor.db'.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Union


class ConexionDB:
    """
    Gestor de contexto para conexiones seguras a la base de datos SQLite
    en 'db/frankie_gestor.db'.
    """

    def __init__(self, ruta_db: Optional[Union[Path, str]] = None) -> None:
        ruta_base = Path(__file__).resolve().parents[1]
        ruta_db_dir = ruta_base / "db"
        ruta_db_dir.mkdir(parents=True, exist_ok=True)

        if ruta_db is None:
            self.ruta_db = ruta_db_dir / "frankie_gestor.db"
        else:
            self.ruta_db = Path(ruta_db)
            self.ruta_db.parent.mkdir(parents=True, exist_ok=True)

        self.conexion: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(str(self.ruta_db))
        try:
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            conexion.close()
            raise

        self.conexion = conexion
        return conexion

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        conexion = self.conexion
        self.conexion = None
        if conexion is None:
            return

        try:
            if exc_type is not None:
                conexion.rollback()
            else:
                conexion.commit()
        finally:
            conexion.close()