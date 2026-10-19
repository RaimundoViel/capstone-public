"""Carga datos reales y adapta las replicas del simulador a la heuristica."""
from collections import Counter
import csv
import json
from math import fsum
from pathlib import Path

import numpy as np

from Simulador.etapa_1 import ConfiguracionInicial, cargar_catalogos
from Simulador.etapa_4 import CalculadorViajes
from Simulador.etapa_9.kpis import calcular_kpis
from Simulador.etapa_10.experimento import ejecutar_replica, preparar_replica
from Simulador.etapa_10.modelos import EscenarioSimulacion
from Simulador.etapa_10.motor import crear_motor


ESCENARIO_HEURISTICA = EscenarioSimulacion("busqueda_heuristica")
VERSION_MOTOR = "Simulador.etapa_10.motor:crear_motor"


def _leer_csv(ruta):
    with Path(ruta).open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def cargar_datos(raiz=None):
    """Lee la carpeta de parametros y prepara los datos del proxy de busqueda."""
    raiz = Path(raiz) if raiz else Path(__file__).resolve().parents[1]
    carpeta = raiz / "Simulador" / "parametros"
    catalogos = cargar_catalogos(raiz)
    constantes = json.loads((carpeta / "constantes.json").read_text(encoding="utf-8"))
    probabilidades_zona = {
        f["zona_id"]: float(f["probabilidad"])
        for f in _leer_csv(carpeta / "probabilidades_zona.csv")
    }
    filas_prioridad = _leer_csv(carpeta / "prioridades.csv")
    suma_prioridades = fsum(float(f["probabilidad"]) for f in filas_prioridad)
    prioridades = sorted(filas_prioridad, key=lambda f: int(f["rango"]))
    probabilidad_prioridad = np.array([
        float(f["probabilidad"]) / suma_prioridades for f in prioridades
    ])
    lam_diaria = fsum(float(f["lambda_poisson"])
                      for f in _leer_csv(carpeta / "bloques.csv"))
    ids_bases = sorted(catalogos.bases)
    ids_zonas = sorted(catalogos.zonas)
    lam = lam_diaria * np.array([
        probabilidades_zona[zona] for zona in ids_zonas
    ])[:, None] * probabilidad_prioridad[None, :]

    # El proxy resume prioridad y bloque en un ETA representativo P3/bloque 3.
    calculador = CalculadorViajes(catalogos, raiz)
    prioridad_representativa = catalogos.prioridades[
        prioridades[2]["prioridad_id"]
    ]
    tiempo = np.empty((len(ids_zonas), len(ids_bases)))
    for i, zona_id in enumerate(ids_zonas):
        origen = catalogos.zonas[zona_id].centroide
        for j, base_id in enumerate(ids_bases):
            destino = catalogos.bases[base_id].posicion
            tiempo[i, j] = calculador.calcular(
                origen, destino, 3, prioridad_representativa.multiplicador_velocidad
            ).duracion_min

    return {
        "raiz": raiz,
        "catalogos": catalogos,
        "ids_bases": ids_bases,
        "ids_zonas": ids_zonas,
        "cap_base": np.array([catalogos.bases[b].capacidad for b in ids_bases]),
        "tiempo": tiempo,
        "lam": lam,
        "umbral": np.array([
            catalogos.prioridades[f["prioridad_id"]].objetivo_min for f in prioridades
        ]),
        "prioridad_id_por_rango": [f["prioridad_id"] for f in prioridades],
        "flota": constantes["flota_total"],
        "minimo_base": constantes["minimo_ambulancias_base_activa"],
        "t_servicio": 75.0,
        "realizaciones": {},
        "cache_simulador": {},
    }


def kpis_a_estandar(kpis, registros, catalogos):
    """Adapta los seis KPI oficiales al diccionario consumido por la heuristica."""
    registros = tuple(registros)
    if not registros:
        raise ValueError("La replica no contiene llamados; no se puede evaluar la solucion.")

    salida = {"n_llamados": len(registros)}
    for prioridad_id, prioridad in catalogos.prioridades.items():
        sufijo = f"P{prioridad.rango}"
        salida[f"t_prom_{sufijo}"] = kpis.tiempo_promedio_respuesta_por_prioridad.get(prioridad_id)
        salida[f"pct_dentro_{sufijo}"] = kpis.cumplimiento_objetivo_por_prioridad_pct.get(prioridad_id)
        percentiles = kpis.percentiles_respuesta_por_prioridad.get(prioridad_id, {})
        for percentil in (90, 95, 99):
            salida[f"p{percentil}_{sufijo}"] = percentiles.get(f"p{percentil}")

    cuenta_zona = Counter(r.zona_id for r in registros)
    cantidad_objetivo = len(registros) * 0.10
    cantidad_incluida = 0.0
    suma_ponderada = 0.0
    for zona_id, media in sorted(
        kpis.tiempo_promedio_respuesta_por_zona.items(),
        key=lambda elemento: (-elemento[1], elemento[0]),
    ):
        peso = min(cuenta_zona[zona_id], cantidad_objetivo - cantidad_incluida)
        if peso <= 0:
            break
        suma_ponderada += media * peso
        cantidad_incluida += peso
    salida["t_prom_peor10_zonas"] = suma_ponderada / cantidad_objetivo
    salida["pct_espera"] = kpis.porcentaje_llamadas_con_espera_recurso
    salida["pct_zonas_cubiertas"] = kpis.porcentaje_zonas_cobertura_adecuada
    return salida


def evaluar_en_simulador(solucion, semilla, datos):
    """Ejecuta una configuracion en una replica real y reproducible."""
    if type(semilla) is not int or semilla < 1:
        raise ValueError("La semilla/numero de replica debe ser un entero positivo.")
    raiz = Path(datos["raiz"])
    catalogos = datos["catalogos"]
    configuracion = ConfiguracionInicial(dict(solucion))
    configuracion.validar(catalogos)

    realizaciones = datos["realizaciones"]
    if semilla not in realizaciones:
        realizaciones[semilla] = preparar_replica(
            raiz, ESCENARIO_HEURISTICA, semilla,
            semilla_maestra=datos.get("semilla_maestra", 42),
        )
    resultado = ejecutar_replica(
        raiz, realizaciones[semilla], configuracion, crear_motor,
        version_motor=VERSION_MOTOR,
    )
    kpis = calcular_kpis(list(resultado.registros), catalogos)
    if datos.get("capturar_detalle_validacion", False):
        from Simulador.etapa_10.estadisticas import indicadores_replica
        clave = (tuple(sorted(solucion.items())), semilla)
        datos.setdefault("detalle_validacion", {})[clave] = indicadores_replica(resultado, catalogos)
    return kpis_a_estandar(kpis, resultado.registros, catalogos)
