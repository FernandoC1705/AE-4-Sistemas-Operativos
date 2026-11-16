"""Interfaz gráfica (Tkinter) del simulador de Sistemas Operativos.

Pensada para usarse sin manual:
  * botones por módulo (①…⑤) que cargan un escenario de ejemplo;
  * tabla de procesos y estados siempre visible, con leyenda de colores;
  * cuadro "¿Qué pasó en este paso?" que narra cada evento en palabras;
  * paso / paso atrás / automático / hasta el final, con atajos de teclado;
  * línea de tiempo por proceso, memoria, tablas de páginas/segmentos/TLB, swap y métricas explicadas;
  * pestañas que sólo aparecen si tienen sentido para el módulo elegido;
  * comparador de políticas que indica cuál rindió mejor; ayuda integrada (F1).
"""
from __future__ import annotations

import colorsys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import models as M
from core.compare import LABELS, PARAM_COLUMNS, compare, default_values
from core.engine import Simulation
from core.memory import ContiguousManager, SegmentationManager
from core.models import Config, Process
from core.paging import PagingManager
from core.scenario import SCENARIO_DIR, list_scenarios, load_scenario, save_scenario
from . import help_text as H
from .demo_scripts import DEMOS

FONT_SCALE = 1.0


def fnt(size, *style):
    """Fuente escalable (modo proyector = letra grande)."""
    return ("TkDefaultFont", max(6, round(size * FONT_SCALE)), *style)

STATE_COLORS = {
    M.NEW: "#e8e8e8", M.WAIT_MEM: "#ffe0b2", M.READY: "#c8e6c9", M.RUNNING: "#81c784",
    M.BLOCKED: "#ffcdd2", M.WAIT_PAGE: "#f8bbd0", M.DONE: "#bbdefb", M.REJECTED: "#d7ccc8",
}
STATE_HELP = {
    M.NEW: "todavía no llegó", M.WAIT_MEM: "no hay memoria para cargarlo", M.READY: "espera su turno de CPU",
    M.RUNNING: "usando la CPU", M.BLOCKED: "esperando una E/S", M.WAIT_PAGE: "esperando una página desde swap",
    M.DONE: "terminó", M.REJECTED: "no cabe en el sistema",
}
LANE_CODES = {"R": M.RUNNING, "L": M.READY, "B": M.BLOCKED, "P": M.WAIT_PAGE, "M": M.WAIT_MEM}

MODULES = [("① Planificación de CPU", "01_planificacion"), ("② Memoria continua", "02_memoria_continua"),
           ("③ Paginación · TLB · swap", "03_paginacion_tlb_swap"), ("④ Segmentación", "05_segmentacion"),
           ("⑤ Comparar los 3 modelos", "06_comparacion_modelos")]
LIVE_KEYS = {"scheduler", "quantum", "fit", "tlb_policy", "repl_policy"}
HIGHER_IS_BETTER = {"tlb_hit", "cpu_uso", "ocupacion_prom", "throughput", "terminados", "mem_ocupacion"}
MAIN_METRIC = {"scheduler": "espera_prom", "quantum": "respuesta_prom", "fit": "espera_mem_prom", "repl_policy": "fallos_pagina",
               "tlb_policy": "tlb_hit", "tlb_size": "tlb_hit", "page_size": "eat_ns", "mem_size": "fallos_pagina", "mode": "retorno_prom"}


def pid_color(pid):
    h = (pid * 0.173) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.45, 0.95)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class Tooltip:
    """Globito de ayuda al pasar el mouse."""

    def __init__(self, widget, text, delay=450):
        self.w, self.text, self.delay, self.tip, self.job = widget, text, delay, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _e):
        self.job = self.w.after(self.delay, self._show)

    def _leave(self, _e=None):
        if self.job:
            self.w.after_cancel(self.job)
            self.job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def _show(self):
        if self.tip or not self.text:
            return
        x, y = self.w.winfo_rootx() + 12, self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", wraplength=340, background="#ffffe0", relief="solid",
                 borderwidth=1, padx=6, pady=3).pack()


