# Simulador de Sistemas Operativos (AE4)

## Cómo usarlo (simple)
1. Doble clic en `Iniciar_Simulador.bat` (Windows) o `./iniciar_simulador.sh`; también `python main.py`.
2. Se abre el navegador con el simulador (el programa es Python; el navegador solo muestra la pantalla). No hace falta instalar nada.
3. Elegir un módulo arriba (① CPU, ② Memoria continua, ③ Paginación, ④ Segmentación, ⑤ Comparar modelos).
4. Apretar **▶ Paso** (o la barra espaciadora) o **⏵ Automático**. El cuadro "¿Qué está pasando?" explica cada paso.
5. En cada módulo hay una fila **🎓 Guía para explicarlo**: botones numerados que dejan todo listo y muestran qué decir.
6. **⚖ Comparar** corre los mismos procesos con distintas opciones y marca la mejor.

Atajos: espacio/→ paso, ← atrás, A automático, R reiniciar. "🔍 Letra grande" para proyectar.
Modificaciones en vivo (defensa): los desplegables de la fila de controles (algoritmo, quantum, tamaño de página, memoria física, TLB, reemplazo); botones "Provocar fallo de página" y "Forzar violación de segmento"; "＋ Proceso".
Interfaz de escritorio completa (opcional, requiere Tkinter): `python main.py --tk`. Consola: `python main.py --cli ...`.

---
# Simulador de Sistemas Operativos (AE4) – Python

Planificación de CPU (FIFO, RR, SJF, SRTF) + memoria continua (First/Best/Worst Fit, particiones fijas/variables, compactación)
+ paginación con TLB y swap (FIFO/LRU/Clock) + segmentación. Sólo biblioteca estándar (Tkinter para la GUI).

## Uso
Lo más fácil: **doble clic en `Iniciar_Simulador.bat`** (Windows) o `./iniciar_simulador.sh` (Linux/macOS). Dentro de la interfaz:
botones ①–⑤ para elegir módulo, ▶ Paso (barra espaciadora), ◀ Atrás, ⏵ Automático, cuadro "¿Qué pasó en este paso?", ayuda con F1 y globitos al pasar el mouse.

Desde consola:
    python main.py                                   # interfaz gráfica
    python main.py scenarios/03_paginacion_tlb_swap.json
    python cli.py scenarios/02_memoria_continua.json --compare fit
    python cli.py scenarios/03_paginacion_tlb_swap.json --compare repl_policy --compare tlb_policy
    python cli.py scenarios/01_planificacion.json --steps 10 -v
    python -m unittest discover -s tests -v          # 30 pruebas
    python informe/datos.py                          # recalcula las tablas del informe

## Estructura
    core/models.py     estados, Config, Process, PTE
    core/policies.py   FIFO/LRU/Clock y First/Best/Worst Fit
    core/memory.py     MemoryMap, ContiguousManager, SegmentationManager
    core/paging.py     PagingManager (tabla de páginas, TLB, swap, fallos, EAT)
    core/engine.py     Simulation (tick a tick: planificador + memoria + métricas)
    core/scenario.py   escenarios JSON y trazas de acceso
    core/compare.py    comparación de políticas
    gui/app.py, cli.py interfaces
    scenarios/         6 escenarios (≥1 por módulo)
    informe/           informe (docx + pdf) y scripts que generan sus tablas/figuras

## Modificaciones típicas en la defensa (dónde tocar)
| Pedido | En la GUI | En el código |
|---|---|---|
| Cambiar algoritmo de reemplazo | combos "Reemplazo de páginas/TLB" (en caliente) | `core/policies.py`, `make_policy` |
| Cambiar tamaño de página / memoria / TLB | panel Paginación + "Aplicar y reiniciar" | `Config.page_size`, `mem_size`, `tlb_size` |
| Provocar un fallo de página | pestaña "Acceso manual" | `PagingManager.access` (rama "fallo de página") |
| Cambiar quantum | campo Quantum (en caliente) | `Simulation._preempt_check` |
| Forzar violación de segmento | "Acceso manual" con desplazamiento ≥ límite | `SegmentationManager.translate` |
| Cambiar First/Best/Worst | combo "Política de ajuste" | `pick_hole` en `core/policies.py` |

Formato de escenarios: ver docstring de `core/scenario.py`.


## Para mostrarlo en la defensa

- **🎬 Demo guiada** (tecla D): elegir un módulo y seguir la barra azul; avanza sola hasta el momento clave y dice qué explicar.
- **Pestaña "¿Cómo funciona?"**: explica el módulo activo en palabras simples.
- **Ver → Letra grande**: modo proyector.
- **informe/Guion_Demostracion_y_Defensa.pdf**: guion paso a paso, modificaciones en vivo con resultados esperados, preguntas frecuentes, mapa del código y receta para agregar una política (MRU).
