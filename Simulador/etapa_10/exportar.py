"""Archivos de realizaciones, resultados y trazabilidad del experimento."""
import csv
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform

from Simulador.etapa_1.modelos import Llamado, Punto
from .aleatoriedad import VERSION_SEMILLAS, derivar_semilla
from .estadisticas import indicadores_replica
from .experimento import huellas_codigo, huellas_parametros
from .modelos import EscenarioSimulacion, RealizacionReplica


def _json(path, datos):
    Path(path).write_text(json.dumps(datos, ensure_ascii=True, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def guardar_realizacion(realizacion: RealizacionReplica, ruta):
    _json(ruta, {"formato": 1, "version_semillas": VERSION_SEMILLAS,
                "python": platform.python_version(), "realizacion": asdict(realizacion)})


def cargar_realizacion(ruta) -> RealizacionReplica:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if datos["formato"] != 1 or datos["version_semillas"] != VERSION_SEMILLAS:
        raise ValueError("Formato o version de semillas incompatible.")
    if datos["python"] != platform.python_version():
        raise ValueError("Usar la misma version de Python para reproducir esta realizacion.")
    r = datos["realizacion"]
    escenario = EscenarioSimulacion(**r["escenario"])
    numero, maestra = r["numero"], r["semilla_maestra"]
    if type(numero) is not int or numero < 1 or type(maestra) is not int or maestra < 0:
        raise ValueError("Numero de replica o semilla maestra invalidos.")
    for tipo in ("demanda", "duraciones"):
        if r[f"semilla_{tipo}"] != derivar_semilla(maestra, escenario.id, numero, tipo):
            raise ValueError("Las semillas no coinciden con la identificacion de la replica.")
    llamados = tuple(Llamado(**{**l, "posicion": Punto(**l["posicion"])}) for l in r["llamados"])
    return RealizacionReplica(escenario, numero, maestra, r["semilla_demanda"],
                              r["semilla_duraciones"], tuple(tuple(p) for p in r["huellas_parametros"]),
                              llamados)


def _csv(ruta, cabecera, filas):
    with Path(ruta).open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.writer(archivo, delimiter=";")
        writer.writerow(cabecera)
        for fila in filas:
            writer.writerow([str(v).replace(".", ",") if isinstance(v, float) else v for v in fila])


def exportar_experimento(raiz, carpeta, plan, configuracion, realizaciones,
                        *, resultados=None, resumen=None):
    """Cada salida debe ser una carpeta nueva para evitar mezclar ejecuciones."""
    realizaciones = tuple(realizaciones)
    esperadas = {(e.id, n) for e in plan.escenarios for n in range(1, plan.replicas + 1)}
    claves = [(r.escenario.id, r.numero) for r in realizaciones]
    if set(claves) != esperadas or len(claves) != len(esperadas):
        raise ValueError("Las realizaciones no corresponden al plan completo.")
    definiciones = {e.id: e for e in plan.escenarios}
    if any(r.escenario != definiciones[r.escenario.id] or r.semilla_maestra != plan.semilla_maestra
           for r in realizaciones):
        raise ValueError("Los escenarios o semillas difieren del plan.")
    huellas = huellas_parametros(raiz)
    if any(r.huellas_parametros != huellas for r in realizaciones):
        raise ValueError("No exportar un experimento con parametros modificados.")
    resultados = tuple(resultados) if resultados is not None else None
    if resultados is not None:
        por_clave = {(r.realizacion.escenario.id, r.realizacion.numero): r for r in resultados}
        if len(por_clave) != len(resultados) or set(por_clave) != esperadas:
            raise ValueError("Faltan resultados o hay replicas repetidas.")
        if resumen is None:
            raise ValueError("Se requiere el resumen estadistico de los resultados.")
        config = tuple(sorted(configuracion.ambulancias_por_base.items()))
        if any(por_clave[r.escenario.id, r.numero].realizacion != r
               or por_clave[r.escenario.id, r.numero].configuracion != config for r in realizaciones):
            raise ValueError("Los resultados no corresponden a estas entradas.")
    elif resumen is not None:
        raise ValueError("No exportar indicadores sin replicas ejecutadas.")
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=False)
    try:
        scipy_version = version("scipy")
    except PackageNotFoundError:
        scipy_version = None
    manifiesto = {
        "formato": 1,
        "estado": "ejecutado" if resultados is not None else "preparado_sin_motor",
        "plan": asdict(plan),
        "configuracion": dict(sorted(configuracion.ambulancias_por_base.items())),
        "python": platform.python_version(),
        "scipy": scipy_version,
        "version_semillas": VERSION_SEMILLAS,
        "huellas_parametros": dict(huellas),
        "huellas_codigo": dict(huellas_codigo()),
        "replicas": [],
    }
    parametros = carpeta / "entradas" / "Simulador" / "parametros"
    parametros.mkdir(parents=True)
    for nombre, huella in huellas:
        contenido = (Path(raiz) / "Simulador" / "parametros" / nombre).read_bytes()
        if sha256(contenido).hexdigest() != huella:
            raise ValueError("Un parametro cambio al guardar su copia.")
        (parametros / nombre).write_bytes(contenido)
    _json(carpeta / "configuracion.json", manifiesto["configuracion"])
    conteos, indicadores = [], []
    from Simulador.etapa_1 import cargar_catalogos
    catalogos = cargar_catalogos(raiz)
    configuracion.validar(catalogos)
    for indice, r in enumerate(realizaciones, 1):
        archivo = f"replica_{indice:04d}.json"
        guardar_realizacion(r, carpeta / archivo)
        entrada = {"escenario": r.escenario.id, "replica": r.numero, "archivo": archivo,
                   "sha256": sha256((carpeta / archivo).read_bytes()).hexdigest()}
        manifiesto["replicas"].append(entrada)
        for b in sorted(catalogos.bloques):
            conteos.append([r.escenario.id, r.numero, b,
                            sum(l.bloque_recepcion == b for l in r.llamados)])
        if resultados is not None:
            resultado = por_clave[r.escenario.id, r.numero]
            ruta_resultado = f"resultado_{indice:04d}.json"
            _json(carpeta / ruta_resultado, {
                "escenario": r.escenario.id, "replica": r.numero,
                "configuracion": dict(resultado.configuracion), "fin_min": resultado.fin_min,
                "version_motor": resultado.version_motor,
                "huellas_codigo": dict(resultado.huellas_codigo),
                "registros": [asdict(registro) for registro in resultado.registros],
            })
            entrada["resultado"] = ruta_resultado
            entrada["sha256_resultado"] = sha256((carpeta / ruta_resultado).read_bytes()).hexdigest()
            for clave, valor in indicadores_replica(resultado, catalogos).items():
                indicadores.append([r.escenario.id, r.numero, *clave, valor])
    _csv(carpeta / "demanda_por_replica.csv", ["escenario", "replica", "bloque", "llamados"], conteos)
    if resultados is not None:
        _csv(carpeta / "kpis_por_replica.csv",
             ["escenario", "replica", "ambito", "indicador", "grupo", "unidad", "valor"], indicadores)
        _csv(carpeta / "resumen_entre_replicas.csv",
             ["escenario", "ambito", "indicador", "grupo", "unidad",
              "replicas_totales", "replicas_con_datos", "media", "desviacion", "error_estandar",
              "margen", "ic_inferior", "ic_superior", "confianza"],
             [[s.escenario_id, s.ambito, s.indicador, s.grupo, s.unidad,
               *asdict(s.estimacion).values()] for s in resumen])
    # Se escribe al final: su presencia identifica una exportacion terminada.
    _json(carpeta / "manifiesto.json", manifiesto)
