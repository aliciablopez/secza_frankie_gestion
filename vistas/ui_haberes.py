"""
===============================================================================
MÓDULO DE INTERFAZ DE USUARIO: LIQUIDACIÓN DE HABERES (vistas/ui_haberes.py)
===============================================================================
Calcula haberes remunerativos y no remunerativos, deducciones de ley,
persiste la liquidación en SQLite, mantiene el historial de liquidaciones y
permite previsualizar el recibo en HTML o exportar/imprimir el PDF bajo
demanda (sin generar archivos duplicados por cada cálculo de prueba).
Solo habilita la emisión/liquidación de recibo de haberes para los vínculos
\x27pasante\x27 y \x27permanente\x27; cualquier otro vínculo (con \x27Contratado\x27 por
defecto) presenta factura.
===============================================================================
"""

from datetime import datetime
import html
from pathlib import Path
import re
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Set

from dominio.entidades_rrhh import Empleado
from infraestructura.repo_haberes import (
    RepositorioHaberes,
    VINCULO_POR_DEFECTO,
    es_vinculo_recibo_haberes,
    normalizar_tipo_vinculo,
    obtener_modalidad_comprobante,
)
from infraestructura.repo_rrhh import RepositorioRRHH

try:
    from config import DIR_RECIBOS_HABERES as _DIR_RECIBOS_CFG
except ImportError:
    _DIR_RECIBOS_CFG = None

try:
    from vistas.ui_estilos import aplicar_estilos_base
except ImportError:
    try:
        from vistas.estilos import aplicar_estilos_base
    except ImportError:
        aplicar_estilos_base = None


ROLES_LIQUIDACION_HABERES: Set[str] = {"admin", "gerente"}

_EXCEPCIONES_OPERACION = (
    sqlite3.Error,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)
_EXCEPCIONES_UI = (
    sqlite3.Error,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    tk.TclError,
    OSError,
)


def _a_float_seguro(valor: Any, respaldo: float = 0.0) -> float:
    """Convierte a float de forma segura evitando advertencias de tipo por None/Any."""
    if valor is None or isinstance(valor, bool):
        return float(respaldo)
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        limpio = valor.strip().replace(",", ".")
        if not limpio:
            return float(respaldo)
        try:
            return float(limpio)
        except ValueError:
            return float(respaldo)
    return float(respaldo)


def _a_int_seguro(valor: Any, respaldo: int = 0) -> int:
    """Convierte a int de forma segura evitando advertencias de tipo por None/Any."""
    if valor is None or isinstance(valor, bool):
        return int(respaldo)
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor)
    if isinstance(valor, str):
        limpio = valor.strip()
        if not limpio:
            return int(respaldo)
        try:
            return int(float(limpio))
        except ValueError:
            return int(respaldo)
    return int(respaldo)


def _normalizar_rol(nombre_rol: str) -> str:
    limpio = (nombre_rol or "").strip().lower()
    if limpio in {"admin", "administrador"}:
        return "admin"
    if limpio == "gerente":
        return "gerente"
    if limpio == "vendedor":
        return "vendedor"
    if limpio == "administrativo":
        return "administrativo"
    return limpio


def _obtener_roles_normalizados(usuario_actual: Any) -> Set[str]:
    roles: Set[str] = set()
    for rol in getattr(usuario_actual, "roles", None) or []:
        nombre = getattr(rol, "nombre", str(rol))
        norm = _normalizar_rol(nombre)
        if norm:
            roles.add(norm)
    return roles


def _obtener_carpeta_recibos_haberes() -> Path:
    """Resuelve siempre comprobantes/recibo_haberes dentro de la raíz del proyecto."""
    raiz_proyecto = Path(__file__).resolve().parent.parent
    if _DIR_RECIBOS_CFG:
        ruta = Path(_DIR_RECIBOS_CFG)
        carpeta = ruta if ruta.is_absolute() else (raiz_proyecto / ruta)
    else:
        carpeta = raiz_proyecto / "comprobantes" / "recibo_haberes"
    return carpeta


def _sanitizar_segmento(valor: str, respaldo: str) -> str:
    """Limpia caracteres especiales para formar un nombre de archivo seguro."""
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", (valor or "").strip()).strip("_")
    return limpio or respaldo


