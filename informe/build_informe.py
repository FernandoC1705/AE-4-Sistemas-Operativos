import json
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

R = json.load(open("datos.json"))
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.3)
sec.top_margin = sec.bottom_margin = Cm(2.2)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.1
for n, sz in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
    h = doc.styles[n]; h.font.name = "Calibri"; h.font.size = Pt(sz); h.font.bold = True; h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.paragraph_format.space_before = Pt(12 if n != "Heading 1" else 18); h.paragraph_format.space_after = Pt(4)

def P(text="", bold=False, italic=False, align=None, size=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold, r.italic = bold, italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor(*color)
    if align: p.alignment = align
    return p

def rich(text):
    """**negrita** inline."""
    p = doc.add_paragraph()
    for i, part in enumerate(text.split("**")):
        r = p.add_run(part); r.bold = i % 2 == 1
    return p

def B(text):
    p = doc.add_paragraph(style="List Bullet")
    for i, part in enumerate(text.split("**")):
        r = p.add_run(part); r.bold = i % 2 == 1
    p.paragraph_format.space_after = Pt(2)
    return p

def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), color); tcPr.append(sh)

def fmt(v):
    if v is None: return "–"
    if isinstance(v, float): return f"{v:,.2f}"
    if isinstance(v, int) and abs(v) >= 10000: return f"{v:,}"
    return str(v)

def T(headers, rows, widths=None, caption=None, bold_min=None):
    if caption:
        c = P(caption, bold=True, size=9.5); c.paragraph_format.keep_with_next = True; c.paragraph_format.space_after = Pt(2)
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(8.5)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER; shade(c, "D9E4F2")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(fmt(v)); r.font.size = Pt(8.5)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if (i == 0 or len(str(v)) > 28) else WD_ALIGN_PARAGRAPH.CENTER
            if i == 0: r.bold = True
    if widths:
        for col, w in zip(t.columns, widths): col.width = Cm(w)
        for row in t.rows:
            for c, w in zip(row.cells, widths): c.width = Cm(w)
    t.autofit = False
    for ri, row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1)
                if ri < len(t.rows) - 1 and len(t.rows) <= 12: p.paragraph_format.keep_with_next = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

