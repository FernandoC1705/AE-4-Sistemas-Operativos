"""Textos de ayuda de la interfaz (guía rápida, glosario, atajos, sugerencias por módulo)."""

# Sugerencias "qué probar" según el escenario cargado (clave = nombre de archivo sin .json)
HINTS = {
    "01_planificacion": "Qué probar: apretá ▶ Paso o ⏵ Automático y mirá el Gantt. Después cambiá el algoritmo (FIFO · RR · SJF · SRTF) "
                        "en el panel izquierdo —se aplica en el acto— y en Round Robin cambiá el Quantum. Con ⚖ Comparar ves los cuatro lado a lado.",
    "02_memoria_continua": "Qué probar: en la pestaña Memoria física mirá cómo R4 queda en “Esperando Memoria” aunque hay lugar libre (fragmentación externa). "
                           "Cambiá la política de ajuste a Best Fit y apretá “Aplicar y reiniciar”; o tildá “Compactar automáticamente”.",
    "03_paginacion_tlb_swap": "Qué probar: los procesos en rosa tuvieron un fallo de página y esperan que la página llegue de swap. Mirá los marcos, la TLB y el orden de reemplazo. "
                              "Cambiá FIFO ↔ LRU ↔ Clock en caliente, o usá la pestaña “Acceso manual” para provocar un fallo a propósito.",
    "04_belady_reemplazo": "Qué probar: un solo proceso con la cadena 1,2,3,4,1,2,5,1,2,3,4,5. Corré hasta el final con FIFO y mirá los fallos; luego cambiá la memoria a 40 "
                           "(4 marcos) y reiniciá: ¡FIFO tiene MÁS fallos con más memoria (anomalía de Belady)!",
    "05_segmentacion": "Qué probar: cada proceso tiene segmentos (código, datos, pila) con base y límite. P5 va a acceder fuera de límite: avanzá hasta el tiempo 18 y mirá "
                       "la violación de segmento en el cuadro “Qué pasó” y en la tabla de procesos. En “Acceso manual” podés forzar otra.",
    "06_comparacion_modelos": "Qué probar: este escenario sirve para comparar los tres modelos con los mismos procesos. Cambiá el módulo en el panel izquierdo "
                              "(Memoria continua / Paginación / Segmentación), o apretá ⚖ Comparar y elegí “Modelo de memoria”.",
}
DEFAULT_HINT = "Qué probar: apretá ▶ Paso para avanzar de a un instante, o ⏵ Automático para verlo correr solo."

INTRO = ("👋 Para empezar: elegí un módulo arriba (①…⑤) y apretá ▶ Paso (o la barra espaciadora). "
         "Acá abajo te voy a contar en palabras qué pasa en cada instante.")

GUIDE = """GUÍA RÁPIDA

1) Elegí qué querés ver (botones ① a ⑤ de arriba). Cada uno carga un escenario de ejemplo ya armado.

2) Mirá la TABLA DE PROCESOS (arriba, siempre visible): cada fila es un proceso y su color indica el estado
   (Listo, Ejecutando, Bloqueado, Esperando Página, Esperando Memoria, Terminado…). Se actualiza en cada paso.

3) Avanzá con ▶ Paso (barra espaciadora), ⏵ Automático (slider "Velocidad") o ⏭ Hasta el final.
   ◀ Atrás retrocede un instante (vuelve a simular desde el inicio, el resultado es idéntico).

4) El cuadro "¿Qué pasó en este paso?" explica en palabras cada evento: llegadas, cambios de contexto,
   fallos de página, TLB hit/miss, asignaciones de memoria, etc.

5) Las pestañas muestran: Gantt y línea de tiempo por proceso · Memoria física · Tablas de páginas/segmentos/TLB ·
   Área de swap · Métricas (con explicación de cada una) · Acceso manual · Registro completo.
   Sólo aparecen las pestañas que tienen sentido para el módulo elegido.

6) Panel izquierdo = configuración. Lo que dice (en caliente) se aplica de inmediato: algoritmo, quantum, política de ajuste,
   reemplazo de TLB y de páginas. Los demás parámetros (tamaño de memoria, de página, TLB, swap…) se aplican con el botón naranja
   "Aplicar y reiniciar". Pasá el mouse sobre cualquier campo para ver qué significa.

7) ⚖ Comparar ejecuta el MISMO escenario con distintas políticas y te dice cuál rindió mejor.

8) ＋ Nuevo proceso agrega un proceso mientras corre la simulación.

Para la defensa: pestaña "Acceso manual" (provocar un fallo de página o una violación de segmento) y
cambios en caliente (algoritmo de reemplazo, quantum, ajuste)."""

