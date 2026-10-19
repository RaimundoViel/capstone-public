"""
=====================================================================================
HEURÍSTICA PARA LOCALIZACIÓN DE BASES Y ASIGNACIÓN DE AMBULANCIAS  —  Capstone G19
=====================================================================================

CONTEXTO (para quien lea esto sin haber estado en la conversación)
-------------------------------------------------------------------
- Problema: hay 65 bases candidatas; se activan 27 como parámetro de búsqueda y se
    reparten las 140 ambulancias, con mínimo 4 y capacidad inicial por base activa.
- El modelo estocástico de dos etapas (con Benders) se DESCARTÓ como método de solución
  por costo computacional. Se reemplaza por esta HEURÍSTICA, que solo busca una buena
  configuración (qué bases y cuántas ambulancias en cada una).
- La calidad de una configuración se mide con los KPI del informe (sección 2.6):
    KPI1 tiempo promedio de respuesta por prioridad   (el más importante)
    KPI2 tiempo promedio por zona (se resume con el 10% de demanda peor atendida)
    KPI3 % de llamadas dentro del tiempo objetivo por prioridad
    KPI4 percentiles 90/95/99 del tiempo de respuesta por prioridad
    KPI5 % de llamadas en espera por falta de ambulancias
    KPI6 % de zonas con cobertura territorial adecuada
- El SIMULADOR del equipo recibe una configuración {base: n_ambulancias} y devuelve los KPI.

CÓMO FUNCIONA (en palabras)
---------------------------
  1. CONSTRUIR (greedy): se activan bases de a una, siempre la que más baja la nota dado lo
     ya elegido (así no se amontonan en el centro). Luego se reparten las ambulancias
     restantes de a una donde más aportan.
  2. MEJORAR (simulated annealing): se prueban cambios pequeños ("vecinos"):
       - swap: cerrar una base activa y abrir una inactiva cercana (las ambulancias se mudan)
       - mover: pasar 1 ambulancia de una base activa a otra
     Si el cambio mejora la nota se acepta. Si empeora, a veces igual se acepta (con
     probabilidad que va bajando en el tiempo) para no quedarse pegado en un óptimo local.
     Con temperatura 0 es búsqueda local pura (hill climbing).
    Los vecinos respetan el número configurado de bases activas, las 140 unidades,
    el mínimo de 4 y la capacidad inicial.
  3. VALIDAR: las mejores soluciones encontradas se corren en el simulador con muchas
     réplicas (Monte Carlo, semillas fijas comunes a todas = números aleatorios comunes)
     y se reportan los KPI con intervalos de confianza.

¿CON QUÉ SE EVALÚA CADA VECINO?
-------------------------------
  - MODO "proxy" (por defecto): una estimación analítica rápida de los KPI (milisegundos).
    Supone que cada ambulancia está ocupada con prob. q (supuesto MEXCLP); en cada zona
    responde la más cercana libre. Sirve para explorar miles de vecinos.
  - MODO "simulador": cada vecino se evalúa con el simulador promediando N semillas fijas
    (esto es Sample Average Approximation). Más fiel, pero solo viable si el simulador es
    rápido. Ambos modos comparten la función de nota; solo el simulador incluye
    la penalización de cobertura, pendiente de estimar adecuadamente en el proxy.

CONEXIÓN CON EL SIMULADOR
-----------------------
    cargar_datos() lee los parámetros consolidados y calcula los ETAs para el proxy.
    simulador() ejecuta el motor de jornada de etapa 10 y adapta los seis KPI de etapa 9.
    Cada configuración reutiliza las mismas realizaciones por semilla.
    Las metas y penalizaciones de cumplimiento P1-P5 son provisionales acordadas.
    Los demás pesos de CONFIG_NOTA siguen pendientes de calibración.
=====================================================================================
"""

import csv
import json
import math
import time
from pathlib import Path
import numpy as np

from Heuristica.conector_simulador import cargar_datos as cargar_datos_reales
from Heuristica.conector_simulador import evaluar_en_simulador

# =====================================================================================
# 0. PARÁMETROS
# =====================================================================================

