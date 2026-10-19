# Etapa 0 — Especificación conceptual del simulador

Actualizado: 2 de octubre de 2026. Estado: etapa 0 cerrada para la primera versión; reglas operacionales, parámetros de demanda, escena y entrega e independencia condicional definidos. T1–T4 están resueltos. Esta etapa no implementa el simulador.

## 1. Propósito y alcance

Construir paso a paso un simulador que reciba una configuración de bases activas y ambulancias asignadas inicialmente a cada una, y reproduzca una jornada de operación. Permitirá ejecutar múltiples días simulados y medir su desempeño. No se optimizarán bases ni dotaciones en esta etapa.

Cada escenario describe las condiciones de un día completo y cada réplica es una realización aleatoria de ese escenario. Para identificar ejecuciones se conservarán por separado la configuración, las condiciones del escenario y las semillas de la réplica. Los bloques seleccionados para reportar no reinician ni recortan la operación de la jornada.

La primera versión es una variante simplificada del sistema documentado: no aplica estados de presión, reservas ni retención estratégica. Por decisión actualizada del usuario, permite despachar durante el retorno desde la posición actual. Estas decisiones prevalecen sobre antecedentes diferentes; no se exige reproducir exactamente los indicadores del sistema original.

## 2. Fuentes y trazabilidad

Rutas relativas a la raíz del proyecto:

| Fuente | Uso |
|---|---|
| `info/01_infraestructura.xlsx` | Geometría de 81 zonas y 9 macrozonas; 65 bases, capacidades y 10 hospitales. |
| `info/02_operacion.xlsx` | Prioridades, bloques, flota observada, velocidades y reglas originales. |
| `info/03_congestion.xlsx` | 405 factores de congestión por zona y bloque. |
| `info/04_diccionario_log.xlsx` | Campos y seis eventos de cada atención. |
| `log/filas_buenas.csv` | Fuente de datos elegida por el usuario. |
| `Codigo/VA_tiempo en escena y tiempo en base/` | Resultados y notebooks de escena y entrega; definiciones, familias, parámetros y particiones en 5.4. |
| `Codigo/VA_Cantidad y Zona/VA_Cantidad/` | Análisis del conteo Poisson por bloque y revisión de homogeneidad intrabloque. |
| `Codigo/VA_Cantidad y Zona/VA_zona/ajuste_probabilidad.ipynb` | Modelo categórico global de zona. |
| `Codigo/VA_Prioridad y ubicación en zona/05_distribuciones_parametrizadas_actualizado.csv` | Especificación entregada por el usuario: categórica global de prioridad y uniformes de X/Y condicionadas a cada una de las 81 zonas. |
| `Codigo/Notebooks entrega 1/Eventos.ipynb`, `Codigo/Notebooks entrega 1/Atenciones.ipynb` | Preparación de datos y definiciones de tiempos observados. |
| `Codigo/Notebooks entrega 1/Trayectos.ipynb` | Análisis de rutas HV/VH; no establece una ruta oficial. |
| `Codigo/Notebooks entrega 1/Estado_sistema.ipynb` | Antecedente de reconstrucción histórica; no copiar sus reglas incompatibles con esta versión. |
| `contexto_data_proyecto.txt`, `Codigo/Notebooks entrega 1/estudio_I1.ipynb` | Contexto y explicación conceptual; no sustituyen los datos ni las decisiones actuales. |

Las decisiones explícitas del usuario prevalecen sobre los antecedentes. Una propuesta pendiente no se convierte en regla por aparecer en este documento. Los parámetros incompletos y las decisiones de generación pendientes se incorporarán al resolverse; no se reemplazarán por ajustes inventados.

## 3. Base de datos acordada

Se usará `log/filas_buenas.csv`. La referencia a “90.246 filas” corresponde a **90.246 llamados**, identificados por recepción (`secuencia_evento = 1`). El CSV actual tiene **541.476 filas de eventos**, seis por atención, en 60 jornadas. La revisión de estructura confirmó 90.246 identificadores con secuencias 1–6 completas; esto no equivale a una auditoría exhaustiva de todas las variables.

Para estudiar demanda se usa una recepción por llamado. Para estudiar duraciones se usan las marcas de los eventos correspondientes. No se contarán las seis filas como seis llamados.

El CSV usa punto y coma como separador y coma decimal. Se conservarán fechas completas para atenciones que pasan de medianoche. Algunas cifras guardadas en notebooks corresponden a versiones anteriores: por ejemplo, la mención de 90.014 atenciones completas en `Estado_sistema.ipynb` no describe el archivo actual.

En la revisión se encontraron tres recepciones exactamente en un límite horario cuya etiqueta conserva el bloque anterior:

| Atención | Instante | `bloque_llegada` registrado |
|---|---|---|
| D0014-A00163 | 2025-09-22 09:00:00 | 1 |
| D0054-A00439 | 2025-11-18 13:00:00 | 2 |
| D0055-A01324 | 2025-11-19 21:00:00 | 4 |

No se corrigieron ni excluyeron registros. Para reproducir los ajustes de cantidad se respeta `bloque_llegada`; para reproducir la revisión horaria del notebook se usa la hora del timestamp. La causa de estas diferencias no está confirmada. El futuro generador debe tener una convención de límites explícita y evitar redondeos internos que cambien el bloque.

## 4. Decisiones confirmadas para la primera versión

### 4.1 Jornada y continuidad

- Un día de operación admite llamados entre 06:00 y 24:00.
- La jornada empieza con la flota disponible en las bases asignadas inicialmente, conforme a la definición del caso.
- Cada nueva réplica reinicia esa condición inicial. No hereda pendientes ni ocupación de otra réplica.
- Dentro del día no hay reinicios: cola, posiciones, atenciones, retornos y eventos futuros se mantienen al cambiar de bloque.
- El bloque de referencia de la atención se fija **al recibir el llamado**. Ambos viajes de la atención usan la congestión de ese bloque, aunque el despacho o la salida de escena ocurran en otro. Un llamado recibido a las 08:59 conserva el bloque 1 aunque se despache a las 09:02.
- El cambio de bloque no altera viajes ni parámetros ya fijados. Los modelos recibidos de escena y entrega no incluyen bloque como condicionante: usan prioridad y, para entrega, macrozona del destino.
- El retorno usa una referencia distinta: el bloque en que comienza el regreso, fijado hasta su término.
- A las 24:00 cesan las nuevas llegadas. La simulación continúa hasta completar todos los llamados pendientes, atenciones y retornos, con todas las ambulancias nuevamente en sus bases.
- Después de medianoche se mantiene el bloque calendario 5 para fijar parámetros de actividades nuevas que dependan del bloque actual, como los retornos. Esto no reemplaza el bloque de recepción ya fijado para una atención pendiente o en curso.