SHORTCUTS = """ATAJOS DE TECLADO

  Barra espaciadora / →   Avanzar un paso
  ←                        Retroceder un paso
  A                        Automático / Pausa
  E                        Ejecutar hasta el final
  R                        Reiniciar
  C                        Abrir la comparación de políticas
  N                        Nuevo proceso
  F1                       Esta ayuda

(Los atajos no funcionan mientras escribís en un campo de texto.)"""

GLOSSARY = """GLOSARIO

Tick: unidad de tiempo del simulador (una unidad de CPU).
Estado: situación de un proceso (Nuevo, Listo, Ejecutando, Bloqueado, Esperando Memoria, Esperando Página, Terminado).
Quantum: tiempo máximo que Round Robin deja a un proceso en la CPU antes de pasar al siguiente.
Cambio de contexto: la CPU pasa de ejecutar un proceso a otro.
Espera: ticks que el proceso pasó en la cola de Listos. Retorno: desde que llegó hasta que terminó. Respuesta: desde que llegó hasta que usó la CPU por 1ª vez.

First / Best / Worst Fit: elegir el primer hueco que alcance / el más ajustado / el más grande.
Fragmentación externa: hay memoria libre suficiente pero repartida en huecos chicos, no contiguos.
Fragmentación interna: memoria asignada pero no usada (particiones fijas o última página).
Compactación: juntar todos los bloques ocupados para formar un solo hueco libre.

Página / marco: trozo de memoria lógica / trozo de memoria física, del mismo tamaño.
Tabla de páginas: dice en qué marco está cada página de un proceso.
TLB: caché chica de traducciones recientes (página → marco). Hit = estaba; miss = hay que ir a la tabla de páginas.
Fallo de página: la página pedida no está en memoria; hay que traerla desde swap (el proceso espera).
Swap: espacio en disco donde viven las páginas que no están en memoria.
Reemplazo (FIFO / LRU / Clock): qué página sacar de memoria cuando no hay marcos libres:
  la más vieja / la menos usada recientemente / segunda oportunidad con bit de referencia.
Página modificada (dirty): al desalojarla hay que escribirla en swap (swap-out).
EAT: tiempo efectivo de acceso a memoria (promedio de todos los accesos, contando TLB y fallos).

Segmento: parte lógica de un programa (código, datos, pila) de tamaño variable. Base = dónde empieza en memoria; límite = su tamaño.
Violación de segmento: acceso con desplazamiento ≥ límite; el proceso se aborta."""

METRIC_HELP = {
    "tiempo": "Ticks simulados hasta ahora.",
    "cpu_uso": "% de ticks en que la CPU estuvo ejecutando algo.",
    "cambios_contexto": "Veces que la CPU cambió de un proceso a otro.",
    "terminados": "Procesos que terminaron bien.",
    "abortados": "Procesos terminados por error (p. ej. violación de segmento).",
    "rechazados": "Procesos que nunca pudieron cargarse (no caben).",
    "espera_prom": "Promedio de ticks esperando en la cola de Listos.",
    "retorno_prom": "Promedio de llegada → fin.",
    "respuesta_prom": "Promedio de llegada → primera vez en CPU.",
    "espera_mem_prom": "Promedio de ticks esperando que haya memoria.",
    "throughput": "Procesos terminados por tick.",
    "mem_ocupacion": "% de la memoria ocupada AHORA.",
    "ocupacion_prom": "% de memoria ocupada, promediado en el tiempo.",
    "mem_libre": "Bytes libres AHORA.",
    "mayor_libre": "Tamaño del mayor hueco libre AHORA.",
    "frag_externa": "Fragmentación externa AHORA: 1 − mayor hueco / libre total.",
    "frag_ext_prom": "Fragmentación externa promediada en el tiempo.",
    "frag_ext_max": "Peor fragmentación externa observada.",
    "frag_interna": "Memoria asignada no usada AHORA (%).",
    "frag_int_prom": "Fragmentación interna promediada en el tiempo.",
    "compactaciones": "Veces que se compactó la memoria.",
    "accesos": "Accesos a memoria traducidos.",
    "fallos_pagina": "Páginas que hubo que traer desde swap.",
    "tasa_fallos": "Fallos de página / accesos (%).",
    "tlb_hit": "% de traducciones resueltas por la TLB.",
    "tlb_miss": "% de traducciones que no estaban en la TLB.",
    "eat_ns": "Tiempo efectivo de acceso a memoria (ns).",
    "swap_in": "Páginas leídas desde swap.",
    "swap_out": "Páginas modificadas escritas a swap al desalojarlas.",
    "swap_trafico": "Bytes movidos entre memoria y swap.",
    "reemplazos": "Páginas desalojadas para hacer lugar.",
    "violaciones": "Accesos fuera del límite de un segmento.",
}