PARAMS = dict(
    n_activas=27,           # maximo de bases activas
    modo_busqueda="simulador",  # "proxy" o "simulador"
    semillas_busqueda=[101, 102, 103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130],          # solo modo "simulador" (SAA con N=5)
    semillas_validacion=list(range(1000, 1030)),  # 30 réplicas, distintas a las de búsqueda
    n_elite=5,              # cuántas mejores soluciones se validan en el simulador
    # simulated annealing
    max_iter=2000000000000,
    max_seg=10800,
    paciencia=50000,         # corta si pasan estas iteraciones sin mejorar la mejor
    T0_factor= 1.0,          # 0 => hill climbing puro
    enfriamiento=0.9,    # T <- T * enfriamiento en cada iteración
    k_cercanas=8,           # el swap abre una de las k bases inactivas más cercanas
    seed=1,
)

# Cómo se arma la NOTA (menor = mejor) a partir de los KPI.
#   ("min", kpi, peso)          -> suma peso * valor              (tiempos, % espera)
#   ("meta", kpi, peso, meta)   -> suma peso * max(0, meta - valor) (castigo bajo la meta)
# Todo queda en "minutos equivalentes". Las metas y penalizaciones de cumplimiento
# P1-P5 son provisionales acordadas; los demás pesos siguen pendientes de calibrar.
# El KPI 6 se aplica solo con KPI del simulador, incluida la validación final.
CONFIG_NOTA = [
    ("min", "t_prom_P1", 3.0),                 # KPI1
    ("min", "t_prom_P2", 2.0),
    ("min", "t_prom_P3", 1.0),
    ("min", "t_prom_peor10_zonas", 0.5),       # KPI2
    ("meta", "pct_dentro_P1", 1.0, 90.0),      # KPI3: penalización por punto porcentual faltante
    ("meta", "pct_dentro_P2", 0.75, 85.0),
    ("meta", "pct_dentro_P3", 0.5, 80.0),
    ("meta", "pct_dentro_P4", 0.25, 75.0),
    ("meta", "pct_dentro_P5", 0.25, 75.0),
    ("min", "p90_P1", 0.9),                    # KPI4
    ("min", "p90_P2", 0.6),
    ("min", "p90_P3", 0.3),
    ("min", "pct_espera", 2.0),                # KPI5
    ("meta", "pct_zonas_cubiertas", 0.5, 90.0), # KPI6: solo simulador
]

# Nombre de KPI -> alias estándar, si se necesita.
MAPEO_KPI = {}

# =====================================================================================
# 1. DATOS
# =====================================================================================

def cargar_datos(raiz=None):
    """
    Debe devolver un dict con:
      ids_bases : lista de ids de bases (como los usa el simulador), largo n_bases
      cap_base  : array (n_bases,) ambulancias máximas por base
            tiempo    : array (81, 65) de ETA proxy para viaje zona <- base
            lam       : array (81, 5) llamados esperados/día por zona y prioridad
            umbral    : array (5,) minutos objetivo por prioridad
      t_servicio: minutos promedio de ciclo (base-incidente-hospital-base)
        Lee parámetros consolidados. El ETA proxy usa P3/bloque 3; los 75 minutos de
        ciclo solo alimentan el proxy y no se usan en la evaluación del simulador.
    """
    return cargar_datos_reales(raiz)

def preparar(D):
    D["n_bases"] = len(D["ids_bases"])
    D["n_zonas"] = len(D["ids_zonas"])
    D["flota"] = int(D["flota"])
    D["minimo_base"] = int(D["minimo_base"])
    if PARAMS["n_activas"] < 1:
        raise ValueError("El maximo de bases activas debe ser positivo.")
    bases_posibles = min(
        PARAMS["n_activas"],
        np.count_nonzero(D["cap_base"] >= D["minimo_base"]),
        D["flota"] // D["minimo_base"],
    )
    if bases_posibles < 1 or np.sort(D["cap_base"])[-bases_posibles:].sum() < D["flota"]:
        raise ValueError("La capacidad conjunta no permite asignar toda la flota.")
    D["q"] = min(0.95, D["lam"].sum() / 1080 * D["t_servicio"] / D["flota"])
    D["K"] = 8                                   # ambulancias alcanzables por zona
    D["t_espera"] = 30.0                         # min extra si las K están ocupadas
    k = np.arange(D["K"])
    D["p_k"] = np.append(D["q"] ** k * (1 - D["q"]), D["q"] ** D["K"])
    # cercanía entre bases (para elegir el swap): diferencia media de tiempos a las zonas
    T = D["tiempo"].T
    D["orden_cercania"] = np.argsort(np.abs(T[:, None, :] - T[None, :, :]).mean(axis=2), axis=1)
    return D