class App(tk.Tk):
    def __init__(self, scenario_path=None):
        super().__init__()
        self.title("Simulador de Sistemas Operativos")
        self.geometry("1400x900")
        self.minsize(1150, 720)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Big.TButton", font=fnt(10, "bold"), padding=(10, 5))
        style.configure("Toolbutton", padding=(10, 6), font=fnt(10, "bold"))
        style.map("Toolbutton", background=[("selected", "#3f7fbf")], foreground=[("selected", "white")])
        self.cfg = Config()
        self.base_procs: list[Process] = []
        self.meta = {"name": "", "description": ""}
        self.scn_stem = ""
        self.sim: Simulation | None = None
        self.auto_job = None
        self.vars: dict[str, tk.Variable] = {}
        self.dirty = False
        self._building = True
        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._building = False
        if scenario_path:
            self.load_path(scenario_path)
        else:
            self.load_path(SCENARIO_DIR / "01_planificacion.json")

    # ================================================================== menú
    def _build_menu(self):
        mb = tk.Menu(self)
        f = tk.Menu(mb, tearoff=0)
        f.add_command(label="Abrir escenario…", command=self.open_file)
        f.add_command(label="Guardar escenario…", command=self.save_file)
        f.add_separator()
        f.add_command(label="Salir", command=self.destroy)
        mb.add_cascade(label="Archivo", menu=f)
        v = tk.Menu(mb, tearoff=0)
        self.big_var = tk.BooleanVar(value=False)
        v.add_checkbutton(label="Letra grande (modo proyector)", variable=self.big_var, command=self.toggle_big_font)
        mb.add_cascade(label="Ver", menu=v)
        dm = tk.Menu(mb, tearoff=0)
        dm.add_command(label="Iniciar demo guiada de este módulo (D)", command=self.start_demo)
        mb.add_cascade(label="Demo", menu=dm)
        a = tk.Menu(mb, tearoff=0)
        a.add_command(label="Guía rápida (F1)", command=lambda: self.show_text("Guía rápida", H.GUIDE))
        a.add_command(label="Glosario", command=lambda: self.show_text("Glosario", H.GLOSSARY))
        a.add_command(label="Atajos de teclado", command=lambda: self.show_text("Atajos de teclado", H.SHORTCUTS))
        mb.add_cascade(label="Ayuda", menu=a)
        self.config(menu=mb)

    def show_text(self, title, text):
        d = tk.Toplevel(self)
        d.title(title)
        d.geometry("760x560")
        t = tk.Text(d, wrap="word", padx=12, pady=10, font=fnt(10))
        sb = ttk.Scrollbar(d, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.insert("1.0", text)
        t.configure(state="disabled")

    # ================================================================== teclado
    def _bind_keys(self):
        def guard(fn):
            def h(e):
                if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text, ttk.Spinbox)):
                    return
                fn()
                return "break"
            return h
        for key, fn in [("<space>", self.do_step), ("<Right>", self.do_step), ("<Left>", self.step_back),
                        ("a", self.toggle_auto), ("e", self.run_all), ("r", self.reset),
                        ("c", self.compare_dialog), ("n", self.new_process_dialog), ("d", self.start_demo)]:
            self.bind(key, guard(fn))
        self.bind("<F1>", lambda e: self.show_text("Guía rápida", H.GUIDE))

    # ================================================================== construcción de la UI
    def _build_ui(self):
        self._build_modules_bar()
        self._build_banner()
        self._build_toolbar()
        self._build_demo_bar()
        self._build_narrator()
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=2)
        left = ttk.Frame(body, width=370)
        body.add(left, weight=0)
        right = ttk.Frame(body)
        body.add(right, weight=1)
        self._build_config(left)
        self._build_right(right)
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=(8, 2),
                  font=fnt(10, "bold")).pack(fill="x", side="bottom")

    def _build_modules_bar(self):
        bar = ttk.Frame(self, padding=(6, 6, 6, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="¿Qué querés ver?", font=fnt(10, "bold")).pack(side="left", padx=(0, 8))
        self.module_var = tk.StringVar()
        for text, stem in MODULES:
            rb = ttk.Radiobutton(bar, text=text, value=stem, variable=self.module_var, style="Toolbutton",
                                 command=lambda s=stem: self.pick_scenario(SCENARIO_DIR / f"{s}.json"))
            rb.pack(side="left", padx=2)
        ttk.Label(bar, text="  Otros:").pack(side="left")
        self.scn_var = tk.StringVar()
        cb = ttk.Combobox(bar, textvariable=self.scn_var, state="readonly", width=30,
                          values=[p.stem for p in list_scenarios()])
        cb.pack(side="left", padx=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.pick_scenario(SCENARIO_DIR / f"{self.scn_var.get()}.json"))
        Tooltip(cb, "Todos los escenarios de la carpeta scenarios (incluye la cadena de Belady).")
        b = ttk.Button(bar, text="Abrir…", command=self.open_file)
        b.pack(side="left", padx=2)
        Tooltip(b, "Abrir un escenario .json propio.")
        b = ttk.Button(bar, text="? Ayuda", command=lambda: self.show_text("Guía rápida", H.GUIDE))
        b.pack(side="right", padx=2)
        Tooltip(b, "Guía rápida (F1)")

    def _build_banner(self):
        self.banner = tk.Label(self, text="", justify="left", anchor="w", bg="#fff8dc", fg="#5a4a00", padx=10, pady=4,
                               wraplength=1300, font=fnt(9))
        self.banner.pack(fill="x", padx=6, pady=(4, 0))
        self.bind("<Configure>", lambda e: self.banner.configure(wraplength=max(300, self.winfo_width() - 40))
                  if e.widget is self else None)

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(6, 6, 6, 2))
        bar.pack(fill="x")
        self.toolbar = bar
        items = [("⟲ Reiniciar", self.reset, "Volver al instante 0 con los parámetros del panel (R)"),
                 ("◀ Atrás", self.step_back, "Retroceder un instante (vuelve a simular desde 0, el resultado es idéntico) (←)"),
                 ("▶ Paso", self.do_step, "Avanzar un instante de tiempo (barra espaciadora o →)")]
        for text, cmd, tip in items:
            b = ttk.Button(bar, text=text, command=cmd, style="Big.TButton")
            b.pack(side="left", padx=2)
            Tooltip(b, tip)
        self.auto_btn = ttk.Button(bar, text="⏵ Automático", command=self.toggle_auto, style="Big.TButton")
        self.auto_btn.pack(side="left", padx=2)
        Tooltip(self.auto_btn, "Avanza solo; apretalo de nuevo para pausar (A)")
        b = ttk.Button(bar, text="⏭ Hasta el final", command=self.run_all, style="Big.TButton")
        b.pack(side="left", padx=2)
        Tooltip(b, "Ejecuta toda la simulación de una vez y muestra el resultado (E)")
        ttk.Label(bar, text="  🐢").pack(side="left")
        self.speed = tk.IntVar(value=500)
        sc = ttk.Scale(bar, from_=1200, to=40, variable=self.speed, length=110)
        sc.pack(side="left")
        ttk.Label(bar, text="🐇").pack(side="left")
        Tooltip(sc, "Velocidad del modo automático")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        b = ttk.Button(bar, text="＋ Nuevo proceso", command=self.new_process_dialog)
        b.pack(side="left", padx=2)
        Tooltip(b, "Agregar un proceso mientras corre la simulación (N)")
        b = ttk.Button(bar, text="⚖ Comparar políticas", command=self.compare_dialog)
        b.pack(side="left", padx=2)
        Tooltip(b, "Corre el mismo escenario con distintas políticas y muestra cuál rinde mejor (C)")
        b = ttk.Button(bar, text="🎬 Demo guiada", command=self.start_demo, style="Big.TButton")
        b.pack(side="left", padx=(10, 2))
        Tooltip(b, "Recorrido paso a paso de este módulo con explicaciones en pantalla, ideal para mostrarle al profe (D)")
        self.time_lbl = tk.StringVar(value="Tiempo: 0")
        ttk.Label(bar, textvariable=self.time_lbl, font=fnt(14, "bold")).pack(side="right", padx=10)

    def _build_narrator(self):
        box = ttk.LabelFrame(self, text="¿Qué pasó en este paso?", padding=(6, 2))
        box.pack(fill="x", padx=6, pady=2)
        self.narr_box = box
        self.narr = tk.Label(box, text=H.INTRO, justify="left", anchor="w", font=fnt(10), wraplength=1300)
        self.narr.pack(fill="x")
        self.narr.bind("<Configure>", lambda e: self.narr.configure(wraplength=max(300, e.width - 10)))

    # ---------------------------------------------------------------- panel de configuración
    def _build_config(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=3, pady=3)
        self.apply_btn = tk.Button(top, text="Aplicar y reiniciar", command=self.reset, relief="raised", bd=2,
                                   font=fnt(10, "bold"), pady=4)
        self.apply_btn.pack(fill="x")
        self.apply_hint = ttk.Label(top, text="Los campos con ⚡ se aplican al instante.", foreground="#666",
                                    wraplength=320, font=fnt(8))
        self.apply_hint.pack(fill="x")
        canvas = tk.Canvas(parent, width=360, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.groups = {}

        def group(key, title):
            f = ttk.LabelFrame(inner, text=title, padding=4)
            self.groups[key] = f
            return f

        def row(f, key, label, kind="entry", values=None, live=None, width=10):
            r = ttk.Frame(f)
            r.pack(fill="x", pady=1)
            lab = ttk.Label(r, text=("⚡ " if key in LIVE_KEYS else "") + label, width=22, anchor="w")
            lab.pack(side="left")
            if kind == "combo":
                v = tk.StringVar()
                w = ttk.Combobox(r, textvariable=v, values=values, state="readonly", width=width)
                if live:
                    w.bind("<<ComboboxSelected>>", lambda e, k=key: live(k))
            elif kind == "check":
                v = tk.BooleanVar()
                w = ttk.Checkbutton(r, variable=v)
            else:
                v = tk.StringVar()
                w = ttk.Entry(r, textvariable=v, width=width)
                if live:
                    w.bind("<Return>", lambda e, k=key: live(k))
                    w.bind("<FocusOut>", lambda e, k=key: live(k))
            w.pack(side="left")
            self.vars[key] = v
            v.trace_add("write", lambda *a, k=key: self._on_var(k))
            tip = H.FIELD_HELP.get(key, "")
            Tooltip(lab, tip)
            Tooltip(w, tip)

        g = group("mode", "1 · Módulo")
        row(g, "mode", "Qué se simula", "combo", list(M.MODES.values()), live=lambda k: self.on_mode_change(), width=22)
        g = group("cpu", "2 · Planificación de CPU")
        row(g, "scheduler", "Algoritmo", "combo", M.SCHEDULERS, live=self.live_change)
        row(g, "quantum", "Quantum (sólo RR)", live=self.live_change, width=6)
        g = group("mem", "3 · Memoria")
        row(g, "mem_size", "Memoria física (bytes)", width=8)
        row(g, "fit", "Política de ajuste", "combo", [M.FIT_NAMES[f] for f in M.FITS], live=self.live_change)
        row(g, "partition", "Particiones", "combo", ["variable", "fixed"], width=8)
        row(g, "fixed_partitions", "Tamaños (si fijas)", width=18)
        row(g, "auto_compact", "Compactar automáticamente", "check")
        b = ttk.Button(g, text="Compactar ahora", command=self.compact_now)
        b.pack(anchor="w", pady=2)
        Tooltip(b, "Junta todos los bloques ocupados hacia el inicio de la memoria.")
        g = group("paging", "4 · Paginación, TLB y swap")
        row(g, "page_size", "Tamaño de página (bytes)", width=6)
        row(g, "tlb_size", "Entradas de TLB (0=sin)", width=6)
        row(g, "tlb_policy", "Reemplazo en TLB", "combo", M.REPL_POLICIES, live=self.live_change, width=8)
        row(g, "repl_policy", "Reemplazo de páginas", "combo", M.REPL_POLICIES, live=self.live_change, width=8)
        row(g, "swap_size", "Área de swap (bytes)", width=8)
        row(g, "tlb_flush_on_switch", "Vaciar TLB al cambiar ctx", "check")
        # opciones avanzadas (ocultas por defecto)
        self.adv_var = tk.BooleanVar(value=False)
        self.adv_chk = ttk.Checkbutton(inner, text="Mostrar opciones avanzadas (tiempos, generación de accesos)",
                                       variable=self.adv_var, command=self.update_groups)
        g = group("times", "Avanzado · Tiempos (para EAT) y fallos")
        row(g, "t_tlb", "Acceso a TLB (ns)", width=8)
        row(g, "t_mem", "Acceso a memoria (ns)", width=8)
        row(g, "t_fault", "Transfer. swap (ns)", width=8)
        row(g, "swap_in_ticks", "Ticks carga de página", width=6)
        row(g, "swap_out_ticks", "Ticks extra por swap-out", width=6)
        g = group("gen", "Avanzado · Generación de accesos")
        row(g, "seed", "Semilla", width=6)
        row(g, "locality", "Localidad (0-1)", width=6)
        row(g, "write_prob", "Prob. escritura (0-1)", width=6)
        self.inner_cfg = inner

    # ---------------------------------------------------------------- panel derecho
    def _build_right(self, parent):
        box = ttk.LabelFrame(parent, text="Tabla de procesos y estados (se actualiza en cada paso)", padding=3)
        box.pack(fill="x")
        cols = [("pid", "PID", 40), ("nombre", "Nombre", 70), ("estado", "Estado", 130), ("llegada", "Llegada", 62),
                ("rafaga", "Ráfaga", 58), ("restante", "Restante", 68), ("tamano", "Tamaño", 58),
                ("memoria", "Memoria asignada", 190), ("espera", "Espera", 58), ("esp_mem", "Esp.mem", 62),
                ("bloq", "Bloq.", 50), ("fallos", "Fallos", 52), ("retorno", "Retorno", 62), ("nota", "Nota", 150)]
        self.ptree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", height=6)
        for k, h, w in cols:
            self.ptree.heading(k, text=h)
            self.ptree.column(k, width=w, anchor="w" if k in ("memoria", "nota", "estado") else "center",
                              stretch=k in ("memoria", "nota"))
        for st, col in STATE_COLORS.items():
            self.ptree.tag_configure(st, background=col)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.ptree.yview)
        self.ptree.configure(yscrollcommand=sb.set)
        self.ptree.pack(side="top", fill="x", expand=True)
        leg = ttk.Frame(box)
        leg.pack(side="bottom", fill="x", pady=(3, 0))
        ttk.Label(leg, text="Estados:").pack(side="left", padx=(0, 4))
        for st, col in STATE_COLORS.items():
            l = tk.Label(leg, text=st, bg=col, padx=5, pady=1, font=fnt(8))
            l.pack(side="left", padx=2)
            Tooltip(l, f"{st}: {STATE_HELP[st]}")
        q = ttk.LabelFrame(parent, text="Colas", padding=3)
        q.pack(fill="x", pady=2)
        self.queue_var = tk.StringVar()
        ttk.Label(q, textvariable=self.queue_var, justify="left", wraplength=1000).pack(anchor="w")
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)
        self.tabs = {}
        self._tab_explain()
        self._tab_gantt()
        self._tab_memory()
        self._tab_tables()
        self._tab_swap()
        self._tab_metrics()
        self._tab_manual()
        self._tab_log()

    def _add_tab(self, key, title):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=title)
        self.tabs[key] = f
        return f

    def _tab_explain(self):
        f = self._add_tab("explain", "¿Cómo funciona?")
        self.explain = tk.Text(f, wrap="word", padx=14, pady=10, relief="flat", bg="#fbfbf7", cursor="arrow")
        sb = ttk.Scrollbar(f, command=self.explain.yview)
        self.explain.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.explain.pack(fill="both", expand=True)

    def update_explain(self, mode):
        t = self.explain
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.tag_configure("h", font=fnt(11, "bold"), foreground="#1f3a5f", spacing1=10, spacing3=3)
        t.tag_configure("p", font=fnt(10), spacing3=2)
        paras, cur = [], ""
        for line in H.EXPLAIN.get(mode, "").split("\n"):
            if line.startswith("## "):
                if cur:
                    paras.append(("p", cur)); cur = ""
                paras.append(("h", line[3:]))
            elif not line.strip():
                if cur:
                    paras.append(("p", cur)); cur = ""
            elif cur and cur[-1] not in ".:;)?!":      # una oración cortada a mitad: se une con la siguiente línea
                cur += " " + line
            else:
                if cur:
                    paras.append(("p", cur))
                cur = line
        if cur:
            paras.append(("p", cur))
        for tag, text in paras:
            t.insert("end", text + "\n", tag)
        t.configure(state="disabled")

    def _tab_gantt(self):
        f = self._add_tab("gantt", "Gantt y tiempos")
        self.gantt = tk.Canvas(f, bg="white", highlightthickness=0)
        hb = ttk.Scrollbar(f, orient="horizontal", command=self.gantt.xview)
        vb = ttk.Scrollbar(f, orient="vertical", command=self.gantt.yview)
        self.gantt.configure(xscrollcommand=hb.set, yscrollcommand=vb.set)
        hb.pack(side="bottom", fill="x")
        vb.pack(side="right", fill="y")
        self.gantt.pack(fill="both", expand=True, padx=4, pady=4)
        leg = ttk.Frame(f)
        leg.pack(side="bottom", fill="x", pady=2)
        ttk.Label(leg, text="Línea de tiempo:").pack(side="left", padx=4)
        for code, st in LANE_CODES.items():
            tk.Label(leg, text=st, bg=STATE_COLORS[st], padx=5, font=fnt(8)).pack(side="left", padx=2)
        self.gantt_summary = ttk.Label(f, text="", justify="left")
        self.gantt_summary.pack(side="bottom", anchor="w", padx=6)

    def _tab_memory(self):
        f = self._add_tab("memory", "Memoria")
        self.mem_canvas = tk.Canvas(f, bg="white", height=250, highlightthickness=0)
        self.mem_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.mem_canvas.bind("<Configure>", lambda e: self.draw_memory())
        self.mem_info = ttk.Label(f, text="", justify="left", wraplength=1000)
        self.mem_info.pack(anchor="w", padx=6, pady=2)
        cols = [("ini", "Inicio", 70), ("fin", "Fin", 70), ("tam", "Tamaño", 70), ("dueno", "Ocupado por", 150), ("uso", "Bytes usados", 90)]
        self.blocks_tree = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings", height=6)
        for k, h, w in cols:
            self.blocks_tree.heading(k, text=h)
            self.blocks_tree.column(k, width=w, anchor="center")
        self.blocks_tree.pack(fill="x", padx=4, pady=2)

    def _tab_tables(self):
        f = self._add_tab("tables", "Tablas y TLB")
        top = ttk.Frame(f)
        top.pack(fill="x", padx=4, pady=3)
        ttk.Label(top, text="Ver las tablas del proceso:").pack(side="left")
        self.sel_proc = tk.StringVar()
        self.sel_box = ttk.Combobox(top, textvariable=self.sel_proc, state="readonly", width=12)
        self.sel_box.pack(side="left", padx=4)
        self.sel_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_tables())
        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True)

        def mk(title, columns, width):
            lf = ttk.LabelFrame(cols, text=title, padding=3)
            lf.pack(side="left", fill="both", expand=True, padx=3)
            t = ttk.Treeview(lf, columns=[c[0] for c in columns], show="headings", height=14)
            for k, h in columns:
                t.heading(k, text=h)
                t.column(k, width=width, anchor="center")
            t.pack(fill="both", expand=True)
            return lf, t
        self.pt_frame, self.pt_tree = mk("Tabla de páginas / segmentos del proceso",
                                         [("a", "Página"), ("b", "Marco"), ("c", "Válida"), ("d", "Modif."), ("e", "Slot swap")], 70)
        self.tlb_frame, self.tlb_tree = mk("TLB (entradas actuales)", [("a", "Pos."), ("b", "Proceso"), ("c", "Página"), ("d", "Marco")], 70)
        self.rep_frame, self.rep_tree = mk("Orden de reemplazo de marcos (próxima víctima arriba)",
                                           [("a", "Orden"), ("b", "Proceso:Pág"), ("c", "Marco"), ("d", "Nota")], 80)

    def _tab_swap(self):
        f = self._add_tab("swap", "Swap")
        self.swap_canvas = tk.Canvas(f, bg="white", highlightthickness=0)
        self.swap_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.swap_canvas.bind("<Configure>", lambda e: self.draw_swap())
        self.swap_info = ttk.Label(f, text="", wraplength=1000)
        self.swap_info.pack(anchor="w", padx=6)

    def _tab_metrics(self):
        f = self._add_tab("metrics", "Métricas")
        self.mtree = ttk.Treeview(f, columns=("k", "v", "h"), show="headings", height=22)
        for k, h, w, a in [("k", "Métrica", 230, "w"), ("v", "Valor", 100, "e"), ("h", "¿Qué significa?", 380, "w")]:
            self.mtree.heading(k, text=h)
            self.mtree.column(k, width=w, anchor=a)
        self.mtree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.ptree2 = ttk.Treeview(f, columns=("n", "r", "e", "m", "b", "f"), show="headings", height=22)
        for k, h, w in [("n", "Proceso", 70), ("r", "Retorno", 65), ("e", "Espera (Listo)", 95), ("m", "Espera mem.", 85),
                        ("b", "Bloqueado", 75), ("f", "Fallos pág.", 75)]:
            self.ptree2.heading(k, text=h)
            self.ptree2.column(k, width=w, anchor="center")
        self.ptree2.pack(side="left", fill="y", padx=4, pady=4)

    def _tab_manual(self):
        f = self._add_tab("manual", "Acceso manual")
        self.man_help = ttk.Label(f, justify="left", wraplength=900)
        self.man_help.pack(anchor="w", padx=8, pady=8)
        r = ttk.Frame(f)
        r.pack(anchor="w", padx=8)
        ttk.Label(r, text="Proceso:").pack(side="left")
        self.man_proc = tk.StringVar()
        self.man_box = ttk.Combobox(r, textvariable=self.man_proc, state="readonly", width=10)
        self.man_box.pack(side="left", padx=(2, 10))
        self.man_a_lbl = ttk.Label(r, text="Dirección lógica:")
        self.man_a_lbl.pack(side="left")
        self.man_a = tk.StringVar(value="0")
        ttk.Entry(r, textvariable=self.man_a, width=7).pack(side="left", padx=(2, 10))
        self.man_b_frame = ttk.Frame(r)
        self.man_b_frame.pack(side="left")
        ttk.Label(self.man_b_frame, text="Desplazamiento:").pack(side="left")
        self.man_b = tk.StringVar(value="0")
        ttk.Entry(self.man_b_frame, textvariable=self.man_b, width=7).pack(side="left", padx=(2, 10))
        self.man_w = tk.BooleanVar()
        ttk.Checkbutton(r, text="Es escritura", variable=self.man_w).pack(side="left", padx=6)
        ttk.Button(r, text="Traducir esta dirección", command=self.manual_access, style="Big.TButton").pack(side="left", padx=6)
        r2 = ttk.Frame(f)
        r2.pack(anchor="w", padx=8, pady=8)
        self.man_quick = ttk.Button(r2, text="", command=self.manual_quick)
        self.man_quick.pack(side="left")
        self.man_out = tk.StringVar()
        tk.Label(f, textvariable=self.man_out, wraplength=900, justify="left", anchor="w", bg="#eef6ff", padx=10, pady=8,
                 font=fnt(10, "bold")).pack(fill="x", padx=8, pady=8)

    def _tab_log(self):
        f = self._add_tab("log", "Registro")
        self.log_text = tk.Text(f, height=12, wrap="none", font=("TkFixedFont", 9))
        sb = ttk.Scrollbar(f, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        self.log_count = 0

    # ================================================================== configuración <-> formulario
    MODE_BY_NAME = {v: k for k, v in M.MODES.items()}
    FIT_BY_NAME = {v: k for k, v in M.FIT_NAMES.items()}

    def _on_var(self, key):
        if self._building or key in LIVE_KEYS:
            return
        self.set_dirty(True)

    def set_dirty(self, d):
        self.dirty = d
        if d:
            self.apply_btn.configure(bg="#ff9800", activebackground="#ffb74d", text="⚠ Aplicar cambios y reiniciar")
        else:
            self.apply_btn.configure(bg="#e0e0e0", activebackground="#eeeeee", text="Aplicar y reiniciar")

    def cfg_to_form(self, cfg: Config):
        self._building = True
        for k, v in self.vars.items():
            val = getattr(cfg, k)
            if k == "mode":
                val = M.MODES[val]
            elif k == "fit":
                val = M.FIT_NAMES[val]
            elif k == "fixed_partitions":
                val = ",".join(map(str, val))
            v.set(val)
        self._building = False
        self.set_dirty(False)
        self.update_groups()

    def form_to_cfg(self) -> Config:
        d = {}
        names = {"mem_size": "Memoria física", "page_size": "Tamaño de página", "tlb_size": "Entradas de TLB", "swap_size": "Área de swap",
                 "quantum": "Quantum"}
        for k, v in self.vars.items():
            raw = v.get()
            try:
                if k == "mode":
                    d[k] = self.MODE_BY_NAME[raw]
                elif k == "fit":
                    d[k] = self.FIT_BY_NAME[raw]
                elif k == "fixed_partitions":
                    d[k] = [int(x) for x in str(raw).replace(";", ",").split(",") if x.strip()]
                elif k in ("auto_compact", "tlb_flush_on_switch"):
                    d[k] = bool(raw)
                elif k in ("locality", "write_prob"):
                    d[k] = float(str(raw).replace(",", "."))
                elif k in ("scheduler", "partition", "tlb_policy", "repl_policy"):
                    d[k] = str(raw)
                else:
                    d[k] = int(raw)
            except (ValueError, KeyError):
                raise ValueError(f"El campo «{names.get(k, k)}» tiene un valor inválido: {raw!r}. Ingresá un número entero (sin letras).")
        d["max_ticks"] = self.cfg.max_ticks
        return Config.from_dict(d)

    def update_groups(self):
        mode = self.MODE_BY_NAME.get(self.vars["mode"].get(), "none")
        adv = self.adv_var.get()
        show = {"mode": True, "cpu": True, "mem": mode in ("contiguous", "segmentation", "paging"),
                "paging": mode == "paging", "times": adv and mode == "paging", "gen": adv and mode in ("paging", "segmentation")}
        order = ["mode", "cpu", "mem", "paging"]
        for k in order + ["times", "gen"]:
            self.groups[k].pack_forget()
        self.adv_chk.pack_forget()
        for k in order:
            if show[k]:
                self.groups[k].pack(fill="x", padx=3, pady=3)
        if mode in ("paging", "segmentation"):
            self.adv_chk.pack(anchor="w", padx=6, pady=2)
            for k in ("times", "gen"):
                if show[k]:
                    self.groups[k].pack(fill="x", padx=3, pady=3)
        self.update_tabs(mode)
        self.update_explain(mode)

    def update_tabs(self, mode):
        vis = {"explain": True, "gantt": True, "memory": mode != "none", "tables": mode in ("paging", "segmentation"),
               "swap": mode == "paging", "metrics": True, "manual": mode in ("paging", "segmentation"), "log": True}
        for key, frame in self.tabs.items():
            self.nb.tab(frame, state="normal" if vis[key] else "hidden")
        cur = self.nb.select()
        if cur and str(self.nb.nametowidget(cur)) in [str(self.tabs[k]) for k, v in vis.items() if not v]:
            self.nb.select(self.tabs["gantt"])

    def on_mode_change(self):
        if self._building:
            return
        self.update_groups()
        self.set_dirty(True)
        self.module_var.set("")

    def live_change(self, key=None):
        """Cambios que se aplican sin reiniciar."""
        if self._building or self.sim is None:
            return
        try:
            if key == "scheduler":
                self.sim.set_scheduler(self.vars["scheduler"].get())
            elif key == "quantum":
                self.sim.set_quantum(int(self.vars["quantum"].get()))
            elif key in ("tlb_policy", "repl_policy"):
                self.sim.set_policies(tlb_policy=self.vars["tlb_policy"].get(), repl_policy=self.vars["repl_policy"].get())
            elif key == "fit":
                self.sim.set_fit(self.FIT_BY_NAME[self.vars["fit"].get()])
        except ValueError:
            messagebox.showerror("Valor inválido", "El quantum debe ser un número entero mayor o igual a 1.")
            return
        self.refresh()
        self.set_narrator("✔ Cambio aplicado en caliente: " + self.sim.events[-1][1] if self.sim.events else "")

    # ================================================================== escenarios
    def load_path(self, path):
        try:
            cfg, procs, meta = load_scenario(path)
        except Exception as e:
            messagebox.showerror("No se pudo abrir el escenario", str(e))
            return
        self.cfg, self.base_procs, self.meta = cfg, procs, meta
        self.scn_stem = Path(path).stem
        self.module_var.set(self.scn_stem if self.scn_stem in [s for _, s in MODULES] else "")
        self.scn_var.set(self.scn_stem)
        self.cfg_to_form(cfg)
        self.banner.configure(text=f"📘 {meta['name']}: {meta['description']}\n💡 {H.HINTS.get(self.scn_stem, H.DEFAULT_HINT)}")
        self.reset(from_form=False)
        self.title(f"Simulador de Sistemas Operativos – {meta['name']}")
        self.nb.select(self.tabs["memory"] if cfg.mode != "none" else self.tabs["gantt"])

    def open_file(self):
        p = filedialog.askopenfilename(initialdir=SCENARIO_DIR, filetypes=[("Escenario JSON", "*.json")])
        if p:
            self.pick_scenario(p)

    def pick_scenario(self, path):
        self.stop_demo()
        self.load_path(path)

    def save_file(self):
        p = filedialog.asksaveasfilename(initialdir=SCENARIO_DIR, defaultextension=".json", filetypes=[("Escenario JSON", "*.json")])
        if p:
            try:
                save_scenario(p, self.form_to_cfg(), self.base_procs, self.meta["name"], self.meta["description"])
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ================================================================== control de simulación
    def reset(self, from_form=True):
        self.stop_auto()
        try:
            cfg = self.form_to_cfg() if from_form else self.cfg
            self.sim = Simulation(cfg, self.base_procs)
            self.cfg = cfg
        except Exception as e:
            messagebox.showerror("Configuración inválida", str(e))
            return
        self.set_dirty(False)
        self.log_text.delete("1.0", "end")
        self.log_count = 0
        names = [p.name for p in self.sim.procs]
        for b in (self.sel_box, self.man_box):
            b["values"] = names
        if names:
            self.sel_proc.set(names[0])
            self.man_proc.set(names[0])
        self.man_out.set("")
        self.update_manual_help()
        self.refresh()
        self.set_narrator(H.INTRO)

    def do_step(self):
        if not self.sim:
            return
        if self.sim.finished:
            self.stop_auto()
            self.set_narrator("🏁 La simulación ya terminó. Mirá la pestaña Métricas, probá ⚖ Comparar políticas o ⟲ Reiniciar.")
            return
        self.sim.step()
        self.refresh()
        self.narrate()

    def step_back(self):
        """Retrocede un instante re-simulando desde 0 (el motor es determinista)."""
        if not self.sim or self.sim.t == 0:
            return
        self.stop_auto()
        target = self.sim.t - 1
        sim = Simulation(self.sim.cfg, self.base_procs)
        for _ in range(target):
            sim.step()
        self.sim = sim
        self.log_text.delete("1.0", "end")
        self.log_count = 0
        self.refresh()
        self.narrate(prefix="◀ (Retrocediste) ")

    def toggle_auto(self):
        if self.auto_job:
            self.stop_auto()
        else:
            self.auto_btn.configure(text="⏸ Pausa")
            self._auto_tick()

    def _auto_tick(self):
        if self.sim is None or self.sim.finished:
            self.stop_auto()
            self.narrate()
            return
        self.sim.step()
        self.refresh()
        self.narrate()
        self.auto_job = self.after(int(self.speed.get()), self._auto_tick)

    def stop_auto(self):
        if self.auto_job:
            self.after_cancel(self.auto_job)
            self.auto_job = None
        self.auto_btn.configure(text="⏵ Automático")

    def run_all(self):
        self.stop_auto()
        if self.sim:
            self.sim.run()
            self.refresh()
            self.set_narrator(f"🏁 Simulación terminada en el tiempo {self.sim.t}. Mirá la pestaña Métricas (cada una tiene su explicación) "
                              f"o apretá ⚖ Comparar políticas.")
            self.nb.select(self.tabs["metrics"])

    def compact_now(self):
        if self.sim:
            self.sim.compact()
            self.refresh()
            self.set_narrator("🧹 " + self.sim.events[-1][1])

    def set_narrator(self, text):
        self.narr.configure(text=text)

    def narrate(self, prefix=""):
        sim = self.sim
        evs = [e for e in sim.recent_events() if not e.startswith("Inicio:")]
        if not evs:
            txt = f"Tiempo {sim.t}: no pasó nada especial (la CPU sigue con el mismo proceso)."
        else:
            show = evs[:5]
            txt = "\n".join("• " + e for e in show) + (f"\n… y {len(evs) - 5} evento(s) más (ver Registro completo)" if len(evs) > 5 else "")
        if sim.finished:
            txt += "\n🏁 La simulación terminó. Mirá la pestaña Métricas o probá ⚖ Comparar políticas."
        self.set_narrator(prefix + txt)

    # ================================================================== demo guiada
    def _build_demo_bar(self):
        bg = "#1565c0"
        self.demo_bar = tk.Frame(self, bg=bg, padx=10, pady=6)
        top = tk.Frame(self.demo_bar, bg=bg)
        top.pack(fill="x")
        self.demo_count = tk.Label(top, bg=bg, fg="#bbdefb", font=fnt(9, "bold"))
        self.demo_count.pack(side="left")
        self.demo_title = tk.Label(top, bg=bg, fg="white", font=fnt(13, "bold"))
        self.demo_title.pack(side="left", padx=12)
        for text, cmd, color in [("✕ Cerrar demo", self.stop_demo, "#ef5350"), ("Siguiente ▶", lambda: self.demo_goto(self.demo_idx + 1), "#43a047"),
                                 ("◀ Anterior", lambda: self.demo_goto(self.demo_idx - 1), "#78909c")]:
            b = tk.Button(top, text=text, command=cmd, bg=color, fg="white", activebackground=color, bd=0, padx=12, pady=3,
                          font=fnt(10, "bold"))
            b.pack(side="right", padx=3)
            if text.startswith("Sig"):
                self.demo_next = b
            elif text.startswith("◀"):
                self.demo_prev = b
        self.demo_text = tk.Label(self.demo_bar, bg=bg, fg="white", justify="left", anchor="w", font=fnt(11), wraplength=1250)
        self.demo_text.pack(fill="x", pady=(4, 0))
        self.demo_text.bind("<Configure>", lambda e: self.demo_text.configure(wraplength=max(300, e.width - 10)))
        self.demo_idx = 0
        self._cmp = None

    def start_demo(self):
        if self.scn_stem not in DEMOS:
            messagebox.showinfo("Demo guiada", "Este escenario no tiene demo guiada. Elegí uno de los botones ①–⑤ (o el de Belady en “Otros”).")
            return
        self.demo_goto(0)

    def stop_demo(self):
        self.demo_bar.pack_forget()
        if self._cmp is not None:
            try:
                self._cmp.destroy()
            except tk.TclError:
                pass
            self._cmp = None

    def demo_goto(self, k):
        script = DEMOS.get(self.scn_stem)
        if not script:
            return
        steps = script["steps"]
        if k >= len(steps):
            self.stop_demo()
            self.set_narrator("🎬 Fin de la demo. Podés seguir jugando con los controles o elegir otro módulo arriba.")
            return
        k = max(0, k)
        self.demo_idx = k
        self.stop_auto()
        if self._cmp is not None:
            try:
                self._cmp.destroy()
            except tk.TclError:
                pass
            self._cmp = None
        self.load_path(SCENARIO_DIR / f"{self.scn_stem}.json")      # siempre se reproduce desde cero: es determinista
        for i in range(k + 1):
            for act in steps[i]["do"]:
                if act[0] == "compare" and i < k:
                    continue
                self.demo_do(act)
        st = steps[k]
        self.demo_count.configure(text=f"🎬 DEMO · {script['title']} · paso {k + 1} de {len(steps)}")
        self.demo_title.configure(text=st["title"])
        self.demo_text.configure(text=st["say"])
        self.demo_prev.configure(state="normal" if k > 0 else "disabled")
        self.demo_next.configure(text="✔ Finalizar" if k == len(steps) - 1 else "Siguiente ▶")
        self.demo_bar.pack(fill="x", padx=6, pady=2, before=self.narr_box)

    def set_form(self, key, value):
        if key == "mode":
            value = M.MODES[value]
        elif key == "fit":
            value = M.FIT_NAMES[value]
        self.vars[key].set(value)
        if key == "mode":
            self.update_groups()

    def demo_do(self, act):
        kind = act[0]
        if kind == "tab":
            if str(self.nb.tab(self.tabs[act[1]], "state")) == "normal":
                self.nb.select(self.tabs[act[1]])
        elif kind == "until":
            while self.sim.t < act[1] and not self.sim.finished:
                self.sim.step()
            self.refresh()
            self.narrate()
        elif kind == "run":
            self.sim.run()
            self.refresh()
            self.set_narrator(f"🏁 Simulación terminada en el tiempo {self.sim.t}.")
        elif kind == "reset":
            self.reset()
        elif kind == "form":
            for k, v in act[1].items():
                self.set_form(k, v)
        elif kind == "select":
            self.sel_proc.set(act[1])
            self.refresh_tables()
        elif kind == "manual":
            self.man_proc.set(act[1])
            self.manual_quick()
            self.set_narrator("🧪 " + self.man_out.get())
        elif kind == "compare":
            self._cmp = CompareWindow(self, self.form_to_cfg(), self.base_procs, initial=act[1])
            self._cmp.geometry("1080x640+60+60")

    # ================================================================== modo proyector
    def toggle_big_font(self):
        global FONT_SCALE
        on = self.big_var.get()
        FONT_SCALE = 1.25 if on else 1.0
        if not hasattr(self, "_base_fonts"):
            self._base_fonts = {n: tkfont.nametofont(n).cget("size") for n in
                                ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont", "TkCaptionFont")}
        for n, size in self._base_fonts.items():
            tkfont.nametofont(n).configure(size=round(size * FONT_SCALE))
        st = ttk.Style(self)
        st.configure("Treeview", rowheight=round(20 * FONT_SCALE))
        st.configure("Big.TButton", font=fnt(10, "bold"))
        st.configure("Toolbutton", font=fnt(10, "bold"))
        for lbl, f in [(self.demo_count, fnt(9, "bold")), (self.demo_title, fnt(13, "bold")), (self.demo_text, fnt(11))]:
            lbl.configure(font=f)
        self.banner.configure(font=fnt(9))
        if on:
            self.banner.pack_forget()          # en modo proyector se libera espacio: la demo ya explica
        else:
            self.banner.pack(fill="x", padx=6, pady=(4, 0), before=self.toolbar)
        self.update_explain(self.MODE_BY_NAME.get(self.vars["mode"].get(), "none"))
        if self.sim:
            self.refresh()
        try:
            self.state("zoomed") if on else self.state("normal")
        except tk.TclError:
            try:
                self.attributes("-zoomed", on)
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- acceso manual
    def update_manual_help(self):
        mode = self.cfg.mode
        if mode == "segmentation":
            self.man_a_lbl.configure(text="Segmento (0, 1, 2…):")
            self.man_b_frame.pack(side="left")
            self.man_help.configure(text=("Traducí una dirección a pedido. Elegí un proceso, el número de segmento (0 = primero) y el desplazamiento. "
                                          "Si el desplazamiento es mayor o igual al límite del segmento ocurre una VIOLACIÓN DE SEGMENTO y el proceso se aborta.\n"
                                          "Los procesos tienen que estar cargados en memoria (no en “Nuevo” ni “Esperando Memoria”)."))
            self.man_quick.configure(text="⚡ Forzar una violación de segmento")
        else:
            self.man_a_lbl.configure(text="Dirección lógica:")
            self.man_b_frame.pack_forget()
            self.man_help.configure(text=("Traducí una dirección lógica a pedido. Se calcula página = dirección ÷ tamaño de página, y desplazamiento = resto. "
                                          "Si la página no está en memoria ocurre un FALLO DE PÁGINA (se trae desde swap, pudiendo desalojar otra).\n"
                                          "El proceso tiene que estar admitido (avanzá hasta que llegue)."))
            self.man_quick.configure(text="⚡ Provocar un fallo de página")

    def _man_proc(self):
        return next((p for p in self.sim.procs if p.name == self.man_proc.get()), None)

    def manual_quick(self):
        p = self._man_proc()
        if not p or not self.sim:
            return
        if self.cfg.mode == "segmentation":
            if not p.blocks:
                self.man_out.set(f"{p.name} todavía no tiene segmentos en memoria (estado: {p.state}). Avanzá la simulación y probá de nuevo.")
                return
            self.man_a.set("0")
            self.man_b.set(str(p.blocks[0].size))
        else:
            if not p.page_table:
                self.man_out.set(f"{p.name} todavía no fue admitido (estado: {p.state}). Avanzá la simulación y probá de nuevo.")
                return
            ps = self.sim.mem.ps
            page = next((i for i, e in enumerate(p.page_table) if not e.valid and not e.loading), 0)
            self.man_a.set(str(page * ps))
        self.manual_access()

    def manual_access(self):
        if not self.sim:
            return
        p = self._man_proc()
        if p is None:
            return
        try:
            msg = self.sim.manual_access(p.pid, int(self.man_a.get()),
                                         int(self.man_b.get()) if self.cfg.mode == "segmentation" else None, self.man_w.get())
        except ValueError:
            msg = "Ingresá números enteros válidos."
        self.man_out.set(msg)
        self.refresh()

    # ================================================================== diálogos
    def new_process_dialog(self):
        if not self.sim:
            return
        d = tk.Toplevel(self)
        d.title("Nuevo proceso")
        d.transient(self)
        d.grab_set()
        mode = self.cfg.mode
        nxt = max([p.pid for p in self.sim.procs], default=0) + 1
        fields = [("name", "Nombre", f"P{nxt}", "Cómo se va a mostrar en las tablas."),
                  ("arrival", "Llegada (tick)", str(self.sim.t), "Instante en que aparece (no puede ser anterior al actual)."),
                  ("burst", "Ráfaga de CPU (ticks)", "6", "Cuánta CPU necesita en total.")]
        if mode == "segmentation":
            fields.append(("segments", "Segmentos", "codigo:200,datos:100,pila:50", "Formato nombre:tamaño separados por coma."))
        elif mode != "none":
            fields.append(("size", "Tamaño (bytes)", "200", "Memoria que necesita el proceso."))
        fields.append(("io", "E/S (opcional)", "", "Formato ticks_de_CPU:duración. Ej: 3:2 = tras 3 ticks de CPU se bloquea 2 ticks."))
        vs = {}
        for i, (k, lbl, dflt, tip) in enumerate(fields):
            ttk.Label(d, text=lbl).grid(row=i, column=0, sticky="w", padx=8, pady=3)
            vs[k] = tk.StringVar(value=dflt)
            e = ttk.Entry(d, textvariable=vs[k], width=30)
            e.grid(row=i, column=1, padx=8)
            ttk.Label(d, text=tip, foreground="#666", font=fnt(8), wraplength=240).grid(row=i, column=2, sticky="w", padx=4)

        def ok():
            try:
                segs = [(a.split(":")[0].strip(), int(a.split(":")[1])) for a in vs.get("segments", tk.StringVar()).get().split(",") if a.strip()]
                io = [(int(a.split(":")[0]), int(a.split(":")[1])) for a in vs["io"].get().split(",") if a.strip()]
                size = int(vs["size"].get()) if "size" in vs else 0
                p = Process(nxt, vs["name"].get(), int(vs["arrival"].get()), int(vs["burst"].get()), size=size, segments=segs, io=io)
                if p.burst < 1 or (mode != "none" and p.size < 1):
                    raise ValueError("La ráfaga y el tamaño deben ser mayores que cero.")
                self.sim.add_process(p)
                self.base_procs.append(Process(p.pid, p.name, p.arrival, p.burst, size=p.size, segments=segs, io=io))
            except Exception as e:
                messagebox.showerror("Datos inválidos", f"{e}\n\nRevisá los formatos indicados a la derecha de cada campo.", parent=d)
                return
            names = [q.name for q in self.sim.procs]
            self.sel_box["values"] = names
            self.man_box["values"] = names
            d.destroy()
            self.refresh()
            self.set_narrator(f"➕ Proceso {p.name} creado: llegará en el tiempo {p.arrival}.")
        ttk.Button(d, text="Crear proceso", command=ok, style="Big.TButton").grid(row=len(fields), column=0, columnspan=3, pady=10)
        d.bind("<Return>", lambda e: ok())

    def compare_dialog(self):
        if not self.sim:
            return
        try:
            cfg = self.form_to_cfg()
        except Exception as e:
            messagebox.showerror("Configuración inválida", str(e))
            return
        CompareWindow(self, cfg, self.base_procs)

    # ================================================================== refresco de vistas
    def refresh(self):
        sim = self.sim
        if sim is None:
            return
        self.time_lbl.set(f"Tiempo: {sim.t}")
        self.refresh_processes()
        q = sim.queues()
        self.queue_var.set("   |   ".join(f"{k}: [{', '.join(v) or '—'}]" for k, v in q.items()))
        self.draw_gantt()
        self.draw_memory()
        self.refresh_tables()
        self.draw_swap()
        self.refresh_metrics()
        self.refresh_log()
        self.refresh_status()

    def refresh_processes(self):
        rows = self.sim.process_rows()
        existing = self.ptree.get_children()
        if len(existing) != len(rows):
            self.ptree.delete(*existing)
            existing = [self.ptree.insert("", "end", iid=f"p{r['pid']}") for r in rows]
        for iid, r in zip(existing, rows):
            vals = [("-" if r[k] is None else r[k]) for k in self.ptree["columns"]]
            self.ptree.item(iid, values=vals, tags=(r["estado"],))

    def draw_gantt(self):
        c = self.gantt
        c.delete("all")
        sim = self.sim
        end = max(sim.t, 1)
        cw = 24 if end <= 50 else 14 if end <= 120 else 8
        x0, y0, h = 62, 34, 44
        c.create_text(8, 12, anchor="w", text="Diagrama de Gantt (quién usa la CPU)", font=fnt(9, "bold"))
        c.create_text(8, y0 + h / 2, anchor="w", text="CPU", font=fnt(9, "bold"))
        for s, e, pid in sim.gantt_segments():
            col = "#dddddd" if pid is None else pid_color(pid)
            c.create_rectangle(x0 + s * cw, y0, x0 + e * cw, y0 + h, fill=col, outline="#555")
            if pid is not None:
                nm = sim.by_pid(pid).name
                c.create_text(x0 + (s + e) * cw / 2, y0 + h / 2, text=nm if (e - s) * cw >= 8 * len(nm) + 6 else str(pid),
                              font=fnt(9, "bold"))
            else:
                c.create_text(x0 + (s + e) * cw / 2, y0 + h / 2, text="·", fill="#888")
        step = 1 if cw >= 14 else 5
        for t in range(end + 1):
            x = x0 + t * cw
            c.create_line(x, y0 + h, x, y0 + h + 5)
            if t % step == 0:
                c.create_text(x, y0 + h + 14, text=str(t), font=fnt(8))
        # línea de tiempo por proceso
        ly = y0 + h + 52
        c.create_text(8, ly - 12, anchor="w", text="Línea de tiempo por proceso (qué estaba haciendo cada uno en cada instante)", font=fnt(9, "bold"))
        for i, p in enumerate(sim.procs):
            y = ly + i * 22
            c.create_text(8, y + 9, anchor="w", text=p.name, font=fnt(9, "bold"))
            for t, code in enumerate(sim.history.get(p.pid, [])):
                if code:
                    c.create_rectangle(x0 + t * cw, y, x0 + (t + 1) * cw, y + 18, fill=STATE_COLORS[LANE_CODES[code]], outline="#999")
            if p.finish is not None and p.state == M.DONE:
                c.create_text(x0 + p.finish * cw + 4, y + 9, anchor="w", text="✔" if not p.reason else "✖", font=fnt(9, "bold"))
        c.configure(scrollregion=(0, 0, x0 + end * cw + 50, ly + len(sim.procs) * 22 + 20))
        c.xview_moveto(1.0)
        done = [p for p in sim.procs if p.state == M.DONE and not p.reason]
        extra = f"Cambios de contexto: {sim.ctx_switches}.   " if sim.ctx_switches else ""
        self.gantt_summary.configure(text=extra + "   ".join(f"{p.name}: retorno={p.turnaround}, espera={p.wait_ready}" for p in done))

    # -------- memoria
    def draw_memory(self):
        c = self.mem_canvas
        c.delete("all")
        sim = self.sim
        self.blocks_tree.delete(*self.blocks_tree.get_children())
        if sim is None or sim.mem is None:
            c.create_text(20, 20, anchor="w", text="Este módulo sólo simula la planificación de CPU (no hay memoria).")
            self.mem_info.configure(text="")
            return
        mem = sim.mem
        W = max(c.winfo_width(), 400)
        if isinstance(mem, PagingManager):
            cols = max(1, (W - 20) // 92)
            for f in range(mem.n_frames):
                x, y = 10 + (f % cols) * 92, 10 + (f // cols) * 62
                key = mem.owner.get(f)
                if key is None:
                    c.create_rectangle(x, y, x + 88, y + 56, fill="#f4f4f4", outline="#999", dash=(3, 2))
                    c.create_text(x + 44, y + 22, text=f"marco {f}", font=fnt(8), fill="#888")
                    c.create_text(x + 44, y + 40, text="libre", fill="#888")
                else:
                    pte = sim.by_pid(key[0]).page_table[key[1]]
                    c.create_rectangle(x, y, x + 88, y + 56, fill=pid_color(key[0]), outline="#333", width=2 if pte.loading else 1)
                    c.create_text(x + 44, y + 12, text=f"marco {f}", font=fnt(8))
                    c.create_text(x + 44, y + 30, text=f"{sim.by_pid(key[0]).name}: pág {key[1]}", font=fnt(9, "bold"))
                    note = ("⏳ cargando" if pte.loading else "") + (" ✎ modif." if pte.dirty else "")
                    c.create_text(x + 44, y + 46, text=note.strip(), font=fnt(8))
            st = mem.stats()
            self.mem_info.configure(text=(
                f"Cada cuadro es un marco de {mem.ps} bytes (color = proceso dueño). ⏳ = página llegando desde swap, ✎ = modificada (hay que escribirla a swap al sacarla).\n"
                f"Marcos: {st['frames_used']}/{st['frames_total']} ocupados ({st['occupancy']:.1f}%) | libre: {st['free']} B | "
                f"fragmentación interna: {st['int_frag']:.1f}% | fragmentación externa: 0% (paginación)"))
            return
        total = mem.map.total
        scale = (W - 30) / total
        y, h = 40, 90
        for b in mem.map.blocks:
            x1, x2 = 15 + b.start * scale, 15 + b.end * scale
            if b.free:
                c.create_rectangle(x1, y, x2, y + h, fill="#f4f4f4", outline="#777", dash=(4, 3))
                c.create_text((x1 + x2) / 2, y + h / 2, text=f"libre\n{b.size}", fill="#777", font=fnt(8))
            else:
                pr = sim.by_pid(b.pid)
                c.create_rectangle(x1, y, x2, y + h, fill=pid_color(b.pid), outline="#333")
                lab = f"{pr.name}\n{b.label}\n{b.size}" if mem.kind == "segmentation" else f"{pr.name}\n{b.size}"
                if mem.map.fixed and b.size > b.used:
                    lab += f"\n(usa {b.used})"
                c.create_text((x1 + x2) / 2, y + h / 2, text=lab, font=fnt(8, "bold"))
            self.blocks_tree.insert("", "end", values=(b.start, b.end, b.size, "libre" if b.free else
                                    f"{sim.by_pid(b.pid).name}" + (f" ({b.label})" if b.label and mem.kind == 'segmentation' else ""),
                                    "-" if b.free else b.used))
        for a in range(0, total + 1, max(1, total // 10)):
            c.create_text(15 + a * scale, y + h + 12, text=str(a), font=fnt(8))
        c.create_text(15, 15, anchor="w", text=f"Mapa de memoria ({total} bytes) – {'particiones fijas' if mem.map.fixed else 'particiones variables'}"
                      f" – {M.FIT_NAMES[mem.fit]}", font=fnt(10, "bold"))
        wait = ", ".join(f"{p.name} ({p.size} B)" for p in sim.wait_mem) or "—"
        c.create_text(15, y + h + 40, anchor="w", text=f"Cola de espera de memoria: {wait}")
        st = mem.stats()
        self.mem_info.configure(text=(
            f"Ocupada: {st['used']} B ({st['occupancy']:.1f}%) | libre: {st['free']} B en {st['holes']} hueco(s) | "
            f"mayor bloque libre: {st['largest_free']} B | fragmentación externa: {st['ext_frag']:.1f}% | "
            f"fragmentación interna: {st['int_frag']:.1f}% | compactaciones: {st['compactions']}"))

    # -------- tablas de páginas / segmentos / TLB
    def refresh_tables(self):
        sim = self.sim
        for t in (self.pt_tree, self.tlb_tree, self.rep_tree):
            t.delete(*t.get_children())
        if sim is None or sim.mem is None:
            return
        p = next((q for q in sim.procs if q.name == self.sel_proc.get()), None)
        mem = sim.mem
        if isinstance(mem, PagingManager):
            self._set_headings(self.pt_tree, ["Página", "Marco", "Válida", "Modif.", "Slot swap"])
            self.pt_frame.configure(text="Tabla de páginas del proceso elegido")
            if p:
                for i, e in enumerate(p.page_table):
                    self.pt_tree.insert("", "end", values=(i, "-" if e.frame is None else e.frame,
                                        "sí" if e.valid else ("cargando" if e.loading else "no"), "sí" if e.dirty else "no", e.swap_slot))
            for i, (k, f) in enumerate(mem.tlb.items()):
                self.tlb_tree.insert("", "end", values=(i, f"{sim.by_pid(k[0]).name}", k[1], f))
            self.tlb_frame.configure(text=f"TLB ({len(mem.tlb)}/{mem.tlb_size}) – política {mem.tlb_policy.name}")
            self.rep_frame.configure(text=f"Orden de reemplazo de marcos – {mem.frame_policy.name}")
            for i, (k, note) in enumerate(mem.frame_policy.describe()):
                self.rep_tree.insert("", "end", values=(i, f"{sim.by_pid(k[0]).name}:{k[1]}", mem.resident.get(k), note))
        elif isinstance(mem, SegmentationManager):
            self._set_headings(self.pt_tree, ["Segmento", "Base", "Límite", "Fin", "Nombre"])
            self.pt_frame.configure(text="Tabla de segmentos del proceso elegido (base, límite)")
            if p:
                for i, (nm, base, lim) in enumerate(mem.seg_table(p)):
                    self.pt_tree.insert("", "end", values=(i, base, lim, base + lim - 1, nm))
            self.tlb_frame.configure(text="TLB (no aplica en segmentación pura)")
            self.rep_frame.configure(text="Violaciones de segmento")
            for q in sim.procs:
                if q.violations:
                    self.rep_tree.insert("", "end", values=("", q.name, "", f"{q.violations} violación(es)"))

    @staticmethod
    def _set_headings(tree, names):
        for k, n in zip(tree["columns"], names):
            tree.heading(k, text=n)

    # -------- swap
    def draw_swap(self):
        c = self.swap_canvas
        c.delete("all")
        sim = self.sim
        if sim is None or not isinstance(sim.mem, PagingManager):
            self.swap_info.configure(text="")
            return
        mem = sim.mem
        W = max(c.winfo_width(), 400)
        cols = max(1, (W - 20) // 62)
        for s in range(mem.swap_slots):
            x, y = 10 + (s % cols) * 62, 10 + (s // cols) * 38
            key = mem.swap_owner.get(s)
            if key is None:
                c.create_rectangle(x, y, x + 58, y + 34, fill="#f4f4f4", outline="#bbb")
                c.create_text(x + 29, y + 17, text=f"#{s}", fill="#aaa", font=fnt(8))
            else:
                res = key in mem.resident
                c.create_rectangle(x, y, x + 58, y + 34, fill=pid_color(key[0]) if not res else "#ffffff", outline="#333", dash=(2, 2) if res else None)
                c.create_text(x + 29, y + 11, text=f"{sim.by_pid(key[0]).name}:{key[1]}", font=fnt(8, "bold"))
                c.create_text(x + 29, y + 25, text="en RAM" if res else "en swap", font=fnt(7))
        st = mem.stats()
        self.swap_info.configure(text=(
            f"Cada cuadro es un lugar del área de swap reservado para una página de un proceso (pintado = sólo está en swap; punteado = tiene copia en RAM).\n"
            f"Slots usados: {st['swap_used']}/{st['swap_total']} | páginas traídas (swap-in): {mem.swap_in} | páginas escritas (swap-out): {mem.swap_out} | "
            f"tráfico total: {(mem.swap_in + mem.swap_out) * mem.ps} B"))

    # -------- métricas / registro / estado
    def refresh_metrics(self):
        m = self.sim.metrics()
        self.mtree.delete(*self.mtree.get_children())
        order = ["tiempo", "cpu_uso", "cambios_contexto", "terminados", "abortados", "rechazados", "espera_prom",
                 "retorno_prom", "respuesta_prom", "throughput", "mem_ocupacion", "ocupacion_prom", "mem_libre", "mayor_libre",
                 "frag_externa", "frag_ext_prom", "frag_ext_max", "frag_interna", "frag_int_prom", "espera_mem_prom",
                 "compactaciones", "accesos", "fallos_pagina", "tasa_fallos", "tlb_hit", "tlb_miss", "eat_ns", "swap_in",
                 "swap_out", "swap_trafico", "reemplazos", "violaciones"]
        for k in order:
            if k in m:
                v = m[k]
                self.mtree.insert("", "end", values=(LABELS.get(k, k), f"{v:.2f}" if isinstance(v, float) else v, H.METRIC_HELP.get(k, "")))
        self.ptree2.delete(*self.ptree2.get_children())
        for p in self.sim.procs:
            self.ptree2.insert("", "end", values=(p.name, "-" if p.turnaround is None else p.turnaround, p.wait_ready, p.wait_mem, p.blocked_time, p.faults))

    def refresh_log(self):
        ev = self.sim.events
        if len(ev) < self.log_count:
            self.log_text.delete("1.0", "end")
            self.log_count = 0
        for t, txt in ev[self.log_count:]:
            self.log_text.insert("end", f"[{t:>4}] {txt}\n")
        self.log_count = len(ev)
        self.log_text.see("end")

    def refresh_status(self):
        sim, m = self.sim, self.sim.metrics()
        parts = [f"Tiempo {sim.t}", f"CPU {m['cpu_uso']:.0f}%", f"cambios de contexto {m['cambios_contexto']}"]
        if sim.mem is not None:
            parts.append(f"memoria {m['mem_ocupacion']:.0f}% ocupada")
            parts.append(f"frag. externa {m['frag_externa']:.0f}% / interna {m['frag_interna']:.0f}%")
        if "fallos_pagina" in m:
            parts += [f"fallos de página {m['fallos_pagina']} ({m['tasa_fallos']:.0f}%)", f"TLB hit {m['tlb_hit']:.0f}%", f"EAT {m['eat_ns']:.0f} ns"]
        if sim.finished:
            parts.append("● SIMULACIÓN FINALIZADA")
        self.status.set("  |  ".join(parts))


# ===================================================================== comparación de políticas
class CompareWindow(tk.Toplevel):
    def __init__(self, app: App, cfg: Config, procs, initial=None):
        super().__init__(app)
        self.title("Comparar políticas con el mismo escenario")
        self.geometry("1080x640")
        self.cfg, self.procs = cfg, procs
        self.rows = []
        mode = cfg.mode
        avail = {"scheduler": "Planificador de CPU (FIFO / RR / SJF / SRTF)", "quantum": "Quantum de Round Robin"}
        if mode in ("contiguous", "segmentation"):
            avail["fit"] = "Ajuste de memoria (First / Best / Worst Fit)"
        if mode == "paging":
            avail.update({"repl_policy": "Reemplazo de páginas (FIFO / LRU / Clock)", "tlb_policy": "Reemplazo de la TLB (FIFO / LRU / Clock)",
                          "tlb_size": "Tamaño de la TLB", "page_size": "Tamaño de página", "mem_size": "Tamaño de la memoria física"})
        if mode != "none":
            avail["mode"] = "Modelo de memoria (continua / paginación / segmentación)"
        self.names = {v: k for k, v in avail.items()}
        ttk.Label(self, wraplength=1000, padding=(8, 6), text=(
            "Se ejecuta el MISMO escenario (mismos procesos, misma secuencia de accesos) cambiando una sola cosa. "
            "Elegí qué comparar: se calcula solo. Podés editar la lista de valores y apretar “Calcular”.")).pack(fill="x")
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="¿Qué comparar?").pack(side="left")
        self.pv = tk.StringVar(value=avail.get(initial, list(avail.values())[0]))
        cb = ttk.Combobox(top, textvariable=self.pv, values=list(avail.values()), state="readonly", width=50)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: (self.fill_values(), self.run()))
        ttk.Label(top, text="Valores:").pack(side="left", padx=(10, 0))
        self.vv = tk.StringVar()
        ttk.Entry(top, textvariable=self.vv, width=26).pack(side="left", padx=4)
        ttk.Button(top, text="Calcular", command=self.run, style="Big.TButton").pack(side="left", padx=6)
        self.verdict = tk.Label(self, text="", justify="left", anchor="w", bg="#e8f5e9", padx=10, pady=6, wraplength=1000,
                                font=fnt(10, "bold"))
        self.verdict.pack(fill="x", padx=8, pady=4)
        self.tree = ttk.Treeview(self, show="headings", height=6)
        self.tree.tag_configure("best", background="#c8e6c9")
        self.tree.pack(fill="x", padx=8, pady=4)
        mb = ttk.Frame(self, padding=(8, 0))
        mb.pack(fill="x")
        ttk.Label(mb, text="Ver en el gráfico:").pack(side="left")
        self.mv = tk.StringVar()
        self.mcb = ttk.Combobox(mb, textvariable=self.mv, state="readonly", width=30)
        self.mcb.pack(side="left", padx=4)
        self.mcb.bind("<<ComboboxSelected>>", lambda e: self.draw_chart())
        self.chart = tk.Canvas(self, bg="white", highlightthickness=0)
        self.chart.pack(fill="both", expand=True, padx=8, pady=6)
        self.chart.bind("<Configure>", lambda e: self.draw_chart())
        self.fill_values()
        self.after(100, self.run)

    def param(self):
        return self.names[self.pv.get()]

    def fill_values(self):
        self.vv.set(", ".join(map(str, default_values(self.param(), self.cfg))))

    def parse_values(self):
        p = self.param()
        out = []
        for raw in self.vv.get().split(","):
            raw = raw.strip()
            if raw:
                out.append(int(raw) if p in ("quantum", "page_size", "mem_size", "tlb_size") else raw)
        return out

    def run(self):
        try:
            self.rows = compare(self.cfg, self.procs, self.param(), self.parse_values())
        except Exception as e:
            messagebox.showerror("No se pudo comparar", f"{e}\n\nRevisá la lista de valores (separados por coma).", parent=self)
            return
        cols = [c for c in PARAM_COLUMNS.get(self.param(), ["tiempo"]) if any(c in m for _, m, _ in self.rows)]
        self.cols = cols
        self.tree["columns"] = ["v"] + cols
        self.tree.heading("v", text="Valor probado")
        self.tree.column("v", width=110, anchor="center")
        for c in cols:
            self.tree.heading(c, text=LABELS.get(c, c))
            self.tree.column(c, width=112, anchor="center")
        main = MAIN_METRIC.get(self.param())
        best = None
        if main and all(main in m for _, m, _ in self.rows):
            f = max if main in HIGHER_IS_BETTER else min
            best = f(range(len(self.rows)), key=lambda i: self.rows[i][1][main])
        self.tree.delete(*self.tree.get_children())
        for i, (v, m, _) in enumerate(self.rows):
            self.tree.insert("", "end", values=[v] + [("-" if m.get(c) is None else (f"{m[c]:.2f}" if isinstance(m[c], float) else m[c])) for c in cols],
                             tags=("best",) if i == best else ())
        if best is not None:
            vals = [(str(v), m[main]) for v, m, _ in self.rows]
            worst = (min if main in HIGHER_IS_BETTER else max)(vals, key=lambda x: x[1])
            bv, bm = vals[best]
            word = "mayor" if main in HIGHER_IS_BETTER else "menor"
            self.verdict.configure(text=f"✔ Con «{bv}» se obtiene el {word} valor de «{LABELS.get(main, main)}»: {bm:.2f}  "
                                        f"(el peor fue «{worst[0]}» con {worst[1]:.2f}). Fila resaltada = mejor según esa métrica; mirá las demás columnas "
                                        f"porque cada política tiene sus compromisos.")
        else:
            self.verdict.configure(text="Comparación calculada. Mirá las columnas para ver los compromisos de cada política.")
        self.mcb["values"] = [LABELS.get(c, c) for c in cols]
        self.lab2key = {LABELS.get(c, c): c for c in cols}
        if cols:
            self.mv.set(LABELS.get(main or cols[0], main or cols[0]))
        self.draw_chart()

    def draw_chart(self):
        c = self.chart
        c.delete("all")
        if not self.rows or not self.mv.get():
            return
        key = self.lab2key[self.mv.get()]
        vals = [(str(v), m.get(key) or 0) for v, m, _ in self.rows]
        W, H_ = max(c.winfo_width(), 300), max(c.winfo_height(), 150)
        mx = max(v for _, v in vals) or 1
        bw = min(90, (W - 80) / len(vals) - 20)
        for i, (lab, v) in enumerate(vals):
            x = 60 + i * ((W - 80) / len(vals)) + 10
            h = (H_ - 60) * v / mx
            c.create_rectangle(x, H_ - 30 - h, x + bw, H_ - 30, fill=pid_color(i + 2), outline="#333")
            c.create_text(x + bw / 2, H_ - 15, text=lab)
            c.create_text(x + bw / 2, H_ - 38 - h, text=f"{v:.2f}" if isinstance(v, float) else str(v))
        c.create_line(55, 10, 55, H_ - 30)
        c.create_line(55, H_ - 30, W - 10, H_ - 30)
        c.create_text(60, 10, anchor="w", text=self.mv.get(), font=fnt(9, "bold"))


def main(path=None):
    App(path).mainloop()