# Descripciones (tooltips) de los campos de configuración
FIELD_HELP = {
    "mode": "Qué se simula: sólo CPU, memoria continua, paginación con TLB y swap, o segmentación.",
    "scheduler": "Algoritmo de planificación de CPU. Se aplica al instante (también durante la simulación).",
    "quantum": "Sólo para Round Robin: cuántos ticks puede usar la CPU un proceso antes de ceder el turno. Se aplica al instante.",
    "mem_size": "Tamaño de la memoria física en bytes (en paginación = marcos × tamaño de página).",
    "fit": "Cómo elegir el hueco: First = el primero que alcance, Best = el más ajustado, Worst = el más grande. Se aplica al instante.",
    "partition": "Variable: los huecos se crean a medida que llegan procesos. Fijas: la memoria ya está dividida en particiones del tamaño indicado.",
    "fixed_partitions": "Tamaños de las particiones fijas separados por coma (sólo si Particiones = fixed).",
    "auto_compact": "Si no hay un hueco contiguo pero sí memoria libre suficiente, junta los bloques automáticamente.",
    "page_size": "Tamaño de cada página y de cada marco, en bytes.",
    "tlb_size": "Cantidad de entradas de la TLB. 0 = sin TLB.",
    "tlb_policy": "Qué traducción sacar de la TLB cuando está llena. Se aplica al instante.",
    "repl_policy": "Qué página sacar de memoria cuando no hay marcos libres. Se aplica al instante.",
    "swap_size": "Tamaño del área de swap en bytes. Cada proceso reserva lugar para todas sus páginas.",
    "tlb_flush_on_switch": "Simula una TLB sin etiqueta de proceso: se vacía en cada cambio de contexto.",
    "t_tlb": "Tiempo de acceso a la TLB en ns (para calcular el EAT).",
    "t_mem": "Tiempo de acceso a memoria principal en ns (para calcular el EAT).",
    "t_fault": "Tiempo de transferir una página entre memoria y swap en ns (para el EAT).",
    "swap_in_ticks": "Cuántos ticks queda bloqueado un proceso mientras se carga su página desde swap.",
    "swap_out_ticks": "Ticks extra de bloqueo si hay que escribir en swap la página desalojada.",
    "seed": "Semilla del generador de accesos: misma semilla = misma secuencia de direcciones.",
    "locality": "0 a 1. Cuanto más alto, más seguido accede un proceso a las mismas páginas (más localidad).",
    "write_prob": "0 a 1. Probabilidad de que un acceso sea una escritura (marca la página como modificada).",
}


