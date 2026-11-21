"""
===============================================================================
MÓDULO DE INTERFAZ DE USUARIO: LIQUIDACIÓN DE HABERES (vistas/ui_haberes.py)
===============================================================================
Calcula haberes remunerativos y no remunerativos, deducciones de ley,
persiste la liquidación en SQLite y permite previsualizar y exportar el recibo
HTML dentro de comprobantes/recibo_haberes/ en la raíz del proyecto.
===============================================================================
"""

from datetime import datetime
from pathlib import Path
import re
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from dominio.entidades_rrhh import Empleado
from infraestructura.repo_haberes import RepositorioHaberes
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


def _obtener_carpeta_recibos_haberes() -> Path:
    """Resuelve siempre comprobantes/recibo_haberes dentro de la raíz del proyecto."""
    raiz_proyecto = Path(__file__).resolve().parent.parent
    if _DIR_RECIBOS_CFG:
        ruta = Path(_DIR_RECIBOS_CFG)
        carpeta = ruta if ruta.is_absolute() else (raiz_proyecto / ruta)
    else:
        carpeta = raiz_proyecto / "comprobantes" / "recibo_haberes"
    carpeta.mkdir(parents=True, exist_ok=True)
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


class InterfazHaberes(ttk.Frame):
    """Componente visual modular basado en ttk.Frame para la Liquidación de Haberes."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        if callable(aplicar_estilos_base):
            try:
                aplicar_estilos_base(self)
            except _EXCEPCIONES_UI:
                pass

        self.empleados_por_etiqueta: Dict[str, Empleado] = {}
        self.empleado_actual: Optional[Empleado] = None
        self.ultima_liquidacion: Optional[Dict[str, Any]] = None

        periodo_actual = datetime.now().strftime("%Y-%m")
        self.var_empleado = tk.StringVar()
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
        self._cargar_empleados()
        self._cargar_historial()

    def _construir_interfaz(self) -> None:
        """Construye el panel de liquidación, barra lateral derecha e historial."""
        encabezado = ttk.Frame(self)
        encabezado.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(encabezado, text="Liquidación de Haberes").pack(anchor="w")
        ttk.Label(
            encabezado,
            text="Cálculo remunerativo, deducciones de ley y emisión de recibos oficiales",
        ).pack(anchor="w")

        frame_superior = ttk.Frame(self)
        frame_superior.pack(fill="x", padx=8, pady=4)
        frame_superior.columnconfigure(0, weight=1)
        frame_superior.columnconfigure(1, weight=1)

        frame_izq = ttk.LabelFrame(frame_superior, text=" Parámetros de Liquidación ", padding=10)
        frame_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        frame_izq.columnconfigure(1, weight=1)

        ttk.Label(frame_izq, text="Empleado:").grid(row=0, column=0, sticky="w", pady=3)
        self.combo_empleado = ttk.Combobox(
            frame_izq, textvariable=self.var_empleado, state="readonly"
        )
        self.combo_empleado.grid(row=0, column=1, sticky="ew", pady=3)
        self.combo_empleado.bind("<<ComboboxSelected>>", self._al_cambiar_empleado)

        ttk.Label(frame_izq, text="Período (AAAA-MM):").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(frame_izq, textvariable=self.var_periodo).grid(
            row=1, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Sueldo Básico ($):").grid(row=2, column=0, sticky="w", pady=3)
        entry_basico = ttk.Entry(
            frame_izq, textvariable=self.var_sueldo_basico, state="readonly"
        )
        entry_basico.grid(row=2, column=1, sticky="ew", pady=3)

        ttk.Label(frame_izq, text="Antigüedad (años):").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(frame_izq, textvariable=self.var_antiguedad).grid(
            row=3, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Horas Extra ($):").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(frame_izq, textvariable=self.var_horas_extra).grid(
            row=4, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Feriados ($):").grid(row=5, column=0, sticky="w", pady=3)
        ttk.Entry(frame_izq, textvariable=self.var_feriados).grid(
            row=5, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Ventas / Comisiones ($):").grid(
            row=6, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_ventas).grid(
            row=6, column=1, sticky="ew", pady=3
        )

        ttk.Label(frame_izq, text="Adelanto de Haberes ($):").grid(
            row=7, column=0, sticky="w", pady=3
        )
        ttk.Entry(frame_izq, textvariable=self.var_adelanto).grid(
            row=7, column=1, sticky="ew", pady=3
        )

        frame_checks = ttk.Frame(frame_izq)
        frame_checks.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 2))
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

        frame_der = ttk.LabelFrame(frame_superior, text=" Resumen de Liquidación ", padding=10)
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

        ttk.Button(
            frame_botones,
            text="Calcular y Guardar",
            command=self._calcular_y_guardar,
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_emitir_recibo = ttk.Button(
            frame_botones,
            text="Emitir / Ver Recibo",
            command=self._abrir_vista_previa_recibo,
            state="disabled",
        )
        self.btn_emitir_recibo.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        frame_hist = ttk.LabelFrame(self, text=" Historial de Liquidaciones ", padding=10)
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

    def _al_cambiar_empleado(self, _event=None) -> None:
        """Actualiza el sueldo básico mostrado según el empleado seleccionado."""
        etiqueta = self.var_empleado.get()
        emp = self.empleados_por_etiqueta.get(etiqueta)
        self.empleado_actual = emp
        if emp is not None:
            sueldo = float(getattr(emp, "sueldo", 0.0) or 0.0)
            self.var_sueldo_basico.set(f"{sueldo:.2f}")
        else:
            self.var_sueldo_basico.set("0.00")

    @staticmethod
    def _a_float(texto: str, nombre_campo: str) -> float:
        limpio = (texto or "").strip().replace(",", ".")
        if not limpio:
            return 0.0
        valor = float(limpio)
        if valor < 0:
            raise ValueError(f"'{nombre_campo}' no puede ser negativo.")
        return valor

    @staticmethod
    def _a_int(texto: str, nombre_campo: str) -> int:
        limpio = (texto or "").strip()
        if not limpio:
            return 0
        valor = int(limpio)
        if valor < 0:
            raise ValueError(f"'{nombre_campo}' no puede ser negativo.")
        return valor

    def _calcular_y_guardar(self) -> None:
        """Calcula los haberes, persiste la liquidación y habilita la emisión del recibo."""
        if not self.empleado_actual or not self.empleado_actual.id_empleado:
            messagebox.showwarning(
                "Empleado Requerido",
                "Seleccione un empleado válido antes de liquidar.",
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
                id_empleado=self.empleado_actual.id_empleado,
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
            )
            datos_liq = res if isinstance(res, dict) else {}
            bruto = float(
                datos_liq.get(
                    "bruto",
                    datos_liq.get("total_remunerativo", basico + horas_extra + feriados + ventas),
                )
                or 0.0
            )
            deducciones = float(
                datos_liq.get(
                    "deducciones",
                    datos_liq.get("total_deducciones", adelanto),
                )
                or 0.0
            )
            neto = float(
                datos_liq.get(
                    "neto",
                    datos_liq.get("neto_a_cobrar", bruto - deducciones),
                )
                or 0.0
            )

            self.ultima_liquidacion = {
                "empleado": self.empleado_actual,
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
                bruto = float(
                    reg.get("bruto", reg.get("total_remunerativo", 0.0)) or 0.0
                )
                ded = float(
                    reg.get("deducciones", reg.get("total_deducciones", 0.0)) or 0.0
                )
                neto = float(
                    reg.get("neto", reg.get("neto_a_cobrar", 0.0)) or 0.0
                )
            else:
                id_liq = getattr(reg, "id_liquidacion", getattr(reg, "id", ""))
                emp_txt = getattr(reg, "empleado", getattr(reg, "id_empleado", ""))
                periodo = getattr(reg, "periodo", "")
                bruto = float(
                    getattr(reg, "bruto", getattr(reg, "total_remunerativo", 0.0)) or 0.0
                )
                ded = float(
                    getattr(reg, "deducciones", getattr(reg, "total_deducciones", 0.0))
                    or 0.0
                )
                neto = float(
                    getattr(reg, "neto", getattr(reg, "neto_a_cobrar", 0.0)) or 0.0
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

    def _abrir_vista_previa_recibo(self) -> None:
        """Despliega una ventana modal con el recibo oficial y permite exportarlo a HTML."""
        if not self.ultima_liquidacion:
            messagebox.showwarning(
                "Sin Liquidación",
                "Primero calcule y guarde una liquidación.",
                parent=self,
            )
            return

        liq = self.ultima_liquidacion
        emp: Empleado = liq["empleado"]
        periodo: str = liq["periodo"]

        texto_recibo = (
            "================================================================\n"
            "                 FRANKIE GESTOR S.R.L. - RECIBO DE HABERES              \n"
            "                      Ley 20.744 - Comprobante de Pago                  \n"
            "================================================================\n"
            f" Legajo: {emp.legajo:<12} Período: {periodo}\n"
            f" Empleado: {emp.apellidos}, {emp.nombres}\n"
            f" CUIL/Doc: {emp.nro_documento}   Cargo: {emp.cargo}\n"
            "----------------------------------------------------------------\n"
            " CONCEPTO                                  HABERES         DEDUCCIONES  \n"
            "----------------------------------------------------------------\n"
            f" Sueldo Básico                         $ {float(liq.get('sueldo_basico', 0.0)):>10,.2f}\n"
            f" Horas Extra                           $ {float(liq.get('horas_extra', 0.0)):>10,.2f}\n"
            f" Feriados                              $ {float(liq.get('feriados', 0.0)):>10,.2f}\n"
            f" Ventas / Comisiones                   $ {float(liq.get('ventas', 0.0)):>10,.2f}\n"
            f" Adelanto de Haberes                                        $ {float(liq.get('adelanto', 0.0)):>10,.2f}\n"
            "----------------------------------------------------------------\n"
            f" TOTAL BRUTO                           $ {float(liq.get('bruto', 0.0)):>10,.2f}\n"
            f" TOTAL DEDUCCIONES                                          $ {float(liq.get('deducciones', 0.0)):>10,.2f}\n"
            f" NETO A COBRAR                         $ {float(liq.get('neto', 0.0)):>10,.2f}\n"
            "================================================================\n"
        )

        modal = tk.Toplevel(self)
        modal.title(f"Recibo de Haberes - {emp.legajo} ({periodo})")
        modal.geometry("680x460")
        modal.transient(self.winfo_toplevel())

        txt_vista = tk.Text(modal, wrap="none", padx=12, pady=12)
        txt_vista.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        txt_vista.insert("1.0", texto_recibo)
        txt_vista.config(state="disabled")

        def _exportar_html() -> None:
            archivo_html = obtener_ruta_recibo_html(emp.legajo, periodo)
            html_contenido = f"""<!DOCTYPE html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<title>Recibo {emp.legajo} - {periodo}</title>
<style>
  body {{ font-family: monospace; background: #f1f5f9; padding: 20px; }}
  .recibo {{ background: #fff; border: 2px solid #0f172a; padding: 25px; max-width: 720px; margin: auto; white-space: pre; }}
</style>
</head>
<body>
  <div class='recibo'>{texto_recibo}</div>
</body>
</html>
"""
            archivo_html.write_text(html_contenido, encoding="utf-8")
            messagebox.showinfo(
                "Recibo Exportado",
                f"Comprobante guardado en:\n{archivo_html}",
                parent=modal,
            )

        ttk.Button(modal, text="Exportar HTML", command=_exportar_html).pack(
            pady=(0, 10)
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Frankie Gestor - Liquidación de Haberes")
    root.geometry("1120x720")
    vista = InterfazHaberes(root)
    vista.pack(fill="both", expand=True, padx=10, pady=10)
    root.mainloop()