def obtener_ruta_recibo_html(legajo: str, periodo: str) -> Path:
    """Devuelve la ruta completa del archivo HTML dentro de comprobantes/recibo_haberes."""
    carpeta_recibos = _obtener_carpeta_recibos_haberes()
    legajo_limpio = _sanitizar_segmento(legajo, "SIN_LEGAJO")
    periodo_limpio = _sanitizar_segmento(periodo, "SIN_PERIODO")
    return carpeta_recibos / f"Recibo_{legajo_limpio}_{periodo_limpio}.html"


def obtener_ruta_recibo_pdf(legajo: str, periodo: str) -> Path:
    """Devuelve la ruta completa del archivo PDF dentro de comprobantes/recibo_haberes."""
    carpeta_recibos = _obtener_carpeta_recibos_haberes()
    legajo_limpio = _sanitizar_segmento(legajo, "SIN_LEGAJO")
    periodo_limpio = _sanitizar_segmento(periodo, "SIN_PERIODO")
    return carpeta_recibos / f"Recibo_{legajo_limpio}_{periodo_limpio}.pdf"


def _escapar_pdf(texto: str) -> str:
    limpio = texto.encode("latin-1", errors="replace").decode("latin-1")
    return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _exportar_pdf_desde_lineas(lineas: List[str], ruta_pdf: Path) -> None:
    """Genera un archivo PDF válido sin requerir dependencias externas."""
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)

    comandos: List[str] = ["BT", "/F1 9 Tf", "36 780 Td", "13 TL"]
    for idx, linea in enumerate(lineas):
        escapada = _escapar_pdf(linea)
        if idx == 0:
            comandos.append(f"({escapada}) Tj")
        else:
            comandos.append(f"T* ({escapada}) Tj")
    comandos.append("ET")
    stream_contenido = "\n".join(comandos).encode("latin-1", errors="replace")

    objetos: List[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream_contenido)} >>\nstream\n".encode("ascii")
            + stream_contenido
            + b"\nendstream\nendobj\n"
        ),
    ]

    salida = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = [0]
    for obj in objetos:
        offsets.append(len(salida))
        salida.extend(obj)

    pos_xref = len(salida)
    salida.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    salida.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        salida.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    salida.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{pos_xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    ruta_pdf.write_bytes(bytes(salida))


class InterfazHaberes(ttk.Frame):
    """Componente visual modular basado en ttk.Frame para la Liquidación de Haberes."""

    def __init__(self, parent: tk.Misc, usuario_actual: Any = None) -> None:
        super().__init__(parent)
        self.usuario_actual = usuario_actual
        roles_activos = _obtener_roles_normalizados(usuario_actual)
        self.puede_liquidar: bool = (
            True
            if usuario_actual is None
            else bool(roles_activos & ROLES_LIQUIDACION_HABERES)
        )

        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self)
            except _EXCEPCIONES_UI:
                pass

        self.empleados_por_etiqueta: Dict[str, Empleado] = {}
        self.empleado_actual: Optional[Empleado] = None
        self.ultima_liquidacion: Optional[Dict[str, Any]] = None
        self.vinculo_actual: str = VINCULO_POR_DEFECTO
        self.habilitado_recibo_actual: bool = False

        periodo_actual = datetime.now().strftime("%Y-%m")
        self.var_empleado = tk.StringVar()
        self.var_vinculo_estado = tk.StringVar(
            value=f"Vínculo: {VINCULO_POR_DEFECTO} — Presenta factura"
        )
        self.var_periodo = tk.StringVar(value=periodo_actual)
        self.var_sueldo_basico = tk.StringVar(value="0.00")
        self.var_antiguedad = tk.StringVar(value="0")
        self.var_horas_extra = tk.StringVar(value="0.00")
        self.var_feriados = tk.StringVar(value="0.00")
        self.var_ventas = tk.StringVar(value="0.00")
        self.var_adelanto = tk.StringVar(value="0.00")

        self.var_aplica_presentismo = tk.BooleanVar(value=True)
        self.var_aplica_jubilacion = tk.BooleanVar(value=True)
        self.var_aplica_pami = tk.BooleanVar(value=True)
        self.var_aplica_obra_social = tk.BooleanVar(value=True)
        self.var_aplica_sindicato = tk.BooleanVar(value=True)

        self.var_resumen_bruto = tk.StringVar(value="$ 0.00")
        self.var_resumen_deducciones = tk.StringVar(value="$ 0.00")
        self.var_resumen_neto = tk.StringVar(value="$ 0.00")

        self._construir_interfaz()
        self._aplicar_permisos_ui()
        self._cargar_empleados()
        self._cargar_historial()

    def _obtener_vinculo_empleado(self, emp: Optional[Empleado]) -> str:
        """Obtiene el tipo de vínculo del empleado; si no está informado o no existe, usa \x27Contratado\x27."""
        if emp is None:
            return VINCULO_POR_DEFECTO
        vinculo_raw = getattr(emp, "tipo_vinculo", None)
        if vinculo_raw is not None and str(vinculo_raw).strip():
            return normalizar_tipo_vinculo(vinculo_raw)
        id_emp = _a_int_seguro(getattr(emp, "id_empleado", None), 0)
        if id_emp > 0:
            try:
                return normalizar_tipo_vinculo(
                    RepositorioHaberes.obtener_tipo_vinculo_empleado(id_emp)
                )
            except _EXCEPCIONES_OPERACION:
                pass
        return VINCULO_POR_DEFECTO

    def _aplicar_permisos_ui(self) -> None:
        """Habilita o bloquea el cálculo y emisión de recibos según rol y tipo de vínculo."""
        permite_accion = bool(self.puede_liquidar and self.habilitado_recibo_actual)
        estado_liq = "normal" if permite_accion else "disabled"
        self.btn_calcular_guardar.config(state=estado_liq)
        if not permite_accion or not self.ultima_liquidacion:
            self.btn_emitir_recibo.config(state="disabled")
        else:
            self.btn_emitir_recibo.config(state="normal")

    def _construir_interfaz(self) -> None:
        """Construye el panel de liquidación, resumen e historial."""
        encabezado = ttk.Frame(self)
        encabezado.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(encabezado, text="Liquidación de Haberes").pack(anchor="w")
        ttk.Label(
            encabezado,
            text=(
                "Recibo de haberes exclusivo para vínculos \x27Pasante\x27 y \x27Permanente\x27; "
                "otros vínculos (por defecto \x27Contratado\x27) presentan factura."
            ),
        ).pack(anchor="w")

        frame_superior = ttk.Frame(self)
        frame_superior.pack(fill="x", padx=8, pady=4)
        frame_superior.columnconfigure(0, weight=1)
        frame_superior.columnconfigure(1, weight=1)

        frame_izq = ttk.LabelFrame(
            frame_superior, text=" Parámetros de Liquidación ", padding=10
        )
        frame_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        frame_izq.columnconfigure(1, weight=1)

        ttk.Label(frame_izq, text="Empleado:").grid(row=0, column=0, sticky="w", pady=3)
        self.combo_empleado = ttk.Combobox(
            frame_izq, textvariable=self.var_empleado, state="readonly"
        )
        self.combo_empleado.grid(row=0, column=1, sticky="ew", pady=3)
        self.combo_empleado.bind("<<ComboboxSelected>>", self._al_cambiar_empleado)

        ttk.Label(frame_izq, text="Modalidad / Vínculo:").grid(
            row=1, column=0, sticky="w", pady=3
        )
        self.lbl_vinculo_estado = ttk.Label(
            frame_izq, textvariable=self.var_vinculo_estado
        )
        self.lbl_vinculo_estado.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(frame_izq, text="Período (AAAA-MM):").grid(
            row=2, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_periodo).grid(
            row=2, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Sueldo Básico ($):").grid(
            row=3, column=0, sticky="w", pady=3
        )
        entry_basico = ttk.Entry(
            frame_izq, textvariable=self.var_sueldo_basico, state="readonly"
        )
        entry_basico.grid(row=3, column=1, sticky="ew", pady=3)

        ttk.Label(frame_izq, text="Antigüedad (años):").grid(
            row=4, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_antiguedad).grid(
            row=4, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Horas Extra ($):").grid(
            row=5, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_horas_extra).grid(
            row=5, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Feriados ($):").grid(
            row=6, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_feriados).grid(
            row=6, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Ventas / Comisiones ($):").grid(
            row=7, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_ventas).grid(
            row=7, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Adelanto de Haberes ($):").grid(
            row=8, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_adelanto).grid(
            row=8, column=1, sticky="ew", pady=3
        )

        frame_checks = ttk.Frame(frame_izq)
        frame_checks.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Checkbutton(
            frame_checks, text="Presentismo", variable=self.var_aplica_presentismo
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            frame_checks, text="Jubilación", variable=self.var_aplica_jubilacion
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            frame_checks, text="PAMI", variable=self.var_aplica_pami
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            frame_checks, text="Obra Social", variable=self.var_aplica_obra_social
        ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            frame_checks, text="Sindicato", variable=self.var_aplica_sindicato
        ).pack(side="left")

        frame_der = ttk.LabelFrame(
            frame_superior, text=" Resumen de Liquidación ", padding=10
        )
        frame_der.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        frame_der.columnconfigure(1, weight=1)

        ttk.Label(frame_der, text="Total Haberes / Bruto:").grid(
            row=0, column=0, sticky="w", pady=6
        )
        ttk.Label(frame_der, textvariable=self.var_resumen_bruto).grid(
            row=0, column=1, sticky="e", pady=6
        )

        ttk.Label(frame_der, text="Total Deducciones:").grid(
            row=1, column=0, sticky="w", pady=6
        )
        ttk.Label(frame_der, textvariable=self.var_resumen_deducciones).grid(
            row=1, column=1, sticky="e", pady=6
        )

        ttk.Label(frame_der, text="Neto a Cobrar:").grid(
            row=2, column=0, sticky="w", pady=6
        )
        ttk.Label(frame_der, textvariable=self.var_resumen_neto).grid(
            row=2, column=1, sticky="e", pady=6
        )

        frame_botones = ttk.Frame(frame_der)
        frame_botones.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        frame_botones.columnconfigure(0, weight=1)
        frame_botones.columnconfigure(1, weight=1)

        self.btn_calcular_guardar = ttk.Button(
            frame_botones,
            text="Calcular y Guardar",
            command=self._calcular_y_guardar,
        )
        self.btn_calcular_guardar.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_emitir_recibo = ttk.Button(
            frame_botones,
            text="Emitir / Ver Recibo",
            command=self._abrir_vista_previa_recibo,
            state="disabled",
        )
        self.btn_emitir_recibo.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        frame_hist = ttk.LabelFrame(
            self, text=" Historial de Liquidaciones ", padding=10
        )
        frame_hist.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        frame_hist.rowconfigure(0, weight=1)
        frame_hist.columnconfigure(0, weight=1)

        columnas = ("id", "empleado", "periodo", "bruto", "deducciones", "neto")
        self.tabla_hist = ttk.Treeview(
            frame_hist, columns=columnas, show="headings", height=6
        )
        self.tabla_hist.heading("id", text="ID")
        self.tabla_hist.heading("empleado", text="Empleado")
        self.tabla_hist.heading("periodo", text="Período")
        self.tabla_hist.heading("bruto", text="Bruto")
        self.tabla_hist.heading("deducciones", text="Deducciones")
        self.tabla_hist.heading("neto", text="Neto")

        self.tabla_hist.column("id", width=60, anchor="center")
        self.tabla_hist.column("empleado", width=240, anchor="w")
        self.tabla_hist.column("periodo", width=110, anchor="center")
        self.tabla_hist.column("bruto", width=130, anchor="e")
        self.tabla_hist.column("deducciones", width=130, anchor="e")
        self.tabla_hist.column("neto", width=130, anchor="e")

        scroll_y = ttk.Scrollbar(
            frame_hist, orient="vertical", command=self.tabla_hist.yview
        )
        self.tabla_hist.configure(yscrollcommand=scroll_y.set)
        self.tabla_hist.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")

    def _cargar_empleados(self) -> None:
        """Carga los empleados activos en el selector."""
        self.empleados_por_etiqueta.clear()
        try:
            empleados = RepositorioRRHH.listar_empleados(incluir_inactivos=False)
        except _EXCEPCIONES_OPERACION:
            empleados = []

        etiquetas: List[str] = []
        for emp in empleados:
            etiqueta = f"[{emp.legajo}] {emp.apellidos}, {emp.nombres}".strip()
            self.empleados_por_etiqueta[etiqueta] = emp
            etiquetas.append(etiqueta)

        self.combo_empleado["values"] = etiquetas
        if etiquetas:
            self.var_empleado.set(etiquetas[0])
            self._al_cambiar_empleado()
        else:
            self.empleado_actual = None
            self.vinculo_actual = VINCULO_POR_DEFECTO
            self.habilitado_recibo_actual = False
            self.var_vinculo_estado.set(
                f"Vínculo: {VINCULO_POR_DEFECTO} — Presenta factura"
            )
            self._aplicar_permisos_ui()

    def _al_cambiar_empleado(self, _event=None) -> None:
        """Actualiza sueldo básico y valida si el vínculo habilita recibo de haberes."""
        etiqueta = self.var_empleado.get()
        emp = self.empleados_por_etiqueta.get(etiqueta)
        self.empleado_actual = emp
        self.ultima_liquidacion = None
        self.var_resumen_bruto.set("$ 0.00")
        self.var_resumen_deducciones.set("$ 0.00")
        self.var_resumen_neto.set("$ 0.00")

        if emp is not None:
            sueldo = _a_float_seguro(getattr(emp, "sueldo", 0.0), 0.0)
            self.var_sueldo_basico.set(f"{sueldo:.2f}")
            vinculo = self._obtener_vinculo_empleado(emp)
        else:
            self.var_sueldo_basico.set("0.00")
            vinculo = VINCULO_POR_DEFECTO

        self.vinculo_actual = vinculo
        self.habilitado_recibo_actual = es_vinculo_recibo_haberes(vinculo)
        modalidad = obtener_modalidad_comprobante(vinculo)
        self.var_vinculo_estado.set(f"Vínculo: {vinculo} — {modalidad}")
        self._aplicar_permisos_ui()

    @staticmethod
    def _a_float(texto: str, nombre_campo: str) -> float:
        limpio = (texto or "").strip().replace(",", ".")
        if not limpio:
            return 0.0
        valor = float(limpio)
        if valor < 0:
            raise ValueError(f"\x27{nombre_campo}\x27 no puede ser negativo.")
        return valor

    @staticmethod
    def _a_int(texto: str, nombre_campo: str) -> int:
        limpio = (texto or "").strip()
        if not limpio:
            return 0
        valor = int(limpio)
        if valor < 0:
            raise ValueError(f"\x27{nombre_campo}\x27 no puede ser negativo.")
        return valor

    def _calcular_y_guardar(self) -> None:
        """Calcula los haberes, persiste la liquidación y habilita la emisión del recibo."""
        if not self.puede_liquidar:
            messagebox.showwarning(
                "Acceso Restringido",
                "Tu rol actual no tiene permisos para liquidar haberes.",
                parent=self,
            )
            return

        if not self.empleado_actual or not self.empleado_actual.id_empleado:
            messagebox.showwarning(
                "Empleado Requerido",
                "Seleccione un empleado válido antes de liquidar.",
                parent=self,
            )
            return

        vinculo = self._obtener_vinculo_empleado(self.empleado_actual)
        self.vinculo_actual = vinculo
        self.habilitado_recibo_actual = es_vinculo_recibo_haberes(vinculo)
        self._aplicar_permisos_ui()

        if not self.habilitado_recibo_actual:
            messagebox.showinfo(
                "Presenta Factura",
                (
                    f"El vínculo actual es \x27{vinculo}\x27: presenta factura y no emite "
                    "recibo de haberes. Solo \x27Pasante\x27 y \x27Permanente\x27 acceden al "
                    "formulario de recibo de haberes."
                ),
                parent=self,
            )
            return

        periodo = self.var_periodo.get().strip()
        if not periodo:
            messagebox.showwarning(
                "Período Requerido",
                "Ingrese el período de liquidación (ej. 2026-11).",
                parent=self,
            )
            return

        try:
            basico = self._a_float(self.var_sueldo_basico.get(), "Sueldo Básico")
            antiguedad = self._a_int(self.var_antiguedad.get(), "Antigüedad")
            horas_extra = self._a_float(self.var_horas_extra.get(), "Horas Extra")
            feriados = self._a_float(self.var_feriados.get(), "Feriados")
            ventas = self._a_float(self.var_ventas.get(), "Ventas")
            adelanto = self._a_float(self.var_adelanto.get(), "Adelanto de Haberes")
        except ValueError as exc:
            messagebox.showwarning("Dato Inválido", str(exc), parent=self)
            return

        try:
            repo = RepositorioHaberes()
            res = repo.calcular_liquidacion(
                id_empleado=_a_int_seguro(self.empleado_actual.id_empleado, 0),
                periodo=periodo,
                basico=basico,
                antiguedad_anios=antiguedad,
                aplica_presentismo=bool(self.var_aplica_presentismo.get()),
                horas_extra=horas_extra,
                feriados=feriados,
                ventas=ventas,
                adelanto=adelanto,
                aplica_jubilacion=bool(self.var_aplica_jubilacion.get()),
                aplica_pami=bool(self.var_aplica_pami.get()),
                aplica_obra_social=bool(self.var_aplica_obra_social.get()),
                aplica_sindicato=bool(self.var_aplica_sindicato.get()),
                tipo_vinculo=vinculo,
                persistir=True,
            )
            datos_liq = res if isinstance(res, dict) else {}

            if not bool(datos_liq.get("emite_recibo", True)):
                messagebox.showinfo(
                    "Presenta Factura",
                    f"El vínculo \x27{vinculo}\x27 presenta factura y no emite recibo de haberes.",
                    parent=self,
                )
                return

            bruto_base = basico + horas_extra + feriados + ventas
            bruto_raw = (
                datos_liq.get("remunerativo")
                if "remunerativo" in datos_liq
                else datos_liq.get(
                    "bruto", datos_liq.get("total_remunerativo", bruto_base)
                )
            )
            bruto = _a_float_seguro(bruto_raw, respaldo=bruto_base)

            ded_raw = (
                datos_liq.get("descuentos")
                if "descuentos" in datos_liq
                else datos_liq.get(
                    "deducciones", datos_liq.get("total_deducciones", adelanto)
                )
            )
            deducciones = _a_float_seguro(ded_raw, respaldo=adelanto)

            neto_base = bruto - deducciones
            neto_raw = (
                datos_liq.get("neto")
                if "neto" in datos_liq
                else datos_liq.get("neto_a_cobrar", neto_base)
            )
            neto = _a_float_seguro(neto_raw, respaldo=neto_base)

            self.ultima_liquidacion = {
                "empleado": self.empleado_actual,
                "tipo_vinculo": vinculo,
                "periodo": periodo,
                "sueldo_basico": basico,
                "antiguedad_anios": antiguedad,
                "horas_extra": horas_extra,
                "feriados": feriados,
                "ventas": ventas,
                "adelanto": adelanto,
                "bruto": bruto,
                "deducciones": deducciones,
                "neto": neto,
                "detalle": datos_liq,
            }

            self.var_resumen_bruto.set(f"$ {bruto:,.2f}")
            self.var_resumen_deducciones.set(f"$ {deducciones:,.2f}")
            self.var_resumen_neto.set(f"$ {neto:,.2f}")
            self.btn_emitir_recibo.config(state="normal")
            self._cargar_historial()

            messagebox.showinfo(
                "Liquidación Guardada",
                f"Liquidación registrada para {self.empleado_actual.legajo} ({periodo}).",
                parent=self,
            )
        except _EXCEPCIONES_OPERACION as exc:
            messagebox.showerror(
                "Error en Liquidación",
                f"No se pudo calcular o guardar la liquidación: {exc}",
                parent=self,
            )

    def _cargar_historial(self) -> None:
        """Recarga la tabla del historial de liquidaciones."""
        for fila in self.tabla_hist.get_children():
            self.tabla_hist.delete(fila)

        try:
            repo = RepositorioHaberes()
            registros = repo.listar_liquidaciones()
        except _EXCEPCIONES_OPERACION:
            registros = []

        for reg in registros:
            if isinstance(reg, dict):
                id_liq = reg.get("id_liquidacion", reg.get("id", ""))
                emp_txt = reg.get("empleado", reg.get("id_empleado", ""))
                periodo = reg.get("periodo", "")
                bruto = _a_float_seguro(
                    reg.get("bruto", reg.get("total_remunerativo", 0.0)), 0.0
                )
                ded = _a_float_seguro(
                    reg.get("deducciones", reg.get("total_deducciones", 0.0)), 0.0
                )
                neto = _a_float_seguro(
                    reg.get("neto", reg.get("neto_a_cobrar", 0.0)), 0.0
                )
            else:
                id_liq = getattr(reg, "id_liquidacion", getattr(reg, "id", ""))
                emp_txt = getattr(reg, "empleado", getattr(reg, "id_empleado", ""))
                periodo = getattr(reg, "periodo", "")
                bruto = _a_float_seguro(
                    getattr(reg, "bruto", getattr(reg, "total_remunerativo", 0.0)), 0.0
                )
                ded = _a_float_seguro(
                    getattr(reg, "deducciones", getattr(reg, "total_deducciones", 0.0)),
                    0.0,
                )
                neto = _a_float_seguro(
                    getattr(reg, "neto", getattr(reg, "neto_a_cobrar", 0.0)), 0.0
                )

            self.tabla_hist.insert(
                "",
                "end",
                values=(
                    id_liq,
                    emp_txt,
                    periodo,
                    f"$ {bruto:,.2f}",
                    f"$ {ded:,.2f}",
                    f"$ {neto:,.2f}",
                ),
            )

    def _formatear_lineas_recibo(self, liq: Dict[str, Any]) -> List[str]:
        emp: Empleado = liq["empleado"]
        vinculo = str(liq.get("tipo_vinculo") or self._obtener_vinculo_empleado(emp))
        periodo: str = str(liq.get("periodo", ""))

        basico_val = _a_float_seguro(liq.get("sueldo_basico", 0.0), 0.0)
        horas_extra_val = _a_float_seguro(liq.get("horas_extra", 0.0), 0.0)
        feriados_val = _a_float_seguro(liq.get("feriados", 0.0), 0.0)
        ventas_val = _a_float_seguro(liq.get("ventas", 0.0), 0.0)
        adelanto_val = _a_float_seguro(liq.get("adelanto", 0.0), 0.0)
        bruto_val = _a_float_seguro(liq.get("bruto", 0.0), 0.0)
        deducciones_val = _a_float_seguro(liq.get("deducciones", 0.0), 0.0)
        neto_val = _a_float_seguro(liq.get("neto", 0.0), 0.0)

        return [
            "================================================================",
            "          FRANKIE GESTOR COMERCIAL - RECIBO DE HABERES          ",
            "                      Ley 20.744 - Comprobante de Pago          ",
            "================================================================",
            f" Legajo: {emp.legajo:<12} Período: {periodo}",
            f" Empleado: {emp.apellidos}, {emp.nombres}",
            f" Vínculo: {vinculo:<12} Cargo: {emp.cargo}",
            f" CUIL/Doc: {emp.nro_documento}",
            "----------------------------------------------------------------",
            " CONCEPTO                                  HABERES   DEDUCCIONES",
            "----------------------------------------------------------------",
            f" Sueldo Básico                         $ {basico_val:>10,.2f}",
            f" Horas Extra                           $ {horas_extra_val:>10,.2f}",
            f" Feriados                              $ {feriados_val:>10,.2f}",
            f" Ventas / Comisiones                   $ {ventas_val:>10,.2f}",
            f" Adelanto de Haberes                               $ {adelanto_val:>10,.2f}",
            "----------------------------------------------------------------",
            f" TOTAL BRUTO                           $ {bruto_val:>10,.2f}",
            f" TOTAL DEDUCCIONES                                 $ {deducciones_val:>10,.2f}",
            f" NETO A COBRAR                         $ {neto_val:>10,.2f}",
            "================================================================",
        ]

    def _abrir_vista_previa_recibo(self) -> None:
        """
        Abre la vista previa del recibo sin escribir archivos en disco por sí sola;
        exporta HTML o genera PDF únicamente al pulsar el botón correspondiente.
        """
        if not self.ultima_liquidacion:
            messagebox.showwarning(
                "Sin Liquidación",
                "Primero calcule y guarde una liquidación.",
                parent=self,
            )
            return

        liq = self.ultima_liquidacion
        emp: Empleado = liq["empleado"]
        vinculo = str(liq.get("tipo_vinculo") or self._obtener_vinculo_empleado(emp))
        if not es_vinculo_recibo_haberes(vinculo):
            messagebox.showinfo(
                "Presenta Factura",
                f"El vínculo \x27{vinculo}\x27 presenta factura y no emite recibo de haberes.",
                parent=self,
            )
            return

        periodo: str = str(liq.get("periodo", ""))
        lineas_recibo = self._formatear_lineas_recibo(liq)
        texto_recibo = "\n".join(lineas_recibo)

        modal = tk.Toplevel(self)
        modal.title(f"Recibo de Haberes - {emp.legajo} ({periodo})")
        modal.geometry("700x480")
        modal.transient(self.winfo_toplevel())

        txt_vista = tk.Text(modal, wrap="none", padx=12, pady=12)
        txt_vista.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt_vista.insert("1.0", texto_recibo)
        txt_vista.config(state="disabled")

        def _exportar_html() -> None:
            try:
                archivo_html = obtener_ruta_recibo_html(emp.legajo, periodo)
                archivo_html.parent.mkdir(parents=True, exist_ok=True)
                recibo_escapado = html.escape(texto_recibo)
                html_contenido = (
                    "<!DOCTYPE html>\n"
                    "<html lang=\x27es\x27>\n"
                    "<head>\n"
                    "<meta charset=\x27utf-8\x27>\n"
                    f"<title>Recibo {html.escape(str(emp.legajo))} - {html.escape(periodo)}</title>\n"
                    "<style>\n"
                    "  body { font-family: monospace; background: #f1f5f9; padding: 20px; }\n"
                    "  .recibo { background: #fff; border: 2px solid #0f172a; padding: 25px; "
                    "max-width: 720px; margin: auto; white-space: pre; }\n"
                    "</style>\n"
                    "</head>\n"
                    "<body>\n"
                    f"  <div class=\x27recibo\x27>{recibo_escapado}</div>\n"
                    "</body>\n"
                    "</html>\n"
                )
                archivo_html.write_text(html_contenido, encoding="utf-8")
                messagebox.showinfo(
                    "Recibo HTML Exportado",
                    f"Comprobante HTML guardado en:\n{archivo_html}",
                    parent=modal,
                )
            except _EXCEPCIONES_OPERACION as exc:
                messagebox.showerror(
                    "Error al Exportar HTML",
                    f"No se pudo guardar el recibo HTML: {exc}",
                    parent=modal,
                )

        def _imprimir_exportar_pdf() -> None:
            try:
                archivo_pdf = obtener_ruta_recibo_pdf(emp.legajo, periodo)
                _exportar_pdf_desde_lineas(lineas_recibo, archivo_pdf)
                messagebox.showinfo(
                    "PDF Generado",
                    f"Recibo PDF generado en:\n{archivo_pdf}",
                    parent=modal,
                )
            except _EXCEPCIONES_OPERACION as exc:
                messagebox.showerror(
                    "Error al Generar PDF",
                    f"No se pudo generar el recibo PDF: {exc}",
                    parent=modal,
                )

        frame_acciones_modal = ttk.Frame(modal)
        frame_acciones_modal.pack(pady=(0, 10))
        ttk.Button(
            frame_acciones_modal, text="Exportar HTML", command=_exportar_html
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            frame_acciones_modal, text="Imprimir / Exportar PDF", command=_imprimir_exportar_pdf
        ).pack(side="left")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor Comercial - Liquidación de Haberes")
    root.geometry("1120x720")
    vista = InterfazHaberes(root)
    vista.pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()