# =====================================================================================
# 2. KPI  ->  NOTA
# =====================================================================================

def nota_desde_kpis(kpis, *, incluir_cobertura=True):
    """Nota completa del simulador; el proxy excluye explícitamente cobertura."""
    total = 0.0
    for termino in CONFIG_NOTA:
        tipo, nombre, peso = termino[:3]
        if nombre == "pct_zonas_cubiertas" and not incluir_cobertura:
            continue
        v = kpis.get(nombre)
        if v is None or not math.isfinite(v):
            raise ValueError(f"KPI {nombre} no disponible para esta evaluacion.")
        total += peso * (v if tipo == "min" else max(0.0, termino[3] - v))
    return total

def kpis_proxy(amb, D):
    """Estimación analítica de los KPI (mismos nombres que espera CONFIG_NOTA)."""
    K, p = D["K"], D["p_k"]
    idx = np.flatnonzero(amb)
    t_u = D["tiempo"][:, np.repeat(idx, amb[idx])]
    if t_u.shape[1] < K:
        t_u = np.hstack([t_u, np.full((t_u.shape[0], K - t_u.shape[1]), 90.0)])
    T = np.sort(np.partition(t_u, K - 1, axis=1)[:, :K], axis=1)
    T = np.hstack([T, T[:, :1] + D["t_espera"]])            # (zonas, K+1) tiempos posibles
    t_zona = T @ p
    lam = D["lam"]
    out = {}
    for pr in range(lam.shape[1]):
        w = lam[:, pr]
        out[f"t_prom_P{pr+1}"] = np.average(t_zona, weights=w)
        out[f"pct_dentro_P{pr+1}"] = 100 * np.average((T <= D["umbral"][pr]) @ p, weights=w)
        vals, pesos = T.ravel(), (w[:, None] * p).ravel()
        o = np.argsort(vals)
        acum = np.cumsum(pesos[o]) / pesos.sum()
        for perc in (90, 95, 99):
            out[f"p{perc}_P{pr+1}"] = vals[o][np.searchsorted(acum, perc / 100)]
    lz = lam.sum(axis=1)
    o = np.argsort(-t_zona)
    peores = o[: np.searchsorted(np.cumsum(lz[o]) / lz.sum(), 0.10) + 1]
    out["t_prom_peor10_zonas"] = np.average(t_zona[peores], weights=lz[peores])
    out["pct_espera"] = 100 * p[-1]
    return out

# =====================================================================================
# 3. SIMULADOR  (CONECTAR AQUÍ)
# =====================================================================================

def simulador(solucion, semilla, D):
    """
    Entrada : solucion = {id_base: n_ambulancias}  (solo bases activas)
              semilla  = int (para que la réplica sea reproducible)
    Salida  : dict de KPI reales calculados por Simulador.etapa_9.
    """
    return evaluar_en_simulador(solucion, semilla, D)

def kpis_simulador(amb, semilla, D):
    clave = (tuple(amb), semilla)
    cache = D.setdefault("cache_simulador", {})
    falta_detalle = False
    if D.get("capturar_detalle_validacion", False):
        clave_detalle = (tuple(sorted(vector_a_solucion(amb, D).items())), semilla)
        falta_detalle = clave_detalle not in D.get("detalle_validacion", {})
    if clave not in cache or falta_detalle:
        crudo = simulador(vector_a_solucion(amb, D), semilla, D)
        cache[clave] = {MAPEO_KPI.get(k, k): v for k, v in crudo.items()}
    return cache[clave]

# =====================================================================================
# 4. EVALUADOR (lo único que ve la heurística: una nota)
# =====================================================================================

