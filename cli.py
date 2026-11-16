"""Interfaz de línea de comandos: ejecutar un escenario, paso a paso o en resumen,
y comparar políticas.

Ejemplos:
    python cli.py scenarios/03_paginacion_tlb_swap.json                 # resumen
    python cli.py scenarios/03_paginacion_tlb_swap.json --steps 10 -v   # 10 ticks con detalle
    python cli.py scenarios/02_memoria_continua.json --compare fit
    python cli.py scenarios/03_paginacion_tlb_swap.json --compare repl_policy --compare tlb_policy
    python cli.py scenarios/01_planificacion.json --set scheduler=SRTF --set quantum=3
"""
import argparse
import sys

from core import models as M
from core.compare import LABELS, PARAM_COLUMNS, compare, default_values, table_text
from core.engine import Simulation
from core.paging import PagingManager
from core.scenario import load_scenario


def gantt_text(sim):
    segs = sim.gantt_segments()
    if not segs:
        return "(vacío)"
    name = {p.pid: p.name for p in sim.procs}
    bar = "".join(f"|{(name.get(pid) if pid is not None else '--'):^{max(3, 2 * (e - s))}}" for s, e, pid in segs) + "|"
    ticks = "".join(f"{s:<{max(3, 2 * (e - s)) + 1}}" for s, e, _ in segs) + str(segs[-1][1])
    return bar + "\n" + ticks


def proc_table(sim):
    cols = [("pid", "PID", 4), ("nombre", "Nombre", 7), ("estado", "Estado", 18), ("llegada", "Lleg", 5),
            ("rafaga", "Ráf", 4), ("restante", "Rest", 5), ("memoria", "Memoria asignada", 26),
            ("espera", "Espera", 7), ("retorno", "Retorno", 8), ("fallos", "Fallos", 6)]
    lines = [" ".join(h.ljust(w) for _, h, w in cols)]
    for r in sim.process_rows():
        lines.append(" ".join(("-" if r[k] is None else str(r[k])).ljust(w)[:w] for k, _, w in cols))
    return "\n".join(lines)


def mem_picture(sim):
    m = sim.mem
    if m is None:
        return ""
    if isinstance(m, PagingManager):
        cells = []
        for f in range(m.n_frames):
            k = m.owner.get(f)
            cells.append("  .  " if k is None else f"P{k[0]}:{k[1]}".center(5))
        return "Marcos: " + "[" + "][".join(cells) + "]"
    out = []
    for b in m.map.blocks:
        out.append(f"[{b.start}-{b.end} {'LIBRE' if b.free else 'P%d%s' % (b.pid, ':' + b.label if b.label else '')}]")
    return "Mapa:   " + " ".join(out)


def show_state(sim):
    print(f"\n=== t = {sim.t} ===")
    print(proc_table(sim))
    print("Colas:", {k: v for k, v in sim.queues().items()})
    mp = mem_picture(sim)
    if mp:
        print(mp)


def print_metrics(sim):
    m = sim.metrics()
    print("\nMétricas:")
    for k, v in m.items():
        print(f"  {LABELS.get(k, k):<28} {v:.2f}" if isinstance(v, float) else f"  {LABELS.get(k, k):<28} {v}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Simulador de Sistemas Operativos (CLI)")
    ap.add_argument("scenario")
    ap.add_argument("--set", action="append", default=[], metavar="CLAVE=VALOR",
                    help="sobrescribe un parámetro de configuración (ej. scheduler=RR)")
    ap.add_argument("--steps", type=int, help="ejecutar N ticks mostrando el estado en cada uno")
    ap.add_argument("-v", "--verbose", action="store_true", help="mostrar el registro de eventos")
    ap.add_argument("--compare", action="append", choices=sorted(PARAM_COLUMNS),
                    help="compara políticas variando ese parámetro (repetible)")
    a = ap.parse_args(argv)

    cfg, procs, meta = load_scenario(a.scenario)
    for kv in a.set:
        k, v = kv.split("=", 1)
        cur = getattr(cfg, k)
        setattr(cfg, k, type(cur)(v) if not isinstance(cur, (bool, list)) else (v.lower() in "1 true si".split()))
    cfg.validate()
    print(f"Escenario: {meta['name']}\n{meta['description']}\nModo: {M.MODES[cfg.mode]} | CPU: {cfg.scheduler}"
          + (f" q={cfg.quantum}" if cfg.scheduler == "RR" else ""))

    if a.compare:
        for param in a.compare:
            print(f"\n### Comparación por '{param}'")
            print(table_text(param, compare(cfg, procs, param, default_values(param, cfg))))
        return 0

    sim = Simulation(cfg, procs)
    if a.steps:
        for _ in range(a.steps):
            if not sim.step():
                break
            show_state(sim)
    else:
        sim.run()
        show_state(sim)
    if a.verbose:
        print("\nRegistro de eventos:")
        for t, txt in sim.events:
            print(f"  [{t:>4}] {txt}")
    print("\nDiagrama de Gantt:\n" + gantt_text(sim))
    print_metrics(sim)
    return 0


if __name__ == "__main__":
    sys.exit(main())
