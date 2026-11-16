import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from gui.demo_scripts import DEMOS

R = json.load(open("datos.json"))
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.0); sec.top_margin = sec.bottom_margin = Cm(1.8)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5); st.paragraph_format.space_after = Pt(5)
for n, sz in (("Heading 1", 15), ("Heading 2", 12), ("Heading 3", 11)):
    h = doc.styles[n]; h.font.name = "Calibri"; h.font.size = Pt(sz); h.font.bold = True; h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.paragraph_format.space_before = Pt(14 if n == "Heading 1" else 9); h.paragraph_format.space_after = Pt(4)

def P(text, bold=False, italic=False, size=None, align=None, color=None):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold, r.italic = bold, italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor(*color)
    if align: p.alignment = align
    return p

def B(text):
    p = doc.add_paragraph(style="List Bullet")
    for i, part in enumerate(text.split("**")):
        r = p.add_run(part); r.bold = i % 2 == 1
    p.paragraph_format.space_after = Pt(2)

def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); tcPr.append(sh)

def T(headers, rows, widths, size=9, head="D9E4F2", mono_cols=()):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); shade(c, head)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            parts = str(v).split("**")
            para = cells[i].paragraphs[0]
            for j, part in enumerate(parts):
                r = para.add_run(part); r.font.size = Pt(size); r.bold = (j % 2 == 1)
                if i in mono_cols: r.font.name = "Consolas"
    for col, w in zip(t.columns, widths): col.width = Cm(w)
    for row in t.rows:
        for c, w in zip(row.cells, widths):
            c.width = Cm(w)
            for p in c.paragraphs: p.paragraph_format.space_after = Pt(1)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

def code(text):
    for line in text.strip("\n").split("\n"):
        p = doc.add_paragraph(); r = p.add_run(line); r.font.name = "Consolas"; r.font.size = Pt(8.5)
        p.paragraph_format.space_after = Pt(0); p.paragraph_format.left_indent = Cm(0.6)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

# ------------------------------------------------------------------ portada
P("Guion de demostración y defensa", bold=True, size=22, color=(0x1F, 0x3A, 0x5F))
P("Simulador de Sistemas Operativos · AE4 · Sistemas Operativos Com. B", size=12, italic=True)
P("Cómo mostrarle el simulador al profe, qué decir en cada pantalla, cómo hacer las modificaciones en vivo y qué responder a las preguntas típicas.", size=10.5)

doc.add_heading("1. Antes de empezar (2 minutos)", 1)
B("**Abrir el programa:** doble clic en Iniciar_Simulador.bat (Windows) o ./iniciar_simulador.sh. Se abre solo en el navegador; no hace falta instalar nada.")
B("**Si se proyecta:** botón ⚙ Más → Letra grande, y pantalla completa del navegador (F11).")
B("**Tener a mano:** el informe en PDF, esta guía y el código abierto en el editor (carpeta core/).")
B("**Reparto sugerido (3 integrantes):** A presenta ① CPU y ② Memoria continua; B presenta ③ Paginación; C presenta ④ Segmentación y ⑤ comparación. Todos tienen que poder explicar cualquier parte.")
doc.add_heading("Cómo usar la pantalla", 2)
P("Arriba están los 5 módulos. En cada uno hay una fila “🎓 Guía para explicarlo” con 3 o 4 botones numerados: al apretar uno, el simulador deja todo listo y el cuadro “¿Qué está pasando?” muestra qué decir. "
  "También se puede usar a mano: ▶ Paso (o barra espaciadora), ⏵ Automático, ◀ Atrás, ⏭ Final y ⚖ Comparar. Los desplegables de arriba cambian parámetros (algoritmo, quantum, tamaño de página, memoria, TLB).")

doc.add_heading("2. Guion de la demostración (≈ 10 minutos)", 1)
GW = json.load(open("guia_web.json", encoding="utf-8"))
titles = {"cpu": "① Planificación de CPU · 2 min", "continua": "② Memoria continua · 2 min", "paginacion": "③ Paginación, TLB y swap · 3 min",
          "segmentacion": "④ Segmentación · 2 min", "modelos": "⑤ Comparar los tres modelos · 1 min"}
for k, t in titles.items():
    doc.add_heading(t, 2)
    T(["#", "Botón de la guía", "Qué decir"], [[i + 1, f"**{a}**", b] for i, (a, b) in enumerate(GW[k])], [0.8, 5.0, 11.2], size=9)
