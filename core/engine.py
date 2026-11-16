"""Motor de simulación integrado: planificación de CPU + gestión de memoria.

Un `step()` avanza un tick. En cada tick:
  1. Se despiertan los procesos cuya E/S o carga de página terminó.
  2. Se reintenta admitir a los procesos que esperan memoria (en orden de llegada).
  3. Llegan los procesos nuevos y se intenta asignarles memoria.
  4. El planificador aplica desalojo (fin de quantum en RR, SRTF) y elige proceso.
  5. El proceso elegido hace su acceso a memoria (traducción de dirección). Si
     falla (fallo de página o violación de segmento) deja de ser candidato en ese
     tick y se elige otro; si no, ejecuta una unidad de CPU.
  6. Se contabilizan los tiempos de espera.
"""
from __future__ import annotations

import copy
from typing import List, Optional

from . import models as M
from .memory import ContiguousManager, SegmentationManager
from .models import Config, Process
from .paging import PagingManager
from .scenario import prepare_accesses


class Simulation:
    def __init__(self, cfg: Config, processes: List[Process]):
        cfg.validate()
        self.cfg = cfg
        self.procs: List[Process] = []
        for p in processes:
            q = copy.deepcopy(p)
            q.reset()
            self.procs.append(q)
        self.procs.sort(key=lambda p: p.pid)
        self.t = 0
        self.running: Optional[Process] = None
        self.ready: List[Process] = []
        self.wait_mem: List[Process] = []
        self.last_pid: Optional[int] = None
        self.ctx_switches = 0
        self.busy = 0
        self.gantt: List[Optional[int]] = []       # pid (o None = ocioso) por tick
        self.events: List[tuple] = []              # (t, texto)
        self.finished = False
        self.history = {p.pid: [] for p in self.procs}   # estado por tick de cada proceso (línea de tiempo)
        self.acc = {"n": 0, "occ": 0.0, "ext": 0.0, "ext_max": 0.0, "int": 0.0}
        self.mem = self._make_mem()
        for p in self.procs:
            prepare_accesses(p, cfg)
        self.log(f"Inicio: modo={M.MODES[cfg.mode]}, planificador={cfg.scheduler}"
                 + (f" (q={cfg.quantum})" if cfg.scheduler == "RR" else ""))

    # ------------------------------------------------------------------ utilidades
    def _make_mem(self):
        m = self.cfg.mode
        if m == "contiguous":
            return ContiguousManager(self.cfg)
        if m == "segmentation":
            return SegmentationManager(self.cfg)
        if m == "paging":
            return PagingManager(self.cfg)
        return None

    def log(self, text):
        self.events.append((self.t, text))
        if len(self.events) > 20000:
            del self.events[:5000]

    def _flush_mem_log(self):
        if self.mem is not None and self.mem.log:
            for line in self.mem.log:
                self.log(line)
            self.mem.log.clear()

    def by_pid(self, pid) -> Optional[Process]:
        return next((p for p in self.procs if p.pid == pid), None)

    # ------------------------------------------------------------------ cambios en caliente
    def set_scheduler(self, name):
        self.cfg.scheduler = name
        self.log(f"Planificador cambiado a {name}")

    def set_quantum(self, q):
        self.cfg.quantum = max(1, int(q))
        self.log(f"Quantum cambiado a {self.cfg.quantum}")

    def set_policies(self, tlb_policy=None, repl_policy=None):
        if isinstance(self.mem, PagingManager):
            self.mem.set_policies(tlb_policy, repl_policy)
            if tlb_policy:
                self.cfg.tlb_policy = tlb_policy
            if repl_policy:
                self.cfg.repl_policy = repl_policy
            self.log(f"Políticas cambiadas: TLB={self.mem.tlb_policy.name}, "
                     f"reemplazo={self.mem.frame_policy.name}")

    def set_fit(self, fit):
        if isinstance(self.mem, ContiguousManager):
            self.mem.fit = fit
            self.cfg.fit = fit
            self.log(f"Política de ajuste cambiada a {M.FIT_NAMES[fit]}")

    def compact(self):
        if isinstance(self.mem, ContiguousManager):
            moved = self.mem.compact()
            self.log(f"Compactación manual: {moved} bytes movidos")
            self._retry_waiting()

    def add_process(self, p: Process):
        """Crea un proceso en caliente (llega en el instante actual o posterior)."""
        if self.by_pid(p.pid):
            raise ValueError(f"Ya existe el PID {p.pid}")
        p.arrival = max(p.arrival, self.t)
        p.reset()
        prepare_accesses(p, self.cfg)
        self.procs.append(p)
        self.procs.sort(key=lambda q: q.pid)
        self.history[p.pid] = [""] * self.t
        self.finished = False
        self.log(f"Proceso {p.name} (PID {p.pid}) creado, llegada={p.arrival}")

    # ------------------------------------------------------------------ transiciones
    def _to_ready(self, p):
        p.state = M.READY
        p.ready_since = self.t
        self.ready.append(p)

    def _admit(self, p):
        """NUEVO -> LISTO (si hay memoria) o ESPERANDO MEMORIA."""
        if self.mem is None:
            self._to_ready(p)
            self.log(f"{p.name}: llega y pasa a Listo")
            return
        if not self.mem.can_ever_fit(p):
            p.state, p.finish, p.reason = M.REJECTED, self.t, "no cabe nunca en el sistema"
            self.log(f"{p.name}: RECHAZADO (su requerimiento supera la capacidad del sistema)")
            return
        if self.mem.admit(p):
            self._to_ready(p)
            self.log(f"{p.name}: llega, memoria asignada ({self.mem.describe(p)}) -> Listo")
            self._flush_mem_log()
        else:
            p.state = M.WAIT_MEM
            self.wait_mem.append(p)
            self.log(f"{p.name}: sin memoria disponible -> Esperando Memoria")
            self._flush_mem_log()

    def _retry_waiting(self):
        for p in list(self.wait_mem):
            if self.mem.admit(p):
                self.wait_mem.remove(p)
                self._to_ready(p)
                self.log(f"{p.name}: memoria asignada ({self.mem.describe(p)}) -> Listo")
        self._flush_mem_log()

    def _terminate(self, p, finish, reason=""):
        was_running = self.running is p
        p.state, p.finish, p.reason = M.DONE, finish, reason
        if p in self.ready:
            self.ready.remove(p)
        if p in self.wait_mem:
            self.wait_mem.remove(p)
        if was_running:
            self.running = None
        if self.mem is not None and (p.blocks or p.page_table):
            self.mem.release(p)
        self.log(f"{p.name}: " + (f"TERMINADO ABRUPTAMENTE ({reason})" if reason else "terminado, memoria liberada"))

    # ------------------------------------------------------------------ planificador
    def _select(self):
        if not self.ready:
            return None
        s = self.cfg.scheduler
        if s in ("FIFO", "RR"):
            return self.ready[0]
        key = (lambda p: (p.remaining, p.ready_since, p.pid))
        return min(self.ready, key=key)          # SJF (restante al decidir) y SRTF

    def _dispatch(self, p):
        self.ready.remove(p)
        p.state = M.RUNNING
        p.quantum_used = 0
        self.running = p
        if self.last_pid is not None and self.last_pid != p.pid:
            self.ctx_switches += 1
            if isinstance(self.mem, PagingManager) and self.cfg.tlb_flush_on_switch:
                self.mem.flush_tlb()
            self.log(f"Cambio de contexto -> {p.name}")
        self.last_pid = p.pid

    def _preempt_check(self):
        r = self.running
        if r is None:
            return
        s = self.cfg.scheduler
        if s == "RR" and r.quantum_used >= self.cfg.quantum:
            self.log(f"{r.name}: fin de quantum -> Listo (cola)")
            self._to_ready(r)
            self.running = None
        elif s == "SRTF" and self.ready:
            best = min(self.ready, key=lambda p: (p.remaining, p.ready_since, p.pid))
            if best.remaining < r.remaining:
                self.log(f"{r.name}: desalojado por {best.name} (SRTF)")
                self._to_ready(r)
                self.running = None

    # ------------------------------------------------------------------ acceso a memoria
    def _try_access(self, p) -> bool:
        """Hace la traducción de dirección del tick. False si p no puede ejecutar ahora."""
        mode = self.cfg.mode
        if mode not in ("paging", "segmentation"):
            return True
        idx = p.cpu_done % len(p.accesses)
        acc = p.accesses[idx]
        if mode == "segmentation":
            seg, off, rw = acc
            p.mem_accesses += 1
            phys, why = self.mem.translate(p, seg, off)
            if why:
                p.violations += 1
                self.log(f"{p.name}: VIOLACIÓN DE SEGMENTO (seg {seg}, desp {off}): {why}")
                self._terminate(p, self.t, "violación de segmento")
                return False
            return True
        # paginación
        if p.resolved:                      # el fallo ya se atendió: reanuda la instrucción
            p.resolved = False
            return True
        addr, rw = acc
        res = self.mem.access(p, addr, rw == "W")
        if res.kind == "invalid":
            self.log(f"{p.name}: acceso inválido: {res.msg}")
            self._terminate(p, self.t, "dirección fuera del espacio de direcciones")
            return False
        if res.kind == "retry":
            self._block_for_page(p, 1, retry=True)
            return False
        if res.kind == "fault":
            v = ""
            if res.victim:
                v = (f"; desaloja P{res.victim[0]}:pág {res.victim[1]}"
                     + (" (modificada, se escribe a swap)" if res.victim_dirty else ""))
            self.log(f"{p.name}: FALLO DE PÁGINA en dir {addr} (pág {res.page}) -> marco {res.frame}{v}; "
                     f"carga desde swap {res.ticks} ticks")
            p.pending = (res.page, rw == "W")
            self._block_for_page(p, res.ticks)
            return False
        tag = "TLB hit" if res.kind == "hit" else "TLB miss (tabla de páginas)"
        self.log(f"{p.name}: dir lógica {addr} = pág {res.page}+{res.offset} -> marco {res.frame} "
                 f"-> física {res.phys} [{tag}]")
        self._flush_mem_log()
        return True

    def _block_for_page(self, p, ticks, retry=False):
        p.state = M.WAIT_PAGE
        p.wake_at = self.t + ticks
        p.retry = retry
        if self.running is p:
            self.running = None
        self._flush_mem_log()

    def _finish_page_load(self, p):
        if p.retry:
            p.retry = False
        else:
            page, write = p.pending
            self.mem.complete_load(p, page, write)
            p.resolved = True
            p.pending = None
            self.log(f"{p.name}: página {page} cargada desde swap -> Listo")
            self._flush_mem_log()
        self._to_ready(p)

    # ------------------------------------------------------------------ un tick
    def step(self) -> bool:
        if self.finished:
            return False
        t = self.t
        # 1) despertar
        for p in self.procs:
            if p.state == M.BLOCKED and p.wake_at <= t:
                self.log(f"{p.name}: E/S completada -> Listo")
                self._to_ready(p)
            elif p.state == M.WAIT_PAGE and p.wake_at <= t:
                self._finish_page_load(p)
        # 2) memoria: reintentar esperas
        if self.mem is not None and self.wait_mem:
            self._retry_waiting()
        # 3) llegadas
        for p in self.procs:
            if p.state == M.NEW and p.arrival <= t:
                self._admit(p)
        # 4) y 5) planificación + acceso a memoria
        self._preempt_check()
        executed = None
        guard = 0
        while guard < len(self.procs) + 2:
            guard += 1
            if self.running is None:
                nxt = self._select()
                if nxt is None:
                    break
                self._dispatch(nxt)
            if self._try_access(self.running):
                executed = self.running
                break
        # ejecución de una unidad de CPU
        if executed is not None:
            p = executed
            if p.first_run is None:
                p.first_run = t
            p.remaining -= 1
            p.cpu_done += 1
            p.quantum_used += 1
            self.busy += 1
            self.gantt.append(p.pid)
            if p.remaining == 0:
                self._terminate(p, t + 1)
            elif p.io_idx < len(p.io) and p.cpu_done == p.io[p.io_idx][0]:
                dur = p.io[p.io_idx][1]
                p.io_idx += 1
                p.state, p.wake_at = M.BLOCKED, t + 1 + dur
                self.running = None
                self.log(f"{p.name}: pide E/S ({dur} ticks) -> Bloqueado")
        else:
            self.gantt.append(None)
        # 6) contabilizar esperas
        for p in self.procs:
            if p is executed:
                continue
            if p.state == M.READY:
                p.wait_ready += 1
            elif p.state == M.WAIT_MEM:
                p.wait_mem += 1
            elif p.state in (M.BLOCKED, M.WAIT_PAGE):
                p.blocked_time += 1
        for p in self.procs:                      # línea de tiempo: R=ejecuta, L=listo, B=E/S, P=página, M=memoria
            if p is executed:
                c = "R"
            else:
                c = {M.READY: "L", M.BLOCKED: "B", M.WAIT_PAGE: "P", M.WAIT_MEM: "M"}.get(p.state, "")
            self.history[p.pid].append(c)
        self._sample_memory()
        self.t += 1
        self._check_finished()
        return True

    def _sample_memory(self):
        """Acumula ocupación y fragmentación en cada tick para obtener promedios y picos."""
        if self.mem is None:
            return
        s = self.mem.stats()
        a = self.acc
        a["n"] += 1
        a["occ"] += s["occupancy"]
        a["ext"] += s["ext_frag"]
        a["ext_max"] = max(a["ext_max"], s["ext_frag"])
        a["int"] += s["int_frag"]

    def _check_finished(self):
        active = [p for p in self.procs if p.state not in (M.DONE, M.REJECTED)]
        if not active:
            self.finished = True
            self.log("Simulación finalizada: todos los procesos terminaron")
            return
        if self.wait_mem and self.mem is not None and self.running is None and not self.ready:
            self._retry_waiting()       # la memoria recién liberada puede servir a los que esperan
        stuck = (self.running is None and not self.ready and
                 not any(p.state in (M.BLOCKED, M.WAIT_PAGE, M.NEW) for p in active))
        if stuck:      # sólo quedan procesos esperando memoria que nunca se liberará
            for p in list(self.wait_mem):
                self.wait_mem.remove(p)
                p.state, p.finish, p.reason = M.REJECTED, self.t, "memoria insuficiente (nunca se liberó)"
                self.log(f"{p.name}: RECHAZADO definitivamente (memoria insuficiente)")
            self.finished = True
            self.log("Simulación finalizada (procesos sin memoria no pueden continuar)")
        elif self.t >= self.cfg.max_ticks:
            self.finished = True
            self.log(f"Simulación detenida: se alcanzó max_ticks={self.cfg.max_ticks}")

    def run(self, max_steps=None):
        n = 0
        while not self.finished and (max_steps is None or n < max_steps):
            self.step()
            n += 1
        return self

    # ------------------------------------------------------------------ acceso manual (demo)
    def manual_access(self, pid, a, b=None, write=False) -> str:
        """Traduce una dirección a pedido (útil para demostrar fallos/violaciones en vivo)."""
        p = self.by_pid(pid)
        if p is None:
            return f"No existe el PID {pid}"
        if self.cfg.mode == "segmentation":
            if not p.blocks:
                return f"{p.name} no tiene segmentos en memoria (estado {p.state})"
            phys, why = self.mem.translate(p, int(a), int(b))
            if why:
                p.violations += 1
                msg = f"{p.name}: VIOLACIÓN DE SEGMENTO: {why}"
                self.log(msg)
                self._terminate(p, self.t, "violación de segmento")
                return msg
            msg = f"{p.name}: (seg {a}, desp {b}) -> dirección física {phys}"
            self.log(msg)
            return msg
        if self.cfg.mode == "paging":
            if not p.page_table:
                return f"{p.name} no está admitido en memoria (estado {p.state})"
            res = self.mem.access(p, int(a), write)
            if res.kind == "invalid":
                return f"{p.name}: {res.msg}"
            if res.kind == "retry":
                return f"No se pudo acceder ahora: {res.msg}. Reintentá."
            if res.kind == "fault":
                self.mem.complete_load(p, res.page, write)
                v = f", desaloja P{res.victim[0]}:pág {res.victim[1]}" if res.victim else ""
                msg = (f"{p.name}: FALLO DE PÁGINA dir {a} (pág {res.page}, desp {res.offset}) -> "
                       f"marco {res.frame}{v}; física {res.phys}")
            else:
                tag = "TLB hit" if res.kind == "hit" else "TLB miss"
                msg = (f"{p.name}: dir {a} = pág {res.page}+{res.offset} -> marco {res.frame} "
                       f"-> física {res.phys} [{tag}]")
            self.log("[manual] " + msg)
            self._flush_mem_log()
            return msg
        return "El acceso manual sólo aplica a paginación y segmentación"

    # ------------------------------------------------------------------ vistas y métricas
    def gantt_segments(self):
        segs, start = [], 0
        for i in range(1, len(self.gantt) + 1):
            if i == len(self.gantt) or self.gantt[i] != self.gantt[start]:
                segs.append((start, i, self.gantt[start]))
                start = i
        return segs

    def mem_text(self, p):
        return self.mem.describe(p) if self.mem is not None else "—"

    def recent_events(self):
        """Eventos del último tick ejecutado (para el cuadro "qué pasó en este paso")."""
        return [txt for t, txt in self.events if t >= self.t - 1] if self.t > 0 else []

    def queues(self):
        names = lambda L: [p.name for p in L]
        return {
            "Nuevos": [p.name for p in self.procs if p.state == M.NEW],
            "Esperando memoria": names(self.wait_mem),
            "Listos": names(self.ready),
            "Ejecutando": [self.running.name] if self.running else [],
            "Bloqueados (E/S)": [p.name for p in self.procs if p.state == M.BLOCKED],
            "Esperando página": [p.name for p in self.procs if p.state == M.WAIT_PAGE],
        }

    def metrics(self) -> dict:
        done = [p for p in self.procs if p.state == M.DONE and not p.reason]
        n = len(done)
        avg = lambda xs: (sum(xs) / len(xs)) if xs else 0.0
        out = {
            "tiempo": self.t,
            "cpu_uso": self.busy / self.t * 100 if self.t else 0.0,
            "cambios_contexto": self.ctx_switches,
            "terminados": n,
            "rechazados": sum(1 for p in self.procs if p.state == M.REJECTED),
            "abortados": sum(1 for p in self.procs if p.state == M.DONE and p.reason),
            "espera_prom": avg([p.wait_ready for p in done]),
            "retorno_prom": avg([p.turnaround for p in done]),
            "respuesta_prom": avg([p.response for p in done]),
            "espera_mem_prom": avg([p.wait_mem for p in done]),
            "throughput": n / self.t if self.t else 0.0,
            "bloqueado_prom": avg([p.blocked_time for p in done]),
        }
        if self.mem is not None:
            out.update({
                "mem_total": 0, "mem_ocupacion": 0.0, "mem_libre": 0, "mayor_libre": 0,
                "frag_externa": 0.0, "frag_interna": 0.0,
            })
            s = self.mem.stats()
            out.update({"mem_total": s["total"], "mem_ocupacion": s["occupancy"],
                        "mem_libre": s["free"], "mayor_libre": s["largest_free"],
                        "frag_externa": s["ext_frag"], "frag_interna": s["int_frag"]})
            n = max(1, self.acc["n"])
            out.update({"ocupacion_prom": self.acc["occ"] / n, "frag_ext_prom": self.acc["ext"] / n,
                        "frag_ext_max": self.acc["ext_max"], "frag_int_prom": self.acc["int"] / n})
            if "compactions" in s:
                out["compactaciones"] = s["compactions"]
            if isinstance(self.mem, PagingManager):
                m = self.mem
                out.update({
                    "accesos": m.accesses, "fallos_pagina": m.faults,
                    "tasa_fallos": m.fault_rate, "tlb_hit": m.tlb_hit_rate,
                    "tlb_miss": 100 - m.tlb_hit_rate if (m.tlb_hits + m.tlb_misses) else 0.0,
                    "eat_ns": m.eat, "swap_in": m.swap_in, "swap_out": m.swap_out,
                    "swap_trafico": (m.swap_in + m.swap_out) * m.ps,
                    "reemplazos": m.replacements,
                })
            if self.cfg.mode == "segmentation":
                out["violaciones"] = sum(p.violations for p in self.procs)
        return out

    def process_rows(self):
        """Filas de la tabla de procesos (siempre visible en la interfaz)."""
        rows = []
        for p in self.procs:
            rows.append({
                "pid": p.pid, "nombre": p.name, "estado": p.state, "llegada": p.arrival,
                "rafaga": p.burst, "restante": p.remaining, "tamano": p.size,
                "memoria": self.mem_text(p), "inicio": p.first_run, "fin": p.finish,
                "retorno": p.turnaround if p.state == M.DONE and not p.reason else None,
                "espera": p.wait_ready, "esp_mem": p.wait_mem, "bloq": p.blocked_time,
                "fallos": p.faults, "nota": p.reason,
            })
        return rows
