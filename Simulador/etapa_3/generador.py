"""Generadores independientes de tiempos de escena y entrega."""
import csv
import random
from math import isfinite, log, sqrt
from pathlib import Path

from Simulador.etapa_1.modelos import Escenario

from .modelos import DuracionGenerada, ModeloDuracion


FAMILIAS = {"norm", "gamma", "lognorm", "rayleigh", "chi2"}
FORMAS = {
    "norm": (),
    "gamma": ("a",),
    "lognorm": ("s",),
    "rayleigh": (),
    "chi2": ("df",),
}


def _leer_csv(carpeta: Path, nombre: str) -> list[dict[str, str]]:
    with (carpeta / nombre).open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _float(valor: str, campo: str, *, requerido: bool = True) -> float | None:
    if valor == "":
        if requerido:
            raise ValueError(f"Campo requerido vacio: {campo}.")
        return None
    numero = float(valor)
    if not isfinite(numero):
        raise ValueError(f"Valor no finito en {campo}: {valor!r}.")
    return numero


def _modelo_desde_fila(tipo: str, fila: dict[str, str]) -> ModeloDuracion:
    familia = fila["familia"]
    if familia not in FAMILIAS:
        raise ValueError(f"Familia no soportada: {familia}.")
    parametros = {
        "loc": _float(fila["loc"], "loc"),
        "scale": _float(fila["scale"], "scale"),
    }
    if parametros["scale"] <= 0:
        raise ValueError("El parametro scale debe ser positivo.")
    for forma in ("a", "s", "df"):
        valor = _float(fila[forma], forma, requerido=False)
        if valor is not None:
            parametros[forma] = valor
    esperados = set(FORMAS[familia])
    presentes = {k for k in ("a", "s", "df") if k in parametros}
    if presentes != esperados:
        raise ValueError(f"Parametros de forma incompatibles con {familia}: {presentes}.")
    if any(parametros[k] <= 0 for k in esperados):
        raise ValueError("Los parametros de forma deben ser positivos.")
    return ModeloDuracion(
        tipo=tipo,
        prioridad_id=fila["prioridad_id"],
        macrozona_destino_id=fila.get("macrozona_destino_id") or None,
        familia=familia,
        parametros=parametros,
        n_ajuste=int(fila["n_ajuste"]),
    )


class GeneradorDuraciones:
    def __init__(self, raiz: str | Path, escenario: Escenario, max_intentos: int = 10000):
        if max_intentos <= 0:
            raise ValueError("max_intentos debe ser positivo.")
        self.raiz = Path(raiz)
        self.escenario = escenario
        self.rng = random.Random(escenario.semilla)
        self.max_intentos = max_intentos
        parametros = self.raiz / "Simulador" / "parametros"
        self.modelos_escena = self._cargar_escena(parametros)
        self.modelos_entrega = self._cargar_entrega(parametros)

    def _cargar_escena(self, parametros: Path) -> dict[str, ModeloDuracion]:
        modelos = {}
        for fila in _leer_csv(parametros, "tiempo_escena.csv"):
            modelo = _modelo_desde_fila("escena", fila)
            if modelo.prioridad_id in modelos:
                raise ValueError(f"Modelo de escena duplicado: {modelo.prioridad_id}.")
            modelos[modelo.prioridad_id] = modelo
        if len(modelos) != 5:
            raise ValueError("Se esperaban 5 modelos de tiempo en escena.")
        return modelos

    def _cargar_entrega(self, parametros: Path) -> dict[tuple[str, str], ModeloDuracion]:
        modelos = {}
        for fila in _leer_csv(parametros, "tiempo_entrega.csv"):
            modelo = _modelo_desde_fila("entrega", fila)
            clave = (modelo.prioridad_id, modelo.macrozona_destino_id)
            if clave in modelos:
                raise ValueError(f"Modelo de entrega duplicado: {clave}.")
            modelos[clave] = modelo
        if not modelos:
            raise ValueError("No se encontraron modelos de tiempo de entrega.")
        return modelos

    def generar_escena(self, prioridad_id: str) -> DuracionGenerada:
        try:
            modelo = self.modelos_escena[prioridad_id]
        except KeyError as exc:
            raise ValueError(f"No existe modelo de escena para prioridad={prioridad_id}.") from exc
        return self._generar(modelo)

    def generar_entrega(self, prioridad_id: str, macrozona_destino_id: str) -> DuracionGenerada:
        clave = (prioridad_id, macrozona_destino_id)
        try:
            modelo = self.modelos_entrega[clave]
        except KeyError as exc:
            raise ValueError(
                "No existe modelo de entrega para "
                f"prioridad={prioridad_id}, macrozona_destino={macrozona_destino_id}."
            ) from exc
        return self._generar(modelo)

    def _generar(self, modelo: ModeloDuracion) -> DuracionGenerada:
        for intento in range(1, self.max_intentos + 1):
            duracion_seg = self._sortear(modelo)
            if isfinite(duracion_seg) and duracion_seg > 0:
                return DuracionGenerada(
                    tipo=modelo.tipo,
                    duracion_seg=duracion_seg,
                    duracion_min=duracion_seg / 60,
                    modelo=modelo,
                    intentos=intento,
                )
        raise RuntimeError(f"No se pudo generar duracion positiva para {modelo}.")

    def _sortear(self, modelo: ModeloDuracion) -> float:
        p = modelo.parametros
        loc = p["loc"]
        scale = p["scale"]
        if modelo.familia == "norm":
            return self.rng.gauss(loc, scale)
        if modelo.familia == "gamma":
            return loc + self.rng.gammavariate(p["a"], scale)
        if modelo.familia == "lognorm":
            return loc + self.rng.lognormvariate(log(scale), p["s"])
        if modelo.familia == "rayleigh":
            return loc + scale * sqrt(-2 * log(1 - self.rng.random()))
        if modelo.familia == "chi2":
            return loc + scale * self.rng.gammavariate(p["df"] / 2, 2)
        raise ValueError(f"Familia no soportada: {modelo.familia}.")
