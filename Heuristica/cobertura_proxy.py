"""Estimación experimental del KPI 6 sin ejecutar jornadas del simulador.

Integra prioridades, bloques y posiciones dentro de las zonas. La disponibilidad
independiente sigue siendo una aproximación; no representa colas ni retornos.
"""
import csv
import math

import numpy as np

from Simulador.etapa_1.modelos import Punto
from Simulador.etapa_4 import CalculadorViajes


def tabla_cobertura(lam, pasos=1000):
    """P(N>0 y al menos 80% a tiempo), N Poisson y éxitos binomiales.

    La tabla incluye la probabilidad de no observar prioridades más urgentes.
    Se trunca la cola Poisson con un margen amplio y se interpola sobre p.
    """
    lam = np.asarray(lam, dtype=float)
    max_lam = float(lam.max())
    n_max = math.ceil(max_lam + 12 * math.sqrt(max_lam) + 30)
    grid = np.linspace(0.0, 1.0, pasos + 1)
    tails = np.zeros((n_max, pasos + 1))
    for n in range(1, n_max + 1):
        # A lo sumo floor(n/5) incumplimientos equivale a >=80% de éxitos.
        for fallos in range(n // 5 + 1):
            tails[n - 1] += (float(math.comb(n, fallos))
                            * grid ** (n - fallos) * (1 - grid) ** fallos)
    poisson = np.exp(-lam)
    pesos = []
    for n in range(1, n_max + 1):
        poisson = poisson * lam / n
        pesos.append(poisson)
    ninguna_mas_urgente = np.exp(-(np.cumsum(lam, axis=1) - lam))
    tabla = np.stack(pesos, axis=-1) @ tails
    return tabla * ninguna_mas_urgente[..., None]


def preparar_cobertura(D):
    """Precalcula qué bases alcanzan cada punto, prioridad y bloque a tiempo."""
    catalogos = D['catalogos']
    calculador = CalculadorViajes(catalogos, D['raiz'])
    prioridades = [catalogos.prioridades[p] for p in D['prioridad_id_por_rango']]
    with (D['raiz'] / 'Simulador/parametros/bloques.csv').open(encoding='utf-8') as f:
        bloques = sorted(csv.DictReader(f), key=lambda row: int(row['bloque_id']))
    lambdas = np.array([float(b['lambda_poisson']) for b in bloques])
    duraciones = np.array([float(b['fin_min']) - float(b['inicio_min']) for b in bloques])
    # La cobertura puede calibrarse con el tiempo hasta quedar redespachable;
    # los demás KPI del proxy conservan su supuesto original de ciclo.
    servicio = D.get('t_servicio_cobertura', D['t_servicio'])
    q = np.clip(lambdas / duraciones * servicio / D['flota'], 0, .95)
    nodos, pesos = np.polynomial.legendre.leggauss(3)
    nodos = (nodos + 1) / 2
    pesos = pesos / 2
    puntos = [(x, y) for x in nodos for y in nodos]
    pesos_puntos = np.outer(pesos, pesos).ravel()
    multiplicadores = np.array([p.multiplicador_velocidad for p in prioridades])
    objetivos = np.array([p.objetivo_min for p in prioridades])
    alcanzable = np.zeros((len(D['ids_zonas']), len(prioridades), len(bloques),
                           len(puntos), len(D['ids_bases'])), dtype=np.uint8)
    for zi, zona_id in enumerate(D['ids_zonas']):
        limites = catalogos.zonas[zona_id].limites
        for si, (x, y) in enumerate(puntos):
            destino = Punto(limites.x_min + x * (limites.x_max - limites.x_min),
                            limites.y_min + y * (limites.y_max - limites.y_min))
            for bi, base_id in enumerate(D['ids_bases']):
                origen = catalogos.bases[base_id].posicion
                tiempos = np.full((len(prioridades), len(bloques)), np.inf)
                # La geometría de las dos rutas no cambia con prioridad ni bloque.
                for sentido in ('HV', 'VH'):
                    ruta = calculador.calcular_ruta(origen, destino, int(bloques[0]['bloque_id']),
                                                   1.0, sentido)
                    if ruta.distancia_km == 0:
                        tiempos[:] = 0
                        continue
                    congestion = np.array([
                        math.fsum(s.distancia_km * catalogos.congestion[
                            s.zona_id, int(b['bloque_id'])] for s in ruta.segmentos)
                        / ruta.distancia_km for b in bloques
                    ])
                    velocidad = np.clip(calculador.velocidad_base * multiplicadores[:, None]
                                        / congestion[None, :], calculador.velocidad_minima,
                                        calculador.velocidad_maxima)
                    tiempos = np.minimum(tiempos, 60 * ruta.distancia_km / velocidad)
                alcanzable[zi, :, :, si, bi] = tiempos <= objetivos[:, None]
    return dict(alcanzable=alcanzable, q=q, pesos_bloques=lambdas / lambdas.sum(),
                pesos_puntos=pesos_puntos, tabla=tabla_cobertura(D['lam']),
                zonas_esperadas=float((-np.expm1(-D['lam'].sum(axis=1))).sum()))


def estimar_cobertura(amb, D):
    """Porcentaje esperado de zonas cubiertas entre zonas con demanda.

    Cuenta toda la flota alcanzable (sin el corte artificial a ocho unidades).
    Aproxima el cociente aleatorio del KPI por un cociente de esperanzas.
    """
    if 'proxy_cobertura' not in D:
        D['proxy_cobertura'] = preparar_cobertura(D)
    C = D['proxy_cobertura']
    cantidad = np.einsum('zphsb,b->zphs', C['alcanzable'], amb, optimize=False)
    a_tiempo = 1 - C['q'][None, None, :, None] ** cantidad
    p = np.einsum('zphs,h,s->zp', a_tiempo, C['pesos_bloques'], C['pesos_puntos'])
    tabla = C['tabla']
    posicion = np.clip(p, 0, 1) * (tabla.shape[-1] - 1)
    inferior = np.minimum(posicion.astype(int), tabla.shape[-1] - 2)
    fraccion = posicion - inferior
    bajo = np.take_along_axis(tabla, inferior[..., None], axis=2)[..., 0]
    alto = np.take_along_axis(tabla, (inferior + 1)[..., None], axis=2)[..., 0]
    cubiertas = np.sum(bajo + fraccion * (alto - bajo))
    return float(100 * cubiertas / C['zonas_esperadas']) if C['zonas_esperadas'] else 0.0