P("Extra para ③: en el menú ⚙ Más → Otros ejemplos está la anomalía de Belady (FIFO con 3 y 4 marcos: 9 → 10 fallos).", italic=True, size=9.5)

doc.add_heading("3. Modificaciones en vivo que pueden pedir", 1)
P("Dónde: los desplegables de arriba de cada módulo (al cambiarlos la simulación se reinicia). Para ver el resultado completo: ⏭ Final y la tarjeta Resultados (“Ver todas las métricas”); ⚖ Comparar muestra las alternativas lado a lado.", size=9.5)
rep = {r[0]: r for r in R["repl"]}; ps = {r[0]: r for r in R["pagesize"]}; ms = {r[0]: r for r in R["memsize"]}
tl = {r[0]: r for r in R["tlbsize"]}; q = {r[0]: r for r in R["quantum"]}; fit = {r[0]: r for r in R["fit"]}
T(["Pedido del profe", "Cómo hacerlo (módulo)", "Resultado esperado"], [
    ["Cambiar el algoritmo de reemplazo de páginas", "③ Desplegable “Reemplazo de páginas”: FIFO / LRU / Clock → ⏭ Final.",
     f"Fallos: FIFO **{rep['FIFO'][1]}**, LRU **{rep['LRU'][1]}**, Clock **{rep['Clock'][1]}**."],
    ["Cambiar el tamaño de página", "③ Desplegable “Tamaño de página” → 32 o 128 → ⏭ Final.",
     f"32 B: **{ps['32'][1]}** fallos · 64 B: **{ps['64'][1]}** · 128 B: **{ps['128'][1]}** (con la misma memoria física, hay menos marcos)."],
    ["Alterar el tamaño de la memoria física", "③ Desplegable “Memoria física” → 320 o 1280 → ⏭ Final.",
     f"320 B: **{ms['320'][1]}** fallos · 640 B: **{ms['640'][1]}** · 1280 B: **{ms['1280'][1]}**."],
    ["Provocar un fallo de página", "③ Botón “⚡ Provocar fallo de página” (debajo de “¿Qué está pasando?”).",
     "El cuadro muestra: dirección lógica = página + desplazamiento → fallo → marco elegido y víctima desalojada."],
    ["Cambiar el tamaño de la TLB", "③ Desplegable “Entradas de TLB” → 0 / 2 / 16 → ⏭ Final.",
     f"Aciertos de TLB: 0 entradas **{tl['0'][1]:.0f} %**, 2 → **{tl['2'][1]:.1f} %**, 16 → **{tl['16'][1]:.0f} %**."],
    ["Cambiar el quantum", "① Desplegable Algoritmo = Round Robin y campo “Quantum”.",
     f"Quantum 1: **{q['1'][4]}** cambios de contexto, respuesta {q['1'][3]:.1f}; quantum 8: **{q['8'][4]}** cambios, igual que FIFO."],
    ["Forzar una violación de segmento", "④ Botón “⚡ Forzar violación de segmento” (avanzar unos pasos antes para que haya procesos en memoria).",
     "Mensaje “VIOLACIÓN DE SEGMENTO: desplazamiento N fuera del límite…”; el proceso se aborta y libera su memoria."],
    ["Cambiar First / Best / Worst Fit", "② Desplegable “Dónde ubicar” (First/Best/Worst) → ⏭ Final.",
     f"Espera por memoria: First **{fit['first'][1]:.2f}**, Best **{fit['best'][1]:.2f}**, Worst **{fit['worst'][1]:.2f}**."],
    ["Pasar de particiones variables a fijas / compactar", "② “Compactar solo si hace falta” = Sí, o botón “🧹 Compactar memoria ahora”.",
     "Fijas: aparece fragmentación interna (≈ 19 %). Con compactación: R4 deja de esperar."],
    ["Agregar un proceso en vivo", "⚙ Más → ＋ Agregar proceso (ráfaga y tamaño o segmentos).", "Aparece en la tabla y entra según su llegada."],
    ["Dejar la TLB sin etiqueta de proceso", "Con la interfaz de escritorio (python main.py --tk): tildar “Vaciar TLB al cambiar ctx”; o por consola.",
     f"Aciertos de TLB bajan de {R['flush'][0][1]:.1f} % a {R['flush'][1][1]:.1f} %."],
], [4.0, 6.7, 6.3], size=8.5)

