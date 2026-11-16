"""Memoria continua (particiones fijas o variables) y segmentación.

Ambos esquemas comparten el mismo mapa de memoria (MemoryMap) y las mismas
políticas First/Best/Worst Fit; la diferencia es qué se pide:
  * Memoria continua: un bloque por proceso (tamaño total del proceso).
  * Segmentación:     un bloque por segmento (tabla de segmentos base/límite).
"""
from __future__ import annotations

from .models import Process
from .policies import pick_hole


class Block:
    """Un tramo del mapa de memoria. pid=None significa libre."""
    __slots__ = ("start", "size", "pid", "label", "used")

    def __init__(self, start, size, pid=None, label="", used=0):
        self.start, self.size, self.pid, self.label, self.used = start, size, pid, label, used

    @property
    def free(self):
        return self.pid is None

    @property
    def end(self):
        return self.start + self.size

    def __repr__(self):
        return f"Block({self.start}..{self.end}, {'libre' if self.free else self.pid})"


class MemoryMap:
    """Mapa de memoria como lista ordenada de bloques contiguos."""

    def __init__(self, total: int, fixed_sizes=None):
        self.fixed = bool(fixed_sizes)
        self.blocks = []
        if self.fixed:
            pos = 0
            for s in fixed_sizes:
                self.blocks.append(Block(pos, int(s)))
                pos += int(s)
            self.total = pos
        else:
            self.total = total
            self.blocks = [Block(0, total)]
        self.compactions = 0
        self.bytes_moved = 0

    # ------------------------------------------------------------ consulta
    def holes(self):
        return [b for b in self.blocks if b.free]

    def allocated(self):
        return [b for b in self.blocks if not b.free]

    @property
    def free_total(self):
        return sum(b.size for b in self.holes())

    @property
    def used_total(self):
        return sum(b.size for b in self.allocated())

    @property
    def largest_free(self):
        return max((b.size for b in self.holes()), default=0)

    @property
    def external_frag(self):
        """% de memoria libre inutilizable para una petición del tamaño de todo lo libre."""
        ft = self.free_total
        return 0.0 if ft == 0 else (1 - self.largest_free / ft) * 100

    @property
    def internal_waste(self):
        return sum(b.size - b.used for b in self.allocated())

    # ------------------------------------------------------------ operaciones
    def allocate(self, size, fit, pid, label=""):
        h = pick_hole(self.holes(), size, fit)
        if h is None:
            return None
        if self.fixed or h.size == size:
            h.pid, h.label, h.used = pid, label, size
            return h
        new = Block(h.start, size, pid, label, size)
        h.start += size
        h.size -= size
        self.blocks.insert(self.blocks.index(h), new)
        return new

    def release(self, pid):
        for b in self.blocks:
            if b.pid == pid:
                b.pid, b.label, b.used = None, "", 0
        if not self.fixed:
            self._coalesce()

    def _coalesce(self):
        out = []
        for b in self.blocks:
            if out and out[-1].free and b.free:
                out[-1].size += b.size
            else:
                out.append(b)
        self.blocks = out

    def compact(self):
        """Compactación: desplaza todos los bloques ocupados hacia la dirección 0.
        Los objetos Block ocupados se conservan (se modifica su .start), por lo que
        las tablas de segmentos / procesos quedan actualizadas automáticamente."""
        if self.fixed:
            return 0
        pos, moved, out = 0, 0, []
        for b in self.allocated():
            if b.start != pos:
                moved += b.size
                b.start = pos
            out.append(b)
            pos += b.size
        if pos < self.total:
            out.append(Block(pos, self.total - pos))
        self.blocks = out
        if moved:
            self.compactions += 1
            self.bytes_moved += moved
        return moved


class ContiguousManager:
    """Asignación contigua. Admite particiones variables o fijas."""
    kind = "contiguous"

    def __init__(self, cfg):
        fixed = cfg.fixed_partitions if cfg.partition == "fixed" else None
        self.map = MemoryMap(cfg.mem_size, fixed)
        self.fit = cfg.fit
        self.auto_compact = cfg.auto_compact
        self.log = []          # mensajes para el registro de eventos del motor

    # petición de memoria de un proceso: lista de (etiqueta, tamaño)
    def requests(self, p: Process):
        return [(p.name, p.size)]

    def can_ever_fit(self, p: Process) -> bool:
        need = [s for _, s in self.requests(p)]
        if self.map.fixed:
            return max(b.size for b in self.map.blocks) >= max(need)
        return sum(need) <= self.map.total

    def _try(self, p):
        got = []
        for label, size in self.requests(p):
            b = self.map.allocate(size, self.fit, p.pid, label)
            if b is None:
                self.map.release(p.pid)
                return None
            got.append(b)
        return got

    def admit(self, p: Process) -> bool:
        blocks = self._try(p)
        need = sum(s for _, s in self.requests(p))
        if (blocks is None and self.auto_compact and not self.map.fixed
                and self.map.free_total >= need):
            moved = self.map.compact()
            self.log.append(f"Compactación automática: {moved} bytes movidos")
            blocks = self._try(p)
        if blocks is None:
            return False
        p.blocks = blocks
        return True

    def release(self, p: Process):
        self.map.release(p.pid)
        p.blocks = []

    def compact(self):
        return self.map.compact()

    # ---------------------------------------------------------- vistas/estadísticas
    def describe(self, p: Process) -> str:
        if not p.blocks:
            return "—"
        return ", ".join(f"[{b.start}..{b.end})" for b in p.blocks)

    def stats(self) -> dict:
        m = self.map
        used = m.used_total
        return {
            "total": m.total,
            "used": used,
            "free": m.free_total,
            "largest_free": m.largest_free,
            "occupancy": used / m.total * 100 if m.total else 0.0,
            "ext_frag": m.external_frag,
            "int_frag": (m.internal_waste / used * 100) if used else 0.0,
            "holes": len(m.holes()),
            "compactions": m.compactions,
        }


class SegmentationManager(ContiguousManager):
    """Segmentación pura: tabla de segmentos (base, límite) por proceso."""
    kind = "segmentation"

    def __init__(self, cfg):
        cfg = cfg.copy(partition="variable")
        super().__init__(cfg)

    def requests(self, p: Process):
        return list(p.segments) if p.segments else [("principal", p.size)]

    def seg_table(self, p: Process):
        """[(nombre, base, límite)] del proceso."""
        return [(b.label, b.start, b.size) for b in p.blocks]

    def translate(self, p: Process, seg: int, offset: int):
        """Devuelve (dirección física, None) o (None, motivo de violación)."""
        if not p.blocks:
            return None, "proceso sin segmentos en memoria"
        if not 0 <= seg < len(p.blocks):
            return None, f"segmento {seg} inexistente"
        b = p.blocks[seg]
        if not 0 <= offset < b.size:
            return None, (f"desplazamiento {offset} fuera del límite del segmento "
                          f"'{b.label}' (límite={b.size})")
        return b.start + offset, None

    def describe(self, p: Process) -> str:
        if not p.blocks:
            return "—"
        return ", ".join(f"{b.label}@{b.start}" for b in p.blocks)