def evaluar(amb, D):
    if PARAMS["modo_busqueda"] == "proxy":
        return evaluar_proxy(amb, D)
    # SAA: promedio de los KPI sobre N semillas fijas
    lista = [kpis_simulador(amb, s, D) for s in PARAMS["semillas_busqueda"]]
    prom = {k: np.mean([d[k] for d in lista]) for k in lista[0]}
    return nota_desde_kpis(prom)


def evaluar_proxy(amb, D):
    """Evalua rápido configuraciones completas o parciales durante el greedy."""
    return nota_desde_kpis(kpis_proxy(amb, D), incluir_cobertura=False)

# =====================================================================================
# 5. UTILIDADES DE SOLUCIÓN
# =====================================================================================

def vector_a_solucion(amb, D):
    return {D["ids_bases"][j]: int(amb[j]) for j in np.flatnonzero(amb)}

def solucion_a_vector(sol, D):
    amb = np.zeros(D["n_bases"], dtype=int)
    for b, n in sol.items():
        amb[D["ids_bases"].index(b)] = n
    return amb

# Caso Base

def cargar_caso_base(D, archivo=None):
    """Carga y valida la distribución inicial definida en caso_base.json."""
    ruta = Path(archivo) if archivo is not None else Path(__file__).with_name("caso_base.json")
    with ruta.open(encoding="utf-8") as entrada:
        solucion = json.load(entrada)
    if not isinstance(solucion, dict):
        raise ValueError("El caso base debe ser un objeto JSON base: ambulancias.")
    if any(type(cantidad) is not int for cantidad in solucion.values()):
        raise ValueError("Las cantidades del caso base deben ser enteros.")
    desconocidas = set(solucion) - set(D["ids_bases"])
    if desconocidas:
        raise ValueError(f"Bases desconocidas en el caso base: {sorted(desconocidas)}.")
    amb = solucion_a_vector(solucion, D)
    if not factible(amb, D):
        raise ValueError(
            "El caso base debe cumplir el número de bases activas, sumar 140 "
            "ambulancias y respetar mínimos y capacidades."
        )
    return amb

def factible(amb, D):
    activas = amb > 0
    n_activas = np.count_nonzero(activas)
    return (0 < n_activas <= PARAMS["n_activas"] and amb.sum() == D["flota"]
            and np.all(amb >= 0) and np.all(amb[activas] >= D["minimo_base"])
            and np.all(amb <= D["cap_base"]))

# =====================================================================================
# 6. CONSTRUCCIÓN GREEDY (warm start)
# =====================================================================================

def construir(D, verbose=True):
    amb = np.zeros(D["n_bases"], dtype=int)
    for _ in range(PARAMS["n_activas"]):                 # A) activar bases
        cand = np.flatnonzero((amb == 0) & (D["cap_base"] >= D["minimo_base"]))
        notas = []
        for j in cand:
            amb[j] = D["minimo_base"]
            notas.append(evaluar_proxy(amb, D))
            amb[j] = 0
        amb[cand[int(np.argmin(notas))]] = D["minimo_base"]
    for _ in range(D["flota"] - amb.sum()):              # B) repartir el resto
        cand = np.flatnonzero((amb > 0) & (amb < D["cap_base"]))
        notas = []
        for j in cand:
            amb[j] += 1; notas.append(evaluar_proxy(amb, D)); amb[j] -= 1
        amb[cand[int(np.argmin(notas))]] += 1
    assert factible(amb, D), "La construcción no es factible (revisar capacidades)"
    if verbose:
        print(f"[construcción] nota = {evaluar(amb, D):.3f}")
    return amb

# =====================================================================================
# 7. VECINOS ALEATORIOS
# =====================================================================================

def _abrir_base(amb, D, rng):
    activas = np.flatnonzero(amb)
    if len(activas) >= PARAMS["n_activas"]:
        return None
    inactivas = np.flatnonzero((amb == 0) & (D["cap_base"] >= D["minimo_base"]))
    donantes = activas[amb[activas] > D["minimo_base"]]
    if not len(inactivas) or amb[donantes].sum() - len(donantes) * D["minimo_base"] < D["minimo_base"]:
        return None

    nueva = amb.copy()
    base = rng.choice(inactivas)
    por_mover = D["minimo_base"]
    for donante in rng.permutation(donantes):
        mover = min(por_mover, nueva[donante] - D["minimo_base"])
        nueva[donante] -= mover
        por_mover -= mover
        if por_mover == 0:
            break
    nueva[base] = D["minimo_base"]
    return nueva