doc.add_heading("Modificación en el código: agregar un algoritmo de reemplazo nuevo (ejemplo MRU)", 2)
P("Si piden “agregá otra política”, son tres cambios chicos. MRU (desaloja la más recientemente usada) es el ejemplo; con el escenario ③ produce 122 fallos contra 91 de LRU, como se espera de una mala política para este patrón de accesos.", size=9.5)
P("1) En core/policies.py, agregar la clase (hereda de LRU y cambia la víctima):", bold=True, size=9.5)
code('''class MRUPolicy(LRUPolicy):
    name = "MRU"
    def victim(self, exclude=frozenset()):
        for k in reversed(self.q):          # la más reciente primero
            if k not in exclude:
                return k
        return None''')
P("2) En core/policies.py, en make_policy(), agregar el caso:", bold=True, size=9.5)
code('''    if n == "MRU":
        return MRUPolicy()''')
P("3) En core/models.py, agregar el nombre a la lista REPL_POLICIES:", bold=True, size=9.5)
code('''REPL_POLICIES = ["FIFO", "LRU", "Clock", "MRU"]''')
P("Al reabrir el programa, “MRU” aparece en los combos de reemplazo (TLB y páginas) y en el comparador; no hay que tocar nada más porque TLB y marcos usan la misma interfaz de política.", size=9.5)

