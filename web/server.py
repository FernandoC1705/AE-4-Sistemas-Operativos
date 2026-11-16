"""Servidor local del simulador (solo biblioteca estándar de Python).

Sirve la interfaz web (web/index.html) y una API JSON mínima sobre el motor de core/.
Uso:  python main.py          (abre el navegador solo)
"""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import models as M                                   # noqa: E402
from core.compare import LABELS, PARAM_COLUMNS, compare, default_values  # noqa: E402
from core.engine import Simulation                              # noqa: E402
from core.models import Config, Process                         # noqa: E402
from core.paging import PagingManager                           # noqa: E402
from core.scenario import load_scenario                         # noqa: E402

SCEN = ROOT / "scenarios"
MODULES = {  # módulo de pantalla -> escenario inicial
    "cpu": "01_planificacion", "continua": "02_memoria_continua",
    "paginacion": "03_paginacion_tlb_swap", "segmentacion": "05_segmentacion",
    "modelos": "06_comparacion_modelos",
}
OTHERS = [("04_belady_reemplazo", "Anomalía de Belady (FIFO)")]
LIVE = {"scheduler", "quantum", "fit", "tlb_policy", "repl_policy"}
HIGHER = {"tlb_hit", "cpu_uso", "ocupacion_prom", "throughput", "terminados"}
MAIN = {"scheduler": "espera_prom", "quantum": "respuesta_prom", "fit": "espera_mem_prom", "repl_policy": "fallos_pagina",
        "tlb_policy": "tlb_hit", "tlb_size": "tlb_hit", "page_size": "eat_ns", "mem_size": "fallos_pagina", "mode": "retorno_prom"}


