import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
R = json.load(open("datos.json"))
COL = {"P1":"#f2e86d","P2":"#7be08a","P3":"#7fdcf0","P4":"#9b8cf0","P5":"#f080c0","P6":"#f0a070",None:"#dddddd"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

# 1) Gantt de los 4 planificadores
fig, axs = plt.subplots(4, 1, figsize=(8, 4.2), sharex=True)
for ax, s in zip(axs, ["FIFO","RR","SJF","SRTF"]):
    for a, b, p in R["gantt"][s]:
        ax.add_patch(Rectangle((a, 0), b-a, 1, fc=COL[p], ec="#444"))
        ax.text((a+b)/2, .5, p or "·", ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set_xlim(0, 32); ax.set_ylim(0, 1); ax.set_yticks([]); ax.set_ylabel(s, rotation=0, labelpad=22, va="center")
axs[-1].set_xlabel("Tiempo (ticks)"); axs[-1].set_xticks(range(0, 33, 2))
plt.tight_layout(); plt.savefig("fig/gantt4.png", dpi=170); plt.close()

# 2) Belady
fig, ax = plt.subplots(figsize=(5.4, 3.1))
fr = list(range(1, 8))
for pol, st in [("FIFO","o-"),("LRU","s--"),("Clock","^:")]:
    ax.plot(fr, R["belady_sweep"][pol], st, label=pol)
ax.set_xlabel("Marcos de memoria física"); ax.set_ylabel("Fallos de página"); ax.legend(); ax.grid(alpha=.3)
ax.annotate("FIFO: 9 → 10\n(anomalía de Belady)", (4, 10), (5, 11.2), arrowprops=dict(arrowstyle="->"), fontsize=8)
plt.tight_layout(); plt.savefig("fig/belady.png", dpi=170); plt.close()

# 3) tamaño de memoria física vs fallos y EAT
fig, axs = plt.subplots(1, 2, figsize=(8, 3))
labs = [r[0] for r in R["memsize"]]
axs[0].bar(labs, [r[1] for r in R["memsize"]], color="#6f9fd8"); axs[0].set_title("Fallos de página"); axs[0].set_xlabel("Memoria física (bytes)")
axs[1].bar(labs, [r[4]/1000 for r in R["memsize"]], color="#d8896f"); axs[1].set_title("Tiempo efectivo de acceso (µs)"); axs[1].set_xlabel("Memoria física (bytes)")
for ax in axs:
    for p in ax.patches: ax.text(p.get_x()+p.get_width()/2, p.get_height(), f"{p.get_height():.0f}", ha="center", va="bottom", fontsize=8)
plt.tight_layout(); plt.savefig("fig/memsize.png", dpi=170); plt.close()

# 4) tamaño de TLB vs hit rate
fig, ax = plt.subplots(figsize=(5.2, 3))
ax.plot([int(r[0]) for r in R["tlbsize"]], [r[1] for r in R["tlbsize"]], "o-")
ax.set_xlabel("Entradas de la TLB"); ax.set_ylabel("Tasa de aciertos de TLB (%)"); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig("fig/tlbsize.png", dpi=170); plt.close()

# 5) Modelos de memoria
fig, axs = plt.subplots(1, 3, figsize=(8.4, 3))
names = ["Continua", "Paginación", "Segmentación"]
ys = [("Fragmentación externa / interna prom. (%)", None), ("Espera de memoria prom. (ticks)", 4), ("Retorno promedio (ticks)", 5)]
ext = [r[2] for r in R["modos"]]; inn = [r[3] for r in R["modos"]]
axs[0].bar(names, ext, label="externa", color="#d8896f"); axs[0].bar(names, inn, bottom=ext, label="interna", color="#6f9fd8"); axs[0].legend(fontsize=7); axs[0].set_title("Fragmentación prom. (%)")
axs[1].bar(names, [r[4] for r in R["modos"]], color="#8fbf7f"); axs[1].set_title("Espera de memoria prom.")
axs[2].bar(names, [r[5] for r in R["modos"]], color="#b99be0"); axs[2].set_title("Retorno prom.")
for ax in axs: ax.tick_params(axis="x", labelrotation=20)
plt.tight_layout(); plt.savefig("fig/modelos.png", dpi=170); plt.close()

# 6) Arquitectura
fig, ax = plt.subplots(figsize=(8, 4.1)); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 52)
def box(x, y, w, h, t, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3", fc=fc, ec="#333")); ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=8)
box(2, 44, 96, 6, "Interfaz: gui/app.py (Tkinter)  ·  cli.py (consola)  ·  main.py", "#e6f0fa")
box(2, 33, 96, 8, "core/engine.py – Simulation: reloj (tick), colas, planificador FIFO/RR/SJF/SRTF, estados,\nintegración CPU↔memoria, bloqueo por E/S y por fallo de página, métricas", "#fdf2cf")
box(2, 18, 29, 12, "core/memory.py\nMemoryMap + Block\nContiguousManager\nSegmentationManager", "#dff3df")
box(35, 18, 29, 12, "core/paging.py\nPagingManager\nTabla de páginas (PTE)\nTLB · swap · marcos", "#dff3df")
box(68, 18, 30, 12, "core/policies.py\nFIFO · LRU · Clock\nFirst/Best/Worst Fit", "#f3dfe9")
box(2, 4, 29, 10, "core/models.py\nConfig · Process · estados", "#eeeeee")
box(35, 4, 29, 10, "core/scenario.py\nJSON + trazas de accesos", "#eeeeee")
box(68, 4, 30, 10, "core/compare.py\nmismo escenario, otra política", "#eeeeee")
for x in (16, 49, 83): ax.annotate("", (x, 32.5), (x, 30.5), arrowprops=dict(arrowstyle="<->"))
ax.annotate("", (50, 43.5), (50, 41.5), arrowprops=dict(arrowstyle="<->"))
plt.tight_layout(); plt.savefig("fig/arquitectura.png", dpi=170); plt.close()
print("figuras ok")
