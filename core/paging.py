"""Memoria paginada con TLB, memoria virtual, área de swap y reemplazo de páginas.

Modelo:
  * Memoria física = n_frames marcos de page_size bytes.
  * Cada proceso tiene una tabla de páginas (lista de PTE). Todas sus páginas
    tienen un lugar reservado en el área de swap desde la admisión (el espacio de
    direcciones virtual puede ser mucho mayor que la memoria física).
  * Carga bajo demanda: una página llega a memoria sólo cuando se la referencia
    (fallo de página). Si no hay marcos libres, se elige una víctima con la
    política de reemplazo; si estaba modificada (dirty) se escribe en swap.
  * La TLB guarda (pid, página) -> marco; por defecto está etiquetada con el PID,
    o se vacía en cada cambio de contexto si tlb_flush_on_switch está activo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .models import PTE, Process
from .policies import convert_policy, make_policy


@dataclass
class AccessResult:
    kind: str                       # hit | tlb_miss | fault | retry | invalid
    page: int = 0
    offset: int = 0
    frame: Optional[int] = None
    phys: Optional[int] = None
    cost_ns: int = 0
    victim: Optional[tuple] = None  # (pid, página) desalojada
    victim_dirty: bool = False
    ticks: int = 0                  # ticks que queda bloqueado el proceso (solo fallos)
    msg: str = ""


class PagingManager:
    kind = "paging"

    def __init__(self, cfg):
        self.cfg = cfg
        self.ps = cfg.page_size
        self.n_frames = cfg.mem_size // cfg.page_size
        self.free_frames = list(range(self.n_frames))
        self.resident = {}              # (pid, página) -> marco
        self.loading = set()            # claves con carga desde swap en curso (no desalojables)
        self.tables = {}                # pid -> tabla de páginas
        self.sizes = {}                 # pid -> tamaño real (para fragmentación interna)
        self.owner = {}                 # marco -> (pid, página)
        self.swap_slots = cfg.swap_size // cfg.page_size
        self.swap_free = list(range(self.swap_slots))
        self.swap_owner = {}            # slot -> (pid, página)
        self.tlb = {}                   # (pid, página) -> marco
        self.tlb_size = cfg.tlb_size
        self.tlb_policy = make_policy(cfg.tlb_policy)
        self.frame_policy = make_policy(cfg.repl_policy)
        self.log = []
        # contadores
        self.accesses = self.tlb_hits = self.tlb_misses = self.faults = 0
        self.swap_in = self.swap_out = 0
        self.total_ns = 0
        self.replacements = 0
        self.flushes = 0

    # --------------------------------------------------------------- admisión
    def pages_of(self, p: Process) -> int:
        return max(1, math.ceil(p.size / self.ps))

    def can_ever_fit(self, p: Process) -> bool:
        return self.pages_of(p) <= self.swap_slots

    def admit(self, p: Process) -> bool:
        n = self.pages_of(p)
        if len(self.swap_free) < n:
            return False
        table = [PTE() for _ in range(n)]
        for i, pte in enumerate(table):
            slot = self.swap_free.pop(0)
            pte.swap_slot = slot
            self.swap_owner[slot] = (p.pid, i)
        p.page_table = table
        self.tables[p.pid] = table
        self.sizes[p.pid] = p.size
        return True

    def release(self, p: Process):
        for page, pte in enumerate(p.page_table):
            key = (p.pid, page)
            if key in self.resident:
                f = self.resident.pop(key)
                self.owner.pop(f, None)
                self.free_frames.append(f)
                self.frame_policy.remove(key)
            self.loading.discard(key)
            if key in self.tlb:
                del self.tlb[key]
                self.tlb_policy.remove(key)
            if pte.swap_slot is not None:
                self.swap_owner.pop(pte.swap_slot, None)
                self.swap_free.append(pte.swap_slot)
        self.free_frames.sort()
        self.swap_free.sort()
        self.tables.pop(p.pid, None)
        self.sizes.pop(p.pid, None)
        p.page_table = []

    # ------------------------------------------------------------------- TLB
    def flush_tlb(self):
        if self.tlb:
            self.flushes += 1
        for k in list(self.tlb):
            self.tlb_policy.remove(k)
        self.tlb.clear()

    def _tlb_insert(self, key, frame):
        if self.tlb_size <= 0:
            return
        if key in self.tlb:
            self.tlb[key] = frame
            self.tlb_policy.touch(key)
            return
        if len(self.tlb) >= self.tlb_size:
            v = self.tlb_policy.victim()
            self.tlb_policy.replace(v, key)
            del self.tlb[v]
            self.log.append(f"TLB: reemplazo ({self.tlb_policy.name}) sale P{v[0]}:pág {v[1]}, "
                            f"entra P{key[0]}:pág {key[1]}")
        else:
            self.tlb_policy.insert(key)
        self.tlb[key] = frame

    def _tlb_invalidate(self, key):
        if key in self.tlb:
            del self.tlb[key]
            self.tlb_policy.remove(key)

    # ---------------------------------------------------------------- acceso
    def access(self, p: Process, addr: int, write: bool) -> AccessResult:
        """Traduce la dirección lógica `addr` del proceso `p`."""
        ps = self.ps
        page, off = divmod(addr, ps)
        if addr < 0 or page >= len(p.page_table):
            return AccessResult("invalid", page, off, msg=(
                f"dirección lógica {addr} fuera del espacio de direcciones "
                f"({len(p.page_table) * ps} bytes)"))
        cfg = self.cfg
        key = (p.pid, page)
        use_tlb = self.tlb_size > 0
        t_tlb = cfg.t_tlb if use_tlb else 0

        # 1) TLB
        if use_tlb and key in self.tlb:
            f = self.tlb[key]
            self._count_access(p, hit=True)
            self.tlb_policy.touch(key)
            self.frame_policy.touch(key)
            if write:
                p.page_table[page].dirty = True
            cost = t_tlb + cfg.t_mem
            self.total_ns += cost
            return AccessResult("hit", page, off, f, f * ps + off, cost)

        # 2) tabla de páginas (en memoria)
        pte = p.page_table[page]
        if pte.loading:          # la página ya se está trayendo desde swap
            return AccessResult("retry", page, off, msg="la página está en carga desde swap")
        if pte.valid:
            self._count_access(p, hit=False)
            self.frame_policy.touch(key)
            if write:
                pte.dirty = True
            self._tlb_insert(key, pte.frame)
            cost = t_tlb + 2 * cfg.t_mem
            self.total_ns += cost
            return AccessResult("tlb_miss", page, off, pte.frame, pte.frame * ps + off, cost)

        # 3) fallo de página: conseguir un marco
        victim, vdirty = None, False
        if self.free_frames:
            f = self.free_frames.pop(0)
            self.frame_policy.insert(key)
        else:
            vk = self.frame_policy.victim(exclude=self.loading)
            if vk is None:       # todos los marcos están en plena carga: reintentar luego
                return AccessResult("retry", page, off, msg="sin marcos desalojables, reintenta")
            f = self.resident.pop(vk)
            vpte = self.tables[vk[0]][vk[1]]
            vdirty = vpte.dirty
            if vdirty:
                self.swap_out += 1
            vpte.valid, vpte.frame, vpte.dirty = False, None, False
            self._tlb_invalidate(vk)
            self.frame_policy.replace(vk, key)
            victim = vk
            self.replacements += 1
        self._count_access(p, hit=False)
        self.faults += 1
        p.faults += 1
        self.swap_in += 1
        self.resident[key] = f
        self.owner[f] = key
        pte.frame, pte.loading = f, True
        self.loading.add(key)
        cost = t_tlb + cfg.t_mem + cfg.t_fault + (cfg.t_fault if vdirty else 0) + cfg.t_mem
        self.total_ns += cost
        ticks = cfg.swap_in_ticks + (cfg.swap_out_ticks if vdirty else 0)
        return AccessResult("fault", page, off, f, f * ps + off, cost, victim, vdirty, ticks)

    def complete_load(self, p: Process, page: int, write: bool):
        """La página llegó desde swap: queda válida y se carga en la TLB."""
        key = (p.pid, page)
        pte = p.page_table[page]
        pte.valid, pte.loading, pte.dirty = True, False, bool(write)
        self.loading.discard(key)
        self._tlb_insert(key, pte.frame)

    def _count_access(self, p, hit):
        self.accesses += 1
        p.mem_accesses += 1
        if self.tlb_size > 0:
            if hit:
                self.tlb_hits += 1
                p.tlb_hits += 1
            else:
                self.tlb_misses += 1
                p.tlb_misses += 1

    # ---------------------------------------------------- cambio en caliente
    def set_policies(self, tlb_policy=None, repl_policy=None):
        if tlb_policy and tlb_policy != self.tlb_policy.name:
            self.tlb_policy = convert_policy(self.tlb_policy, tlb_policy)
        if repl_policy and repl_policy != self.frame_policy.name:
            self.frame_policy = convert_policy(self.frame_policy, repl_policy)

    # ----------------------------------------------------------------- vistas
    def describe(self, p: Process) -> str:
        if not p.page_table:
            return "—"
        res = sum(1 for e in p.page_table if e.valid or e.loading)
        return f"{res}/{len(p.page_table)} págs en RAM"

    def stats(self) -> dict:
        used = len(self.resident)
        free = self.n_frames - used
        pages_alloc = sum(len(pt) for pt in self.tables.values())
        waste = pages_alloc * self.ps - sum(self.sizes.values())
        return {
            "total": self.n_frames * self.ps,
            "used": used * self.ps,
            "free": free * self.ps,
            "largest_free": free * self.ps,        # sin fragmentación externa
            "occupancy": used / self.n_frames * 100 if self.n_frames else 0.0,
            "ext_frag": 0.0,
            "int_frag": (waste / (pages_alloc * self.ps) * 100) if pages_alloc else 0.0,
            "frames_used": used,
            "frames_total": self.n_frames,
            "swap_used": self.swap_slots - len(self.swap_free),
            "swap_total": self.swap_slots,
        }

    @property
    def tlb_hit_rate(self):
        n = self.tlb_hits + self.tlb_misses
        return self.tlb_hits / n * 100 if n else 0.0

    @property
    def fault_rate(self):
        return self.faults / self.accesses * 100 if self.accesses else 0.0

    @property
    def eat(self):
        return self.total_ns / self.accesses if self.accesses else 0.0