| Bloque | Intervalo de ingreso confirmado | Duración |
|---|---|---:|
| 1 | [06:00, 09:00) | 180 min |
| 2 | [09:00, 13:00) | 240 min |
| 3 | [13:00, 17:00) | 240 min |
| 4 | [17:00, 21:00) | 240 min |
| 5 | [21:00, 24:00) | 180 min |

Los horarios están documentados. La convención semiabierta fue aceptada: por ejemplo, una recepción exactamente a las 09:00 pertenece al bloque 2. No se modifican las etiquetas históricas.

### 4.2 Configuración de bases y ambulancias

- La entrada especifica las bases activadas y un número entero de ambulancias por base.
- Una base activa tiene al menos **4 ambulancias asignadas inicialmente**. Esta decisión resuelve para esta versión la contradicción textual del Excel.
- Puede haber más o menos de 25 bases activas; 25 corresponde solo al caso observado.
- Las bases inactivas no reciben dotación inicial ni son destinos admisibles de P4/P5.
- La capacidad máxima de cada base registrada en infraestructura limita **solo la asignación inicial**: entre 4 y su capacidad para cada base activa. No se agregan restricciones de recepción temporal ni colas por capacidad para P4/P5.
- Toda configuración debe asignar exactamente **140 ambulancias** entre las bases activas.
- La base asignada a cada ambulancia no cambia durante la jornada. La ambulancia siempre regresa a ella después de una atención.

### 4.3 Prioridades, cola y despacho

- Se respeta el orden P1, P2, P3, P4, P5; dentro de una prioridad se atiende primero al llamado más antiguo.
- No se implementan estados Normal/Alerta/Crítico ni reglas derivadas de ellos. “Normal todo el tiempo” significa operar sin esa protección, no falsear los umbrales originales.
- No hay retención estratégica, reservas globales o locales ni topes de retención. El radio de 7 km no restringe el despacho.
- Si no hay unidad disponible, el llamado espera en cola. No se interrumpe una atención clínica; el retorno sí puede interrumpirse para atender cualquier prioridad.
- Se evalúa la cola al llegar un llamado y cuando una unidad queda disponible, asignando recursos sucesivamente mientras existan pendientes y unidades elegibles.
- La ambulancia seleccionada es la disponible con menor ETA al paciente en toda la ciudad. El ETA compara las rutas HV/VH con la fórmula de la sección 6 y el bloque de recepción del llamado.
- P1–P3 se trasladan al hospital de menor tiempo de viaje entre los hospitales del catálogo.
- P4–P5 se trasladan a la base activa de menor tiempo de viaje entre las activadas por la configuración inicial.
- El hospital o base de destino se elige **al terminar la escena**, usando la congestión del bloque de recepción del llamado para comparar los tiempos. Entonces se programa el traslado.
- Se incorporan todas las llegadas y nuevas disponibilidades de un mismo instante antes de despachar. Los empates exactos se resuelven por identificador estable, respetando primero prioridad y antigüedad para llamados y ETA mínimo para unidades y destinos. Estas convenciones fueron aceptadas (P8).

### 4.4 Ciclo y disponibilidad de la ambulancia

Secuencia: disponible en su base → viaje al paciente → escena → viaje a hospital/base → entrega → retorno a su base inicial → disponible.

La ambulancia es **indisponible desde el despacho hasta fin de entrega**. Desde entonces compite por nuevos despachos, incluso durante el retorno, usando su posición actual sobre la ruta y ETA exacto. No pueden interrumpirse viaje al paciente, escena, traslado ni entrega.

Si P4/P5 termina la entrega en la propia base asignada, el retorno tiene distancia y duración cero. Si termina en otra base activa, inicia un retorno despachable hacia su base inicial. La disponibilidad comienza al terminar la entrega en ambos casos.

El retorno usa multiplicador neutro **1**, velocidad base 50 km/h y límites 22–80 km/h. Su congestión corresponde al bloque en que comienza el regreso, fijado hasta su término; si comienza después de medianoche, usa bloque 5. No conserva el multiplicador clínico ni el bloque de referencia del paciente anterior.

### 4.5 Diferencias explícitas frente al modelo original

| Aspecto | Documentación original | Primera versión acordada |
|---|---|---|
| Unidad temporal | Jornada con cinco bloques | Jornada con cinco bloques; sustituye la propuesta anterior de escenarios aislados por bloque. |
| Estados y protección | Normal/Alerta/Crítico; reservas y retención | Sin estados de protección ni retención. |
| Liberación | Fin de entrega en destino | Fin de entrega en destino. |
| Retorno | Despachable desde posición en ruta | Despachable desde posición en ruta. |
| Bases activas | Caso observado con 25 | Número variable, mínimo 4 unidades por base. |
| Destino P4/P5 | “Base candidata” | Solo bases activadas inicialmente. |

Estas diferencias afectan esperas, utilización y comparación con el log. El tiempo de retorno debe contabilizarse incluso después del sexto evento de atención.

## 5. Modelo de demanda y duraciones

### 5.1 Cantidad de llamados

Se mantiene `N(d,b) ~ Poisson(lambda_b)`, donde `lambda_b` es el número esperado de llamados de un bloque completo. No debe multiplicarse nuevamente por la duración del bloque. La tasa por minuto, cuando se necesite, es `lambda_b / duración_b`.

| Bloque | Lambda seleccionado: ajuste con 48 días | Media con 60 días: solo referencia |
|---|---:|---:|
| 1 | 161,937500 | 162,083333 |
| 2 | 287,000000 | 286,716667 |
| 3 | 373,020833 | 371,900000 |
| 4 | 487,958333 | 488,433333 |
| 5 | 195,770833 | 194,966667 |

**Decisión confirmada (P6): conservar los parámetros Poisson estimados con los primeros 48 días**, correspondientes a la segunda columna. Los últimos 12 días se mantienen para validar ese ajuste; no se incorporan a la estimación de lambda. En la implementación se conservará la precisión de los parámetros originales del notebook, sin limitarla al redondeo de esta tabla.

La columna de 60 días se calculó contando recepciones por `dia` y `bloque_llegada` y queda únicamente como referencia descriptiva; no se usará para generar los conteos. Se mantiene `filas_buenas.csv` completo como fuente, distinguiendo los subconjuntos de estimación y validación.

### 5.2 Revisión rápida de homogeneidad dentro del bloque

El notebook `Codigo/VA_Cantidad y Zona/VA_Cantidad/relacion_dependencia.ipynb`, sección “¿La tasa es constante dentro de cada bloque?”, ya compara conteos horarios de las mismas 60 jornadas mediante Friedman. Sus resultados guardados son:

| Bloque | Diferencia máxima–mínima entre medias horarias, relativa a la media | p de Friedman |
|---|---:|---:|
| 1 | 2,468 % | 0,520309 |
| 2 | 1,628 % | 0,978144 |
| 3 | 2,922 % | 0,580551 |
| 4 | 3,153 % | 0,393198 |
| 5 | 3,411 % | 0,097978 |

La revisión directa del archivo actual, reproduciendo la agrupación por día y hora del notebook, confirmó los cinco resultados de la tabla. Agrupar por etiqueta de bloque y hora puede producir pequeñas diferencias respecto de agrupar únicamente por hora, por las tres recepciones de frontera descritas antes.

Conclusión: hay respaldo para una intensidad constante dentro de cada bloque. No se detectan diferencias horarias al 5 %, pero esto no demuestra independencia de incrementos ni descarta variaciones a escalas menores que una hora. No se confunde homogeneidad temporal con uniformidad territorial: las zonas tienen probabilidades diferentes.

Confirmado por el usuario (P7a): generar un conteo Poisson por bloque y, condicionado a ese conteo, generar exactamente N instantes uniformes dentro del intervalo y ordenarlos. Así se representa un proceso Poisson homogéneo dentro de cada bloque, con intensidad distinta entre bloques. Este mecanismo no requiere una segunda generación de llegadas exponenciales; usar ambos para generar conteos independientes duplicaría la demanda. La dependencia entre los conteos de bloques distintos se trata por separado en P7b.

### 5.3 Zona, coordenadas y prioridad

- Zona: categórica global de 81 categorías seleccionada en el análisis de zona. Sus probabilidades finales son las frecuencias de las 90.246 recepciones, sin suavización. No sustituirlas automáticamente por probabilidades condicionadas por bloque.
- Coordenadas: ubicación uniforme dentro de los límites de la zona seleccionada. La nueva especificación contiene los dos intervalos X/Y para las 81 zonas; véase 5.3.2.
- Prioridad: categórica global con las cinco probabilidades del CSV entregado, incorporadas en 5.3.1. No confundir rango, riesgo vital o sensibilidad con probabilidades.
- Cantidad, zona, prioridad y aleatoriedad de posición se generarán conforme a la independencia indicada por el usuario. Las coordenadas absolutas quedan necesariamente condicionadas por los límites de la zona.
- Usar los parámetros correspondientes a cada bloque cuando el modelo aprobado tenga esa segmentación. Los modelos globales de zona y prioridad utilizan sus respectivas tablas en los cinco bloques. Los límites de coordenadas dependen únicamente de la zona seleccionada.

#### 5.3.1 Prioridad: categórica global incorporada

Fuente: [05_distribuciones_parametrizadas_actualizado.csv](../Codigo/VA_Prioridad%20y%20ubicaci%C3%B3n%20en%20zona/05_distribuciones_parametrizadas_actualizado.csv), filas `variable=prioridad`, `distribucion=Categorica`, `condicion=global`.

| Resultado | Probabilidad entregada | Porcentaje aproximado |
|---|---:|---:|
| P1_reanimacion | 0,061897480 | 6,1897480 % |
| P2_emergencia | 0,171774926 | 17,1774926 % |
| P3_urgencia | 0,253351949 | 25,3351949 % |
| P4_moderada | 0,282549919 | 28,2549919 % |
| P5_baja | 0,230425725 | 23,0425725 % |

Se sortea una prioridad por llamado con esta misma mezcla global, sin condicionar por bloque, zona ni estado operacional. Se mantienen los códigos completos de prioridad para vincularlos con rango, multiplicador de velocidad, objetivo y tipo de destino del catálogo operacional. No se reestimaron las probabilidades.

Control numérico: las probabilidades entregadas suman `0,999999999`, una diferencia de `10^-9` respecto de uno. La columna `probabilidad_acumulada` termina en 1 y presenta diferencias de hasta `10^-9` respecto de la suma acumulada de las probabilidades individuales. Para la futura implementación se tomarán las probabilidades individuales como entrada y se normalizarán por su suma, calculando de ellas una única acumulada consistente. Esta normalización solo resuelve el redondeo de exportación; no es un nuevo ajuste estadístico. El CSV original se conserva intacto.

**Procedencia confirmada por el usuario:** las probabilidades de prioridad se estimaron con los **60 días completos**. Esta información complementa el CSV, que no declara la muestra ni el método de estimación o las pruebas de selección. Se conservan los valores entregados, sin reestimarlos ni atribuirles resultados de validación ausentes. Los últimos 12 días no son una muestra independiente para validar el ajuste de prioridad, porque participaron en su estimación. Esto no cambia la decisión de usar 48 días para estimar los parámetros Poisson.

#### 5.3.2 Ubicación uniforme dentro de la zona incorporada

La misma fuente contiene 162 filas: una para `x_km` y otra para `y_km` por cada zona Z001–Z081. En todas ellas, `distribucion=Uniforme`, `condicion=zona=Znnn`, `parametro_a` es el límite inferior y `parametro_b` el superior, en kilómetros.

Para la zona seleccionada z:

- `X | Z=z ~ Uniforme(x_min(z), x_max(z))`.
- `Y | Z=z ~ Uniforme(y_min(z), y_max(z))`.
- Para materializar la ubicación uniforme en el rectángulo ya acordada, se usan dos sorteos uniformes independientes Ux y Uy y se transforman como `X = x_min + (x_max - x_min) × Ux` y `Y = y_min + (y_max - y_min) × Uy`.

La independencia condicional de los sorteos X/Y implementa la ubicación uniforme rectangular confirmada por el usuario; el CSV proporciona las marginales y no incluye pruebas adicionales de independencia. Las coordenadas absolutas no son independientes de la zona: quedan dentro de sus límites. No se generan uniformemente en toda la ciudad antes de asignar zona, ni se reemplazan por centroides.

Ejemplos de los intervalos proporcionados (valores numéricos del CSV):

| Zona | Intervalo de X (km) | Intervalo de Y (km) |
|---|---|---|
| Z001 | 0 a 3,888888889 | 0 a 3,888888889 |
| Z040 | 11,66666667 a 15,55555556 | 15,55555556 a 19,44444444 |
| Z081 | 31,11111111 a 35 | 31,11111111 a 35 |

Se verificaron las 81 zonas contra `info/01_infraestructura.xlsx`, hoja `Zonas`: cobertura completa, una fila por zona/eje, parámetros finitos y límite inferior menor que el superior. La diferencia absoluta máxima entre los límites numéricos del CSV y los del Excel es aproximadamente `4,44 × 10^-9 km`, compatible con su distinta precisión decimal.