def _cerrar_base(amb, D, rng):
    activas = np.flatnonzero(amb)
    if len(activas) <= 1:
        return None
    candidatas = []
    for base in activas:
        otras = activas[activas != base]
        espacio = D["cap_base"][otras] - amb[otras]
        if espacio.sum() >= amb[base]:
            candidatas.append(base)
    if not candidatas:
        return None

    nueva = amb.copy()
    base = rng.choice(candidatas)
    por_mover = nueva[base]
    otras = np.flatnonzero(nueva)
    otras = otras[otras != base]
    nueva[base] = 0
    for destino in rng.permutation(otras):
        mover = min(por_mover, D["cap_base"][destino] - nueva[destino])
        nueva[destino] += mover
        por_mover -= mover
        if por_mover == 0:
            break
    return nueva


def vecino_aleatorio(amb, D, rng):
    """Devuelve un vecino factible o None si el sorteo no sirvió."""
    accion = rng.integers(4)
    if accion == 0:
        return _abrir_base(amb, D, rng)
    if accion == 1:
        return _cerrar_base(amb, D, rng)

    activas = np.flatnonzero(amb > 0)
    if accion == 2:                                         # swap de base
        a = rng.choice(activas)
        inact = [b for b in D["orden_cercania"][a] if amb[b] == 0 and D["cap_base"][b] >= amb[a]]
        if not inact:
            return None
        b = inact[rng.integers(min(PARAMS["k_cercanas"], len(inact)))]
        nuevo = amb.copy(); nuevo[b], nuevo[a] = amb[a], 0
    else:                                                   # mover 1 ambulancia
        origen = activas[amb[activas] > D["minimo_base"]]
        destino = activas[amb[activas] < D["cap_base"][activas]]
        if len(origen) == 0 or len(destino) == 0:
            return None
        a, b = rng.choice(origen), rng.choice(destino)
        if a == b:
            return None
        nuevo = amb.copy(); nuevo[a] -= 1; nuevo[b] += 1
    return nuevo

# =====================================================================================
# 8. SIMULATED ANNEALING (T0_factor = 0  =>  hill climbing)
# =====================================================================================

def simulated_annealing(amb0, D, verbose=True):
    rng = np.random.default_rng(PARAMS["seed"])
    actual, n_act = amb0.copy(), evaluar(amb0, D)
    mejor, n_mej = actual.copy(), n_act
    elite = {tuple(actual): n_act}                           # mejores soluciones distintas

    # temperatura inicial: que un empeoramiento típico se acepte ~50% al inicio
    deltas = [abs(evaluar(v, D) - n_act) for v in
              (vecino_aleatorio(actual, D, rng) for _ in range(50)) if v is not None]
    T = PARAMS["T0_factor"] * (np.mean(deltas) / math.log(2) if deltas else 0)

    t0, sin_mejora = time.time(), 0
    for it in range(1, PARAMS["max_iter"] + 1):
        cand = vecino_aleatorio(actual, D, rng)
        if cand is None:
            continue
        n_cand = evaluar(cand, D)
        delta = n_cand - n_act
        if delta < 0 or (T > 0 and rng.random() < math.exp(-delta / T)):
            actual, n_act = cand, n_cand
            elite[tuple(actual)] = n_act
            if len(elite) > 50 * PARAMS["n_elite"]:          # podar para no crecer sin fin
                elite = dict(sorted(elite.items(), key=lambda x: x[1])[: 10 * PARAMS["n_elite"]])
        if n_act < n_mej - 1e-9:
            mejor, n_mej, sin_mejora = actual.copy(), n_act, 0
            if verbose:
                print(f"[SA] it {it:6d}  T={T:8.4f}  mejor nota = {n_mej:.3f}")
        else:
            sin_mejora += 1
        T *= PARAMS["enfriamiento"]
        if sin_mejora >= PARAMS["paciencia"] or time.time() - t0 > PARAMS["max_seg"]:
            break

    if verbose:
        print(f"[SA] terminó en it {it} ({time.time()-t0:.0f}s). Mejor nota = {n_mej:.3f}")
    top = sorted(elite.items(), key=lambda x: x[1])[: PARAMS["n_elite"]]
    return mejor, [np.array(s) for s, _ in top]

