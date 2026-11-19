"""
===============================================================================
MÓDULO DE INFRAESTRUCTURA: REPOSITORIO CORE (infraestructura/repo_core.py)
===============================================================================
Gestiona la persistencia de usuarios, verificación de contraseñas y asignación
de roles para la autenticación segura en el sistema, adaptado al esquema oficial.
===============================================================================
"""

import hashlib
import hmac
import sqlite3
from typing import Optional

from dominio.entidades_core import Rol, Usuario
from infraestructura.conexion import ConexionDB


class RepoCore:
    """
    Repositorio encargado de las operaciones de autenticación, consulta de usuarios
    y mapeo de roles de seguridad.
    """

    @staticmethod
    def _hashear_password(password: str) -> str:
        """Genera un hash seguro para la contraseña utilizando SHA-256."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def _verificar_password(cls, password_plana: str, password_almacenada: str) -> bool:
        """
        Verifica la contraseña contra el hash SHA-256 almacenado
        (con respaldo a texto plano solo si no está hasheada en BD).
        """
        if not password_plana or not password_almacenada:
            return False

        hash_calculado = cls._hashear_password(password_plana)
        if hmac.compare_digest(password_almacenada, hash_calculado):
            return True

        return hmac.compare_digest(password_almacenada, password_plana)

    @classmethod
    def autenticar_usuario(cls, username: str, password_plana: str) -> Optional[Usuario]:
        """
        Valida las credenciales de acceso de un usuario en la base de datos.
        Retorna el objeto Usuario con sus roles si las credenciales son correctas,
        o None en caso contrario.
        """
        usuario_limpio = (username or "").strip()
        if not usuario_limpio or not password_plana:
            return None

        try:
            with ConexionDB() as conn:
                cursor = conn.cursor()

                # 1. Buscar el usuario activo consultando la columna 'password' del esquema oficial
                cursor.execute(
                    """
                    SELECT id, username, password, activo
                    FROM usuarios
                    WHERE username = ? AND activo = 1;
                    """,
                    (usuario_limpio,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                password_almacenada = row["password"] or ""
                if not cls._verificar_password(password_plana, password_almacenada):
                    return None

                id_usuario = row["id"]
                usuario = Usuario(
                    id_usuario=id_usuario,
                    username=row["username"],
                    password_hash=password_almacenada,
                    activo=row["activo"],
                )

                # 2. Cargar roles asociados usando la tabla intermedia oficial 'usuarios_roles'
                cursor.execute(
                    """
                    SELECT r.id, r.nombre, r.descripcion
                    FROM roles r
                    JOIN usuarios_roles ur ON r.id = ur.id_rol
                    WHERE ur.id_usuario = ?;
                    """,
                    (id_usuario,),
                )
                filas_roles = cursor.fetchall()
                for r_row in filas_roles:
                    rol = Rol(
                        id_rol=r_row["id"],
                        nombre=r_row["nombre"],
                        descripcion=r_row["descripcion"] or "",
                    )
                    usuario.agregar_rol(rol)

                return usuario
        except sqlite3.Error as exc:
            raise RuntimeError(f"Error al consultar autenticación de usuario en SQLite: {exc}") from exc

    @classmethod
    def autenticar(cls, username: str, password_plana: str) -> Optional[Usuario]:
        """
        Método adaptador de clase para mantener compatibilidad directa con ui_login.py.
        """
        return cls.autenticar_usuario(username, password_plana)