Para evitar discrepancias de borde entre generación y geometría de viajes, se conservará la geometría de infraestructura como catálogo territorial común, con su precisión original. El CSV define la distribución uniforme y permite comprobar la concordancia de esos intervalos; no se crean rectángulos alternativos a partir de sus redondeos. La futura generación usará sorteos en `[0,1)` para mantener cada punto dentro de su zona conforme a la convención geométrica; no se redondearán internamente sus coordenadas antes de calcular viajes.

#### 5.3.3 Dependencia entre conteos de distintos bloques

La independencia entre estas variables no demuestra independencia entre los cinco conteos de una jornada. La revisión solicitada se documenta en [revisión de dependencia entre bloques](revision%20dependencia%20entre%20bloques.md). En los 48 días, B2–B4 tiene r = 0,350 (p individual = 0,0149; p Holm = 0,1489), y el contraste global por permutaciones entrega p = 0,1809. Ningún par corregido rechaza al 5 %, pero eso no demuestra independencia. La señal B2–B4 permanece positiva en los 12 días restantes (r = 0,394), con gran incertidumbre. **El usuario confirmó generar los cinco conteos diarios independientemente como simplificación de la primera versión (P7b)**, manteniendo los lambdas de 48 días. Es un supuesto de modelación, no una conclusión de independencia demostrada. Su efecto sobre la demanda diaria y la cola/ocupación heredada se revisará en la validación. La independencia de los conteos no reinicia el estado operacional entre bloques.

### 5.4 Tiempo en escena y tiempo de entrega: resultados incorporados

Fuentes recibidas en `Codigo/VA_tiempo en escena y tiempo en base/`: los archivos `Resultados tiempo en escena` y `Resultados tiempo base de entrega`, y los notebooks `analisis_tiempo_en_escena.ipynb` y `analisis_tiempo_base_de_entrega.ipynb`. Se revisaron el código y las salidas guardadas; no se ejecutaron ajustes ni se reestimaron parámetros.

#### 5.4.1 Definiciones, unidades y factores

| Variable | Diferencia en el log | Unidad del ajuste | Factores del modelo recibido |
|---|---|---|---|
| Tiempo en escena | Evento 4 menos evento 3: inicio de escena a salida al destino | Segundos | Prioridad |
| Tiempo de entrega | Evento 6 menos evento 5: llegada a hospital/base a fin de entrega | Segundos | Prioridad y macrozona del destino |

Ambos notebooks calculan duraciones con `total_seconds()`. Para un reloj en minutos se genera la duración con los parámetros originales en segundos y luego se divide el resultado por 60. No se deben interpretar los parámetros como minutos ni dividir por 60 los parámetros de forma adimensionales.

El notebook de entrega reutiliza nombres como `tiempo_en_escena`, pero calcula explícitamente eventos 5–6. “Tiempo base de entrega” no significa exclusivamente permanencia en una base de ambulancias: incluye hospitales para P1–P3 y bases activas para P4/P5. No se encontró una descomposición en tiempo basal más recargos; se incorpora la duración completa observada entre esos eventos, sin añadir factores hospitalarios ni congestión adicionales.

La macrozona usada en el ajuste de entrega proviene del **evento 5**, es decir, de la instalación de destino. En simulación se obtiene del hospital o base elegido, no de la zona del paciente ni de la base inicial de la ambulancia. Su distribución queda determinada una vez seleccionado el destino; puede sortearse al iniciar la entrega.

Los modelos recibidos no incluyen bloque horario como condicionante. Las exploraciones por bloque en los notebooks no constituyen parámetros por bloque. Se conserva la regla del bloque de recepción para los viajes, sin agregar segmentación horaria a escena o entrega.

Terminar la entrega habilita nuevos despachos. El retorno no forma parte del tiempo de entrega ajustado ni de la indisponibilidad clínica.

#### 5.4.2 Escena: parámetros completos incorporados

La nueva versión de `Resultados tiempo en escena` contiene los cinco juegos completos de parámetros y corrige la cantidad P5 a 20.781. Se conservan los números entregados, sin reestimar. Las envolturas `np.float64(...)` indican el tipo numérico de exportación; no modifican el valor ni constituyen parámetros adicionales.

| Código del simulador | Familia | Parámetros en segundos (forma adimensional) | Observaciones del ajuste |
|---|---|---|---:|
| P1_reanimacion | gamma | `a=9.644969955343276, loc=-84.28791356027531, scale=226.3778313738813` | 5583 |
| P2_emergencia | lognorm | `s=0.29177716263264786, loc=-51.03094490525805, scale=1915.5523794124038` | 15489 |
| P3_urgencia | norm | `loc=1632.7860082304526, scale=455.35889977840554` | 22842 |
| P4_moderada | gamma | `a=6.587987150060426, loc=30.028034331990945, scale=187.3201287158057` | 25472 |
| P5_baja | norm | `loc=958.9103989220923, scale=180.87930265511892` | 20781 |

Convenciones: gamma usa forma `a`, desplazamiento `loc` y escala `scale`; lognormal usa forma `s`, desplazamiento `loc` y escala `scale`; normal usa media `loc` y desviación estándar `scale`. Los parámetros de forma son adimensionales y `loc/scale` se expresan en segundos. Se preservan los desplazamientos negativos de P1 y P2, aplicando el rechazo de duraciones no positivas acordado en T3.

Se verificaron las cinco prioridades sin duplicados, los parámetros requeridos de cada familia, valores finitos y escalas/formas positivas. Los conteos suman **90.167 observaciones**, con P5=20.781; son metadatos del ajuste, no cantidades de llamados a generar. No se confunden con las 90.246 atenciones del CSV de referencia. La procedencia de la muestra se mantiene documentada en 5.4.4.

T1 queda resuelto: ya no faltan escalas ni diccionarios completos. El notebook de referencia es `analisis_tiempo_en_escena.ipynb`; la fuente de estos parámetros completos es el archivo de resultados actualizado.

#### 5.4.3 Entrega: especificación actualizada y cobertura completa

La nueva tabla sustituye íntegramente la anterior de 40 filas. Contiene **42 combinaciones** y coincide, fila por fila, con los parámetros, familias y tamaños de muestra guardados en la celda 25 (índice desde cero) del notebook actualizado `analisis_tiempo_base_de_entrega.ipynb`.

El cambio no es solo agregar dos macrozonas: **23 de las 40 combinaciones anteriores cambian de familia**. El procedimiento actual usa `Fitter`, selecciona por `sumsquare_error` (SSE) y ajusta sobre todos los casos disponibles de cada grupo, después de eliminar nulos y duraciones no positivas. Exige al menos 100 casos en el grupo completo. Los `loc` se estiman libremente; ya no se fijan en cero. No se deben combinar parámetros del pipeline anterior con los actuales.

