"""Salidas por corrida; no altera decisiones de búsqueda ni la función de nota."""
import csv
import json
import platform
import time
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from Heuristica.conector_simulador import ESCENARIO_HEURISTICA, VERSION_MOTOR
from Simulador.etapa_10.estadisticas import estimar
from Simulador.etapa_10.experimento import ARCHIVOS_PARAMETROS, huellas_codigo


def escribir_json(ruta, contenido):
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False, indent=2,
                                    allow_nan=False), encoding="utf-8")
    temporal.replace(ruta)


def escribir_csv(ruta, columnas, filas):
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(columnas)
        escritor.writerows(filas)


def iniciar_corrida(h, datos):
    ahora = datetime.now(timezone.utc)
    ahora_local = ahora.astimezone(ZoneInfo("America/Santiago"))
    identificador = ahora_local.strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:8]
    raiz = Path(datos["raiz"])
    carpeta = raiz / "Resultados" / f"solucion_{identificador}"
    carpeta.mkdir(parents=True, exist_ok=False)
    entradas = {}
    for nombre in ARCHIVOS_PARAMETROS:
        contenido = (raiz / "Simulador" / "parametros" / nombre).read_bytes()
        entradas[nombre] = {"sha256": sha256(contenido).hexdigest(),
                            "contenido": contenido.decode("utf-8-sig")}
    meta = {
        "formato": 1, "id_corrida": identificador, "estado": "en_curso",
        "inicio_utc": ahora.isoformat(), "PARAMS": dict(h.PARAMS),
        "inicio_local": ahora_local.isoformat(), "zona_horaria": "America/Santiago",
        "CONFIG_NOTA": list(h.CONFIG_NOTA), "MAPEO_KPI": dict(h.MAPEO_KPI),
        "semilla_maestra": datos.get("semilla_maestra", 42),
        "escenario": asdict(ESCENARIO_HEURISTICA), "version_motor": VERSION_MOTOR,
        "python": platform.python_version(),
        "dependencias": {n: version(n) for n in ("numpy", "scipy")},
        "parametros_simulador": entradas,
        "huellas_codigo_simulador": dict(huellas_codigo()),
        "huellas_codigo_heuristica": {
            p.name: sha256(p.read_bytes()).hexdigest()
            for p in sorted((raiz / "Heuristica").glob("*.py"))},
        "proxy": {k: datos[k] for k in ("K", "q", "t_espera", "t_servicio")},
        "metodo_ic_resumen": "normal, factor 1.96 (sin cambios)",
        "metodo_ic_detalle": "t de Student, confianza 0.95, omite grupos sin datos",
        "criterio_ganadora": "Menor nota de validacion entre candidatas elite del SA",
        "duraciones_segundos": {},
    }
    escribir_json(carpeta / "configuracion_simulador.json", meta)
    return carpeta, meta


def exportar_detalle(carpeta, sufijo, identificador, solucion, datos, semillas):
    clave = tuple(sorted(solucion.items()))
    replicas = [datos["detalle_validacion"][clave, s] for s in semillas]
    columnas = ["id_configuracion", "escenario", "ambito", "indicador", "grupo", "unidad"]
    escenario = ESCENARIO_HEURISTICA.id
    filas = []
    detalle = []
    for indicador in sorted(replicas[0]):
        valores = [rep[indicador] for rep in replicas]
        estimacion = asdict(estimar(valores))
        filas.append([identificador, escenario, *indicador, *estimacion.values()])
        for semilla, valor in zip(semillas, valores):
            detalle.append([identificador, escenario, *indicador, semilla, valor])
    escribir_csv(carpeta / f"kpis_{sufijo}.csv", columnas + list(estimacion), filas)
    escribir_csv(carpeta / f"kpis_por_replica_{sufijo}.csv",
                 columnas + ["replica", "valor"], detalle)