# ---------------------------------------------------------------- pestaña "¿Cómo funciona?"
# Formato: líneas "## Título" = encabezado; el resto es texto.
EXPLAIN = {
    "none": """## La idea
Hay una sola CPU y varios procesos que la quieren. El planificador decide, en cada instante, quién la usa.
Cada proceso pasa por estados: Nuevo → Listo → Ejecutando → (Bloqueado por E/S → Listo) → Terminado.

## Los algoritmos
FIFO: se atiende por orden de llegada y nadie desaloja a nadie. Un proceso largo al principio hace esperar a todos (efecto convoy).
Round Robin: cada proceso usa la CPU como máximo "quantum" ticks y vuelve al final de la cola. Buen tiempo de respuesta, pero más cambios de contexto.
SJF (no apropiativo): entre los Listos elige el que necesita menos CPU, y lo deja terminar su turno.
SRTF (SJF apropiativo): igual, pero si llega uno con menos tiempo restante, desaloja al que está ejecutando.

## Cómo lo hace este programa
El tiempo avanza de a un "tick". En cada tick: (1) llegan los procesos nuevos, (2) se despiertan los que terminaron una E/S,
(3) se aplica el desalojo (fin de quantum, SRTF) y se elige a quién ejecutar, (4) el elegido usa 1 tick de CPU.
Código: core/engine.py → Simulation.step(), _select(), _preempt_check().

## Qué mirar en pantalla
• Gantt: quién usó la CPU en cada instante.  • Línea de tiempo: qué hacía cada proceso (ejecutando, esperando, bloqueado).
• Métricas: espera = tiempo en la cola de Listos; retorno = llegada→fin; respuesta = llegada→primera vez en CPU; uso de CPU; cambios de contexto.""",

    "contiguous": """## La idea
Cada proceso necesita UN bloque contiguo de memoria del tamaño de todo el proceso. Cuando un proceso termina, deja un hueco.
Con el tiempo la memoria queda llena de huecos chicos: hay memoria libre, pero no junta → fragmentación externa.

## Cómo se elige el hueco
First Fit: el primer hueco (por dirección) donde entre.   Best Fit: el hueco más ajustado.   Worst Fit: el hueco más grande.
Si no entra en ninguno, el proceso espera en la cola "Esperando Memoria" y se reintenta cada vez que otro proceso libera memoria.
Particiones fijas: la memoria ya viene dividida; si el proceso es más chico que la partición se desperdicia el resto (fragmentación interna).
Compactación: se corren todos los bloques ocupados hacia el principio para juntar los huecos en uno solo (cuesta mover bytes).

## Cómo lo hace este programa
La memoria es una lista de bloques (inicio, tamaño, dueño). Al liberar, se fusionan los huecos vecinos.
Código: core/memory.py → MemoryMap.allocate(), release(), compact(); la elección del hueco está en core/policies.py → pick_hole().

## Qué mirar en pantalla
Pestaña "Memoria física": el mapa a escala, la cola de espera y la fragmentación externa (= 1 − mayor hueco / memoria libre).""",

    "paging": """## La idea
La memoria física se divide en MARCOS y la memoria de cada proceso en PÁGINAS del mismo tamaño. Una página puede ir en cualquier marco,
por eso no hay fragmentación externa. Una dirección lógica = (número de página, desplazamiento). La tabla de páginas dice en qué marco está cada página.

## Memoria virtual y swap
No hace falta tener todo el proceso en memoria: las páginas viven en el área de swap (disco) y se traen BAJO DEMANDA.
Si el proceso pide una página que no está en memoria → FALLO DE PÁGINA: el proceso queda "Esperando Página" mientras la página llega de swap
y la CPU atiende a otro. Si no hay marcos libres, hay que sacar una página (víctima); si estaba modificada se escribe en swap primero.

## TLB
Es una caché chica de traducciones recientes (página → marco). Acierto (hit): se traduce sin mirar la tabla de páginas. Fallo (miss): hay que consultarla.

## Políticas de reemplazo (para la TLB y para los marcos)
FIFO: sale la más vieja.  LRU: sale la menos recientemente usada.  Clock: como FIFO pero con bit de referencia: si la página fue usada, tiene segunda oportunidad.

## Tiempo efectivo de acceso (EAT)
Acierto de TLB: t_TLB + t_mem.  Fallo de TLB: t_TLB + 2·t_mem.  Fallo de página: además se suma el tiempo de swap (y otro si hay que escribir la víctima).

## Cómo lo hace este programa
Código: core/paging.py → PagingManager.access() (TLB → tabla de páginas → fallo), complete_load(); políticas en core/policies.py.

## Qué mirar en pantalla
Memoria física (marcos y de quién son), Tablas (tabla de páginas, TLB, orden de reemplazo), Swap, y las métricas: fallos, hit rate, EAT.""",

    "segmentation": """## La idea
Un programa se ve como un conjunto de SEGMENTOS con significado (código, datos, pila) de tamaño variable.
Cada segmento se ubica en memoria como un bloque contiguo; la tabla de segmentos guarda su BASE (dónde empieza) y su LÍMITE (cuánto mide).

## Traducción de direcciones
Dirección lógica = (segmento, desplazamiento). Si desplazamiento < límite → dirección física = base + desplazamiento.
Si desplazamiento ≥ límite → VIOLACIÓN DE SEGMENTO: el proceso intentó acceder fuera de su segmento y se aborta (protección).

## Asignación
Los segmentos se ubican en los huecos libres con First / Best / Worst Fit, como en memoria continua. Un proceso entra "todo o nada":
si algún segmento no entra, no se le asigna nada y espera. Hay fragmentación externa y se puede compactar.

## Cómo lo hace este programa
Código: core/memory.py → SegmentationManager.translate() y seg_table(); reutiliza MemoryMap con un bloque por segmento.

## Qué mirar en pantalla
Memoria física (cada segmento pintado con el color de su proceso), pestaña Tablas (base y límite), y el registro de la violación de segmento.""",
}