# =====================================================================================
# 9. VALIDACIÓN EN EL SIMULADOR (Monte Carlo con números aleatorios comunes)
# =====================================================================================

def validar(soluciones, D, archivo="validacion_simulador.csv", etiquetas=None):
    soluciones = list(soluciones)
    nombres = [f"Solución {i + 1}" for i in range(len(soluciones))]
    if etiquetas:
        numero_sa = 0
        for i, (identificador, origen) in enumerate(etiquetas):
            roles = []
            for rol in origen.split("|"):
                if rol == "SA":
                    numero_sa += 1
                    roles.append(f"Candidata SA {numero_sa}")
                else:
                    roles.append({"caso_base": "Caso base", "greedy": "Greedy"}.get(rol, rol))
            nombres[i] = f"{' + '.join(roles)} ({identificador})"
    semillas = PARAMS["semillas_validacion"]
    R = len(semillas)
    total = len(soluciones) * R
    inicio = time.perf_counter()
    print(f"\n=== Iniciando validación: {len(soluciones)} soluciones x {R} réplicas "
          f"= {total} evaluaciones ===", flush=True)
    filas = []
    for i, amb in enumerate(soluciones):
        reps = []
        for replica, semilla in enumerate(semillas, 1):  # mismas semillas para todas
            inicio_replica = time.perf_counter()
            reps.append(kpis_simulador(amb, semilla, D))
            completadas = i * R + replica
            print(f"[validación] {nombres[i]} | configuración {i + 1}/{len(soluciones)} | "
                  f"réplica {replica}/{R} (semilla {semilla}) completada | "
                  f"total {completadas}/{total} ({100 * completadas / total:.1f}%) | "
                  f"réplica: {time.perf_counter() - inicio_replica:.1f}s | "
                  f"transcurrido: {(time.perf_counter() - inicio) / 60:.1f} min",
                  flush=True)
        kpis = sorted(reps[0])
        prom = {k: float(np.mean([r[k] for r in reps])) for k in kpis}
        ic = {k: float(1.96 * np.std([r[k] for r in reps], ddof=1) / math.sqrt(R)) for k in kpis}
        filas.append(dict(id=i, nota=nota_desde_kpis(prom), prom=prom, ic=ic, amb=amb))
    filas.sort(key=lambda f: f["nota"])

    print(f"\n=== Validación en simulador: {len(filas)} soluciones x {R} réplicas ===")
    for ranking, f in enumerate(filas, 1):
        print(f"\nRanking {ranking} | {nombres[f['id']]} | nota = {f['nota']:.3f}")
        for k in f["prom"]:
            print(f"   {k:22s} {f['prom'][k]:8.2f}  ± {f['ic'][k]:.2f}")

    with open(archivo, "w", newline="") as fh:
        w = csv.writer(fh)
        kpis = list(filas[0]["prom"])
        w.writerow(["ranking", "nota"] + [f"{k}_prom" for k in kpis] + [f"{k}_ic95" for k in kpis]
                   + ["configuracion"] + (["id_configuracion", "origen"] if etiquetas else []))
        for r, f in enumerate(filas, 1):
            w.writerow([r, round(f["nota"], 4)] + [round(f["prom"][k], 4) for k in kpis]
                       + [round(f["ic"][k], 4) for k in kpis] + [vector_a_solucion(f["amb"], D)]
                       + (list(etiquetas[f["id"]]) if etiquetas else []))
    print(f"\nResultados guardados en {archivo}")
    return filas

def guardar_solucion(amb, D, archivo="mejor_solucion.csv"):
    with open(archivo, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["base", "ambulancias"])
        for b, n in vector_a_solucion(amb, D).items():
            w.writerow([b, n])
    print(f"Mejor solución guardada en {archivo}")

# =====================================================================================
# 10. MAIN
# =====================================================================================

if __name__ == "__main__":
    import sys
    from Heuristica.salidas import ejecutar_con_salidas

    ejecutar_con_salidas(sys.modules[__name__])
