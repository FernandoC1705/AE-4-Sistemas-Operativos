"""Carga/guardado de escenarios (JSON) y generación de accesos a memoria.

Formato JSON:
{
  "name": "...", "description": "...",
  "config": { ...campos de Config... },
  "processes": [
     {"pid":1, "name":"P1", "arrival":0, "burst":8, "size":300,
      "segments":[["codigo",200],["datos",100]],      # solo segmentación
      "io":[[3,2]],                                   # tras 3 ticks de CPU, E/S de 2 ticks
      "accesses":[[addr,"R"], ...]}                   # opcional (ver abajo)
  ]
}
Accesos explícitos (opcionales; se completan con accesos generados hasta `burst`):
  paginación:    entero (dirección lógica) o [dirección, "R"|"W"]
  segmentación:  [segmento (índice o nombre), desplazamiento] o [seg, desp, "R"|"W"]
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import List, Tuple

from .models import Config, Process

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def process_from_dict(d: dict, default_pid: int) -> Process:
    return Process(
        pid=int(d.get("pid", default_pid)),
        name=str(d.get("name", f"P{d.get('pid', default_pid)}")),
        arrival=int(d.get("arrival", 0)),
        burst=int(d["burst"]),
        size=int(d.get("size", 0)),
        segments=[tuple(s) for s in d.get("segments", [])],
        io=[tuple(x) for x in d.get("io", [])],
        accesses=list(d.get("accesses", [])),
    )


def process_to_dict(p: Process) -> dict:
    d = {"pid": p.pid, "name": p.name, "arrival": p.arrival, "burst": p.burst, "size": p.size}
    if p.segments:
        d["segments"] = [list(s) for s in p.segments]
    if p.io:
        d["io"] = [list(x) for x in p.io]
    if p.accesses:
        d["accesses"] = [list(a) if isinstance(a, (tuple, list)) else a for a in p.accesses]
    return d


def load_scenario(path) -> Tuple[Config, List[Process], dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = Config.from_dict(data.get("config", {}))
    procs = [process_from_dict(d, i + 1) for i, d in enumerate(data["processes"])]
    pids = [p.pid for p in procs]
    if len(set(pids)) != len(pids):
        raise ValueError("PIDs duplicados en el escenario")
    meta = {"name": data.get("name", Path(path).stem), "description": data.get("description", "")}
    return cfg, procs, meta


def save_scenario(path, cfg: Config, procs: List[Process], name="", description=""):
    data = {"name": name, "description": description, "config": cfg.to_dict(),
            "processes": [process_to_dict(p) for p in procs]}
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_scenarios():
    return sorted(SCENARIO_DIR.glob("*.json"))


# ------------------------------------------------------------ generación de accesos
def _rng(cfg: Config, p: Process):
    # Semilla dependiente sólo de (seed, pid): todas las políticas ven la misma traza.
    return random.Random(cfg.seed * 100003 + p.pid)


def generate_paging_accesses(p: Process, cfg: Config, n: int, rng, start_page=None):
    """Traza con localidad: con prob. `locality` se queda cerca de la página actual."""
    ps = cfg.page_size
    npages = max(1, math.ceil(p.size / ps))
    window = min(npages, 3)
    cur = rng.randrange(npages) if start_page is None else start_page
    out = []
    for _ in range(n):
        if rng.random() < cfg.locality:
            page = (cur + rng.randint(0, window - 1)) % npages
        else:
            cur = rng.randrange(npages)
            page = cur
        if rng.random() < 0.1:
            cur = (cur + 1) % npages
        limit = min(ps, p.size - page * ps) if p.size else ps
        addr = page * ps + rng.randrange(max(1, limit))
        out.append((addr, "W" if rng.random() < cfg.write_prob else "R"))
    return out


def generate_segment_accesses(p: Process, cfg: Config, n: int, rng):
    segs = p.segments or [("principal", p.size)]
    out = []
    cur = 0
    for _ in range(n):
        if rng.random() > cfg.locality:
            cur = rng.randrange(len(segs))
        out.append((cur, rng.randrange(max(1, segs[cur][1])),
                    "W" if rng.random() < cfg.write_prob else "R"))
    return out


def prepare_accesses(p: Process, cfg: Config):
    """Normaliza los accesos explícitos y completa hasta `burst` con accesos generados."""
    if cfg.mode not in ("paging", "segmentation"):
        p.accesses = []
        return
    rng = _rng(cfg, p)
    norm = []
    for a in p.accesses:
        if cfg.mode == "paging":
            if isinstance(a, int):
                norm.append((a, "R"))
            else:
                norm.append((int(a[0]), (a[1] if len(a) > 1 else "R").upper()))
        else:
            seg = a[0]
            if isinstance(seg, str):
                names = [n for n, _ in p.segments]
                seg = names.index(seg)
            norm.append((int(seg), int(a[1]), (a[2] if len(a) > 2 else "R").upper()))
    missing = p.burst - len(norm)
    if missing > 0:
        if cfg.mode == "paging":
            norm += generate_paging_accesses(p, cfg, missing, rng)
        else:
            norm += generate_segment_accesses(p, cfg, missing, rng)
    p.accesses = norm
