"""Lectura explicita de los parametros consolidados. No estima distribuciones."""
import csv
from collections import Counter
from hashlib import sha256
from math import isfinite
from pathlib import Path

from .configuracion import ConfiguracionInicial
from .modelos import (
    Base, Bloque, Catalogos, Hospital, Macrozona, Prioridad, Punto,
    Rectangulo, Zona,
)


ARCHIVOS_CATALOGOS = (
    "bases.csv",
    "hospitales.csv",
    "zonas.csv",
    "macrozonas.csv",
    "prioridades.csv",
    "bloques.csv",
    "congestion.csv",
)


def _leer_csv(carpeta: Path, nombre: str, columnas: tuple[str, ...]) -> list[dict[str, str]]:
    ruta = carpeta / nombre
    with ruta.open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != list(columnas):
            raise ValueError(f"{nombre}: columnas inesperadas.")
        datos = list(lector)
    if any(any(f.get(c) in (None, "") for c in columnas) for f in datos):
        raise ValueError(f"{nombre}: hay campos requeridos vacios.")
    return datos


def _indice(elementos):
    resultado = {}
    for elemento in elementos:
        if elemento.id in resultado:
            raise ValueError(f"Identificador duplicado: {elemento.id}.")
        resultado[elemento.id] = elemento
    return resultado


