"""
===============================================================================
REPOSITORIO DE HABERES Y LIQUIDACIONES (infraestructura/repo_haberes.py)
===============================================================================
Estrategia y Buenas Prácticas Aplicadas:
1. Conexión Centralizada: Utiliza \x27ConexionDB\x27 mediante el gestor de contexto (with),
   garantizando transacciones atómicas seguras, commits automáticos y control de errores.
2. Configuración Centralizada: Obtiene los porcentajes de aportes/descuentos y
   parámetros sensibles desde \x27config.py\x27 (CONFIG_SISTEMA / constantes) con
   respaldo seguro por defecto.
3. Sintonizado con la Base de Datos: Persiste directamente en la tabla oficial
   \x27liquidaciones_haberes\x27 respetando las claves foráneas y restricciones del proyecto.
4. Regla de Vínculo / Facturación: Si el tipo de vínculo es \x27pasante\x27 o
   \x27permanente\x27, corresponde recibo de haberes; en cualquier otro caso
   (con \x27Contratado\x27 por defecto), presenta factura.
===============================================================================
"""

from typing import Any, Dict, List, Optional

from dominio.entidades_haberes import LiquidacionHaberes
from infraestructura.conexion import ConexionDB

try:
    import config as _config
except ImportError:
    _config = None


VINCULO_POR_DEFECTO = "Contratado"
VINCULOS_RECIBO_HABERES = {"pasante", "permanente", "empleado permanente"}


def normalizar_tipo_vinculo(tipo_vinculo: Any) -> str:
    """Devuelve el tipo de vínculo limpio o \x27Contratado\x27 por defecto."""
    texto = str(tipo_vinculo or "").strip()
    return texto if texto else VINCULO_POR_DEFECTO


def es_vinculo_recibo_haberes(tipo_vinculo: Any) -> bool:
    """
    Devuelve True únicamente si el tipo de vínculo es \x27pasante\x27 o \x27permanente\x27
    (emite recibo de haberes). En cualquier otro caso (ej. \x27Contratado\x27,
    \x27Propietario\x27), presenta factura.
    """
    vinculo_norm = normalizar_tipo_vinculo(tipo_vinculo).lower()
    return vinculo_norm in VINCULOS_RECIBO_HABERES


def obtener_modalidad_comprobante(tipo_vinculo: Any) -> str:
    """
    Indica la modalidad de comprobante según el tipo de vínculo:
    - \x27Recibo de haberes\x27 si es \x27pasante\x27 o \x27permanente\x27
    - \x27Presenta factura\x27 en cualquier otro caso (\x27Contratado\x27 por defecto)
    """
    return "Recibo de haberes" if es_vinculo_recibo_haberes(tipo_vinculo) else "Presenta factura"


def _obtener_parametro(
    attr_config_sistema: str,
    constante_modulo: str,
    valor_por_defecto: float,
) -> float:
    """Lee un parámetro desde CONFIG_SISTEMA, constante en config.py o fallback."""
    if _config is not None:
        cfg_obj = getattr(_config, "CONFIG_SISTEMA", None)
        if cfg_obj is not None and hasattr(cfg_obj, attr_config_sistema):
            return float(getattr(cfg_obj, attr_config_sistema))
        if hasattr(_config, constante_modulo):
            return float(getattr(_config, constante_modulo))
    return float(valor_por_defecto)