El código exporta los parámetros con `round(valor, 6)`; se conserva esa precisión entregada, sin inventar dígitos adicionales. La tabla usa parámetros con nombre para evitar ambigüedades:

| Familia | Distribución SciPy | Parámetros | Interpretación |
|---|---|---|---|
| `norm` | `stats.norm` | `loc, scale` | Media y desviación estándar en segundos. |
| `gamma` | `stats.gamma` | `a, loc, scale` | Forma adimensional, desplazamiento y escala en segundos; escala no es tasa. |
| `lognorm` | `stats.lognorm` | `s, loc, scale` | Desviación logarítmica adimensional, desplazamiento y escala en segundos; scale no es la media aritmética. |
| `chi2` | `stats.chi2` | `df, loc, scale` | Grados de libertad adimensionales, desplazamiento y escala en segundos. |
| `rayleigh` | `stats.rayleigh` | `loc, scale` | Desplazamiento y escala en segundos. |

La tabla vigente no contiene Weibull. Se preservan los desplazamientos estimados, incluidos los negativos; la positividad de las duraciones se garantiza mediante la regla T3 ya confirmada, sin modificar los parámetros.

| Prioridad | Macrozona del destino | N del ajuste | Familia | Parámetros entregados |
|---|---|---:|---|---|
| P1_reanimacion | Centro | 765 | lognorm | `s=0.31558, loc=58.436256, scale=1281.624875` |
| P1_reanimacion | NorOriente | 534 | lognorm | `s=0.296482, loc=-30.551054, scale=1176.066858` |
| P1_reanimacion | NorPoniente | 360 | rayleigh | `loc=569.959972, scale=528.575249` |
| P1_reanimacion | Norte | 286 | lognorm | `s=0.307479, loc=62.33093, scale=1152.402208` |
| P1_reanimacion | Oriente | 1505 | gamma | `a=4.707272, loc=455.782349, scale=184.37193` |
| P1_reanimacion | Poniente | 598 | gamma | `a=6.443607, loc=314.766402, scale=146.420757` |
| P1_reanimacion | Sur | 763 | lognorm | `s=0.330062, loc=107.551108, scale=986.143297` |
| P1_reanimacion | SurPoniente | 772 | lognorm | `s=0.296618, loc=38.89064, scale=1037.2559` |
| P2_emergencia | Centro | 1962 | lognorm | `s=0.252914, loc=-488.148036, scale=1680.345624` |
| P2_emergencia | NorOriente | 1643 | lognorm | `s=0.23658, loc=-495.524875, scale=1523.352749` |
| P2_emergencia | NorPoniente | 1087 | gamma | `a=8.262947, loc=-4.688412, scale=128.92686` |
| P2_emergencia | Norte | 988 | gamma | `a=8.180107, loc=-16.804973, scale=143.779904` |
| P2_emergencia | Oriente | 4141 | gamma | `a=7.679771, loc=28.924614, scale=153.089854` |
| P2_emergencia | Poniente | 1589 | chi2 | `df=18.82468, loc=-74.748059, scale=64.643144` |
| P2_emergencia | Sur | 2058 | chi2 | `df=14.275993, loc=55.701986, scale=67.678618` |
| P2_emergencia | SurPoniente | 2024 | gamma | `a=7.983724, loc=-20.717042, scale=128.670763` |
| P3_urgencia | Centro | 2634 | norm | `loc=1215.221336, scale=378.188602` |
| P3_urgencia | NorOriente | 2596 | norm | `loc=1021.278505, scale=318.424096` |
| P3_urgencia | NorPoniente | 1919 | norm | `loc=1023.115685, scale=322.969061` |
| P3_urgencia | Norte | 1523 | lognorm | `s=0.017943, loc=-18172.508253, scale=19256.398511` |
| P3_urgencia | Oriente | 5977 | norm | `loc=1137.437176, scale=362.413706` |
| P3_urgencia | Poniente | 2359 | norm | `loc=1077.849936, scale=340.629169` |
| P3_urgencia | Sur | 3041 | norm | `loc=964.215061, scale=303.266671` |
| P3_urgencia | SurPoniente | 2797 | norm | `loc=961.974258, scale=298.005742` |
| P4_moderada | Centro | 4609 | norm | `loc=719.544804, scale=89.342966` |
| P4_moderada | NorOriente | 2141 | norm | `loc=540.441383, scale=90.975059` |
| P4_moderada | NorPoniente | 2287 | norm | `loc=540.585046, scale=89.37151` |
| P4_moderada | Norte | 1714 | norm | `loc=598.357643, scale=91.050263` |
| P4_moderada | Oriente | 3983 | norm | `loc=660.488576, scale=91.235197` |
| P4_moderada | Poniente | 2060 | norm | `loc=602.88835, scale=89.222141` |
| P4_moderada | Sur | 2210 | norm | `loc=479.839367, scale=87.633193` |
| P4_moderada | SurOriente | 2777 | norm | `loc=480.466331, scale=89.110507` |
| P4_moderada | SurPoniente | 3696 | norm | `loc=480.403409, scale=92.370044` |
| P5_baja | Centro | 3797 | chi2 | `df=61.807008, loc=61.476833, scale=9.974782` |
| P5_baja | NorOriente | 1716 | lognorm | `s=0.042431, loc=-2094.457133, scale=2598.182435` |
| P5_baja | NorPoniente | 1908 | lognorm | `s=0.009157, loc=-11729.019375, scale=12231.519157` |
| P5_baja | Norte | 1396 | lognorm | `s=0.033307, loc=-2736.978525, scale=3295.344537` |
| P5_baja | Oriente | 3311 | chi2 | `df=94.222511, loc=-135.869635, scale=8.04184` |
| P5_baja | Poniente | 1713 | chi2 | `df=99.013912, loc=-190.980663, scale=7.637456` |
| P5_baja | Sur | 1796 | chi2 | `df=98.75911, loc=-341.549544, scale=7.923482` |
| P5_baja | SurOriente | 2221 | lognorm | `s=0.039191, loc=-2383.805799, scale=2824.679357` |
| P5_baja | SurPoniente | 2911 | norm | `loc=439.217451, scale=110.865291` |

Se verificaron 42 claves únicas, parámetros finitos, escalas positivas y formas positivas cuando corresponden. Las filas suman 90.167 observaciones. La cobertura coincide con todas las combinaciones admisibles de los catálogos: ocho macrozonas con hospitales para cada prioridad P1–P3 y nueve macrozonas con bases para P4/P5.

