"""
===============================================================================
MÓDULO DE DOMINIO: ENTIDADES CORE
===============================================================================
Define las clases base para la autenticación y control de acceso del sistema Frankie.
===============================================================================
"""

from typing import Optional


class Rol:
    """
    Molde (Entidad) que representa los niveles de acceso del sistema.
    Ejemplo: Administrador, Gerente, Empleado.
    """

    def __init__(self, id_rol: int, nombre: str, descripcion: str = "") -> None:
        self.id_rol = id_rol
        self.nombre = nombre
        self.descripcion = descripcion

    def __repr__(self) -> str:
        return f"<Rol id={self.id_rol} nombre='{self.nombre}'>"


class Usuario:
    """
    Molde (Entidad) que representa a quien inicia sesión en el sistema.
    Nota: 'password_hash' almacena el texto cifrado, no la clave real.
    """

    def __init__(
        self,
        id_usuario: int,
        username: str,
        password_hash: str,
        activo: int = 1,
        roles: Optional[list[Rol]] = None,
    ) -> None:
        self.id_usuario = id_usuario
        self.username = username
        self.password_hash = password_hash
        self.activo = activo
        self.roles: list[Rol] = list(roles) if roles else []

    def agregar_rol(self, rol: Rol) -> None:
        """Añade un objeto Rol a la lista del usuario sin duplicar por id_rol."""
        if not any(r.id_rol == rol.id_rol for r in self.roles):
            self.roles.append(rol)

    def __repr__(self) -> str:
        return f"<Usuario username='{self.username}'>"