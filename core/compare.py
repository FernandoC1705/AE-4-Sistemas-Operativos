"""Comparación de políticas: ejecuta el MISMO escenario variando un parámetro.

Ejemplos de uso (ver también cli.py):
    compare(cfg, procs, "fit", ["first", "best", "worst"])
    compare(cfg, procs, "repl_policy", ["FIFO", "LRU", "Clock"])
    compare(cfg, procs, "scheduler", ["FIFO", "RR", "SJF", "SRTF"])
"""
from __future__ import annotations

from typing import List

from .engine import Simulation
from .models import Config, Process

# Parámetros comparables y las columnas de métricas relevantes para cada uno
PARAM_COLUMNS = {
    "scheduler": ["espera_prom", "retorno_prom", "respuesta_prom", "cpu_uso", "cambios_contexto", "tiempo"],
    "fit": ["espera_mem_prom", "retorno_prom", "ocupacion_prom", "frag_ext_prom", "frag_ext_max",
            "frag_int_prom", "compactaciones", "rechazados", "tiempo"],
    "tlb_policy": ["tlb_hit", "eat_ns", "fallos_pagina", "tiempo"],
    "repl_policy": ["fallos_pagina", "tasa_fallos", "swap_in", "swap_out", "eat_ns", "retorno_prom", "tiempo"],
    "page_size": ["fallos_pagina", "tasa_fallos", "tlb_hit", "frag_int_prom", "eat_ns", "tiempo"],
    "mem_size": ["fallos_pagina", "tasa_fallos", "swap_trafico", "eat_ns", "retorno_prom", "tiempo"],
    "tlb_size": ["tlb_hit", "eat_ns", "tiempo"],
    "mode": ["ocupacion_prom", "frag_ext_prom", "frag_int_prom", "espera_mem_prom", "retorno_prom",
             "cpu_uso", "fallos_pagina", "rechazados", "tiempo"],
    "quantum": ["espera_prom", "retorno_prom", "respuesta_prom", "cambios_contexto", "cpu_uso"],
}

LABELS = {
    "espera_prom": "Espera prom.", "retorno_prom": "Retorno prom.", "respuesta_prom": "Respuesta prom.",
    "cpu_uso": "Uso CPU %", "cambios_contexto": "Cambios ctx", "tiempo": "Tiempo total",
    "espera_mem_prom": "Espera mem. prom.", "mem_ocupacion": "Ocupación mem. %",
    "frag_externa": "Frag. externa %", "frag_interna": "Frag. interna %", "mayor_libre": "Mayor bloque libre",
    "rechazados": "Rechazados", "tlb_hit": "TLB hit %", "eat_ns": "EAT (ns)", "fallos_pagina": "Fallos de página",
    "tasa_fallos": "Tasa de fallos %", "swap_in": "Swap-in (págs)", "swap_out": "Swap-out (págs)",
    "swap_trafico": "Tráfico swap (B)", "mem_libre": "Memoria libre", "compactaciones": "Compactaciones",
    "violaciones": "Violaciones", "abortados": "Abortados", "terminados": "Terminados",
    "accesos": "Accesos a memoria", "tlb_miss": "TLB miss %", "reemplazos": "Reemplazos de página",
    "ocupacion_prom": "Ocupación mem. prom. %", "frag_ext_prom": "Frag. ext. prom. %",
    "frag_ext_max": "Frag. ext. máx. %", "frag_int_prom": "Frag. int. prom. %",
    "throughput": "Throughput", "bloqueado_prom": "Bloqueado prom.",
}


def run_one(cfg: Config, procs: List[Process], **changes):
    c = cfg.copy(**changes)
    sim = Simulation(c, procs).run()
    return sim


def compare(cfg: Config, procs: List[Process], param: str, values):
    """Devuelve [(valor, métricas_dict, sim)] ejecutando el escenario con cada valor."""
    rows = []
    for v in values:
        sim = run_one(cfg, procs, **{param: v})
        rows.append((v, sim.metrics(), sim))
    return rows


def default_values(param: str, cfg: Config):
    return {
        "scheduler": ["FIFO", "RR", "SJF", "SRTF"],
        "fit": ["first", "best", "worst"],
        "tlb_policy": ["FIFO", "LRU", "Clock"],
        "repl_policy": ["FIFO", "LRU", "Clock"],
        "page_size": [32, 64, 128],
        "mem_size": [cfg.mem_size // 2, cfg.mem_size, cfg.mem_size * 2],
        "tlb_size": [0, 2, 4, 8],
        "mode": ["contiguous", "paging", "segmentation"],
        "quantum": [1, 2, 4, 8],
    }[param]


def format_value(key, v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def table_text(param, rows, columns=None):
    cols = columns or PARAM_COLUMNS.get(param, ["tiempo"])
    cols = [c for c in cols if any(c in m for _, m, _ in rows)]
    head = [param] + [LABELS.get(c, c) for c in cols]
    data = [[str(v)] + [format_value(c, m.get(c)) for c in cols] for v, m, _ in rows]
    widths = [max(len(r[i]) for r in [head] + data) for i in range(len(head))]
    line = lambda r: " | ".join(x.ljust(w) for x, w in zip(r, widths))
    sep = "-+-".join("-" * w for w in widths)
    return "\n".join([line(head), sep] + [line(r) for r in data])