def _numero(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Se esperaba un numero, recibido {valor!r}.") from exc
    if not isfinite(numero):
        raise ValueError(f"Se esperaba un numero finito, recibido {valor!r}.")
    return numero


def _entero(valor):
    if isinstance(valor, bool):
        raise ValueError(f"Se esperaba un entero, recibido {valor!r}.")
    if isinstance(valor, str):
        if not valor.strip().isdigit():
            raise ValueError(f"Se esperaba un entero, recibido {valor!r}.")
        return int(valor)
    if not isinstance(valor, (int, float)) or not isfinite(valor) or int(valor) != valor:
        raise ValueError(f"Se esperaba un entero, recibido {valor!r}.")
    return int(valor)


def cargar_catalogos(raiz: str | Path) -> Catalogos:
    parametros = Path(raiz) / "Simulador" / "parametros"
    bases = _indice(
        Base(f["base_id"], Punto(_numero(f["x_km"]), _numero(f["y_km"])),
             f["macrozona_id"], _entero(f["capacidad_inicial"]))
        for f in _leer_csv(parametros, "bases.csv", (
            "base_id", "x_km", "y_km", "macrozona_id", "capacidad_inicial"))
    )
    hospitales = _indice(
        Hospital(f["hospital_id"], Punto(_numero(f["x_km"]), _numero(f["y_km"])),
                 f["macrozona_id"])
        for f in _leer_csv(parametros, "hospitales.csv", (
            "hospital_id", "x_km", "y_km", "macrozona_id"))
    )
    zonas = _indice(
        Zona(f["zona_id"], _entero(f["fila"]), _entero(f["columna"]),
             Rectangulo(_numero(f["x_min_km"]), _numero(f["x_max_km"]),
                        _numero(f["y_min_km"]), _numero(f["y_max_km"])),
             Punto(_numero(f["centroide_x_km"]), _numero(f["centroide_y_km"])),
             f["macrozona_id"])
        for f in _leer_csv(parametros, "zonas.csv", (
            "zona_id", "fila", "columna", "x_min_km", "x_max_km",
            "y_min_km", "y_max_km", "centroide_x_km", "centroide_y_km",
            "macrozona_id"))
    )
    macrozonas = _indice(
        Macrozona(f["macrozona_id"], _entero(f["fila"]), _entero(f["columna"]),
                  Rectangulo(_numero(f["x_min_km"]), _numero(f["x_max_km"]),
                             _numero(f["y_min_km"]), _numero(f["y_max_km"])))
        for f in _leer_csv(parametros, "macrozonas.csv", (
            "macrozona_id", "fila", "columna", "x_min_km", "x_max_km",
            "y_min_km", "y_max_km"))
    )
    prioridades = _indice(
        Prioridad(f["prioridad_id"], _entero(f["rango"]),
                  _numero(f["objetivo_respuesta_min"]), f["tipo_destino"],
                  _numero(f["multiplicador_velocidad"]))
        for f in _leer_csv(parametros, "prioridades.csv", (
            "prioridad_id", "rango", "objetivo_respuesta_min", "tipo_destino",
            "multiplicador_velocidad", "probabilidad"))
    )
    bloques = _indice(
        Bloque(_entero(f["bloque_id"]), _numero(f["inicio_min"]), _numero(f["fin_min"]))
        for f in _leer_csv(parametros, "bloques.csv", (
            "bloque_id", "inicio_min", "fin_min", "lambda_poisson"))
    )
    congestion = {}
    for f in _leer_csv(parametros, "congestion.csv", ("zona_id", "bloque_id", "factor")):
        clave = (f["zona_id"], _entero(f["bloque_id"]))
        factor = _numero(f["factor"])
        if clave in congestion:
            raise ValueError(f"Congestion duplicada: {clave}.")
        if factor <= 0:
            raise ValueError(f"Congestion no positiva: {clave}.")
        congestion[clave] = factor
    huellas = {nombre: sha256((parametros / nombre).read_bytes()).hexdigest()
               for nombre in ARCHIVOS_CATALOGOS}
    catalogos = Catalogos(bases, hospitales, zonas, macrozonas,
                          prioridades, bloques, congestion, huellas)
    _validar_catalogos(catalogos)
    return catalogos


def _validar_catalogos(c):
    for nombre, esperado in (
        ("bases", 65), ("hospitales", 10), ("zonas", 81),
        ("macrozonas", 9), ("prioridades", 5), ("bloques", 5)
    ):
        if len(getattr(c, nombre)) != esperado:
            raise ValueError(f"El catalogo {nombre} debe contener {esperado} registros.")
    for entidad in (*c.bases.values(), *c.hospitales.values(), *c.zonas.values()):
        if entidad.macrozona not in c.macrozonas:
            raise ValueError(f"{entidad.id}: macrozona inexistente.")
    if any(b.capacidad < 4 for b in c.bases.values()):
        raise ValueError("Capacidad incompatible con el minimo de 4 por base activa.")
    esperado = [(1, 0, 180), (2, 180, 420), (3, 420, 660),
                (4, 660, 900), (5, 900, 1080)]
    if sorted((b.id, b.inicio_min, b.fin_min) for b in c.bloques.values()) != esperado:
        raise ValueError("Los bloques difieren de la jornada acordada en etapa 0.")
    if {p.rango for p in c.prioridades.values()} != set(range(1, 6)):
        raise ValueError("Los rangos deben ser P1 a P5, sin duplicados.")
    for p in c.prioridades.values():
        if (p.destino != ("hospital" if p.rango <= 3 else "base")
                or not isfinite(p.objetivo_min) or p.objetivo_min <= 0
                or not isfinite(p.multiplicador_velocidad)
                or p.multiplicador_velocidad <= 0):
            raise ValueError(f"Prioridad incompatible con etapa 0: {p.id}.")
    if set(c.congestion) != {(z, b) for z in c.zonas for b in c.bloques}:
        raise ValueError("La congestion debe cubrir exactamente las 81 zonas x 5 bloques.")


def cargar_configuracion_observada(raiz: str | Path, catalogos: Catalogos) -> ConfiguracionInicial:
    parametros = Path(raiz) / "Simulador" / "parametros"
    filas = _leer_csv(parametros, "configuracion_observada.csv", ("base_id", "ambulancias"))
    bases = [f["base_id"] for f in filas]
    if len(bases) != len(set(bases)):
        raise ValueError("Bases repetidas en la configuracion observada.")
    configuracion = ConfiguracionInicial(Counter({
        f["base_id"]: _entero(f["ambulancias"])
        for f in filas
    }))
    configuracion.validar(catalogos)
    return configuracion
