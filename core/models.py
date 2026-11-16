"""Modelos de datos del simulador: estados, configuración y procesos.

Convenciones:
  * Una unidad de tiempo ("tick") = una unidad de CPU.
  * Los tamaños de memoria se expresan en bytes (números chicos para poder
    seguir las cuentas a mano durante la defensa).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import List, Optional, Tuple

# ---------------------------------------------------------------- estados
NEW = "Nuevo"
WAIT_MEM = "Esperando Memoria"
READY = "Listo"
RUNNING = "Ejecutando"
BLOCKED = "Bloqueado"
WAIT_PAGE = "Esperando Página"
DONE = "Terminado"
REJECTED = "Rechazado"

ALL_STATES = [NEW, WAIT_MEM, READY, RUNNING, BLOCKED, WAIT_PAGE, DONE, REJECTED]

MODES = {
    "none": "Solo planificación de CPU",
    "contiguous": "Memoria continua",
    "paging": "Paginación + TLB + swap",
    "segmentation": "Segmentación",
}
SCHEDULERS = ["FIFO", "RR", "SJF", "SRTF"]
FITS = ["first", "best", "worst"]
FIT_NAMES = {"first": "First Fit", "best": "Best Fit", "worst": "Worst Fit"}
REPL_POLICIES = ["FIFO", "LRU", "Clock"]


@dataclass
class Config:
    """Parámetros de un escenario (todos configurables desde la interfaz)."""
    mode: str = "paging"            # none | contiguous | paging | segmentation
    # --- planificación de CPU
    scheduler: str = "RR"           # FIFO | RR | SJF | SRTF
    quantum: int = 4
    # --- memoria continua / segmentación
    mem_size: int = 1024            # memoria física total (bytes)
    fit: str = "first"              # first | best | worst
    partition: str = "variable"     # variable | fixed (solo memoria continua)
    fixed_partitions: List[int] = field(default_factory=lambda: [128, 128, 256, 512])
    auto_compact: bool = False      # compactar automáticamente si no hay hueco contiguo
    # --- paginación
    page_size: int = 64
    tlb_size: int = 4               # 0 = sin TLB
    tlb_policy: str = "LRU"         # FIFO | LRU | Clock
    repl_policy: str = "LRU"        # reemplazo de páginas: FIFO | LRU | Clock
    swap_size: int = 8192           # tamaño del área de swap (bytes)
    tlb_flush_on_switch: bool = False  # TLB sin ASID: se vacía en cada cambio de contexto
    # --- tiempos (ns) para el tiempo efectivo de acceso
    t_tlb: int = 10
    t_mem: int = 100
    t_fault: int = 100_000          # servicio de una transferencia página<->swap
    # --- efecto de los fallos de página sobre la planificación (en ticks)
    swap_in_ticks: int = 3
    swap_out_ticks: int = 2
    # --- generación de accesos
    seed: int = 1
    locality: float = 0.8
    write_prob: float = 0.3
    max_ticks: int = 20000

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        names = {f.name for f in fields(cls)}
        c = cls(**{k: v for k, v in (d or {}).items() if k in names})
        c.validate()
        return c

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def copy(self, **changes) -> "Config":
        c = copy.deepcopy(self)
        for k, v in changes.items():
            setattr(c, k, v)
        c.validate()
        return c

    def validate(self):
        if self.mode not in MODES:
            raise ValueError(f"Modo inválido: {self.mode}")
        if self.scheduler not in SCHEDULERS:
            raise ValueError(f"Planificador inválido: {self.scheduler}")
        if self.fit not in FITS:
            raise ValueError(f"Política de ajuste inválida: {self.fit}")
        if self.tlb_policy not in REPL_POLICIES or self.repl_policy not in REPL_POLICIES:
            raise ValueError("Política de reemplazo inválida (FIFO, LRU o Clock)")
        if self.quantum < 1:
            raise ValueError("El quantum debe ser >= 1")
        if self.page_size < 1 or self.mem_size < 1:
            raise ValueError("Tamaños de memoria/página deben ser >= 1")
        if self.mode == "paging" and self.mem_size < self.page_size:
            raise ValueError("La memoria física debe contener al menos un marco")


@dataclass
class PTE:
    """Entrada de la tabla de páginas."""
    frame: Optional[int] = None
    valid: bool = False      # presente en memoria física
    dirty: bool = False
    loading: bool = False    # carga desde swap en curso
    swap_slot: Optional[int] = None


@dataclass
class Process:
    pid: int
    name: str
    arrival: int
    burst: int
    size: int = 0
    segments: List[Tuple[str, int]] = field(default_factory=list)
    io: List[Tuple[int, int]] = field(default_factory=list)       # (ráfaga de CPU acumulada, duración)
    accesses: list = field(default_factory=list)                  # ver scenario.normalize_accesses
    # ------------------------------------------------ estado de ejecución
    state: str = NEW
    remaining: int = 0
    cpu_done: int = 0
    first_run: Optional[int] = None
    finish: Optional[int] = None
    reason: str = ""
    quantum_used: int = 0
    wake_at: int = 0
    io_idx: int = 0
    ready_since: int = 0
    wait_ready: int = 0
    wait_mem: int = 0
    blocked_time: int = 0
    resolved: bool = False        # el acceso pendiente ya se resolvió (fallo atendido)
    retry: bool = False
    pending: Optional[tuple] = None   # (página, es_escritura) de una carga en curso
    # métricas por proceso
    faults: int = 0
    mem_accesses: int = 0
    tlb_hits: int = 0
    tlb_misses: int = 0
    violations: int = 0
    # estructuras de memoria
    blocks: list = field(default_factory=list)      # bloques (continua / segmentos)
    page_table: list = field(default_factory=list)  # lista de PTE (paginación)

    def __post_init__(self):
        if self.segments:
            self.segments = [(str(n), int(s)) for n, s in self.segments]
            if not self.size:
                self.size = sum(s for _, s in self.segments)
        self.io = sorted((int(a), int(b)) for a, b in self.io)
        self.reset()

    def reset(self):
        self.state = NEW
        self.remaining = self.burst
        self.cpu_done = 0
        self.first_run = self.finish = None
        self.reason = ""
        self.quantum_used = self.wake_at = self.io_idx = self.ready_since = 0
        self.wait_ready = self.wait_mem = self.blocked_time = 0
        self.resolved = self.retry = False
        self.pending = None
        self.faults = self.mem_accesses = self.tlb_hits = self.tlb_misses = self.violations = 0
        self.blocks = []
        self.page_table = []

    # -- métricas derivadas
    @property
    def turnaround(self):
        return None if self.finish is None else self.finish - self.arrival

    @property
    def response(self):
        return None if self.first_run is None else self.first_run - self.arrival