doc.add_heading("4. Preguntas que pueden hacer y cómo responderlas", 1)
QA = [
 ("¿Qué diferencia hay entre página y marco?", "La página es un trozo de la memoria lógica del proceso; el marco es un trozo de la memoria física del mismo tamaño. La tabla de páginas del proceso dice en qué marco está cada página. Código: PTE en core/models.py, PagingManager en core/paging.py."),
 ("¿Qué pasa exactamente en un fallo de página?", "1) El proceso accede a una página con bit de válida en no. 2) Se busca un marco libre; si no hay, la política de reemplazo elige una víctima. 3) Si la víctima estaba modificada se escribe en swap (swap-out). 4) El proceso pasa a Esperando Página los ticks que tarda la carga desde swap y la CPU atiende a otro. 5) Al llegar la página se marca válida, se carga en la TLB y el proceso vuelve a Listo; la instrucción se reanuda. Código: PagingManager.access() y complete_load(); Simulation._try_access()."),
 ("¿Para qué sirve la TLB y qué pasa si falla?", "Es una caché de traducciones recientes página→marco. Si acierta (hit) se traduce sin consultar la tabla de páginas (t_TLB + t_mem). Si falla (miss) se consulta la tabla en memoria (t_TLB + 2·t_mem) y se carga la traducción en la TLB, reemplazando otra con la política elegida."),
 ("¿Cómo calculan el tiempo efectivo de acceso (EAT)?", "Acceso por acceso: acierto de TLB = t_TLB + t_mem; fallo de TLB con página presente = t_TLB + 2·t_mem; fallo de página = t_TLB + t_mem + t_swap (+ t_swap si la víctima estaba modificada) + t_mem. El EAT es el promedio de todos los accesos. Con 100 µs de swap, el EAT queda dominado por los fallos de página y la TLB casi no se nota."),
 ("¿Qué es la anomalía de Belady y por qué la tiene FIFO?", "Es que, con FIFO, dar más marcos puede producir más fallos (cadena 1,2,3,4,1,2,5,1,2,3,4,5: 9 fallos con 3 marcos y 10 con 4). FIFO no mira el uso, sólo la antigüedad, por lo que el conjunto de páginas residentes con más memoria no incluye necesariamente al conjunto con menos. LRU es un algoritmo de pila (con n+1 marcos contiene a lo de n marcos), por eso no la sufre. Se muestra en el escenario 04."),
 ("¿Cómo funciona Clock?", "Es FIFO con segunda oportunidad: los marcos forman un anillo con un bit de referencia. La manecilla recorre: si el bit está en 1 lo pone en 0 y sigue; si está en 0 desaloja esa página. Aproxima a LRU con poco costo. Código: ClockPolicy.victim() en core/policies.py; en pantalla, la pestaña Tablas y TLB muestra R=0/1 y la manecilla ◄."),
 ("¿Qué es fragmentación interna y externa? ¿Dónde aparece cada una?", "Externa: hay memoria libre suficiente pero no contigua (memoria continua y segmentación). Interna: memoria asignada que no se usa (particiones fijas, y la última página de cada proceso en paginación). Paginación no tiene externa. Se calcula como 1 − mayor hueco / memoria libre (externa) y desperdicio / asignado (interna)."),
 ("¿Cuál es mejor: First, Best o Worst Fit?", "Depende de la carga. En el escenario ② Best Fit alojó a todos (conserva el hueco grande para el proceso grande); First y Worst dejaron a R4 esperando. Worst Fit fragmenta primero los huecos grandes (mayor fragmentación externa máxima, 75 %). No hay una mejor siempre; el simulador permite medirlas con la misma carga."),
 ("¿Qué hace la compactación y qué cuesta?", "Mueve todos los bloques ocupados hacia la dirección 0 para unir los huecos en uno solo, de modo que un proceso que no entraba pueda entrar. Cuesta mover bytes (se cuenta en el informe) y en la realidad requiere reubicar direcciones. Implementada en MemoryMap.compact(); los procesos guardan referencias a sus Block, así que se actualizan solos."),
 ("¿Cómo se traduce una dirección en segmentación y qué es una violación?", "La dirección lógica es (segmento, desplazamiento). Se busca el segmento en la tabla; si desplazamiento < límite, física = base + desplazamiento; si no, hay violación de segmento y el proceso se aborta. Código: SegmentationManager.translate() en core/memory.py."),
 ("¿Diferencia entre paginación y segmentación?", "Paginación divide en bloques fijos sin significado lógico: sin fragmentación externa pero con interna y fallos de página. Segmentación divide en partes lógicas de tamaño variable (código, datos, pila) con protección por límite, pero con fragmentación externa. En el escenario ⑤ se ve: paginación 0 % externa y 6,5 % interna; segmentación 13 % externa."),
 ("¿Cómo integran la planificación de CPU con la memoria?", "Un único motor (core/engine.py, Simulation.step) avanza por ticks. El planificador sólo elige entre procesos Listos. Cuando un proceso hace un acceso y falla (fallo de página o violación), deja de ser candidato en ese tick: un fallo lo pasa a Esperando Página y se elige otro proceso; por eso los fallos afectan el tiempo de ejecución, los cambios de contexto y el uso de CPU."),
 ("¿Qué pasa con la TLB en un cambio de contexto?", "Por defecto cada entrada lleva el PID (como una TLB con ASID), así que no hace falta vaciarla. Con la opción “Vaciar TLB al cambiar ctx” se simula una TLB sin etiquetas: los aciertos bajan casi a la mitad (47,7 % → 25,8 % en el escenario ③)."),
 ("¿Qué es el swap y por qué reservan lugar para todas las páginas?", "Es el espacio en disco donde viven las páginas que no están en memoria. Cada proceso admitido reserva un slot por página (si el swap no alcanza, el proceso espera). Sólo se escribe a swap la página desalojada que fue modificada (bit dirty); las limpias se descartan porque ya tienen copia. Esto permite medir swap-in y swap-out por separado."),
 ("¿Por qué SJF y SRTF dieron 87,5 % de uso de CPU?", "Porque dejaron para el final al proceso más largo (P3), que hace una E/S de 4 ticks: cuando la pide ya no hay otro proceso listo y la CPU queda ociosa. Con FIFO y RR esa E/S se solapa con la ejecución de otros procesos."),
 ("¿Cómo garantizan que la comparación es justa?", "Los accesos a memoria se generan con una semilla que sólo depende de (semilla, PID): la secuencia de direcciones es idéntica para todas las políticas. Además hay 20 repeticiones con distintas semillas (LRU 83,6 · Clock 85,1 · FIFO 91,6 fallos promedio) para no depender de una sola traza."),
 ("¿Cómo validaron que anda bien?", "30 pruebas automáticas (python -m unittest discover -s tests): Gantt de ejemplos conocidos, la cadena de Belady (9/10 y 10/8), traducción de direcciones, invariantes (sin marcos duplicados, TLB coherente con la tabla de páginas, swap liberado al terminar), violaciones de segmento, etc."),
 ("¿Qué limitaciones tiene?", "Una sola CPU; el cambio de contexto se cuenta pero no consume tiempo; trazas de acceso sintéticas; no hay segmentación paginada (fuera de alcance); no hay algoritmo óptimo (OPT) como referencia. Está dicho en la sección 5.3 del informe."),
]
for qn_, ans in QA:
    p = doc.add_paragraph(); r = p.add_run("• " + qn_); r.bold = True; p.paragraph_format.space_after = Pt(1); p.paragraph_format.keep_with_next = True
    p2 = doc.add_paragraph(ans); p2.paragraph_format.left_indent = Cm(0.5); p2.paragraph_format.space_after = Pt(5)