**T2 queda resuelto.** P1–NorPoniente tiene Rayleigh con `loc=569.959972, scale=528.575249` y N=360; P1–Norte tiene lognormal con `s=0.307479, loc=62.33093, scale=1152.402208` y N=286. Se incluyen los destinos H03 y H08 sin usar parámetros prestados de otra macrozona.

La ausencia de P1–P3 en SurOriente no es una carencia: no hay hospitales en esa macrozona en el catálogo actual. P4/P5 sí tienen modelos en las nueve macrozonas.

#### 5.4.4 Muestra y alcance de validación actualizados

Escena usa los casos disponibles del log cargado, con cobertura de jornadas 1–60 en las salidas y sin partición de entrenamiento/evaluación en el ajuste mostrado.

La tabla vigente de entrega también se ajusta sobre toda la muestra disponible de cada grupo, sin partición temporal de entrenamiento/evaluación. La cobertura de días del log mostrado es 1–60; las 42 filas suman 90.167 duraciones válidas. **La división temporal 70 %/30 %, la selección inicial por AIC y el criterio de colas de la versión anterior ya no describen estos parámetros.**

El notebook conserva un experimento posterior con división aleatoria 80 %/20 % por atención para comparar modelos con y sin macrozona, seleccionando familias por AIC. Ese experimento es diferente del ajuste por SSE que produce la tabla actual; no convierte sus parámetros en estimaciones obtenidas solo con entrenamiento ni constituye validación independiente de la tabla completa.

Las salidas guardadas de los notebooks no corresponden exactamente al CSV de referencia previamente verificado: el notebook de escena muestra 541.240 filas frente a las 541.476 del log acordado, y algunos tamaños guardados difieren entre celdas. Se conserva la especificación entregada; no se afirma que haya sido reproducida sobre las 90.246 atenciones actuales. No se reestimaron modelos ni se alteraron los datos.

#### 5.4.5 Duraciones positivas: decisión confirmada

**El usuario confirmó volver a sortear cualquier duración menor o igual a cero hasta obtener una positiva**, tanto para escena como para entrega. Esto genera la distribución ajustada condicionada a `T > 0`. Se conservan sus parámetros; no se aplica valor absoluto, reemplazo por cero, recorte ni cambio de familia.

Las normales y las familias desplazadas con soporte que alcance valores negativos pueden generar duraciones no positivas, tanto en escena como en entrega. Con los parámetros actualizados, antes de condicionar, entrega P3–Oriente asigna aproximadamente 0,0849 % a tiempos negativos y P3–Sur aproximadamente 0,0738 %. Filtrar datos negativos antes de ajustar no elimina ese soporte de una normal. T3 se aplica a todas las familias.

Las pruebas del futuro generador verificarán positividad y la distribución condicionada, no exigirán que sus momentos sean exactamente los de la distribución sin condicionar. La conversión segundos/minutos se realiza después de obtener la duración positiva.

#### 5.4.6 Decisiones de duraciones resueltas

| ID | Estado | Punto |
|---|---|---|
| T1 | Resuelto | Los cinco juegos de parámetros de escena están completos; P5 tiene 20.781 observaciones. |
| T2 | Resuelto | La nueva tabla de entrega cubre 42 combinaciones, incluidas P1–NorPoniente y P1–Norte; se sustituyeron también los otros ajustes por la versión vigente. |
| T3 | Confirmado | Volver a sortear duraciones no positivas hasta obtener un valor positivo; distribución condicionada a T > 0. |
| T4 | Confirmado por el equipo | El usuario comunica que su compañero confirmó la independencia condicional entre escena y entrega. Se usan sorteos independientes una vez fijados los factores de cada distribución. |

**T4 confirmado por el usuario a partir del análisis del equipo:** se generan escena y entrega con sorteos independientes, usando prioridad para escena y prioridad más macrozona del destino para entrega. La independencia es condicional: no implica independencia de ambas duraciones respecto de la prioridad ni independencia marginal al mezclar distintos grupos.

Operacionalmente, se sortea escena con la prioridad del llamado y se sortea entrega con la prioridad y la macrozona del destino elegido. Cada variable conserva su propia regla de rechazo de valores no positivos; un rechazo de entrega no obliga a volver a generar escena, ni viceversa. No se añade correlación ni un factor aleatorio compartido.

La confirmación se incorpora como resultado comunicado por el equipo. En esta revisión no se recibió ni ejecutó el contraste estadístico que la sustenta; no se atribuyen métodos, tamaños de muestra o valores p que no se hayan entregado. Esto no deja pendiente la decisión de modelación ya confirmada. T1–T4 están resueltos.

## 6. Viajes: reglas confirmadas

Confirmado por los archivos: distancia Manhattan; velocidad base 50 km/h; límites comunes 22 y 80 km/h; tiempo determinista condicionado a geometría, congestión, bloque y prioridad. No habrá ruido aleatorio de viaje.

| Prioridad | Multiplicador de velocidad | Objetivo de respuesta | Destino |
|---|---:|---:|---|
| P1 | 2,1 | 10 min | Hospital |
| P2 | 1,6 | 12 min | Hospital |
| P3 | 1,15 | 15 min | Hospital |
| P4 | 0,9 | 18 min | Base activa |
| P5 | 0,8 | 21 min | Base activa |

Los límites de velocidad son comunes; lo que cambia por prioridad es el multiplicador. Se comparan únicamente las dos rutas Manhattan canónicas: **HV** (horizontal y luego vertical) y **VH** (vertical y luego horizontal). Se elige la de menor tiempo calculado. Esta regla se aplica a los viajes al paciente, al destino y de retorno; no se busca entre todas las rutas Manhattan posibles.

La fórmula confirmada para cada ruta es:

- Distancia total: suma de distancias de sus segmentos.
- Congestión de ruta: promedio de factores zonales ponderado por kilómetros recorridos en cada zona.
- Velocidad: `clip(50 / congestión_ruta × multiplicador, 22, 80)`.
- Tiempo: `60 × distancia_total / velocidad` minutos.

Esto aplica el límite a una velocidad única para todo el viaje. **Puede diferir del notebook de trayectos**, que aplica el límite a cada segmento antes de sumar tiempos. No se considerarán equivalentes cuando actúan los límites. La fórmula de esta sección es la confirmada para el simulador.

Para ambos viajes de atención se usa el bloque de recepción y el multiplicador de la prioridad del llamado. Para el retorno se usa el bloque de inicio del regreso y multiplicador 1. La elección de bloque y los parámetros no se actualizan durante el trayecto. Si origen y destino coinciden, el viaje dura cero y no requiere dividir por una distancia total nula para promediar congestión.

