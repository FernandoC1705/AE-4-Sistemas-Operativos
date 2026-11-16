"""Pruebas automáticas del núcleo. Ejecutar:  python -m unittest discover -s tests -v"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import models as M
from core.engine import Simulation
from core.memory import MemoryMap
from core.models import Config, Process
from core.policies import ClockPolicy, FIFOPolicy, LRUPolicy, pick_hole
from core.scenario import list_scenarios, load_scenario


def run(cfg, procs):
    return Simulation(cfg, procs).run()


class TestPlanificacion(unittest.TestCase):
    procs = [Process(1, "P1", 0, 5), Process(2, "P2", 1, 3), Process(3, "P3", 2, 1)]

    def seg(self, sched, q=2):
        s = run(Config(mode="none", scheduler=sched, quantum=q), self.procs)
        return s.gantt_segments(), s.metrics()

    def test_fifo(self):
        g, m = self.seg("FIFO")
        self.assertEqual(g, [(0, 5, 1), (5, 8, 2), (8, 9, 3)])
        self.assertAlmostEqual(m["espera_prom"], (0 + 4 + 6) / 3)

    def test_rr(self):
        g, m = self.seg("RR")
        self.assertEqual(g, [(0, 2, 1), (2, 4, 2), (4, 5, 3), (5, 7, 1), (7, 8, 2), (8, 9, 1)])
        self.assertEqual(m["cambios_contexto"], 5)

    def test_sjf_no_apropiativo(self):
        g, _ = self.seg("SJF")
        self.assertEqual(g, [(0, 5, 1), (5, 6, 3), (6, 9, 2)])

    def test_srtf(self):
        g, m = self.seg("SRTF")
        self.assertEqual(g, [(0, 1, 1), (1, 2, 2), (2, 3, 3), (3, 5, 2), (5, 9, 1)])
        self.assertLess(m["espera_prom"], self.seg("SJF")[1]["espera_prom"])

    def test_es_bloquea_y_libera_cpu(self):
        ps = [Process(1, "A", 0, 4, io=[(2, 3)]), Process(2, "B", 0, 3)]
        s = run(Config(mode="none", scheduler="FIFO"), ps)
        a, b = s.procs
        self.assertEqual(a.blocked_time, 3)
        self.assertEqual(s.gantt[:5], [1, 1, 2, 2, 2])   # mientras A está bloqueado corre B

    def test_cpu_ociosa(self):
        s = run(Config(mode="none", scheduler="FIFO"), [Process(1, "A", 5, 2)])
        self.assertEqual(s.gantt, [None] * 5 + [1, 1])
        self.assertAlmostEqual(s.metrics()["cpu_uso"], 2 / 7 * 100)


class TestPoliticas(unittest.TestCase):
    def test_fifo_lru_clock(self):
        f, l, c = FIFOPolicy(), LRUPolicy(), ClockPolicy()
        for p in (f, l, c):
            for k in "abc":
                p.insert(k)
            p.touch("a")
        self.assertEqual(f.victim(), "a")      # la más vieja, aunque se usó
        self.assertEqual(l.victim(), "b")      # la menos recientemente usada
        self.assertEqual(c.victim(), "a")      # todas con R=1 -> se limpian y sale la primera
        self.assertEqual(c.victim(exclude={"a"}), "b")

    def test_fit(self):
        m = MemoryMap(1000)
        a = m.allocate(100, "first", 1); b = m.allocate(50, "first", 2)
        c = m.allocate(300, "first", 3); d = m.allocate(50, "first", 4)
        m.release(1); m.release(3)             # huecos: [0,100) y [150,450) y cola
        holes = m.holes()
        self.assertEqual(pick_hole(holes, 80, "first").start, 0)
        self.assertEqual(pick_hole(holes, 80, "best").start, 0)
        self.assertEqual(pick_hole(holes, 80, "worst").start, 500)  # la cola (550) es la mayor

    def test_coalescencia_y_compactacion(self):
        m = MemoryMap(300)
        for pid in (1, 2, 3):
            m.allocate(100, "first", pid)
        m.release(2)
        self.assertEqual(m.largest_free, 100)
        self.assertEqual(m.compact(), 100)     # P3 se mueve 100 bytes
        self.assertEqual([(b.start, b.size, b.pid) for b in m.blocks][-1], (200, 100, None))

    def test_particiones_fijas_fragmentacion_interna(self):
        m = MemoryMap(0, [100, 200])
        b = m.allocate(150, "best", 1)
        self.assertEqual(b.size, 200)
        self.assertEqual(m.internal_waste, 50)


class TestMemoriaContinua(unittest.TestCase):
    def setUp(self):
        self.cfg, self.procs, _ = load_scenario("scenarios/02_memoria_continua.json")

    def test_best_fit_aloja_todos_first_y_worst_esperan(self):
        res = {}
        for fit in ("first", "best", "worst"):
            s = run(self.cfg.copy(fit=fit), self.procs)
            res[fit] = s.metrics()["espera_mem_prom"]
        self.assertEqual(res["best"], 0)
        self.assertGreater(res["first"], 0)
        self.assertGreater(res["worst"], 0)

    def test_compactacion_automatica_evita_espera(self):
        s = run(self.cfg.copy(fit="first", auto_compact=True), self.procs)
        self.assertEqual(s.metrics()["espera_mem_prom"], 0)
        self.assertEqual(s.metrics()["compactaciones"], 1)

    def test_rechazo_por_tamano(self):
        ps = [Process(1, "G", 0, 3, size=5000)]
        s = run(Config(mode="contiguous", mem_size=1000), ps)
        self.assertEqual(s.procs[0].state, M.REJECTED)

    def test_cola_espera_y_liberacion(self):
        ps = [Process(1, "A", 0, 3, size=600), Process(2, "B", 0, 2, size=600)]
        s = Simulation(Config(mode="contiguous", scheduler="FIFO", mem_size=1000), ps)
        s.step()
        self.assertEqual(s.procs[1].state, M.WAIT_MEM)
        s.run()
        self.assertEqual(s.procs[1].state, M.DONE)
        self.assertEqual(s.procs[1].wait_mem, 3)


class TestPaginacion(unittest.TestCase):
    REF = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

    def faults(self, policy, frames):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=10 * frames,
                     tlb_size=0, repl_policy=policy, swap_size=1000)
        p = Process(1, "P", 0, len(self.REF), size=60, accesses=[r * 10 for r in self.REF])
        return run(cfg, [p]).metrics()["fallos_pagina"]

    def test_belady(self):
        self.assertEqual(self.faults("FIFO", 3), 9)
        self.assertEqual(self.faults("FIFO", 4), 10)     # anomalía de Belady
        self.assertEqual(self.faults("LRU", 3), 10)
        self.assertEqual(self.faults("LRU", 4), 8)

    def test_traduccion_direccion(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=64, mem_size=256, tlb_size=2, swap_size=2048)
        p = Process(1, "P", 0, 3, size=300, accesses=[130, 130, 5])
        s = Simulation(cfg, [p])
        s._admit(s.procs[0])                        # admitido (tabla de páginas creada) pero sin correr
        msg = s.manual_access(1, 130)               # pág 2, desplazamiento 2 -> fallo, marco 0
        self.assertIn("FALLO", msg)
        self.assertIn("física 2", msg)
        msg = s.manual_access(1, 130)
        self.assertIn("TLB hit", msg)
        self.assertIn("pág 2+2", msg)

    def test_tlb_hit_miss_y_reemplazo(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=100, tlb_size=2,
                     tlb_policy="LRU", swap_size=1000)
        # páginas 0,1,0,2,0,1: con TLB LRU de 2 entradas
        refs = [0, 10, 0, 20, 0, 10]
        s = run(cfg, [Process(1, "P", 0, 6, size=60, accesses=refs)])
        m = s.metrics()
        self.assertEqual(m["fallos_pagina"], 3)
        self.assertEqual(s.mem.tlb_hits + s.mem.tlb_misses, 6 - 0)   # todos los accesos cuentan
        self.assertGreater(s.mem.tlb_hits, 0)

    def test_fallo_bloquea_proceso_y_afecta_tiempo(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=100, tlb_size=0,
                     swap_size=1000, swap_in_ticks=3)
        s = run(cfg, [Process(1, "P", 0, 2, size=20, accesses=[0, 10])])
        # cada fallo bloquea 3 ticks: 2 fallos -> 6 ticks bloqueado + 2 de CPU
        self.assertEqual(s.t, 8)
        self.assertEqual(s.procs[0].blocked_time, 6)

    def test_fallo_de_un_proceso_deja_correr_a_otro(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=100, tlb_size=0,
                     swap_size=1000, swap_in_ticks=3)
        ps = [Process(1, "A", 0, 3, size=20, accesses=[0, 10, 10]),
              Process(2, "B", 0, 4, size=20, accesses=[0, 0, 0, 0])]
        s = Simulation(cfg, ps)
        for _ in range(5):
            s.step()
        # t0..2 ambos esperan su primera página; t3 corre A; t4 A falla (pág 1) y corre B
        self.assertEqual(s.gantt[:5], [None, None, None, 1, 2])
        self.assertEqual(s.procs[0].state, M.WAIT_PAGE)

    def test_dirty_genera_swap_out(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=10, tlb_size=0, swap_size=1000)
        s = run(cfg, [Process(1, "P", 0, 3, size=30, accesses=[[0, "W"], [10, "R"], [20, "R"]])])
        self.assertEqual(s.mem.swap_out, 1)              # sólo la pág 0 estaba modificada
        self.assertEqual(s.mem.swap_in, 3)

    def test_fragmentacion_interna(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=64, mem_size=512, swap_size=2048)
        s = Simulation(cfg, [Process(1, "P", 0, 2, size=100)])
        s.step()
        st = s.mem.stats()
        self.assertAlmostEqual(st["int_frag"], (128 - 100) / 128 * 100)

    def test_invariantes_marcos_y_swap(self):
        cfg, procs, _ = load_scenario("scenarios/03_paginacion_tlb_swap.json")
        for pol in ("FIFO", "LRU", "Clock"):
            s = Simulation(cfg.copy(repl_policy=pol, tlb_policy=pol), procs)
            while not s.finished:
                s.step()
                m = s.mem
                self.assertEqual(len(set(m.resident.values())), len(m.resident))  # sin marcos duplicados
                self.assertEqual(len(m.resident) + len(m.free_frames), m.n_frames)
                self.assertLessEqual(len(m.tlb), cfg.tlb_size)
                for (pid, pg), f in m.tlb.items():                              # TLB coherente
                    self.assertEqual(s.by_pid(pid).page_table[pg].frame, f)
            self.assertEqual(len(m.swap_free), m.swap_slots)                   # todo liberado
            self.assertEqual(len(m.free_frames), m.n_frames)

    def test_swap_insuficiente_espera_memoria(self):
        cfg = Config(mode="paging", scheduler="FIFO", page_size=10, mem_size=50, swap_size=60)
        ps = [Process(1, "A", 0, 2, size=40), Process(2, "B", 0, 2, size=40)]
        s = Simulation(cfg, ps); s.step()
        self.assertEqual(s.procs[1].state, M.WAIT_MEM)

    def test_mismo_escenario_misma_traza(self):
        cfg, procs, _ = load_scenario("scenarios/03_paginacion_tlb_swap.json")
        a = Simulation(cfg.copy(repl_policy="FIFO"), procs)
        b = Simulation(cfg.copy(repl_policy="LRU"), procs)
        self.assertEqual([p.accesses for p in a.procs], [p.accesses for p in b.procs])

    def test_cambio_de_algoritmo_en_caliente(self):
        cfg, procs, _ = load_scenario("scenarios/03_paginacion_tlb_swap.json")
        s = Simulation(cfg.copy(repl_policy="FIFO"), procs)
        for _ in range(30):
            s.step()
        s.set_policies(repl_policy="Clock", tlb_policy="FIFO")
        self.assertEqual(s.mem.frame_policy.name, "Clock")
        self.assertEqual(sorted(s.mem.frame_policy.keys()), sorted(s.mem.resident))
        s.run()
        self.assertTrue(s.finished)


class TestSegmentacion(unittest.TestCase):
    def sim(self):
        cfg = Config(mode="segmentation", scheduler="FIFO", mem_size=500, fit="first")
        p = Process(1, "P", 0, 3, segments=[("codigo", 100), ("pila", 50)],
                    accesses=[["codigo", 99], ["pila", 49], ["pila", 50]])
        return Simulation(cfg, [p])

    def test_traduccion_y_violacion(self):
        s = self.sim()
        s.step()
        p = s.procs[0]
        self.assertEqual(s.mem.seg_table(p), [("codigo", 0, 100), ("pila", 100, 50)])
        self.assertEqual(s.mem.translate(p, 1, 10), (110, None))
        s.run()
        self.assertEqual(p.state, M.DONE)
        self.assertEqual(p.reason, "violación de segmento")   # pila[50] con límite 50
        self.assertEqual(p.violations, 1)
        self.assertEqual(s.mem.map.used_total, 0)              # memoria liberada

    def test_violacion_manual(self):
        s = self.sim(); s.step()
        self.assertIn("VIOLACIÓN", s.manual_access(1, 0, 100))

    def test_todo_o_nada(self):
        cfg = Config(mode="segmentation", scheduler="FIFO", mem_size=300)
        ps = [Process(1, "A", 0, 5, segments=[("c", 100), ("d", 100)]),
              Process(2, "B", 0, 2, segments=[("c", 80), ("d", 80)])]
        s = Simulation(cfg, ps); s.step()
        self.assertEqual(s.procs[1].state, M.WAIT_MEM)
        self.assertEqual(s.mem.map.used_total, 200)           # nada quedó asignado a medias


class TestEscenarios(unittest.TestCase):
    def test_todos_los_escenarios_terminan(self):
        paths = list_scenarios()
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            cfg, procs, _ = load_scenario(path)
            s = run(cfg, procs)
            self.assertTrue(s.finished, path)
            self.assertLess(s.t, cfg.max_ticks, path)

    def test_determinismo(self):
        cfg, procs, _ = load_scenario("scenarios/03_paginacion_tlb_swap.json")
        a, b = run(cfg, procs).metrics(), run(cfg, procs).metrics()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