doc.add_heading("5. Mapa del código (para saber dónde mirar)", 1)
T(["Archivo", "Qué contiene", "Funciones / clases clave"], [
    ["core/models.py", "Estados, parámetros (Config) y procesos.", "Config, Process, PTE, constantes de estados"],
    ["core/policies.py", "Reemplazo FIFO/LRU/Clock y elección de hueco.", "FIFOPolicy, LRUPolicy, ClockPolicy, make_policy, pick_hole"],
    ["core/memory.py", "Mapa de memoria, memoria continua y segmentación.", "MemoryMap.allocate/release/compact, ContiguousManager.admit, SegmentationManager.translate"],
    ["core/paging.py", "Paginación, TLB, swap, fallos y EAT.", "PagingManager.access, complete_load, _tlb_insert, stats"],
    ["core/engine.py", "Reloj, planificadores, estados, integración CPU–memoria, métricas.", "Simulation.step, _select, _preempt_check, _try_access, metrics, manual_access"],
    ["core/scenario.py", "Escenarios JSON y trazas de acceso.", "load_scenario, generate_paging_accesses"],
    ["core/compare.py · cli.py", "Comparaciones y modo consola.", "compare, table_text"],
    ["web/server.py · web/index.html", "Interfaz web simple (servidor Python + pantalla).", "App, Handler, guide()"],
    ["gui/app.py", "Interfaz de escritorio completa (opcional, --tk).", "App, CompareWindow"],
    ["tests/test_simulador.py", "30 pruebas automáticas.", "python -m unittest discover -s tests"],
], [3.6, 6.4, 7.0], size=8.5, mono_cols=(0,))

doc.add_heading("6. Cada módulo en una frase (para abrir o cerrar la explicación)", 1)
for t_ in ["**① Planificación:** una sola CPU y varios procesos; cada algoritmo decide el orden y eso cambia espera, respuesta y cambios de contexto.",
           "**② Memoria continua:** un bloque contiguo por proceso; al liberar quedan huecos y aparece la fragmentación externa; Best/First/Worst y la compactación son formas de lidiar con eso.",
           "**③ Paginación con TLB y swap:** la memoria se parte en marcos fijos, las páginas se traen del disco bajo demanda, la TLB acelera la traducción y el reemplazo decide a quién sacar cuando no hay lugar.",
           "**④ Segmentación:** el proceso se parte en segmentos lógicos con base y límite; protege (violación de segmento) pero fragmenta externamente.",
           "**⑤ Comparación:** con los mismos procesos, paginar cambia espera de memoria por fallos de página; continua y segmentación esperan memoria pero no tienen fallos."]:
    B(t_)

doc.add_heading("7. Números para tener a mano", 1)
T(["Qué", "Resultado"], [
    ["Planificación (escenario ①, q=3)", "Espera prom.: FIFO 9,20 · RR 12,80 · SJF 7,80 · SRTF 6,40. Respuesta: FIFO 8,6 · RR 4,2 · SJF 7,8 · SRTF 3,8."],
    ["Memoria continua (②)", "Espera por memoria: First 3,46 · Best 0,00 · Worst 3,46. Con compactación automática, First y Worst bajan a 0."],
    ["Reemplazo de páginas (③)", f"Fallos: FIFO {rep['FIFO'][1]} · LRU {rep['LRU'][1]} · Clock {rep['Clock'][1]}. Promedio de 20 trazas: FIFO 91,6 · LRU 83,6 · Clock 85,1."],
    ["Belady (③b)", "FIFO 9 → 10 fallos al pasar de 3 a 4 marcos; LRU 10 → 8; Clock 9 → 10."],
    ["TLB (③)", "Aciertos: 0 entradas 0 % · 2 → 23,9 % · 6 → 47,7 % · 16 → 65 %. EAT casi no cambia porque dominan los fallos de página (100 µs de swap)."],
    ["Segmentación (④)", "P5 aborta por violación de segmento en el tiempo 18. Espera por memoria: First 11,50 · Best 9,75 · Worst 11,75."],
    ["Tres modelos (⑤)", "Continua: espera mem. 17,7 · retorno 36,7. Paginación: espera mem. 0 · 26 fallos · retorno 50,5. Segmentación: espera mem. 17,0 · frag. externa 13 %."],
], [5.0, 12.0], size=9)
doc.save("Guion_Demostracion_y_Defensa.docx")
print("ok")