Al despachar desde un retorno se conserva el viaje planificado y se registra el instante y posición de interrupción, sin inventar una llegada a base. Se invalida la llegada antigua. El nuevo viaje usa el bloque de recepción y prioridad del nuevo llamado. La base inicial permanece fija; al terminar la nueva entrega se calcula un nuevo retorno. Un retorno cero o una llegada a base simultánea se procesa antes del despacho. La jornada termina con todas las unidades físicamente en sus bases. El tiempo y distancia efectivos del retorno se contabilizan solo hasta llegada o interrupción; son tiempo disponible en movimiento.

## 7. Decisiones resueltas

Las decisiones P1–P9 fueron resueltas y confirmadas por el usuario e incorporadas a las secciones anteriores. P7 se divide para distinguir la distribución de instantes intrabloque de la dependencia entre conteos. Se conservan los identificadores para trazabilidad:

| ID | Decisión confirmada |
|---|---|
| P1 | Comparar solo HV/VH; congestión ponderada por distancia y un único clip de velocidad por ruta. |
| P2 | Fijar el bloque al recibir el llamado; ambos viajes de atención usan ese bloque. |
| P3 | Retorno con multiplicador 1, límites 22–80 y congestión del bloque de inicio del retorno, sin cambios durante el viaje. |
| P4 | Cerrar ingresos a las 24:00 y completar pendientes, atenciones y retornos. Mantener bloque calendario 5 después de medianoche, sin sobrescribir referencias ya fijadas. |
| P5 | Exactamente 140 ambulancias; mínimo 4 por base activa y capacidad máxima aplicada solo a la asignación inicial. |
| P6 | Conservar los parámetros Poisson estimados con los primeros 48 días; los últimos 12 se reservan para validar ese ajuste. No reestimar lambda con los 60 días. |
| P7a | Generar un conteo Poisson por bloque y distribuir uniformemente sus llamados dentro de él, ordenando los instantes. |
| P7b | Generar los cinco conteos diarios independientemente como simplificación explícita, manteniendo los lambdas de 48 días. La revisión estadística no demostró independencia. |
| P8 | Intervalos semiabiertos; incorporar todas las llegadas y disponibilidades simultáneas antes de despachar; desempates exactos por identificador estable. |
| P9 | Elegir el hospital/base de destino al terminar la escena, comparando tiempos con la congestión del bloque de recepción. |

La base de retorno no requiere nueva decisión: siempre es la asignada inicialmente. Si el destino P4/P5 es esa misma base, no existe un tramo positivo de retorno.

Decisión P9: seleccionar el destino al finalizar la escena y programar entonces el traslado, usando el bloque de recepción del llamado. Esto significa comparar los diez hospitales para P1–P3 o todas las bases activas para P4/P5 y escoger el menor tiempo. En esta versión, calcular esa elección antes produciría el mismo resultado: ubicación del paciente, prioridad, bloque de referencia e instalaciones elegibles son fijos y no hay restricciones de ocupación en destinos.

## 8. Entradas, estado y salidas previstas

### Entradas

Configuración inicial; catálogos de infraestructura y prioridades; factores de congestión; modelos estadísticos aprobados; semillas; cantidad de réplicas; reglas temporales y operacionales confirmadas. Toda ejecución debe identificar la versión de estas entradas.

### Estado que se mantiene entre bloques

Reloj; ambulancias y su fase; bases asignadas; llamados pendientes ordenados por prioridad/antigüedad; atenciones en curso; agenda de eventos futuros; bloque calendario; parámetros fijados para cada actividad; acumuladores de tiempos e indicadores.

El bloque calendario actual se distingue del bloque de llegada del llamado y del bloque fijado para sus parámetros. No se sobrescribe uno para representar a los otros.

### Salidas

- Registro de los seis eventos de cada atención, compatible en significado con el log original.
- Registro interno adicional de retornos y llegadas a base. La llegada a base no reemplaza “fin entrega paciente”.
- Tabla por atención con espera, viajes, escena, entrega, respuesta y cumplimiento.
- Historial o intervalos de cola y disponibilidad, incluyendo unidades retornando como disponibles para despacho.
- Resultados por día/réplica, prioridad y bloque de recepción; métricas temporales por bloque calendario.

El registro es retrospectivo: datos como la ambulancia asignada pueden completarse después del despacho, sin usarlos anticipadamente para decidir en la recepción.

## 9. KPIs y comprobaciones conceptuales

Los KPIs vigentes para evaluar una ejecución son seis, ordenados según su prioridad y vinculados a los objetivos del proyecto: disminuir tiempos de respuesta, lograr cobertura territorial completa y obtener un sistema robusto y equilibrado.

Definición base:

- Respuesta: recepción a inicio de escena. En esta versión equivale a espera por recurso más viaje al paciente, porque no existe retención estratégica.
- Cumplimiento: respuesta menor o igual al objetivo de la prioridad.
- Espera por recurso: tiempo desde recepción hasta despacho atribuible a falta de ambulancia disponible. Si el motor futuro entrega este componente separado, se usará ese valor; si no, en esta primera versión sin retención se calcula como despacho menos recepción.

KPIs oficiales:

1. **Tiempo promedio de respuesta por prioridad.** Mide el desempeño general frente a cada prioridad clínica y se vincula al objetivo de disminuir los tiempos de respuesta.
2. **Tiempo promedio de respuesta por zona.** Permite detectar zonas desprotegidas o más vulnerables aunque el promedio general sea bueno; se vincula al objetivo de cobertura completa.
3. **Porcentaje de llamadas atendidas dentro de su tiempo objetivo por prioridad.** Evalúa el cumplimiento efectivo de los estándares de respuesta, no solo el promedio.
4. **Percentiles 90, 95 y 99 del tiempo de respuesta por prioridad.** Evalúan robustez y equilibrio, evitando que los casos extremos queden ocultos por el promedio.
5. **Porcentaje de llamadas que quedan en espera por falta de ambulancias disponibles.** Mide la capacidad del sistema para cubrir la demanda, especialmente en escenarios de alta exigencia.
6. **Porcentaje de zonas con cobertura territorial adecuada.** Para cada zona con demanda se identifica la prioridad más grave registrada durante el período evaluado. Luego se calcula la proporción de llamados de esa prioridad atendidos dentro de su objetivo. La zona se considera adecuadamente cubierta si al menos 80 % de esos llamados cumple el objetivo. El KPI es el porcentaje de zonas cubiertas respecto de las zonas que registraron demanda.

El sexto KPI incorpora el feedback de robustez geográfica: no basta con medir cobertura promedio del territorio; se debe verificar que cada zona responda razonablemente frente a la prioridad más grave que efectivamente enfrenta.

