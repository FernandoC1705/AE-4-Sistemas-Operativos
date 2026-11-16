"""Ejecuta todas las comparaciones del informe y devuelve los resultados (reproducible)."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.scenario import load_scenario
from core.compare import compare, run_one
from core.models import Config, Process

def sc(n):
    return load_scenario(f"scenarios/{n}.json")

def rows(cfg, procs, param, values, keys):
    out = []
    for v, m, s in compare(cfg, procs, param, values):
        out.append([str(v)] + [m.get(k) for k in keys])
    return out

R = {}
cfg, procs, _ = sc("01_planificacion")
R["sched"] = rows(cfg, procs, "scheduler", ["FIFO","RR","SJF","SRTF"], ["espera_prom","retorno_prom","respuesta_prom","cpu_uso","cambios_contexto","tiempo"])
R["quantum"] = rows(cfg, procs, "quantum", [1,2,3,4,6,8], ["espera_prom","retorno_prom","respuesta_prom","cambios_contexto"])
R["gantt"] = {}
for s in ["FIFO","RR","SJF","SRTF"]:
    sim = run_one(cfg, procs, scheduler=s)
    R["gantt"][s] = [(a,b,(None if p is None else f"P{p}")) for a,b,p in sim.gantt_segments()]

cfg, procs, _ = sc("02_memoria_continua")
k = ["espera_mem_prom","ocupacion_prom","frag_ext_prom","frag_ext_max","frag_int_prom","compactaciones","tiempo"]
R["fit"] = rows(cfg, procs, "fit", ["first","best","worst"], k)
R["fit_compact"] = rows(cfg.copy(auto_compact=True), procs, "fit", ["first","best","worst"], k)
R["fit_fixed"] = rows(cfg.copy(partition="fixed"), procs, "fit", ["first","best","worst"], k)

cfg, procs, _ = sc("03_paginacion_tlb_swap")
R["repl"] = rows(cfg, procs, "repl_policy", ["FIFO","LRU","Clock"], ["fallos_pagina","tasa_fallos","swap_in","swap_out","eat_ns","retorno_prom","tiempo"])
R["tlbpol"] = rows(cfg, procs, "tlb_policy", ["FIFO","LRU","Clock"], ["tlb_hit","eat_ns","fallos_pagina"])
R["tlbsize"] = rows(cfg, procs, "tlb_size", [0,2,4,6,8,16], ["tlb_hit","eat_ns"])
R["pagesize"] = rows(cfg, procs, "page_size", [32,64,128], ["fallos_pagina","tasa_fallos","tlb_hit","frag_int_prom","eat_ns","tiempo"])
R["memsize"] = rows(cfg, procs, "mem_size", [320,640,1280], ["fallos_pagina","tasa_fallos","swap_trafico","eat_ns","retorno_prom","tiempo"])
R["flush"] = rows(cfg, procs, "tlb_flush_on_switch", [False, True], ["tlb_hit","eat_ns","fallos_pagina","cambios_contexto"])

cfg, procs, _ = sc("04_belady_reemplazo")
bel = []
for pol in ["FIFO","LRU","Clock"]:
    row=[pol]
    for fr in (3,4):
        m = run_one(cfg, procs, repl_policy=pol, mem_size=10*fr).metrics()
        row.append(m["fallos_pagina"])
    bel.append(row)
R["belady"] = bel

cfg, procs, _ = sc("05_segmentacion")
R["seg_fit"] = rows(cfg, procs, "fit", ["first","best","worst"], ["espera_mem_prom","retorno_prom","ocupacion_prom","frag_ext_prom","frag_ext_max","compactaciones","tiempo"])
R["seg_fit_compact"] = rows(cfg.copy(auto_compact=True), procs, "fit", ["first","best","worst"], ["espera_mem_prom","retorno_prom","frag_ext_prom","compactaciones"])
sim = run_one(cfg, procs)
R["seg_viol"] = [(t,x) for t,x in sim.events if "VIOLACI" in x or "ABRUPT" in x]

cfg, procs, _ = sc("06_comparacion_modelos")
R["modos"] = rows(cfg, procs, "mode", ["contiguous","paging","segmentation"], ["ocupacion_prom","frag_ext_prom","frag_int_prom","espera_mem_prom","retorno_prom","espera_prom","cpu_uso","cambios_contexto","fallos_pagina","tiempo"])
R["modos_pag_repl"] = rows(cfg.copy(mode="paging"), procs, "repl_policy", ["FIFO","LRU","Clock"], ["fallos_pagina","tasa_fallos","eat_ns","retorno_prom","tiempo"])

# --- experimentos adicionales
cfg, procs, _ = sc("04_belady_reemplazo")
R["belady_sweep"] = {pol: [run_one(cfg, procs, repl_policy=pol, mem_size=10*fr).metrics()["fallos_pagina"] for fr in range(1,8)] for pol in ["FIFO","LRU","Clock"]}
cfg, procs, _ = sc("03_paginacion_tlb_swap")
multi = {}
for pol in ["FIFO","LRU","Clock"]:
    fs, es = [], []
    for seed in range(1, 21):
        m = run_one(cfg, procs, repl_policy=pol, seed=seed).metrics()
        fs.append(m["fallos_pagina"]); es.append(m["eat_ns"])
    multi[pol] = [sum(fs)/20, min(fs), max(fs), sum(es)/20]
R["multi_seed"] = multi
R["tlb_low_faults"] = rows(cfg.copy(mem_size=2560), procs, "tlb_size", [0, 4, 8, 16], ["tlb_hit","eat_ns","fallos_pagina"])
json.dump(R, open("informe/datos.json","w"), indent=1, ensure_ascii=False, default=str)
if __name__ == "__main__":
    for k,v in R.items():
        print("##",k)
        for r in (v if isinstance(v,list) else v.items()):
            print("  ", [round(x,2) if isinstance(x,float) else x for x in r] if isinstance(r,list) else r)