class RepositorioHaberes:
    """
    Repositorio encargado de procesar, almacenar y recuperar las liquidaciones
    de sueldos e historial remunerativo de los empleados en SQLite.
    """

    @staticmethod
    def _asegurar_columna_vinculo(cursor: Any) -> None:
        """Asegura que la tabla liquidaciones_haberes tenga columna tipo_vinculo."""
        try:
            columnas = [
                str(col["name"] if isinstance(col, dict) else col[1]).lower()
                for col in cursor.execute("PRAGMA table_info(liquidaciones_haberes)").fetchall()
            ]
            if columnas and "tipo_vinculo" not in columnas:
                cursor.execute(
                    f"ALTER TABLE liquidaciones_haberes ADD COLUMN tipo_vinculo TEXT NOT NULL DEFAULT \x27{VINCULO_POR_DEFECTO}\x27"
                )
        except Exception:
            pass

    @staticmethod
    def obtener_tipo_vinculo_empleado(id_empleado: int) -> str:
        """
        Consulta el tipo de vínculo del empleado en la base de datos.
        Si no existe la columna o no está informado, devuelve \x27Contratado\x27.
        """
        id_emp_seguro = int(id_empleado) if id_empleado is not None else 0
        if id_emp_seguro <= 0:
            return VINCULO_POR_DEFECTO

        with ConexionDB() as conexion:
            cursor = conexion.cursor()
            cols = [
                str(col["name"] if isinstance(col, dict) else col[1]).lower()
                for col in cursor.execute("PRAGMA table_info(empleados)").fetchall()
            ]
            if "tipo_vinculo" not in cols:
                return VINCULO_POR_DEFECTO

            cursor.execute(
                "SELECT tipo_vinculo FROM empleados WHERE id = ?",
                (id_emp_seguro,),
            )
            fila = cursor.fetchone()
            if not fila:
                return VINCULO_POR_DEFECTO
            valor = fila["tipo_vinculo"] if isinstance(fila, dict) or hasattr(fila, "keys") else fila[0]
            return normalizar_tipo_vinculo(valor)

    @staticmethod
    def calcular_liquidacion(
        id_empleado: int,
        periodo: str,
        basico: float,
        antiguedad_anios: int = 0,
        aplica_presentismo: bool = True,
        horas_extra: float = 0.0,
        feriados: float = 0.0,
        ventas: float = 0.0,
        adelanto: float = 0.0,
        aplica_jubilacion: bool = True,
        aplica_pami: bool = True,
        aplica_obra_social: bool = True,
        aplica_sindicato: bool = True,
        tipo_vinculo: Optional[str] = None,
        persistir: bool = True,
    ) -> Dict[str, Any]:
        """
        Realiza el cálculo de conceptos remunerativos, deducciones de ley
        y, cuando corresponde recibo de haberes (\x27pasante\x27 o \x27permanente\x27),
        persiste/actualiza el resultado en la tabla \x27liquidaciones_haberes\x27.
        """
        id_emp_seguro: int = int(id_empleado) if id_empleado is not None else 0
        periodo_limpio: str = (periodo or "").strip()
        basico_val: float = max(0.0, float(basico or 0.0))
        anios_val: int = max(0, int(antiguedad_anios or 0))
        horas_extra_val: float = max(0.0, float(horas_extra or 0.0))
        feriados_val: float = max(0.0, float(feriados or 0.0))
        ventas_val: float = max(0.0, float(ventas or 0.0))
        adelanto_val: float = max(0.0, float(adelanto or 0.0))

        vinculo_resuelto = (
            normalizar_tipo_vinculo(tipo_vinculo)
            if tipo_vinculo is not None and str(tipo_vinculo).strip()
            else RepositorioHaberes.obtener_tipo_vinculo_empleado(id_emp_seguro)
        )
        emite_recibo = es_vinculo_recibo_haberes(vinculo_resuelto)
        modalidad_comprobante = obtener_modalidad_comprobante(vinculo_resuelto)

        # Parámetros sensibles obtenidos de config.py
        porc_antiguedad = _obtener_parametro(
            "antiguedad_porc", "PORC_ANTIGUEDAD_ANUAL", 0.01
        )
        porc_presentismo = _obtener_parametro(
            "presentismo_porc", "PORC_PRESENTISMO", 0.0833
        )
        horas_base = _obtener_parametro(
            "horas_mensuales_base", "HORAS_MENSUALES_BASE", 160.0
        )
        dias_base = _obtener_parametro(
            "dias_mensuales_base", "DIAS_MENSUALES_BASE", 20.0
        )
        mult_extra = _obtener_parametro(
            "multiplicador_horas_extra", "MULTIPLICADOR_HORAS_EXTRA", 1.5
        )
        mult_feriados = _obtener_parametro(
            "multiplicador_feriados", "MULTIPLICADOR_FERIADOS", 2.0
        )
        porc_comision = _obtener_parametro(
            "comision_ventas_porc", "PORC_COMISION_VENTAS", 0.05
        )

        porc_jubilacion = _obtener_parametro(
            "aporte_jubilacion", "APORTE_JUBILACION_PORC", 0.11
        )
        porc_pami = _obtener_parametro(
            "aporte_pami", "APORTE_PAMI_PORC", 0.03
        )
        porc_obra_social = _obtener_parametro(
            "aporte_obra_social", "APORTE_OBRA_SOCIAL_PORC", 0.03
        )
        porc_sindicato = _obtener_parametro(
            "aporte_sindicato", "APORTE_SINDICATO_PORC", 0.025
        )

        # 1. Haberes Remunerativos
        monto_antiguedad = basico_val * (porc_antiguedad * anios_val)
        monto_presentismo = (basico_val * porc_presentismo) if aplica_presentismo else 0.0

        valor_hora = (basico_val / horas_base) if (basico_val > 0 and horas_base > 0) else 0.0
        monto_horas_extra = horas_extra_val * valor_hora * mult_extra

        valor_dia = (basico_val / dias_base) if (basico_val > 0 and dias_base > 0) else 0.0
        monto_feriados = feriados_val * valor_dia * mult_feriados

        monto_comision = ventas_val * porc_comision

        total_remunerativo = (
            basico_val
            + monto_antiguedad
            + monto_presentismo
            + monto_horas_extra
            + monto_feriados
            + monto_comision
        )

        # 2. Haberes No Remunerativos
        total_no_remunerativo = 0.00

        # 3. Deducciones
        jubilacion = (total_remunerativo * porc_jubilacion) if aplica_jubilacion else 0.0
        pami = (total_remunerativo * porc_pami) if aplica_pami else 0.0
        obra_social = (total_remunerativo * porc_obra_social) if aplica_obra_social else 0.0
        cuota_sindical = (total_remunerativo * porc_sindicato) if aplica_sindicato else 0.0

        total_descuentos = jubilacion + pami + obra_social + cuota_sindical + adelanto_val

        # 4. Neto a Cobrar
        neto_a_cobrar = max(0.0, (total_remunerativo + total_no_remunerativo) - total_descuentos)

        # 5. Persistencia atómica en la tabla oficial \x27liquidaciones_haberes\x27
        #    solo si emite recibo de haberes (\x27pasante\x27 o \x27permanente\x27).
        if persistir and emite_recibo:
            with ConexionDB() as conexion:
                cursor = conexion.cursor()
                RepositorioHaberes._asegurar_columna_vinculo(cursor)
                cursor.execute(
                    """
                    INSERT INTO liquidaciones_haberes (
                        id_empleado, periodo, tipo_vinculo, sueldo_basico,
                        total_remunerativo, total_no_remunerativo,
                        total_descuentos, neto_a_cobrar
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_empleado, periodo) DO UPDATE SET
                        tipo_vinculo = excluded.tipo_vinculo,
                        sueldo_basico = excluded.sueldo_basico,
                        total_remunerativo = excluded.total_remunerativo,
                        total_no_remunerativo = excluded.total_no_remunerativo,
                        total_descuentos = excluded.total_descuentos,
                        neto_a_cobrar = excluded.neto_a_cobrar;
                    """,
                    (
                        id_emp_seguro,
                        periodo_limpio,
                        vinculo_resuelto,
                        basico_val,
                        total_remunerativo,
                        total_no_remunerativo,
                        total_descuentos,
                        neto_a_cobrar,
                    ),
                )

        return {
            "tipo_vinculo": vinculo_resuelto,
            "emite_recibo": emite_recibo,
            "presenta_factura": not emite_recibo,
            "modalidad_comprobante": modalidad_comprobante,
            "remunerativo": total_remunerativo,
            "no_remunerativo": total_no_remunerativo,
            "descuentos": total_descuentos,
            "neto": neto_a_cobrar,
            "desglose_deducciones": {
                "jubilacion": jubilacion,
                "pami": pami,
                "obra_social": obra_social,
                "sindicato": cuota_sindical,
                "adelanto": adelanto_val,
            },
        }

    def guardar_liquidacion(self, liquidacion: LiquidacionHaberes) -> int:
        """
        Inserta una nueva liquidación o actualiza una existente usando el objeto de dominio.
        """
        id_emp_seguro: int = int(liquidacion.id_empleado) if liquidacion.id_empleado is not None else 0
        id_liq_seguro: int = int(liquidacion.id) if liquidacion.id is not None else 0
        periodo_limpio: str = (liquidacion.periodo or "").strip()

        vinculo_resuelto = normalizar_tipo_vinculo(
            getattr(liquidacion, "tipo_vinculo", None)
            or RepositorioHaberes.obtener_tipo_vinculo_empleado(id_emp_seguro)
        )
        if not es_vinculo_recibo_haberes(vinculo_resuelto):
            raise ValueError(
                f"El vínculo \x27{vinculo_resuelto}\x27 presenta factura y no emite recibo de haberes."
            )

        with ConexionDB() as conexion:
            cursor = conexion.cursor()
            RepositorioHaberes._asegurar_columna_vinculo(cursor)

            if liquidacion.id is None:
                cursor.execute(
                    """
                    INSERT INTO liquidaciones_haberes (
                        id_empleado, periodo, tipo_vinculo, sueldo_basico,
                        total_remunerativo, total_no_remunerativo,
                        total_descuentos, neto_a_cobrar
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_empleado, periodo) DO UPDATE SET
                        tipo_vinculo = excluded.tipo_vinculo,
                        sueldo_basico = excluded.sueldo_basico,
                        total_remunerativo = excluded.total_remunerativo,
                        total_no_remunerativo = excluded.total_no_remunerativo,
                        total_descuentos = excluded.total_descuentos,
                        neto_a_cobrar = excluded.neto_a_cobrar;
                    """,
                    (
                        id_emp_seguro,
                        periodo_limpio,
                        vinculo_resuelto,
                        float(liquidacion.sueldo_basico or 0.0),
                        float(liquidacion.total_remunerativo or 0.0),
                        float(liquidacion.total_no_remunerativo or 0.0),
                        float(liquidacion.total_descuentos or 0.0),
                        float(liquidacion.neto_a_cobrar or 0.0),
                    ),
                )
                cursor.execute(
                    """
                    SELECT id_liquidacion FROM liquidaciones_haberes
                    WHERE id_empleado = ? AND periodo = ?;
                    """,
                    (id_emp_seguro, periodo_limpio),
                )
                fila = cursor.fetchone()
                liquidacion.id = int(fila["id_liquidacion"]) if fila else cursor.lastrowid
            else:
                cursor.execute(
                    """
                    UPDATE liquidaciones_haberes
                    SET id_empleado = ?, periodo = ?, tipo_vinculo = ?, sueldo_basico = ?,
                        total_remunerativo = ?, total_no_remunerativo = ?,
                        total_descuentos = ?, neto_a_cobrar = ?
                    WHERE id_liquidacion = ?;
                    """,
                    (
                        id_emp_seguro,
                        periodo_limpio,
                        vinculo_resuelto,
                        float(liquidacion.sueldo_basico or 0.0),
                        float(liquidacion.total_remunerativo or 0.0),
                        float(liquidacion.total_no_remunerativo or 0.0),
                        float(liquidacion.total_descuentos or 0.0),
                        float(liquidacion.neto_a_cobrar or 0.0),
                        id_liq_seguro,
                    ),
                )

        return int(liquidacion.id) if liquidacion.id is not None else 0

    def listar_liquidaciones(self, id_empleado: Optional[int] = None) -> List[LiquidacionHaberes]:
        """
        Recupera el historial de liquidaciones de haberes registradas,
        opcionalmente filtrado por empleado.
        """
        with ConexionDB() as conexion:
            cursor = conexion.cursor()
            query = """
                SELECT id_liquidacion, id_empleado, periodo, sueldo_basico,
                       total_remunerativo, total_no_remunerativo,
                       total_descuentos, neto_a_cobrar
                FROM liquidaciones_haberes
            """
            params: List[Any] = []
            if id_empleado is not None:
                query += " WHERE id_empleado = ?"
                params.append(int(id_empleado))

            query += " ORDER BY periodo DESC, id_liquidacion DESC;"
            cursor.execute(query, params)
            filas = cursor.fetchall()

            liquidaciones: List[LiquidacionHaberes] = []
            for fila in filas:
                liq = LiquidacionHaberes(
                    id_empleado=int(fila["id_empleado"]),
                    periodo=str(fila["periodo"]),
                    sueldo_basico=float(fila["sueldo_basico"]),
                    total_remunerativo=float(fila["total_remunerativo"]),
                    total_no_remunerativo=float(fila["total_no_remunerativo"] or 0.0),
                    total_descuentos=float(fila["total_descuentos"]),
                    neto_a_cobrar=float(fila["neto_a_cobrar"]),
                    id=int(fila["id_liquidacion"]),
                )
                liquidaciones.append(liq)

            return liquidaciones
