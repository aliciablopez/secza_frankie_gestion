"""
===============================================================================
REPOSITORIO DE HABERES Y LIQUIDACIONES (infraestructura/repo_haberes.py)
===============================================================================
Estrategia y Buenas Prácticas Aplicadas:
1. Conexión Centralizada: Utiliza 'ConexionDB' mediante el gestor de contexto (with),
   garantizando transacciones atómicas seguras, commits automáticos y control de errores.
2. Configuración Centralizada: Obtiene los porcentajes de aportes/descuentos y
   parámetros sensibles desde 'config.py' (CONFIG_SISTEMA / constantes) con
   respaldo seguro por defecto.
3. Sintonizado con la Base de Datos: Persiste directamente en la tabla oficial
   'liquidaciones_haberes' respetando las claves foráneas y restricciones del proyecto.
===============================================================================
"""

from typing import Any, Dict, List, Optional

from dominio.entidades_haberes import LiquidacionHaberes
from infraestructura.conexion import ConexionDB

try:
    import config as _config
except ImportError:
    _config = None


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
    ) -> Dict[str, Any]:
        """
        Realiza el cálculo de conceptos remunerativos, deducciones de ley
        y persiste/actualiza el resultado en la tabla 'liquidaciones_haberes'.
        """
        id_emp_seguro: int = int(id_empleado) if id_empleado is not None else 0
        periodo_limpio: str = (periodo or "").strip()
        basico_val: float = max(0.0, float(basico or 0.0))
        anios_val: int = max(0, int(antiguedad_anios or 0))
        horas_extra_val: float = max(0.0, float(horas_extra or 0.0))
        feriados_val: float = max(0.0, float(feriados or 0.0))
        ventas_val: float = max(0.0, float(ventas or 0.0))
        adelanto_val: float = max(0.0, float(adelanto or 0.0))

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

        # 5. Persistencia atómica en la tabla oficial 'liquidaciones_haberes'
        with ConexionDB() as conexion:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO liquidaciones_haberes (
                    id_empleado, periodo, sueldo_basico,
                    total_remunerativo, total_no_remunerativo,
                    total_descuentos, neto_a_cobrar
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_empleado, periodo) DO UPDATE SET
                    sueldo_basico = excluded.sueldo_basico,
                    total_remunerativo = excluded.total_remunerativo,
                    total_no_remunerativo = excluded.total_no_remunerativo,
                    total_descuentos = excluded.total_descuentos,
                    neto_a_cobrar = excluded.neto_a_cobrar;
                """,
                (
                    id_emp_seguro,
                    periodo_limpio,
                    basico_val,
                    total_remunerativo,
                    total_no_remunerativo,
                    total_descuentos,
                    neto_a_cobrar,
                ),
            )

        return {
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

        with ConexionDB() as conexion:
            cursor = conexion.cursor()

            if liquidacion.id is None:
                cursor.execute(
                    """
                    INSERT INTO liquidaciones_haberes (
                        id_empleado, periodo, sueldo_basico,
                        total_remunerativo, total_no_remunerativo,
                        total_descuentos, neto_a_cobrar
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_empleado, periodo) DO UPDATE SET
                        sueldo_basico = excluded.sueldo_basico,
                        total_remunerativo = excluded.total_remunerativo,
                        total_no_remunerativo = excluded.total_no_remunerativo,
                        total_descuentos = excluded.total_descuentos,
                        neto_a_cobrar = excluded.neto_a_cobrar;
                    """,
                    (
                        id_emp_seguro,
                        periodo_limpio,
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
                    SET id_empleado = ?, periodo = ?, sueldo_basico = ?,
                        total_remunerativo = ?, total_no_remunerativo = ?,
                        total_descuentos = ?, neto_a_cobrar = ?
                    WHERE id_liquidacion = ?;
                    """,
                    (
                        id_emp_seguro,
                        periodo_limpio,
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