def F(path, width, caption):
    doc.add_picture(path, width=Cm(width)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    c = P(caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)

NAMES = {"first": "First Fit", "best": "Best Fit", "worst": "Worst Fit", "contiguous": "Memoria continua",
         "paging": "Paginación", "segmentation": "Segmentación", "False": "TLB etiquetada con PID", "True": "TLB vaciada en cada cambio de contexto"}
def named(rows): return [[NAMES.get(r[0], r[0])] + r[1:] for r in rows]

# ================================================================ portada
for _ in range(3): doc.add_paragraph()
P("Facultad de Ingeniería y Tecnología", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
P("Ingeniería en Sistemas de Información", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
P("Sistemas Operativos – Comisión B", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
P("AE4 – Actividad de Evaluación Integradora", size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
P("Simulador de Sistemas Operativos", bold=True, size=26, align=WD_ALIGN_PARAGRAPH.CENTER, color=(0x1F, 0x3A, 0x5F))
P("Planificación de procesos, memoria continua, paginación con TLB y swap, y segmentación", size=12, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph(); doc.add_paragraph()
P("Informe técnico", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
p = P("Integrantes: [COMPLETAR – apellido y nombre de cada integrante del grupo]", align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
p.runs[0].font.highlight_color = 7
P("Docentes: Mg. Christian Parkinson · Lic. Alejandro Sebastián de León · Lic. Marcos Portel", align=WD_ALIGN_PARAGRAPH.CENTER, size=10.5)
P("Año 2026 · Fecha de presentación: 16/11/2026", align=WD_ALIGN_PARAGRAPH.CENTER, size=10.5)
doc.add_page_break()

# ================================================================ 1. Introducción
doc.add_heading("1. Introducción", 1)
doc.add_heading("1.1 Contexto", 2)
P("Un sistema operativo debe resolver dos problemas que se condicionan mutuamente: decidir qué proceso usa la CPU en cada instante "
  "(planificación) y decidir dónde y cómo se alojan los procesos en la memoria principal (administración de memoria). Cuando la memoria "
  "física no alcanza para todos los procesos, a ello se suma la memoria virtual: parte del espacio de direcciones vive en disco (área de swap) y se "
  "trae a memoria bajo demanda mediante fallos de página. La elección de políticas (qué algoritmo de CPU, cómo ubicar un bloque, qué página desalojar) "
  "tiene un impacto medible en el tiempo de espera, la fragmentación y el tiempo efectivo de acceso a memoria.")
doc.add_heading("1.2 Objetivo", 2)
P("Desarrollar, en Python, un simulador que permita modelar, visualizar y comparar distintos esquemas de planificación de procesos y de administración "
  "de memoria, integrando memoria continua, paginación (con TLB y swap) y segmentación, junto con sus políticas de asignación y reemplazo, y "
  "analizar con métricas cuantitativas el comportamiento de cada una frente a un mismo escenario.")
doc.add_heading("1.3 Alcance del simulador", 2)
B("**Planificación de CPU:** FIFO, Round Robin (quantum configurable), SJF no apropiativo y SRTF; diagrama de Gantt, tiempos de espera, retorno y respuesta, uso de CPU y cambios de contexto.")
B("**Memoria continua:** particiones variables o fijas con First, Best y Worst Fit; fragmentación externa e interna, compactación (manual y automática, implementada), cola de espera de procesos y mapa de memoria en cada asignación/liberación.")
B("**Paginación con TLB y swap:** tabla de páginas por proceso, TLB de tamaño configurable, traducción lógica→física, carga bajo demanda, fallos de página que bloquean al proceso, área de swap, reemplazo FIFO/LRU/Clock tanto en la TLB como en los marcos, y métricas (hit rate, fallos, tráfico de swap, tiempo efectivo de acceso).")
B("**Segmentación pura:** tabla de segmentos (base, límite), traducción (segmento, desplazamiento) → física, detección de violaciones de segmento, asignación de segmentos con First/Best/Worst Fit, fragmentación externa y compactación.")
B("**Transversal:** tabla de procesos y estados siempre visible, interfaz de configuración de escenarios, ejecución paso a paso y automática, comparador de políticas y modo consola.")
P("Quedan fuera de alcance, conforme a la consigna, la segmentación paginada, y por decisión de diseño un modelo de CPU única sin costo temporal explícito del cambio de contexto (se cuenta, pero no consume ticks). Los límites se detallan en la sección 5.")

# ================================================================ 2. Funciones
doc.add_heading("2. Descripción de las funciones más importantes", 1)
P("El simulador se ejecuta con una interfaz gráfica (Tkinter) o por consola; ambas usan el mismo núcleo. Los escenarios son archivos JSON (procesos, "
  "llegadas, ráfagas, tamaños, segmentos, operaciones de E/S y parámetros de memoria).")
doc.add_heading("2.1 Tabla de procesos y estados (siempre visible)", 2)
P("En la parte superior de la interfaz se muestra, en todo momento, una tabla con PID, nombre, estado, llegada, ráfaga, tiempo restante, tamaño, memoria asignada, "
  "tiempos de espera, fallos de página, retorno y notas. Cada estado tiene color propio y la tabla se actualiza tick a tick. Los estados implementados son: "
  "Nuevo, Esperando Memoria, Listo, Ejecutando, Bloqueado (E/S), Esperando Página (fallo de página en atención), Terminado y Rechazado "
  "(el requerimiento no cabe nunca en el sistema). Debajo se muestran las colas (nuevos, esperando memoria, listos, ejecutando, bloqueados y esperando página).")
F("fig/pag_tablas.png", 15.5, "Figura 1. Interfaz en modo paginación: módulos, cuadro “qué pasó en este paso”, tabla de procesos con leyenda de estados, colas, tabla de páginas, TLB y orden de reemplazo de marcos.")
doc.add_heading("2.2 Planificación de procesos", 2)
P("El planificador opera sobre los procesos en estado Listo. FIFO atiende por orden de entrada a la cola; Round Robin usa un quantum configurable y devuelve "
  "al final de la cola al proceso que lo agota; SJF elige el proceso con menor tiempo de CPU restante sin desalojar; SRTF desaloja al proceso en ejecución cuando llega (o vuelve) uno con "
  "menor tiempo restante. Los procesos pueden tener operaciones de E/S (pasan a Bloqueado un número de ticks y liberan la CPU). Se muestran el diagrama de Gantt, los tiempos de espera "
  "(en cola de Listos), retorno y respuesta, el porcentaje de uso de CPU y la cantidad de cambios de contexto. El algoritmo y el quantum pueden cambiarse en caliente.")
doc.add_heading("2.3 Memoria continua", 2)
P("La memoria se modela como una lista de bloques (inicio, tamaño, propietario). Al llegar, cada proceso solicita un bloque contiguo de su tamaño total; el hueco se elige "
  "con First Fit (primer hueco suficiente por dirección), Best Fit (el más chico suficiente) o Worst Fit (el mayor). Si no hay hueco, el proceso pasa a la cola Esperando Memoria "
  "y se reintenta en cada liberación. Al terminar, el bloque se libera y se fusiona con los huecos vecinos. Se admite el esquema de particiones fijas (con fragmentación interna) y la compactación, manual (botón) o automática cuando "
  "hay memoria libre suficiente pero no contigua. El mapa de memoria se dibuja a escala y se complementa con una tabla de bloques, la cola de espera y las métricas de fragmentación.")
F("fig/cont.png", 15.5, "Figura 2. Memoria continua (escenario 02): mapa de memoria con huecos, cola de espera con R4 y fragmentación externa.")
doc.add_heading("2.4 Paginación con TLB y swap", 2)
P("La memoria física se divide en marcos y el espacio de cada proceso en páginas del mismo tamaño (ambos configurables). Cada proceso tiene su tabla de páginas (marco, bit de válida, bit de modificada, "
  "slot de swap). Todas sus páginas tienen reservado un lugar en el área de swap al ser admitido (el espacio virtual total puede superar a la memoria física); si el swap no alcanza, el proceso espera. "
  "Cada acceso se traduce así: (1) se consulta la TLB; (2) si falla, se consulta la tabla de páginas en memoria y se actualiza la TLB; (3) si la página no está presente se produce un fallo de página: se obtiene un marco libre o se desaloja una "
  "víctima con la política elegida (FIFO, LRU o Clock) y, si la víctima estaba modificada, se escribe en swap; el proceso pasa a Esperando Página durante los ticks que demora la carga desde swap, mientras la CPU atiende a otro proceso. "
  "Al completarse la carga, la página queda válida, se carga en la TLB y el proceso vuelve a Listo. La TLB también admite FIFO, LRU y Clock, tamaño configurable (incluso 0) y la opción de vaciarla en cada cambio de contexto.")
P("Se calculan: tasa de aciertos y de fallos de la TLB, cantidad y tasa de fallos de página, páginas transferidas desde y hacia swap, tráfico de swap en bytes, fragmentación interna y tiempo efectivo de acceso (EAT) medido acceso por acceso:")
B("acierto de TLB: t_TLB + t_mem;")
B("fallo de TLB con página presente: t_TLB + 2·t_mem (consulta de la tabla de páginas + acceso);")
B("fallo de página: t_TLB + t_mem + t_swap (+ t_swap si la víctima estaba modificada) + t_mem.")
P("Con t_TLB = 10 ns, t_mem = 100 ns y t_swap = 100 000 ns por defecto (todos configurables). Además se registra cada reemplazo (TLB y marcos) en el registro de eventos, y la pestaña de swap muestra qué páginas están sólo en swap y cuáles tienen copia en RAM.")
doc.add_heading("2.5 Segmentación", 2)
P("Cada proceso declara sus segmentos (por ejemplo código, datos y pila) y recibe una tabla de segmentos con base y límite. Los segmentos se ubican en los huecos libres con First/Best/Worst Fit; la admisión es "
  "“todo o nada” (si algún segmento no entra, se deshacen las asignaciones parciales y el proceso espera). La traducción verifica que el desplazamiento sea menor que el límite: "
  "en caso contrario se registra una violación de segmento y el proceso se aborta liberando su memoria. Se calcula la fragmentación externa y se ofrece compactación.")
doc.add_heading("2.6 Control de la simulación, comparación y defensa", 2)
B("**Pensada para usarse sin manual:** botones ①–⑤ que cargan un escenario de ejemplo por módulo con una sugerencia de qué probar; cuadro “¿Qué pasó en este paso?” que narra en palabras cada evento (llegadas, fallos de página, TLB hit/miss, asignaciones); leyenda de colores de estados; globitos de ayuda en cada campo; guía rápida, glosario y atajos de teclado (F1); solo se muestran las pestañas y parámetros que corresponden al módulo elegido; el botón de aplicar cambios se resalta cuando hay cambios pendientes.")
B("**Paso a paso / paso atrás / automático / hasta el final**, con velocidad regulable (barra espaciadora para avanzar); el retroceso re-simula desde el inicio, algo posible porque el motor es determinista. La línea de tiempo por proceso muestra, instante a instante, quién ejecutaba, esperaba CPU, estaba bloqueado, esperaba una página o esperaba memoria.")
B("**Cambios en caliente:** quantum, algoritmo de planificación, política de ajuste y algoritmos de reemplazo (de TLB y de páginas) se modifican sin reiniciar; el tamaño de página, de memoria, de TLB y de swap se aplican con “Aplicar y reiniciar”.")
B("**Crear procesos** durante la simulación y **acceso manual**: traducir una dirección a pedido para provocar un fallo de página o forzar una violación de segmento.")
B("**Comparador de políticas:** ejecuta el mismo escenario (misma traza de accesos) variando un parámetro, resalta la mejor opción según la métrica principal con una frase que lo explica, y muestra tabla y gráfico de barras; la misma funcionalidad está en consola (python cli.py escenario.json --compare repl_policy).")
B("**Escenarios en JSON** (uno o más por módulo) y **suite de 30 pruebas automáticas** del núcleo.")

# ================================================================ 3. Diseño
doc.add_heading("3. Diseño", 1)
doc.add_heading("3.1 Arquitectura general", 2)
P("El código está separado en un núcleo independiente de la interfaz (paquete core) y dos interfaces (gui y cli). El motor de simulación (Simulation) coordina al planificador con "
  "un administrador de memoria intercambiable, que se elige según el modo: ContiguousManager, SegmentationManager o PagingManager. Esto permite ejecutar el mismo escenario con "
  "los tres modelos y comparar, y usar el núcleo sin interfaz (consola, pruebas, comparaciones).")
F("fig/arquitectura.png", 15, "Figura 3. Módulos del simulador y sus dependencias.")
T(["Módulo", "Responsabilidad"], [
    ["core/models.py", "Estados, Config (todos los parámetros), Process (datos de entrada y estado de ejecución) y PTE (entrada de tabla de páginas)."],
    ["core/policies.py", "Políticas de reemplazo FIFO, LRU y Clock con una interfaz común (insert, touch, remove, victim, replace) y selección de hueco First/Best/Worst Fit."],
    ["core/memory.py", "MemoryMap (bloques, fusión de huecos, compactación), ContiguousManager y SegmentationManager."],
    ["core/paging.py", "PagingManager: marcos, tablas de páginas, TLB, área de swap, fallos de página y EAT."],
    ["core/engine.py", "Simulation: reloj, colas, planificadores, máquina de estados, integración CPU–memoria, métricas y acceso manual."],
    ["core/scenario.py", "Carga/guardado JSON y generación de trazas de accesos con localidad (con semilla)."],
    ["core/compare.py", "Ejecuta un escenario variando un parámetro y arma las tablas comparativas."],
    ["gui/app.py · cli.py", "Interfaz Tkinter (vistas en pestañas, comparador) y modo consola."],
], widths=[3.6, 12.6], caption="Tabla 1. Módulos del código fuente.")
doc.add_heading("3.2 Modelo de tiempo e integración CPU–memoria", 2)
P("El simulador avanza por ticks (una unidad de CPU). En cada tick el motor: (1) despierta a los procesos cuya E/S o carga de página terminó; (2) reintenta admitir a los que esperan memoria, en orden de llegada y "
  "sin bloquear a los siguientes si uno no entra; (3) admite a los que llegan; (4) aplica el desalojo (fin de quantum en RR, SRTF) y elige proceso; (5) hace la traducción de dirección del proceso elegido "
  "—si falla (fallo de página o violación) deja de ser candidato en ese tick y se elige otro—, y si no, ejecuta una unidad de CPU; (6) acumula los tiempos de espera. De este modo los fallos de página y el swapping afectan directamente el tiempo de ejecución y la planificación: un fallo "
  "bloquea al proceso entre 3 ticks (carga) y 5 ticks (carga más escritura de la víctima modificada), valores configurables.")
doc.add_heading("3.3 Estructuras de datos", 2)
B("**Cola de listos:** lista ordenada por instante de entrada a Listo; FIFO y RR toman la cabeza, SJF y SRTF buscan el mínimo por (tiempo restante, orden de llegada, PID).")
B("**Mapa de memoria:** lista ordenada de objetos Block(inicio, tamaño, pid, etiqueta, bytes usados). Los procesos guardan referencias a sus Block; la compactación modifica el atributo de inicio de los mismos objetos, por lo que las tablas de segmentos y los mapas se mantienen coherentes sin reconstruirlos.")
B("**Tabla de segmentos:** se deriva de los bloques del proceso (etiqueta = nombre del segmento, inicio = base, tamaño = límite).")
B("**Tabla de páginas:** lista de PTE (marco, válida, modificada, en carga, slot de swap); la posición en la lista es el número de página.")
B("**Marcos y swap:** diccionario (pid, página) → marco, lista de marcos libres, y diccionario slot → (pid, página) para el área de swap.")
B("**TLB:** diccionario (pid, página) → marco con una política de reemplazo independiente de la de los marcos.")
B("**Políticas de reemplazo:** FIFO y LRU con un OrderedDict (LRU mueve la clave al final en cada acceso); Clock con un anillo, bit de referencia y manecilla. Todas comparten la misma interfaz, por lo que se usan igual para la TLB y para los marcos, y se pueden intercambiar en caliente conservando las entradas.")
doc.add_heading("3.4 Decisiones de diseño relevantes", 2)
B("**Misma traza para todas las políticas.** Los accesos a memoria se generan con una semilla que depende sólo de (semilla, PID) y de un modelo de localidad configurable; así, al comparar FIFO contra LRU o First contra Best Fit, la única variable es la política. También se aceptan trazas explícitas (por ejemplo la cadena de Belady).")
B("**Carga bajo demanda con reserva de swap.** Todas las páginas de un proceso admitido tienen un slot de swap; sólo se escribe a swap la víctima modificada (bit dirty), lo que permite medir swap-in y swap-out por separado.")
B("**Marcos “fijados” durante la carga.** Un marco asignado a una página en carga no puede ser elegido como víctima hasta que la carga termina, evitando desalojos de páginas que todavía no llegaron. Si todos los marcos están en carga, el proceso reintenta en el tick siguiente.")
B("**Acceso del fallo ya resuelto.** Cuando una página termina de cargarse, la instrucción que falló se reanuda sin volver a contar un acceso ni un fallo (el fallo se contabiliza una sola vez).")
B("**TLB etiquetada por PID** (como una TLB con ASID); la opción tlb_flush_on_switch modela una TLB sin ASID que debe vaciarse en cada cambio de contexto.")
B("**SJF** usa el tiempo de CPU restante en el momento de decidir (coincide con la ráfaga total si el proceso no hizo E/S). **Desempates** por orden de entrada a Listo y luego por PID. Los procesos que llegan en el mismo tick que vence un quantum se encolan antes que el proceso desalojado (convención habitual).")
B("**Espera de memoria sin bloqueo de cola:** si el primero de la cola de espera no entra pero otro sí, se admite al segundo (evita bloqueo por cabeza de línea).")
B("**Rechazo definitivo:** un proceso que no cabe nunca en el sistema (mayor que la memoria o que el mayor tamaño de partición, o con más páginas que slots de swap) pasa a Rechazado en lugar de esperar eternamente; si sólo quedan procesos esperando memoria que nunca se liberará, la simulación termina y se los rechaza.")
B("**Métricas promediadas en el tiempo:** además de los valores instantáneos (para la interfaz), se acumulan ocupación y fragmentación en cada tick para poder comparar políticas al final de la corrida (de otro modo, al terminar todos los procesos la memoria queda vacía y no habría nada que comparar).")
B("**Fragmentación.** Externa = 1 − (mayor bloque libre / memoria libre total), en %; interna = bytes asignados no utilizados (particiones fijas) o desperdicio de la última página de cada proceso (paginación), en % de lo asignado.")

# ================================================================ 4. Comparaciones
doc.add_heading("4. Comparaciones", 1)
P("Todas las tablas se generaron ejecutando los escenarios incluidos (carpeta scenarios) con el comando de comparación del simulador; son reproducibles (script informe/datos.py). "
  "Cada comparación usa el mismo escenario y la misma traza de accesos; sólo cambia la política indicada. Los resultados corresponden a un conjunto de procesos concreto y deben leerse como ilustración de tendencias, no como valores generales (cuando era posible, se verificó con varias semillas).")

doc.add_heading("4.1 Planificación de CPU: FIFO vs RR vs SJF vs SRTF", 2)
P("Escenario 01: cinco procesos (ráfagas 8, 4, 9, 5 y 2; llegadas 0, 1, 2, 3 y 6; P3 realiza una E/S de 4 ticks tras 3 de CPU), RR con quantum 3.")
F("fig/gantt4.png", 15, "Figura 4. Diagramas de Gantt de los cuatro planificadores sobre el escenario 01.")
T(["Política", "Espera prom.", "Retorno prom.", "Respuesta prom.", "Uso CPU %", "Cambios ctx", "Tiempo total"], R["sched"], widths=[2.4, 2.3, 2.4, 2.5, 2.3, 2.3, 2.3],
  caption="Tabla 2. Métricas de planificación (escenario 01, quantum 3).")
P("Análisis. SRTF obtiene los mejores tiempos de espera (6,40), retorno (12,80) y respuesta (3,80), a costa de más cambios de contexto que FIFO y SJF. SJF mejora a FIFO en espera (7,80 contra 9,20) porque evita que P1 (la ráfaga más larga) retrase a los cortos. "
  "FIFO sufre el efecto convoy pero es el que menos cambios de contexto hace (5). Round Robin es el que mejor tiempo de respuesta da entre los que no requieren conocer las ráfagas (4,20 contra 8,60 de FIFO), "
  "pero tiene el peor espera y retorno promedio (12,80 y 19,20), porque los procesos medianos se turnan y todos terminan tarde, y duplica los cambios de contexto (10).")
P("Un resultado a notar: SJF y SRTF muestran 87,5 % de uso de CPU (28 ticks útiles sobre 32) frente a 100 % de FIFO y RR. No es un defecto: al dejar para el final al proceso más largo (P3), su E/S de 4 ticks se produce cuando ya no hay otro proceso para ejecutar y la CPU queda ociosa; "
  "con FIFO y RR esa E/S se solapa con la ejecución de otros procesos. Es un ejemplo de cómo el orden de planificación interactúa con la E/S.")
T(["Quantum", "Espera prom.", "Retorno prom.", "Respuesta prom.", "Cambios ctx"], R["quantum"], widths=[2.4, 3, 3, 3, 3],
  caption="Tabla 3. Efecto del quantum en Round Robin (escenario 01).")
P("Con quantum 1 la respuesta es la mejor (1,20) pero se hacen 25 cambios de contexto; a medida que crece, la respuesta empeora (8,60 con quantum 8) y los cambios de contexto bajan a 5. Con quantum 8, mayor o igual que la ráfaga más larga, RR se comporta como FIFO y sus métricas coinciden exactamente (espera 9,20, retorno 15,60). "
  "Los tiempos de espera y retorno no son monótonos en el quantum porque dependen de cómo se alinean las ráfagas con el quantum (y de la E/S de P3).")

doc.add_heading("4.2 Memoria continua: First Fit vs Best Fit vs Worst Fit", 2)
P("Escenario 02 (memoria de 1900 bytes, SJF): los procesos cortos S1..S5 (100, 500, 200, 300 y 600 bytes) terminan primero y dejan huecos entre los procesos largos L1..L4 (50 bytes). Luego llegan R1..R4 (212, 417, 112 y 426 bytes).")
hdr = ["Política", "Espera mem. prom.", "Ocupación prom. %", "Frag. ext. prom. %", "Frag. ext. máx. %", "Frag. int. prom. %", "Compact.", "Tiempo"]
T(hdr, named(R["fit"]), widths=[2.3, 2.2, 2.2, 2.2, 2.2, 2.2, 1.7, 1.6], caption="Tabla 4. Particiones variables, sin compactación.")
P("Best Fit es la única política que aloja a los cuatro procesos al llegar (espera de memoria 0): coloca cada solicitud en el hueco más ajustado (R1→300, R2→500, R3→200) y deja libre el hueco de 600 para R4 (426). "
  "First Fit parte el hueco de 500 con R1 y el de 600 con R2; Worst Fit parte primero el hueco más grande (600) con R1; en ambos casos R4 queda en la cola de espera (espera promedio de 3,46 ticks) aunque la suma de memoria libre alcanzaba: fragmentación externa. "
  "La ocupación promedio también es mayor con Best Fit (23,9 % contra 18,2 %) porque los procesos entran antes. Worst Fit alcanza la mayor fragmentación externa máxima (75,4 % contra 70,2–70,4 %), ya que fragmenta primero los bloques grandes.")
T(hdr, named(R["fit_compact"]), widths=[2.3, 2.2, 2.2, 2.2, 2.2, 2.2, 1.7, 1.6], caption="Tabla 5. Mismas políticas con compactación automática.")
P("Con compactación automática, First y Worst Fit eliminan la espera de R4 (0,00) al costo de una compactación, y la fragmentación externa promedio baja de 53,3 % a 19,9 % y de 53,5 % a 23,5 %. Best Fit no necesita compactar (0 compactaciones) y obtiene el mismo resultado sin mover memoria.")
T(hdr, named(R["fit_fixed"]), widths=[2.3, 2.2, 2.2, 2.2, 2.2, 2.2, 1.7, 1.6], caption="Tabla 6. Particiones fijas (60, 60, 60, 60, 100, 200, 300, 500 y 600 bytes).")
P("Con particiones fijas aparece la fragmentación interna: 18,9 % con First y Best Fit y 47,97 % con Worst Fit, que ubica los procesos pequeños en las particiones más grandes, desperdiciando espacio y haciendo esperar a procesos grandes (espera 6,85). "
  "En este caso el esquema fijo evita la espera de R4 en First/Best a costa de la fragmentación interna; el variable aprovecha mejor la memoria pero sufre fragmentación externa.")

doc.add_heading("4.3 Paginación: FIFO vs LRU vs Clock", 2)
P("Escenario 03: cuatro procesos (300, 420, 250 y 500 bytes: 24 páginas virtuales de 64 bytes) comparten 640 bytes de memoria física (10 marcos) con TLB de 6 entradas, 4096 bytes de swap y RR con quantum 6. Los accesos se generan con localidad 0,9 (30 % de escrituras).")
T(["Política", "Fallos", "Tasa fallos %", "Swap-in (págs)", "Swap-out (págs)", "EAT (ns)", "Retorno prom.", "Tiempo"], R["repl"], widths=[2, 1.6, 2, 2.1, 2.2, 2.2, 2.2, 1.7],
  caption="Tabla 7. Reemplazo de páginas (escenario 03).")
ms = R["multi_seed"]
T(["Política", "Fallos prom. (20 semillas)", "Mínimo", "Máximo", "EAT prom. (ns)"], [[k] + v for k, v in ms.items()], widths=[2.6, 4.2, 2.2, 2.2, 3.2],
  caption="Tabla 8. Mismo escenario repetido con 20 semillas distintas de la traza de accesos.")
P("Con la traza de la Tabla 7, Clock produce menos fallos (88) que LRU (91) y que FIFO (102); FIFO también genera más escrituras a swap (41 contra 37 y 35) y el mayor EAT (55,2 µs contra 49,4 y 47,5 µs). "
  "Como una sola traza puede favorecer a una política, se repitió con 20 trazas: LRU resulta la mejor en promedio (83,6 fallos), Clock queda muy cerca (85,1) y FIFO es claramente peor (91,6, con picos de 118), lo que concuerda con la teoría: "
  "LRU y su aproximación Clock aprovechan la localidad de referencia, mientras que FIFO desaloja páginas muy usadas sólo por ser viejas. La diferencia entre LRU y Clock es pequeña y dentro de la variabilidad entre trazas.")
P("El retorno promedio no sigue exactamente el orden de los fallos (LRU tiene menos fallos que FIFO pero mayor retorno promedio en la Tabla 7): con varios procesos, los fallos modifican el intercalado de la CPU y qué proceso termina antes, por lo que el retorno depende del orden de finalización además del total de fallos.")
doc.add_heading("Anomalía de Belady", 3)
P("Escenario 04: un único proceso con la cadena de referencias 1,2,3,4,1,2,5,1,2,3,4,5 y sin TLB.")
T(["Política", "3 marcos", "4 marcos"], R["belady"], widths=[3, 3, 3], caption="Tabla 9. Fallos de página con la cadena de Belady.")
F("fig/belady.png", 10.5, "Figura 5. Fallos de página según la cantidad de marcos (cadena de Belady).")
P("FIFO produce 9 fallos con 3 marcos y 10 con 4: agregar memoria empeora el resultado (anomalía de Belady). LRU, un algoritmo de pila, mejora de 10 a 8 fallos. Clock se comporta aquí igual que FIFO (9 y 10). "
  "Este caso, además de ilustrar el concepto, sirve como prueba de corrección del simulador porque los valores coinciden con los de la bibliografía.")
doc.add_heading("4.4 TLB: política, tamaño y vaciado", 2)
T(["Política de TLB", "Aciertos TLB %", "EAT (ns)", "Fallos de página"], R["tlbpol"], widths=[3.5, 3.2, 3.2, 3.2], caption="Tabla 10. Política de reemplazo de la TLB (6 entradas).")
T(["Entradas de TLB", "Aciertos TLB %", "EAT (ns)"], R["tlbsize"], widths=[3.5, 3.5, 3.5], caption="Tabla 11. Tamaño de la TLB (política LRU).")
F("fig/tlbsize.png", 9.5, "Figura 6. Tasa de aciertos de la TLB según su tamaño.")
T(["Variante", "Aciertos TLB %", "EAT (ns)", "Fallos de página", "Cambios ctx"], named(R["flush"]), widths=[5.2, 2.6, 2.6, 2.6, 2.4], caption="Tabla 12. TLB etiquetada con PID vs TLB que se vacía en cada cambio de contexto.")
P("La tasa de aciertos crece con el tamaño de la TLB (de 23,9 % con 2 entradas a 65 % con 16), con rendimientos decrecientes. Entre FIFO, LRU y Clock la diferencia de aciertos es pequeña (47,7–51,9 %); en esta traza FIFO resultó levemente mejor, lo que muestra que LRU no gana siempre en una TLB tan chica y con cuatro procesos compitiendo. "
  "El impacto sobre el EAT, en cambio, es mínimo en este escenario (49 430 ns sin TLB contra 49 376 ns con 16 entradas, ≈0,1 %): con 91 fallos de página de 100 µs cada uno, el tiempo efectivo está dominado por el servicio de swap, no por la traducción. "
  "La TLB sólo se nota en el EAT cuando los fallos de página son raros. Vaciar la TLB en cada cambio de contexto (sin ASID) reduce los aciertos casi a la mitad (47,7 % → 25,8 %) con 107 cambios de contexto, lo que justifica etiquetar las entradas con el PID.")
doc.add_heading("4.5 Tamaño de página y de memoria física", 2)
T(["Tamaño de página", "Fallos", "Tasa fallos %", "Aciertos TLB %", "Frag. int. prom. %", "EAT (ns)", "Tiempo"], R["pagesize"], widths=[2.8, 1.8, 2.3, 2.4, 2.6, 2.3, 1.8],
  caption="Tabla 13. Tamaño de página con 640 bytes de memoria física (20, 10 y 5 marcos).")
T(["Memoria física (B)", "Fallos", "Tasa fallos %", "Tráfico swap (B)", "EAT (ns)", "Retorno prom.", "Tiempo"], R["memsize"], widths=[2.8, 1.8, 2.3, 2.6, 2.3, 2.3, 1.8],
  caption="Tabla 14. Tamaño de la memoria física (páginas de 64 bytes).")
F("fig/memsize.png", 14, "Figura 7. Fallos de página y tiempo efectivo de acceso según la memoria física disponible.")
P("Con la memoria fija, páginas más grandes significan menos marcos: pasar de 32 a 128 bytes eleva los fallos de 63 a 132 y el EAT de 30,5 a 70,2 µs, y la fragmentación interna se duplica (4,4 % → 11,6 %). Por el lado favorable, las páginas grandes mejoran levemente los aciertos de TLB (45,0 % → 49,2 %) porque cada entrada cubre más direcciones, "
  "y requieren tablas de páginas más chicas (no medido por el simulador). Respecto de la memoria física, duplicarla (640 → 1280 bytes) reduce los fallos de 91 a 31, el tráfico de swap de 8192 a 2304 bytes y el EAT de 49,4 a 14,0 µs, mientras que reducirla a la mitad lleva la tasa de fallos a 64,6 % (comportamiento cercano a la hiperpaginación, "
  "con 5 marcos para 4 procesos).")

doc.add_heading("4.6 Segmentación", 2)
P("Escenario 05: cinco procesos con segmentos código/datos/pila en 1000 bytes de memoria. P5 accede a la pila con desplazamiento 60 siendo su límite 50.")
T(["Política", "Espera mem. prom.", "Retorno prom.", "Ocupación prom. %", "Frag. ext. prom. %", "Frag. ext. máx. %", "Compact.", "Tiempo"], named(R["seg_fit"]), widths=[2.2, 2.2, 2.1, 2.2, 2.2, 2.2, 1.6, 1.5],
  caption="Tabla 15. Segmentación: First/Best/Worst Fit sobre los huecos libres.")
T(["Política", "Espera mem. prom.", "Retorno prom.", "Frag. ext. prom. %", "Compactaciones"], named(R["seg_fit_compact"]), widths=[2.6, 3, 3, 3.2, 3], caption="Tabla 16. Segmentación con compactación automática.")
P("La violación se detecta en el tick 18 (\"P5: VIOLACIÓN DE SEGMENTO (seg 2, desp 60) … límite=50\"): el proceso se aborta, se libera su memoria y no se contabiliza entre los procesos terminados con éxito. "
  "Best Fit logra el menor tiempo de espera (9,75) y menor fragmentación externa promedio (1,08 %) frente a First Fit (11,50 y 3,05 %) y Worst Fit (11,75 y 1,08 %); el pico de fragmentación externa es el mismo (37,7 %) porque depende de la llegada de los procesos. "
  "Un resultado contraintuitivo es que la compactación automática no mejora el promedio de Best Fit (9,75 → 11,50): al compactar, P2 —un proceso largo de 670 bytes— se admite en el tick 19 en vez del 25, pero entonces el pequeño P4 espera hasta el 32 en lugar del 19. "
  "La compactación reduce la fragmentación, pero el promedio de espera depende también del orden en que se admiten los procesos (cola FIFO de espera).")

doc.add_heading("4.7 Comparación entre los tres modelos de memoria", 2)
P("Escenario 06: seis procesos (270 a 550 bytes) con segmentos código/datos/pila y 1024 bytes de memoria física, ejecutado en los tres modelos con RR (quantum 4). En paginación se usan páginas de 64 bytes, TLB de 8 entradas y LRU.")
T(["Modelo", "Ocup. prom. %", "Frag. ext. prom. %", "Frag. int. prom. %", "Espera mem. prom.", "Retorno prom.", "Espera Listo prom.", "Uso CPU %", "Cambios ctx", "Fallos pág.", "Tiempo"],
  named(R["modos"]), widths=[2.3, 1.4, 1.5, 1.5, 1.5, 1.4, 1.5, 1.3, 1.3, 1.2, 1.2], caption="Tabla 17. Mismo conjunto de procesos en memoria continua, paginación y segmentación.")
F("fig/modelos.png", 15, "Figura 8. Fragmentación, espera de memoria y retorno según el modelo.")
P("Memoria continua y segmentación reservan memoria para todo el proceso antes de ejecutarlo: no hay fallos de página y la CPU se usa al 100 %, pero los procesos esperan memoria (17,7 y 17,0 ticks en promedio) y sufren fragmentación externa (7,9 % y 13,1 %). "
  "La segmentación ocupa más memoria (74,3 % contra 71,3 %) y fragmenta más porque coloca varios bloques más chicos por proceso, pero puede alojar procesos cuyo total no entra en un único hueco. "
  "La paginación elimina la fragmentación externa y la espera de memoria (0 ticks: se admite a todos gracias al swap) con sólo 6,5 % de fragmentación interna, pero su costo está en los 26 fallos de página: más cambios de contexto (35 contra 15), 93,75 % de uso de CPU (la CPU queda ociosa cuando todos esperan una página) "
  "y un retorno promedio de 50,5 contra 36,7 ticks. Es decir, paginar intercambia espera de memoria por tiempo de servicio de páginas; si la memoria fuera más escasa o el swap más lento, la diferencia se ampliaría.")
T(["Reemplazo", "Fallos", "Tasa fallos %", "EAT (ns)", "Retorno prom.", "Tiempo"], R["modos_pag_repl"], widths=[2.6, 2, 2.6, 2.6, 2.6, 2], caption="Tabla 18. Reemplazo de páginas en el escenario 06 (paginación).")
P("En este escenario, con memoria más holgada y trazas cortas, las tres políticas quedan prácticamente empatadas (25 a 26 fallos): la política de reemplazo sólo diferencia cuando la memoria es escasa respecto del conjunto de trabajo, como en el escenario 03.")

# ================================================================ 5. Conclusiones
doc.add_heading("5. Conclusiones", 1)
doc.add_heading("5.1 Ventajas y desventajas observadas", 2)
T(["Modelo / política", "Ventajas observadas", "Desventajas observadas"], [
    ["Memoria continua", "Traducción trivial (base + desplazamiento), sin fallos de página ni TLB; CPU al 100 %.", "Fragmentación externa (hasta 70 % en el escenario 02) o interna con particiones fijas (19–48 %); procesos esperan memoria; la compactación mueve bytes."],
    ["Best Fit", "Mejor aprovechamiento: alojó todos los procesos y dio el menor tiempo de espera de memoria en continua y segmentación.", "Deja huecos residuales muy pequeños; requiere recorrer todos los huecos."],
    ["First / Worst Fit", "First Fit es simple y rápido. Worst Fit deja huecos grandes tras cada asignación.", "Dejaron esperando a R4; Worst Fit tuvo la mayor fragmentación externa máxima (75 %) y la mayor fragmentación interna en particiones fijas (48 %)."],
    ["Paginación", "Sin fragmentación externa; admite procesos más grandes que la memoria (memoria virtual); sin espera de memoria.", "Fallos de página (35 % de tasa con 10 marcos), EAT dominado por el servicio de swap, fragmentación interna (4–12 %), tabla de páginas y TLB necesarias."],
    ["Segmentación", "Protección natural (límite por segmento, violaciones detectadas), visión lógica del programa.", "Fragmentación externa; más bloques que ubicar por proceso; requiere compactación para sostener la ocupación."],
    ["LRU / Clock vs FIFO", "Menos fallos y menos escrituras a swap con localidad (LRU 83,6; Clock 85,1; FIFO 91,6 de promedio); Clock es una aproximación barata de LRU.", "FIFO es el más simple pero sufre la anomalía de Belady y desaloja páginas muy usadas."],
    ["TLB", "Los aciertos suben con el tamaño (hasta 65 % con 16 entradas) y con la localidad; la etiqueta de PID evita vaciarla en cada cambio de contexto.", "Con pocos fallos de página su efecto en el EAT es pequeño aquí; sin ASID pierde la mitad de los aciertos."],
    ["SRTF / SJF", "Menor espera y retorno promedio.", "Requieren conocer las ráfagas, pueden postergar a los procesos largos y, en presencia de E/S, dejaron la CPU ociosa (87,5 %)."],
    ["Round Robin", "Mejor tiempo de respuesta sin conocer las ráfagas; con quantum grande se comporta como FIFO.", "Peor espera/retorno promedio y más cambios de contexto (10 contra 5 de FIFO); el quantum es un compromiso."],
], widths=[3.0, 6.7, 6.7], caption="Tabla 19. Síntesis de ventajas y desventajas.")
doc.add_heading("5.2 Aprendizajes", 2)
B("La interacción entre componentes es tan importante como cada algoritmo por separado: un fallo de página bloquea al proceso y cambia el intercalado de la CPU, la E/S modifica el uso de CPU de SJF/SRTF, y el orden de admisión a memoria altera el tiempo de espera promedio incluso cuando la compactación mejora la fragmentación.")
B("Para comparar políticas hace falta fijar la carga: usar la misma traza (semilla), medir promedios en el tiempo (no sólo el estado final) y repetir con varias trazas antes de concluir (LRU y FIFO se ordenaron distinto según la traza).")
B("Validar con casos de la bibliografía (cadena de Belady, diagramas de Gantt de ejemplos) y con invariantes (marcos sin duplicar, TLB coherente con la tabla de páginas, swap y marcos liberados al final) permitió detectar errores durante el desarrollo, por ejemplo un error de borde por el que se rechazaba a procesos que esperaban memoria justo cuando otro la liberaba al finalizar.")
B("Separar el núcleo de la interfaz y definir una interfaz común para las políticas permitió agregar Clock, cambiar políticas en caliente y reutilizar el mismo código para la consola, las pruebas y el comparador.")
doc.add_heading("5.3 Limitaciones y trabajo futuro", 2)
B("Una única CPU; el cambio de contexto se cuenta pero no consume ticks. Un tick equivale a una unidad de CPU y un acceso a memoria; los tiempos en nanosegundos sólo se usan para el cálculo del EAT.")
B("Las trazas de accesos son sintéticas (modelo de localidad simple); un trabajo futuro sería cargar trazas reales y agregar el algoritmo óptimo (OPT) como referencia.")
B("Las páginas se reservan en swap al admitir al proceso (no hay copia en blanco bajo demanda ni compartición de páginas); la segmentación pura no incluye paginación de segmentos (fuera de alcance).")
B("Los resultados numéricos del informe provienen de escenarios chicos elegidos para que sean fáciles de seguir a mano; las tendencias (no los valores exactos) son lo generalizable.")

# ================================================================ anexos
doc.add_heading("Anexo A. Escenarios de prueba y cómo ejecutarlos", 1)
T(["Escenario", "Módulo", "Qué muestra"], [
    ["01_planificacion.json", "Planificación", "FIFO, RR (quantum), SJF y SRTF con un proceso que hace E/S."],
    ["02_memoria_continua.json", "Memoria continua", "Huecos intercalados; Best Fit aloja todo, First/Worst dejan a R4 en espera; fijas y compactación."],
    ["03_paginacion_tlb_swap.json", "Paginación", "24 páginas virtuales sobre 10 marcos, TLB, swap, FIFO/LRU/Clock, tamaños de página y memoria."],
    ["04_belady_reemplazo.json", "Paginación", "Cadena de Belady con accesos explícitos."],
    ["05_segmentacion.json", "Segmentación", "Segmentos con First/Best/Worst, espera por memoria y violación de segmento."],
    ["06_comparacion_modelos.json", "Los tres", "Mismos procesos en continua, paginación y segmentación (--compare mode)."],
], widths=[5, 3.2, 8], caption="Tabla 20. Escenarios incluidos (uno o más por módulo).")
P("Ejecución (Python 3.10 o superior; la interfaz gráfica requiere Tkinter, incluido en la instalación estándar de Python):")
for line in ["python main.py                                   # interfaz gráfica",
             "python main.py scenarios/03_paginacion_tlb_swap.json",
             "python cli.py scenarios/03_paginacion_tlb_swap.json --compare repl_policy --compare tlb_policy",
             "python cli.py scenarios/01_planificacion.json --steps 10 -v        # paso a paso con eventos",
             "python -m unittest discover -s tests -v                          # 30 pruebas automáticas",
             "python informe/datos.py                                          # regenera las tablas del informe"]:
    p = doc.add_paragraph(); r = p.add_run(line); r.font.name = "Consolas"; r.font.size = Pt(8.5); p.paragraph_format.space_after = Pt(0)
doc.add_paragraph()
doc.add_heading("Anexo B. Bibliografía de referencia", 1)
P("Material de la cátedra de Sistemas Operativos (Com. B). Referencias generales: Silberschatz, Galvin y Gagne, Fundamentos de Sistemas Operativos (capítulos de planificación de CPU, memoria principal y memoria virtual); "
  "Tanenbaum y Bos, Sistemas Operativos Modernos (administración de memoria). [Completar con las fuentes efectivamente consultadas por el grupo para el portafolio.]")

doc.save("Informe_AE4_Simulador_SO.docx")
print("docx ok")
