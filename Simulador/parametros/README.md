# Parámetros de ejecución del simulador

**`Simulador/etapa 0.md` es la fuente autoritativa de las reglas del simulador y `Simulador/parametros/` es la fuente autoritativa de los parámetros de ejecución.**

Estos archivos consolidan la especificación vigente sin reestimar distribuciones ni ejecutar notebooks. Para construir el futuro simulador bastan esta carpeta y la etapa 0. Los archivos de análisis y Excel quedan como antecedentes de procedencia, no como dependencias de ejecución.

Ante una contradicción de reglas, familias o valores explícitos con la etapa 0, prevalece la etapa 0: se debe corregir la consolidación mediante una revisión documentada, no adoptar silenciosamente otra versión de un notebook. Los valores de mayor precisión permitidos por la etapa 0 se conservan de la fuente vigente. Una modificación posterior de las fuentes históricas no actualiza automáticamente estos parámetros.

## Formato y lectura

CSV UTF-8, separador coma, punto decimal y encabezados estables. Identificadores como Z001, B01, H01 y P1_reanimacion se conservan como texto. Las macrozonas mantienen sus nombres originales, sin traducirlos. No se redondean coordenadas ni parámetros de escena al exportar. Las celdas vacías de formas estadísticas significan **no aplicable**, nunca cero.

Ejemplo con biblioteca estándar:

```python
import csv
import json
from pathlib import Path

carpeta = Path("Simulador/parametros")  # Desde la raíz del repositorio.
with (carpeta / "zonas.csv").open(encoding="utf-8", newline="") as archivo:
    zonas = {fila["zona_id"]: fila for fila in csv.DictReader(archivo)}
constantes = json.loads((carpeta / "constantes.json").read_text(encoding="utf-8"))
# csv devuelve cadenas: convertir explícitamente columnas numéricas con float/int.
```

## Archivos, columnas y claves

En las columnas siguientes, `*_km` está en kilómetros, `*_min` en minutos y `*_id` es identificador.

| Archivo | Columnas | Clave y unidades |
|---|---|---|
| `zonas.csv` | zona_id, fila, columna, x_min_km, x_max_km, y_min_km, y_max_km, centroide_x_km, centroide_y_km, macrozona_id | zona_id; 81 rectángulos, fila/columna desde 0. |
| `macrozonas.csv` | macrozona_id, fila, columna, x_min_km, x_max_km, y_min_km, y_max_km | macrozona_id; nueve rectángulos, fila/columna desde 0. |
| `bases.csv` | base_id, x_km, y_km, macrozona_id, capacidad_inicial | base_id; 65 bases; capacidad en ambulancias asignadas inicialmente. |
| `hospitales.csv` | hospital_id, x_km, y_km, macrozona_id | hospital_id; 10 hospitales. |
| `congestion.csv` | zona_id, bloque_id, factor | (zona_id, bloque_id); 405 factores adimensionales. |
| `bloques.csv` | bloque_id, inicio_min, fin_min, lambda_poisson | bloque_id; minutos desde las 06:00; lambda en llamados por bloque completo. |
| `probabilidades_zona.csv` | zona_id, probabilidad, conteo_fuente_60_dias | zona_id; probabilidad adimensional; conteo es metadato de procedencia. |
| `prioridades.csv` | prioridad_id, rango, objetivo_respuesta_min, tipo_destino, multiplicador_velocidad, probabilidad | prioridad_id; cinco prioridades; multiplicador y probabilidad adimensionales; destino hospital/base. |
| `tiempo_escena.csv` | prioridad_id, familia, a, s, df, loc, scale, n_ajuste | prioridad_id; cinco modelos. loc/scale en segundos; formas adimensionales; n_ajuste es metadato. |
| `tiempo_entrega.csv` | prioridad_id, macrozona_destino_id, familia, a, s, df, loc, scale, n_ajuste | (prioridad_id, macrozona_destino_id); 42 modelos; mismas unidades que escena. |
| `configuracion_observada.csv` | base_id, ambulancias | base_id; dotación inicial observada en 25 bases, total 140. Es un caso de entrada, no una restricción a otras configuraciones. |
| `constantes.json` | flota_total, minimo_ambulancias_base_activa, velocidad_base_kmh, velocidad_minima_kmh, velocidad_maxima_kmh, multiplicador_retorno | Claves únicas: 140 unidades, 4 unidades, 50 km/h, 22 km/h, 80 km/h y 1 adimensional. |

El bloque 1 empieza en minuto 0; el bloque 5 termina en 1080 (24:00). No se exportan tasas por minuto ni duraciones de bloque redundantes: pueden obtenerse de lambda y los límites.

Los límites de `zonas.csv` son también los parámetros de ubicación uniforme. No hay otra copia de la geometría. La asociación a macrozona de bases/hospitales permite seleccionar el modelo de entrega del destino.

La configuración observada está separada de `bases.csv`: no marca permanentemente cuáles bases están activas. Semillas, número de réplicas y configuraciones alternativas son entradas elegidas por quien ejecuta, no parámetros estimados; no se inventan valores predeterminados aquí.

## Procedencia vigente

Rutas relativas a la raíz del repositorio:

| Archivos de salida | Fuente |
|---|---|
| zonas, macrozonas, bases, hospitales | `info/01_infraestructura.xlsx`, hojas Zonas, Macrozonas, Bases y Hospitales; precisión numérica almacenada en Excel. |
| congestion | `info/03_congestion.xlsx`, hoja Factores; se omiten macrozona/fila/columna repetidas, recuperables desde zonas. |
| bloques: horarios | `info/02_operacion.xlsx`, hoja Bloques, con jornada y convención temporal de etapa 0 §4.1. |
| bloques: lambda | `Codigo/VA_Cantidad y Zona/VA_Cantidad/ajuste_distribucion.ipynb`, salida guardada de celda 21 (índice desde cero), modelos Poisson de 48 días. Se evita la tabla redondeada de celda 25 y la sugerencia antigua de reestimar con 60 días. |
| probabilidades_zona | Modelo global final de `Codigo/VA_Cantidad y Zona/VA_zona/ajuste_probabilidad.ipynb`, celda 16; etapa 0 §5.3. Detalle de recuperación debajo. |
| prioridades: probabilidad | `Codigo/VA_Prioridad y ubicación en zona/05_distribuciones_parametrizadas_actualizado.csv`, filas prioridad/Categorica/global; estimación con 60 días. |
| prioridades: otros campos | `info/02_operacion.xlsx`, hoja Prioridades; valores vigentes de etapa 0 §6. |
| tiempo_escena | `Codigo/VA_tiempo en escena y tiempo en base/Resultados tiempo en escena`, versión completa de cinco modelos; coincidencia exacta con etapa 0 §5.4.2. |
| tiempo_entrega | `Codigo/VA_tiempo en escena y tiempo en base/Resultados tiempo base de entrega`, tabla de 42 modelos; coincide con etapa 0 §5.4.3 y la celda 25 guardada de `analisis_tiempo_base_de_entrega.ipynb`. |
| configuracion_observada | `info/02_operacion.xlsx`, hoja Ambulancias; conteo de unidades por base. |
| constantes | Etapa 0 §§4.2, 4.4 y 6; flota, mínimo y velocidades contrastados con hoja Parámetros de `info/02_operacion.xlsx`. Multiplicador de retorno: decisión explícita de etapa 0. |

### Recuperación de la tabla de zona

Las salidas guardadas del notebook muestran solo parte de las 81 filas. El archivo existente `Codigo/VA_Cantidad y Zona/VA_zona/anexo_zona.tex`, tabla Z1, conserva los 81 conteos enteros. Su productor `generar_anexo.py` toma precisamente `tabla_probabilidades_final`; se revisó ese código, **sin ejecutarlo**.

Se exportaron esos conteos ya publicados y se materializó la fórmula aprobada `p_z = conteo / 90246`, con precisión de float de Python. No se usan porcentajes redondeados, suavización de Jeffreys ni el modelo condicionado por bloque. No se vuelve a estimar el modelo. Los 20 conteos visibles en las salidas guardadas del notebook coinciden; además, como validación de procedencia, los 81 coinciden con las recepciones del log actual. Esa comprobación no sustituyó ni actualizó la tabla exportada.

### Precisión y modelos de duración

- Las probabilidades originales de prioridad suman 0.999999999. Se conservan tal cual; al consumirlas debe aplicarse la normalización por su suma definida en etapa 0 §5.3.1. No se exporta otra acumulada ni otra copia normalizada.
- Escena conserva todos los dígitos entregados; se retira únicamente la envoltura textual `np.float64(...)`.
- Entrega conserva los valores exportados con hasta seis decimales. No se recuperan supuestos dígitos adicionales ni se mezclan los antiguos 40 ajustes con los 42 vigentes.
- Familias y parámetros usan la convención SciPy: norm y rayleigh (`loc, scale`), gamma (`a, loc, scale`), lognorm (`s, loc, scale`), chi2 (`df, loc, scale`). Gamma usa escala, no tasa. En lognorm, scale no es la media aritmética.
- Los desplazamientos negativos son válidos. La regla de volver a sortear duraciones no positivas permanece en etapa 0 §5.4.5. Los tiempos se generan en segundos y se convierten después a minutos.
- Entrega está condicionada por la macrozona **del destino**, no la del paciente. La ausencia de P1–P3/SurOriente es correcta: no hay hospitales allí.
- `n_ajuste` suma 90.167 en cada tabla de duración; no es la demanda ni se fuerza a coincidir con las 90.246 recepciones. Se mantienen las limitaciones de muestra de etapa 0 §5.4.4.

No se encontraron ambigüedades pendientes que impidan exportar los valores vigentes. No se trasladan umbrales de presión, retención ni radio de despacho. El despacho durante retorno está habilitado por la especificación actual y no requiere nuevos parámetros estadísticos.

## Validación y trazabilidad

Desde la raíz del repositorio:

```powershell
python -B Simulador/parametros/validar.py
```

Solo requiere la biblioteca estándar de Python. Comprueba cantidades, claves únicas, referencias, cobertura territorial, probabilidades, bloques, destinos, parámetros finitos y formas/escalas positivas. Verifica también las huellas de los datos exportados.

- `procedencia.json`: versión de esquema, SHA-256 de fuentes y datos exportados, y controles de concordancia realizados durante la extracción. Las huellas de fuentes son informativas para auditoría; el validador no necesita abrirlas.
- `validacion.json`: resultado guardado de la validación inicial y comprobaciones de procedencia.
- `herramientas/consolidar.py`: utilidad documental de extracción; requiere openpyxl y las fuentes originales. No es parte de la ejecución del futuro simulador. Lee salidas guardadas, no ejecuta celdas. Exige una carpeta de salida nueva para no sobrescribir los parámetros vigentes.

Para auditar una nueva extracción, pasar raíz del repositorio y una carpeta temporal nueva como argumentos de `consolidar.py`. Revisar cambios respecto de etapa 0 antes de sustituir archivos o huellas. La exportación está ligada a la estructura actual de las fuentes; un cambio en su formato requiere revisión.

La etapa 1 ya está actualizada y lee los catálogos y la configuración observada desde los CSV consolidados de `Simulador/parametros/`, sin depender de los Excel originales para su ejecución. Véase el [README de etapa 1](../etapa_1/README.md) para los detalles de carga, validación y creación del estado inicial.
