"""Variabilidad entre replicas; cada jornada aporta una observacion por KPI."""
from functools import lru_cache
from math import isfinite, sqrt
from statistics import mean, stdev

from Simulador.etapa_9 import calcular_kpis
from .modelos import Estimacion, ResumenIndicador


@lru_cache(maxsize=128)
def _critico_t(confianza, grados_libertad):
    try:
        from scipy.stats import t
    except ImportError as exc:
        raise RuntimeError(
            "Falta SciPy. Instalar: python -m pip install -r Simulador/etapa_10/requirements.txt"
        ) from exc
    return float(t.isf((1 - confianza) / 2, grados_libertad))


def estimar(valores, confianza: float = 0.95) -> Estimacion:
    if not isfinite(confianza) or not 0 < confianza < 1:
        raise ValueError("La confianza debe estar entre 0 y 1.")
    valores = tuple(valores)
    datos = [v for v in valores if v is not None]
    if any(not isfinite(v) for v in datos):
        raise ValueError("Los indicadores deben ser finitos o None si no hay demanda.")
    total, n = len(valores), len(datos)
    promedio = mean(datos) if n else None
    if n < 2:
        return Estimacion(total, n, promedio, None, None, None, None, None, confianza)
    desviacion = stdev(datos)
    error = desviacion / sqrt(n)
    margen = _critico_t(confianza, n - 1) * error
    return Estimacion(total, n, promedio, desviacion, error, margen,
                      promedio - margen, promedio + margen, confianza)


def indicadores_replica(resultado, catalogos):
    """Incluye grupos sin demanda como None y no los convierte en ceros."""
    por_id = {l.id: l.bloque_recepcion for l in resultado.realizacion.llamados}
    grupos = {"jornada": resultado.registros}
    for b in resultado.realizacion.escenario.bloques_evaluados:
        grupos[f"bloque_{b}"] = tuple(r for r in resultado.registros if por_id[r.atencion_id] == b)
    valores = {}
    for ambito, registros in grupos.items():
        k = calcular_kpis(registros, catalogos) if registros else None
        valores[ambito, "llamados", "todos", "llamados"] = len(registros)
        for p in sorted(catalogos.prioridades):
            valores[ambito, "kpi_01", p, "minutos"] = (
                k.tiempo_promedio_respuesta_por_prioridad.get(p) if k else None)
            valores[ambito, "kpi_03", p, "porcentaje"] = (
                k.cumplimiento_objetivo_por_prioridad_pct.get(p) if k else None)
            for percentil in ("p90", "p95", "p99"):
                valores[ambito, f"kpi_04_{percentil}", p, "minutos"] = (
                    k.percentiles_respuesta_por_prioridad.get(p, {}).get(percentil) if k else None)
        for z in sorted(catalogos.zonas):
            valores[ambito, "kpi_02", z, "minutos"] = (
                k.tiempo_promedio_respuesta_por_zona.get(z) if k else None)
        valores[ambito, "kpi_05", "todos", "porcentaje"] = (
            k.porcentaje_llamadas_con_espera_recurso if k else None)
        valores[ambito, "kpi_06", "zonas_con_demanda", "porcentaje"] = (
            k.porcentaje_zonas_cobertura_adecuada if k else None)
    return valores


def resumir_resultados(resultados, catalogos, confianza: float = 0.95):
    resultados = tuple(resultados)
    if not resultados:
        raise ValueError("No hay replicas ejecutadas para resumir.")
    claves = [(r.realizacion.escenario.id, r.realizacion.numero) for r in resultados]
    if len(claves) != len(set(claves)):
        raise ValueError("Hay replicas duplicadas; no son observaciones independientes.")
    versiones = {(r.configuracion, r.realizacion.huellas_parametros, r.huellas_codigo,
                  r.version_motor, r.realizacion.semilla_maestra) for r in resultados}
    if len(versiones) != 1:
        raise ValueError("Resumir por separado configuraciones, parametros, motores o semillas maestras distintos.")
    huellas = dict(resultados[0].realizacion.huellas_parametros)
    if any(huellas.get(n) != h for n, h in catalogos.huellas_fuentes.items()):
        raise ValueError("El catalogo no corresponde a los parametros de los resultados.")
    escenarios = {}
    for r in resultados:
        e = r.realizacion.escenario
        if e.id in escenarios and escenarios[e.id] != e:
            raise ValueError("Un ID de escenario tiene definiciones distintas.")
        escenarios[e.id] = e
    series = {}
    for r in resultados:
        for clave, valor in indicadores_replica(r, catalogos).items():
            series.setdefault((r.realizacion.escenario.id, *clave), []).append(valor)
    return tuple(ResumenIndicador(*clave, estimar(valores, confianza))
                 for clave, valores in sorted(series.items()))