Convención de reporte para jornadas sin llamados: son ejecuciones válidas con cero
atenciones. Los indicadores sin denominador se representan como `None` (celdas vacías
en CSV), no como 0 % ni 100 %. Los resultados por prioridad y zona quedan vacíos.
El resumen general conserva zonas con demanda, zonas cubiertas y porcentaje global
de cobertura; el detalle por zona se exporta por separado. Esto no cambia los seis
KPIs ni sus reglas operacionales.

El registro de la etapa de KPIs debe conservar:

- Log de seis marcas de cada atención, compatible en significado con el log original.
- Resumen por atención con prioridad, zona, recepción, despacho, llegada a escena, respuesta, cumplimiento y espera por recurso.
- Historial interno de flota, cola y estado cuando el motor operacional lo produzca.

Los eventos internos del motor se mantendrán separados del formato de seis eventos del log original. La utilización, cola media y fracciones de tiempo por fase pueden reportarse como métricas auxiliares, calculadas ponderando por duración y no promediando observaciones tomadas solo cuando ocurre un evento, pero ya no forman parte de los seis KPIs principales.

Invariantes: conservación del número de ambulancias; una atención clínica activa como máximo por unidad; ningún despacho durante atención clínica; llegadas de retornos interrumpidos invalidadas; ninguna asignación a base inactiva; tiempos no negativos y reloj no decreciente; respeto de prioridades entre pendientes elegibles; continuidad total entre bloques.

## 10. Funcionamiento previsto del simulador

1. Validar configuración y parámetros; iniciar la jornada a las 06:00 con flota en sus bases y cola vacía.
2. Generar independientemente los cinco conteos Poisson con los parámetros de 48 días, distribuir uniformemente los instantes dentro de cada bloque y generar los atributos con los modelos aprobados. Registrar las recepciones futuras. Pueden generarse de antemano sin revelar llegadas futuras a la política de despacho.
3. Avanzar el reloj al siguiente evento, conservando todas las actividades al cruzar un bloque.
4. Incorporar llamados y nuevas disponibilidades según la convención temporal acordada; despachar por prioridad y antigüedad, eligiendo la unidad de menor ETA.
5. Ejecutar viaje al paciente y escena. Al finalizar la escena, elegir el destino de menor tiempo con la congestión del bloque de recepción y programar el traslado; después realizar la entrega. Generar escena y entrega con sorteos condicionalmente independientes, usando sus factores aprobados y repitiendo cualquier sorteo no positivo.
6. Al terminar la entrega, habilitar la unidad, iniciar retorno a la base asignada y reevaluar la cola. Si se reasigna durante el retorno, invalidar su llegada anterior y conservar su interrupción en el historial.
7. A las 24:00 cerrar nuevas llegadas; completar todos los pendientes, atenciones y retornos hasta que la flota esté en sus bases. Mantener el bloque calendario 5 durante esta extensión y respetar el bloque de recepción de cada atención.
8. Calcular KPIs, conservar registros y repetir con otra semilla, sin heredar estado entre días simulados.

### Réplicas y resumen estadístico (etapa 10)

Confirmado el 3 de octubre de 2026: comenzar con **30 réplicas de jornada completa** e **intervalos de confianza del 95 %**, manteniendo el estado entre bloques. Todavía no se exige una precisión objetivo ni se establece una regla automática de parada.

La [etapa 10](etapa_10/README.md) diferencia escenario, realización y configuración, conserva semillas y versiones de parámetros y permite reutilizar realizaciones entre configuraciones. Cada réplica aporta un valor por KPI; se reportan media, desviación muestral, error estándar e intervalo de Student entre réplicas. Los indicadores diarios se recalculan con todos los llamados del día, sin promediar directamente los porcentajes o percentiles de bloques. Los grupos sin demanda quedan sin valor y se informa cuántas réplicas aportaron datos. Los reportes por bloque clasifican por recepción y conservan atenciones que terminan más tarde.

La preparación de demanda no equivale a una ejecución operacional. Sin seleccionar motor, etapa 10 guarda realizaciones preparadas sin presentar KPIs simulados. La fábrica `Simulador.etapa_10.motor:crear_motor` conecta el motor de etapa 7, la verificación de etapa 8 y los registros de etapa 9; usa fuentes de duración reproducibles por llamado y admite retornos interrumpidos.

## 11. Criterio de cierre de la etapa 0 y trabajo siguiente

La definición operacional de la etapa 0 queda cerrada para esta primera versión: todas las decisiones P1–P9 están resueltas. Las probabilidades de prioridad y los intervalos de ubicación dentro de zona ya están incorporados y contrastados estructuralmente con los catálogos; la estimación de prioridad con los 60 días está confirmada. Los resultados de escena y entrega ya se incorporaron: unidades en segundos, escena condicionada por prioridad y entrega por prioridad y macrozona del destino. Los cinco modelos de escena y las 42 combinaciones de entrega están completos, y la independencia condicional entre ambas duraciones fue confirmada por el equipo. T1–T4 están resueltos; se mantiene el rechazo y nuevo sorteo de duraciones no positivas. Con ello queda cerrada la especificación de la etapa 0 para esta primera versión, con las decisiones y limitaciones de validación documentadas. No se autoriza rellenar datos ausentes con supuestos inventados. Los detalles de reporte de KPIs, como su ventana de utilización, se acordarán en esa etapa y no cambian las reglas operacionales cerradas aquí.

El siguiente paso es la etapa 1: catálogos, configuración y estructuras de datos. Antes de implementar cada componente se revisarán sus dependencias. Las pruebas manuales con datos fijados se etiquetarán como pruebas, nunca como parámetros del modelo real.

Orden propuesto posterior: catálogos y configuración → demanda → duraciones → viajes → motor de una atención → flota y cola → retorno y disponibilidad → registros/KPIs → réplicas → validación integrada. Las pruebas de cola y disponibilidad deben incluir agotamiento de recursos, cambios de bloque, retorno a base distinta del destino y atención posterior a medianoche.

La validación distinguirá errores de implementación de diferencias esperables por las simplificaciones autorizadas. Para el conteo Poisson se conserva la partición de 48 días de estimación y 12 de validación. Esta separación no implica que esos 12 días sean independientes de todos los componentes del simulador: los modelos finales de zona y prioridad usan los 60 días; las tablas vigentes de escena y entrega no muestran separación de estimación/evaluación en los ajustes que proporcionan sus parámetros (véase 5.4.4). Los límites de ubicación son consistentes con la infraestructura conocida. Las comparaciones sobre datos utilizados para estimar se describirán como calibración/comparación histórica, no como validación independiente del ajuste correspondiente.