class App:
    def __init__(self):
        self.lock = threading.Lock()
        self.stem = None
        self.load(MODULES["cpu"])

    def load(self, stem):
        cfg, procs, meta = load_scenario(SCEN / f"{stem}.json")
        self.stem, self.meta = stem, meta
        self.cfg0, self.procs0 = cfg, procs
        self.sim = Simulation(cfg.copy(), procs)

    def reset(self):
        self.sim = Simulation(self.cfg0.copy(), self.procs0)

    def step(self, n=1):
        for _ in range(n):
            if self.sim.finished:
                break
            self.sim.step()

    def back(self):
        t = max(0, self.sim.t - 1)
        self.reset()
        self.step(t)

    def run_all(self):
        self.sim.run()

    def set_config(self, changes):
        live = {k: v for k, v in changes.items() if k in LIVE}
        rest = {k: v for k, v in changes.items() if k not in LIVE}
        cfg = self.cfg0.copy(**changes)           # valida
        self.cfg0 = cfg
        if rest:
            self.reset()
        else:
            s = self.sim
            if "scheduler" in live: s.set_scheduler(live["scheduler"])
            if "quantum" in live: s.set_quantum(int(live["quantum"]))
            if "fit" in live: s.set_fit(live["fit"])
            if "tlb_policy" in live or "repl_policy" in live:
                s.set_policies(live.get("tlb_policy"), live.get("repl_policy"))

    def add_process(self, d):
        pid = max([p.pid for p in self.procs0] + [0]) + 1
        segs = [(f"seg{i + 1}", int(x)) for i, x in enumerate(d.get("segments", []))]
        p = Process(pid=pid, name=f"P{pid}", arrival=max(int(d.get("arrival", 0)), self.sim.t),
                    burst=int(d["burst"]), size=int(d.get("size", 0)), segments=segs)
        self.procs0 = self.procs0 + [p]
        self.sim.add_process(p)

    # ---------------------------------------------------------------- vista
    def memory_view(self):
        s, mode = self.sim, self.cfg0.mode
        names = {p.pid: p.name for p in s.procs}
        if mode in ("contiguous", "segmentation"):
            blocks = [{"start": b.start, "size": b.size, "free": b.pid is None,
                       "pid": b.pid, "name": names.get(b.pid, ""), "label": b.label}
                      for b in s.mem.map.blocks]
            v = {"kind": mode, "total": s.mem.map.total, "blocks": blocks}
            if mode == "segmentation":
                v["tables"] = [{"name": p.name, "pid": p.pid,
                                "rows": [{"seg": i, "name": n, "base": b, "limit": l}
                                         for i, (n, b, l) in enumerate(s.mem.seg_table(p))]}
                               for p in s.procs if p.blocks]
            return v
        if mode == "paging":
            m = s.mem
            frames = []
            for f in range(m.n_frames):
                o = m.owner.get(f)
                if o is None:
                    frames.append({"f": f, "free": True})
                else:
                    pte = s.by_pid(o[0]).page_table[o[1]]
                    frames.append({"f": f, "free": False, "pid": o[0], "name": names[o[0]], "page": o[1],
                                   "dirty": pte.dirty, "loading": (o in m.loading)})
            tables = [{"name": p.name, "pid": p.pid,
                       "rows": [{"page": i, "frame": e.frame, "valid": e.valid, "dirty": e.dirty,
                                 "loading": e.loading, "swap": e.swap_slot}
                                for i, e in enumerate(p.page_table)]}
                      for p in s.procs if p.page_table]
            tlb = [{"name": names.get(k[0], k[0]), "page": k[1], "frame": m.tlb[k]}
                   for k in m.tlb] if m.tlb else []
            order = [{"name": names.get(k[0], k[0]), "page": k[1], "note": n}
                     for k, n in m.frame_policy.describe()]
            return {"kind": "paging", "frames": frames, "tables": tables, "tlb": tlb,
                    "tlb_size": m.tlb_size, "policy": self.cfg0.repl_policy, "order": order,
                    "page_size": m.ps, "swap_used": m.swap_slots - len(m.swap_free), "swap_total": m.swap_slots}
        return None

    def state(self):
        s = self.sim
        evs = [e for e in s.recent_events() if not e.startswith("Inicio:")]
        hist = {p.name: "".join(c if c else " " for c in s.history[p.pid]) for p in s.procs}
        return {
            "stem": self.stem, "name": self.meta.get("name", ""), "description": self.meta.get("description", ""),
            "cfg": self.cfg0.to_dict(), "t": s.t, "finished": s.finished,
            "procs": s.process_rows(), "queues": s.queues(),
            "gantt": [[a, b, (s.by_pid(pid).name if pid else None)] for a, b, pid in s.gantt_segments()],
            "history": hist, "events": evs, "log": [f"t={t}: {x}" for t, x in s.events][-60:],
            "metrics": s.metrics(), "mem": self.memory_view(),
            "can_manual": self.cfg0.mode in ("paging", "segmentation"),
        }

    def compare(self, param):
        vals = default_values(param, self.cfg0)
        rows = compare(self.cfg0, self.procs0, param, vals)
        cols = [c for c in PARAM_COLUMNS[param] if any(c in m for _, m, _ in rows)]
        main = MAIN.get(param, cols[0])
        better = max if main in HIGHER else min
        best = better(range(len(rows)), key=lambda i: rows[i][1].get(main, 0))
        return {"param": param, "values": [str(v) for v, _, _ in rows], "cols": cols,
                "labels": {c: LABELS.get(c, c) for c in cols}, "main": main, "best": best,
                "rows": [[m.get(c) for c in cols] for _, m, _ in rows]}

    def manual(self, d):
        s = self.sim
        what = d["what"]
        if self.cfg0.mode == "paging":
            p = next((p for p in s.procs if p.page_table and p.state not in (M.DONE, M.REJECTED)), None)
            if p is None:
                return "Todavía no hay procesos en memoria. Avanzá unos pasos primero."
            if what == "fault":
                pg = next((i for i, e in enumerate(p.page_table) if not e.valid and not e.loading), None)
                if pg is None:
                    return f"{p.name} ya tiene todas sus páginas en memoria. Probá con otro paso."
                return s.manual_access(p.pid, pg * s.mem.ps + 1)
            if what == "hit":
                pg = next((i for i, e in enumerate(p.page_table) if e.valid), None)
                if pg is None:
                    return "Ninguna página cargada todavía."
                return s.manual_access(p.pid, pg * s.mem.ps + 1)
            return s.manual_access(int(d["pid"]), int(d["addr"]))
        if self.cfg0.mode == "segmentation":
            p = next((p for p in s.procs if p.blocks and p.state not in (M.DONE, M.REJECTED)), None)
            if p is None:
                return "Todavía no hay procesos con segmentos en memoria. Avanzá unos pasos."
            if what == "violation":
                return s.manual_access(p.pid, len(p.blocks) - 1, p.blocks[-1].size + 10)
            return s.manual_access(p.pid, 0, 1)
        return "Este módulo no tiene acceso manual."


APP = App()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send((ROOT / "web" / "index.html").read_bytes(), ctype="text/html")
        if self.path == "/api/state":
            with APP.lock:
                return self._send(APP.state())
        if self.path == "/api/modules":
            return self._send({"modules": MODULES, "others": OTHERS})
        self._send({"error": "no existe"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        d = json.loads(self.rfile.read(n) or b"{}")
        msg = ""
        try:
            with APP.lock:
                p = self.path
                if p == "/api/load": APP.load(d["stem"])
                elif p == "/api/module": APP.load(MODULES[d["module"]])
                elif p == "/api/step": APP.step(int(d.get("n", 1)))
                elif p == "/api/back": APP.back()
                elif p == "/api/reset": APP.reset()
                elif p == "/api/run": APP.run_all()
                elif p == "/api/config": APP.set_config(d)
                elif p == "/api/add": APP.add_process(d)
                elif p == "/api/compact": APP.sim.compact(); APP.sim._flush_mem_log()
                elif p == "/api/manual": msg = APP.manual(d)
                elif p == "/api/compare": return self._send(APP.compare(d["param"]))
                else: return self._send({"error": "no existe"}, 404)
                out = APP.state(); out["msg"] = msg
            self._send(out)
        except Exception as e:  # noqa: BLE001
            self._send({"error": str(e)}, 400)


def main(port=8765, open_browser=True):
    srv = None
    for pt in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", pt), Handler)
            break
        except OSError:
            continue
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Simulador de Sistemas Operativos -> {url}\n(cerrá esta ventana o Ctrl+C para salir)")
    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