def exportar_validacion(h, datos, carpeta, meta, caso_base, greedy, elite):
    # Una configuración puede ser simultáneamente referencia y candidata del SA.
    candidatos = []
    indices = {}
    origenes = []
    for origen, amb in [("caso_base", caso_base), ("greedy", greedy)] + [("SA", a) for a in elite]:
        clave = tuple(int(n) for n in amb)
        if clave not in indices:
            indices[clave] = len(candidatos)
            candidatos.append(amb)
            origenes.append([])
        roles = origenes[indices[clave]]
        if origen not in roles:
            roles.append(origen)
    etiquetas = [(f"config_{i + 1:03d}", "|".join(roles)) for i, roles in enumerate(origenes)]
    datos["capturar_detalle_validacion"] = True
    try:
        filas = h.validar(candidatos, datos, carpeta / "validacion_simulador.csv", etiquetas=etiquetas)
    finally:
        datos["capturar_detalle_validacion"] = False
    ganadora = next(f for f in filas if "SA" in origenes[f["id"]])
    id_mejor = etiquetas[ganadora["id"]][0]
    print(f"\nMejor candidata del SA según validación: {id_mejor} "
          f"({etiquetas[ganadora['id']][1]}) | nota = {ganadora['nota']:.3f}", flush=True)
    meta["mejor_validacion_sa"] = id_mejor
    meta["configuraciones"] = [
        {"id_configuracion": etiquetas[f["id"]][0], "origen": origenes[f["id"]],
         "ranking": r, "nota_validacion": f["nota"],
         "distribucion": h.vector_a_solucion(f["amb"], datos)}
        for r, f in enumerate(filas, 1)]
    escribir_csv(carpeta / "distribucion_mejor_solucion.csv",
                 ["id_configuracion", "base", "ambulancias", "activa"],
                 ([id_mejor, b, int(n), int(n > 0)] for b, n in zip(datos["ids_bases"], ganadora["amb"])))
    for sufijo, amb in (("mejor_solucion", ganadora["amb"]), ("caso_base", caso_base), ("greedy", greedy)):
        identificador = etiquetas[indices[tuple(int(n) for n in amb)]][0]
        exportar_detalle(carpeta, sufijo, identificador, h.vector_a_solucion(amb, datos),
                         datos, h.PARAMS["semillas_validacion"])
    desglose = []
    for f in filas:
        for termino in h.CONFIG_NOTA:
            tipo, kpi, peso = termino[:3]
            valor = f["prom"][kpi]
            penalizacion = max(0.0, termino[3] - valor) if tipo == "meta" else None
            aporte = peso * (valor if tipo == "min" else penalizacion)
            desglose.append([etiquetas[f["id"]][0], tipo, kpi, valor, peso,
                             termino[3] if tipo == "meta" else None, penalizacion, aporte])
    escribir_csv(carpeta / "desglose_nota.csv",
                 ["id_configuracion", "tipo", "kpi", "valor_promedio", "peso", "meta",
                  "deficit_meta", "aporte_nota"], desglose)
    datos.pop("detalle_validacion", None)
    return ganadora


def ejecutar_con_salidas(h):
    inicio = time.perf_counter()
    datos = h.preparar(h.cargar_datos())
    carpeta, meta = iniciar_corrida(h, datos)
    print(f"Resultados de esta corrida: {carpeta}", flush=True)
    try:
        caso_base = h.cargar_caso_base(datos)
        meta["caso_base"] = h.vector_a_solucion(caso_base, datos)
        escribir_json(carpeta / "configuracion_simulador.json", meta)
        t0 = time.perf_counter()
        greedy = h.construir(datos)
        meta["duraciones_segundos"]["greedy"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        mejor, elite = h.simulated_annealing(greedy, datos)
        meta["duraciones_segundos"]["sa"] = time.perf_counter() - t0
        meta["mejor_busqueda"] = {"distribucion": h.vector_a_solucion(mejor, datos),
                                  "nota": h.evaluar(mejor, datos)}
        meta["nota_greedy_busqueda"] = h.evaluar(greedy, datos)
        escribir_json(carpeta / "configuracion_simulador.json", meta)
        t0 = time.perf_counter()
        exportar_validacion(h, datos, carpeta, meta, caso_base, greedy, elite)
        meta["duraciones_segundos"]["validacion_y_exportacion"] = time.perf_counter() - t0
        meta["estado"] = "completada"
    except BaseException as exc:
        meta["estado"] = "interrumpida" if isinstance(exc, KeyboardInterrupt) else "fallida"
        meta["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        meta["fin_utc"] = datetime.now(timezone.utc).isoformat()
        meta["duraciones_segundos"]["total"] = time.perf_counter() - inicio
        escribir_json(carpeta / "configuracion_simulador.json", meta)
    return carpeta
