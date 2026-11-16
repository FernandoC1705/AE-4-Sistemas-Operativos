"""Políticas de reemplazo (FIFO, LRU, Clock) y de ajuste (First/Best/Worst Fit).

Las políticas de reemplazo se usan tanto para la TLB como para los marcos de la
memoria física; trabajan sobre "claves" opacas (aquí, tuplas (pid, página)).
Interfaz común:
    insert(k)       agrega una clave nueva (la entrada ya tiene lugar)
    touch(k)        registra un acceso a la clave
    remove(k)       elimina la clave
    victim(exclude) devuelve la clave a reemplazar (sin sacarla), o None
    replace(old,new) reemplaza la víctima por una clave nueva
    keys()          claves en el orden interno (para mostrar y para convertir)
"""
from __future__ import annotations

from collections import OrderedDict


class ReplacementPolicy:
    name = ""

    def __len__(self):
        raise NotImplementedError

    def insert(self, key): raise NotImplementedError
    def touch(self, key): raise NotImplementedError
    def remove(self, key): raise NotImplementedError
    def victim(self, exclude=frozenset()): raise NotImplementedError
    def keys(self): raise NotImplementedError

    def replace(self, old, new):
        self.remove(old)
        self.insert(new)

    def describe(self):
        """Lista de (clave, nota) para mostrar en la interfaz."""
        return [(k, "") for k in self.keys()]


class FIFOPolicy(ReplacementPolicy):
    """Reemplaza la entrada más antigua (orden de carga); los accesos no cuentan."""
    name = "FIFO"

    def __init__(self):
        self.q = OrderedDict()

    def __len__(self): return len(self.q)
    def insert(self, key): self.q[key] = True
    def touch(self, key): pass
    def remove(self, key): self.q.pop(key, None)
    def keys(self): return list(self.q)

    def victim(self, exclude=frozenset()):
        for k in self.q:
            if k not in exclude:
                return k
        return None


class LRUPolicy(FIFOPolicy):
    """Reemplaza la entrada menos recientemente usada (se mueve al final al accederla)."""
    name = "LRU"

    def touch(self, key):
        if key in self.q:
            self.q.move_to_end(key)


class ClockPolicy(ReplacementPolicy):
    """Segunda oportunidad con anillo circular y bit de referencia."""
    name = "Clock"

    def __init__(self):
        self.ring = []
        self.ref = {}
        self.hand = 0

    def __len__(self): return len(self.ring)

    def insert(self, key):
        self.ring.append(key)
        self.ref[key] = True

    def touch(self, key):
        if key in self.ref:
            self.ref[key] = True

    def remove(self, key):
        if key not in self.ref:
            return
        i = self.ring.index(key)
        del self.ring[i]
        del self.ref[key]
        if i < self.hand:
            self.hand -= 1
        if self.ring:
            self.hand %= len(self.ring)
        else:
            self.hand = 0

    def victim(self, exclude=frozenset()):
        if not self.ring or all(k in exclude for k in self.ring):
            return None
        n = len(self.ring)
        while True:
            k = self.ring[self.hand]
            if k in exclude:
                self.hand = (self.hand + 1) % n
            elif self.ref[k]:
                self.ref[k] = False          # segunda oportunidad
                self.hand = (self.hand + 1) % n
            else:
                return k

    def replace(self, old, new):
        """La entrada nueva ocupa la posición de la víctima y la manecilla avanza."""
        i = self.ring.index(old)
        del self.ref[old]
        self.ring[i] = new
        self.ref[new] = True
        self.hand = (i + 1) % len(self.ring)

    def keys(self): return list(self.ring)

    def describe(self):
        return [(k, f"R={int(self.ref[k])}" + (" ◄" if i == self.hand else ""))
                for i, k in enumerate(self.ring)]


def make_policy(name: str) -> ReplacementPolicy:
    n = name.upper()
    if n == "FIFO":
        return FIFOPolicy()
    if n == "LRU":
        return LRUPolicy()
    if n == "CLOCK":
        return ClockPolicy()
    raise ValueError(f"Política desconocida: {name}")


def convert_policy(old: ReplacementPolicy, new_name: str) -> ReplacementPolicy:
    """Cambia de algoritmo en caliente conservando las entradas actuales."""
    new = make_policy(new_name)
    for k in old.keys():
        new.insert(k)
    return new


# ------------------------------------------------------------------ ajuste
def pick_hole(holes, need: int, fit: str):
    """Elige un hueco (objeto con .start y .size) según la política de ajuste."""
    cand = [h for h in holes if h.size >= need]
    if not cand:
        return None
    if fit == "first":
        return min(cand, key=lambda h: h.start)
    if fit == "best":
        return min(cand, key=lambda h: (h.size, h.start))
    if fit == "worst":
        return max(cand, key=lambda h: (h.size, -h.start))
    raise ValueError(f"Política de ajuste desconocida: {fit}")
