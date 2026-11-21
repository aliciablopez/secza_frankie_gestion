"""
===============================================================================
MÓDULO DE INFRAESTRUCTURA: REPOSITORIO DE RECURSOS HUMANOS (infraestructura/repo_rrhh.py)
===============================================================================
Capa de acceso a datos para la gestión del personal y registros de personas,
coordinando transacciones atómicas sobre 'personas' y 'empleados'.
===============================================================================
"""

from typing import Any, List, Optional

from dominio.entidades_persona import limpiar_documento
from dominio.entidades_rrhh import Empleado
from infraestructura.conexion import ConexionDB


class RepositorioRRHH:
    """Capa de acceso a datos para la gestión del personal y registros de personas."""

    CARGOS_VALIDOS = (
        "Gerente",
        "Administrativo",
        "Admin",
        "Vendedor",
    )
    SECTORES_VALIDOS = (
        "Gestión",
        "Staff",
        "Ventas",
        "Compras",
        "Administración",
    )
    VINCULOS_VALIDOS = (
        "Propietario",
        "Contratado",
        "Pasante",
        "Permanente",
    )

    @staticmethod
    def _obtener_columnas_tabla(cursor, tabla: str) -> List[str]:
        """Obtiene los nombres de columna existentes de una tabla SQLite."""
        cursor.execute(f"PRAGMA table_info({tabla});")
        return [col[1] for col in cursor.fetchall()]

    @staticmethod
    def _normalizar_documento_y_tipo(
        nro_documento: str, tipo_doc_actual: Optional[str] = None
    ) -> tuple[str, str]:
        """Limpia el número de documento y determina un tipo válido para el CHECK."""
        doc_limpio = limpiar_documento(nro_documento)
        if tipo_doc_actual in ("DNI", "CUIT", "CUIL", "Pasaporte"):
            return doc_limpio, tipo_doc_actual
        tipo_doc = "CUIL" if len(doc_limpio) == 11 else "DNI"
        return doc_limpio, tipo_doc

    @classmethod
    def _normalizar_datos_laborales(cls, emp: Empleado) -> tuple[str, str, str, float]:
        """Normaliza y valida cargo, sector, tipo de vínculo y sueldo."""
        cargo = (getattr(emp, "cargo", "") or "").strip()
        sector = (getattr(emp, "sector", "") or "").strip()
        vinculo = (getattr(emp, "tipo_vinculo", "") or "Contratado").strip()
        sueldo = float(getattr(emp, "sueldo", 0.0) or 0.0)

        if not cargo:
            raise ValueError("El cargo del empleado es obligatorio.")
        if cargo not in cls.CARGOS_VALIDOS:
            raise ValueError(
                f"Cargo inválido '{cargo}'. Valores permitidos: {', '.join(cls.CARGOS_VALIDOS)}."
            )
        if not sector:
            raise ValueError("El sector del empleado es obligatorio.")
        if vinculo not in cls.VINCULOS_VALIDOS:
            vinculo = "Contratado"
        if sueldo < 0.0:
            raise ValueError("El sueldo del empleado no puede ser negativo.")

        return cargo, sector, vinculo, sueldo

    @staticmethod
    def generar_siguiente_legajo() -> str:
        """Genera el siguiente legajo correlativo con formato 'E001', 'E002', etc."""
        with ConexionDB() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT legajo FROM empleados ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            if row and row["legajo"]:
                digitos = "".join(c for c in str(row["legajo"]) if c.isdigit())
                if digitos:
                    return f"E{int(digitos) + 1:03d}"
            return "E001"

    @staticmethod
    def crear_empleado(emp: Empleado) -> bool:
        """Inserta de forma coordinada el registro en 'personas' y luego en 'empleados'."""
        with ConexionDB() as conn:
            cursor = conn.cursor()
            try:
                doc_limpio, tipo_doc = RepositorioRRHH._normalizar_documento_y_tipo(
                    emp.nro_documento, getattr(emp, "tipo_documento", None)
                )
                if not doc_limpio:
                    raise ValueError("El número de documento/CUIL del empleado es obligatorio.")

                nombres = (emp.nombres or "").strip()
                apellidos = (emp.apellidos or "").strip()
                if not nombres or not apellidos:
                    raise ValueError("Nombres y apellidos son obligatorios para persona física.")

                cargo, sector, vinculo, sueldo = RepositorioRRHH._normalizar_datos_laborales(emp)

                cols_per = RepositorioRRHH._obtener_columnas_tabla(cursor, "personas")
                campos_per = [
                    "tipo_persona",
                    "nombres",
                    "apellidos",
                    "razon_social",
                    "tipo_documento",
                    "nro_documento",
                    "telefono",
                    "email",
                ]
                valores_per: List[Any] = [
                    "Fisica",
                    nombres,
                    apellidos,
                    None,
                    tipo_doc,
                    doc_limpio,
                    (emp.telefono or "").strip(),
                    (emp.email or "").strip(),
                ]

                for campo_extra, attr_extra in (
                    ("domicilio", "domicilio"),
                    ("ciudad", "ciudad"),
                    ("provincia", "provincia"),
                    ("codigo_postal", "codigo_postal"),
                ):
                    if campo_extra in cols_per:
                        campos_per.append(campo_extra)
                        valores_per.append((getattr(emp, attr_extra, "") or "").strip())

                placeholders_per = ", ".join(["?"] * len(campos_per))
                cursor.execute(
                    f"INSERT INTO personas ({', '.join(campos_per)}) VALUES ({placeholders_per});",
                    valores_per,
                )
                id_persona_nueva = cursor.lastrowid

                cols_emp = RepositorioRRHH._obtener_columnas_tabla(cursor, "empleados")
                legajo_final = (
                    emp.legajo or ""
                ).strip() or RepositorioRRHH.generar_siguiente_legajo()

                campos_emp = ["id_persona", "id_usuario", "legajo", "cargo", "sector", "sueldo"]
                valores_emp: List[Any] = [
                    id_persona_nueva,
                    getattr(emp, "id_usuario", None),
                    legajo_final,
                    cargo,
                    sector,
                    sueldo,
                ]

                if "tipo_vinculo" in cols_emp:
                    campos_emp.append("tipo_vinculo")
                    valores_emp.append(vinculo)

                if "activo" in cols_emp:
                    campos_emp.append("activo")
                    valores_emp.append(1 if getattr(emp, "activo", True) else 0)

                placeholders_emp = ", ".join(["?"] * len(campos_emp))
                cursor.execute(
                    f"INSERT INTO empleados ({', '.join(campos_emp)}) VALUES ({placeholders_emp});",
                    valores_emp,
                )

                emp.id_persona = id_persona_nueva
                emp.id_empleado = cursor.lastrowid
                emp.legajo = legajo_final
                return True

            except Exception as e:
                print(f"[ERROR RepoRRHH.crear_empleado]: {e}")
                raise e

    @staticmethod
    def actualizar_empleado(emp: Empleado) -> bool:
        """Actualiza los datos de 'personas' y 'empleados' para un empleado existente."""
        if not getattr(emp, "id_empleado", None):
            raise ValueError("No se puede actualizar un empleado sin 'id_empleado'.")

        with ConexionDB() as conn:
            cursor = conn.cursor()
            try:
                doc_limpio, tipo_doc = RepositorioRRHH._normalizar_documento_y_tipo(
                    emp.nro_documento, getattr(emp, "tipo_documento", None)
                )
                if not doc_limpio:
                    raise ValueError("El número de documento/CUIL del empleado es obligatorio.")

                nombres = (emp.nombres or "").strip()
                apellidos = (emp.apellidos or "").strip()
                if not nombres or not apellidos:
                    raise ValueError("Nombres y apellidos son obligatorios para persona física.")

                cargo, sector, vinculo, sueldo = RepositorioRRHH._normalizar_datos_laborales(emp)

                if emp.id_persona:
                    cols_per = RepositorioRRHH._obtener_columnas_tabla(cursor, "personas")
                    sets_per = [
                        "nombres = ?",
                        "apellidos = ?",
                        "tipo_documento = ?",
                        "nro_documento = ?",
                        "telefono = ?",
                        "email = ?",
                    ]
                    valores_per: List[Any] = [
                        nombres,
                        apellidos,
                        tipo_doc,
                        doc_limpio,
                        (emp.telefono or "").strip(),
                        (emp.email or "").strip(),
                    ]

                    for campo_extra, attr_extra in (
                        ("domicilio", "domicilio"),
                        ("ciudad", "ciudad"),
                        ("provincia", "provincia"),
                        ("codigo_postal", "codigo_postal"),
                    ):
                        if campo_extra in cols_per:
                            sets_per.append(f"{campo_extra} = ?")
                            valores_per.append((getattr(emp, attr_extra, "") or "").strip())

                    valores_per.append(emp.id_persona)
                    cursor.execute(
                        f"UPDATE personas SET {', '.join(sets_per)} WHERE id = ?;",
                        valores_per,
                    )

                cols_emp = RepositorioRRHH._obtener_columnas_tabla(cursor, "empleados")
                legajo_final = (
                    emp.legajo or ""
                ).strip() or RepositorioRRHH.generar_siguiente_legajo()
                sets_emp = ["legajo = ?", "cargo = ?", "sector = ?", "sueldo = ?"]
                valores_emp: List[Any] = [
                    legajo_final,
                    cargo,
                    sector,
                    sueldo,
                ]

                if "tipo_vinculo" in cols_emp:
                    sets_emp.append("tipo_vinculo = ?")
                    valores_emp.append(vinculo)

                if "activo" in cols_emp:
                    sets_emp.append("activo = ?")
                    valores_emp.append(1 if getattr(emp, "activo", True) else 0)

                valores_emp.append(emp.id_empleado)
                cursor.execute(
                    f"UPDATE empleados SET {', '.join(sets_emp)} WHERE id = ?;",
                    valores_emp,
                )

                emp.legajo = legajo_final
                return cursor.rowcount > 0

            except Exception as e:
                print(f"[ERROR RepoRRHH.actualizar_empleado]: {e}")
                raise e

    @staticmethod
    def guardar_empleado(emp: Empleado) -> bool:
        """Método unificado para alta o modificación."""
        if getattr(emp, "id_empleado", None):
            return RepositorioRRHH.actualizar_empleado(emp)
        return RepositorioRRHH.crear_empleado(emp)

    @staticmethod
    def cambiar_estado_empleado(id_empleado: int, nuevo_estado: bool) -> bool:
        """
        Realiza la baja o alta lógica (Soft Delete) actualizando 'activo' (1 o 0).
        Si la columna no existiera en una BD heredada, la agrega automáticamente.
        """
        with ConexionDB() as conn:
            cursor = conn.cursor()
            cols_emp = RepositorioRRHH._obtener_columnas_tabla(cursor, "empleados")
            if "activo" not in cols_emp:
                cursor.execute("ALTER TABLE empleados ADD COLUMN activo INTEGER NOT NULL DEFAULT 1;")

            valor_estado = 1 if nuevo_estado else 0
            cursor.execute(
                "UPDATE empleados SET activo = ? WHERE id = ?;",
                (valor_estado, id_empleado),
            )
            return cursor.rowcount > 0

    @staticmethod
    def obtener_empleado_por_id(id_empleado: int) -> Optional[Empleado]:
        """Recupera un empleado puntual uniendo 'empleados' y 'personas'."""
        with ConexionDB() as conn:
            cursor = conn.cursor()
            cols_emp = RepositorioRRHH._obtener_columnas_tabla(cursor, "empleados")
            col_vinculo = (
                "e.tipo_vinculo" if "tipo_vinculo" in cols_emp else "'Contratado' AS tipo_vinculo"
            )
            col_activo = (
                "COALESCE(e.activo, 1) AS activo" if "activo" in cols_emp else "1 AS activo"
            )

            cursor.execute(
                f"""
                SELECT e.id AS id_empleado, e.id_persona, e.id_usuario, e.legajo, e.cargo,
                       e.sector, {col_vinculo}, e.sueldo, {col_activo},
                       p.tipo_documento, p.nro_documento, p.nombres, p.apellidos,
                       p.email, p.telefono
                FROM empleados e
                JOIN personas p ON e.id_persona = p.id
                WHERE e.id = ?;
                """,
                (id_empleado,),
            )
            f = cursor.fetchone()
            if not f:
                return None

            return Empleado(
                id_empleado=f["id_empleado"],
                id_persona=f["id_persona"],
                id_usuario=f["id_usuario"],
                nro_documento=f["nro_documento"],
                tipo_documento=f["tipo_documento"] or "CUIL",
                nombres=f["nombres"],
                apellidos=f["apellidos"],
                legajo=f["legajo"],
                cargo=f["cargo"],
                sector=f["sector"],
                tipo_vinculo=f["tipo_vinculo"],
                sueldo=f["sueldo"],
                email=f["email"],
                telefono=f["telefono"],
                activo=bool(f["activo"]),
            )

    @staticmethod
    def listar_empleados(
        criterio_busqueda: str = "", incluir_inactivos: bool = False
    ) -> List[Empleado]:
        """Lista empleados con filtro opcional por texto y por estado activo/inactivo."""
        with ConexionDB() as conn:
            cursor = conn.cursor()
            cols_emp = RepositorioRRHH._obtener_columnas_tabla(cursor, "empleados")

            col_vinculo = (
                "e.tipo_vinculo" if "tipo_vinculo" in cols_emp else "'Contratado' AS tipo_vinculo"
            )
            col_activo = (
                "COALESCE(e.activo, 1) AS activo" if "activo" in cols_emp else "1 AS activo"
            )

            query = f"""
                SELECT e.id AS id_empleado, e.id_persona, e.id_usuario, e.legajo, e.cargo,
                       e.sector, {col_vinculo}, e.sueldo, {col_activo},
                       p.tipo_documento, p.nro_documento, p.nombres, p.apellidos,
                       p.email, p.telefono
                FROM empleados e
                JOIN personas p ON e.id_persona = p.id
                WHERE 1 = 1
            """
            parametros: List[Any] = []

            if not incluir_inactivos and "activo" in cols_emp:
                query += " AND COALESCE(e.activo, 1) = 1"

            if criterio_busqueda:
                query += """
                    AND (p.nombres LIKE ? OR p.apellidos LIKE ? OR e.legajo LIKE ? OR p.nro_documento LIKE ?)
                """
                patron = f"%{criterio_busqueda.strip()}%"
                parametros.extend([patron, patron, patron, patron])

            query += " ORDER BY e.id ASC;"
            cursor.execute(query, parametros)
            filas = cursor.fetchall()

            lista: List[Empleado] = []
            for f in filas:
                emp = Empleado(
                    id_empleado=f["id_empleado"],
                    id_persona=f["id_persona"],
                    id_usuario=f["id_usuario"],
                    nro_documento=f["nro_documento"],
                    tipo_documento=f["tipo_documento"] or "CUIL",
                    nombres=f["nombres"],
                    apellidos=f["apellidos"],
                    legajo=f["legajo"],
                    cargo=f["cargo"],
                    sector=f["sector"],
                    tipo_vinculo=f["tipo_vinculo"],
                    sueldo=f["sueldo"],
                    email=f["email"],
                    telefono=f["telefono"],
                    activo=bool(f["activo"]),
                )
                lista.append(emp)

            return lista