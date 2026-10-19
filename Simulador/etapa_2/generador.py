"""Generador de demanda exogena para una jornada o un bloque."""
import csv
import random
from math import isclose
from pathlib import Path

from Simulador.etapa_1.modelos import Catalogos, Escenario, Llamado, Punto

from .modelos import DemandaGenerada


def _leer_csv(carpeta: Path, nombre: str) -> list[dict[str, str]]:
    with (carpeta / nombre).open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _distribucion(filas: list[dict[str, str]], id_col: str, prob_col: str) -> tuple[tuple[str, float], ...]:
    pares = tuple((fila[id_col], float(fila[prob_col])) for fila in filas)
    if not pares:
        raise ValueError("La distribucion no puede estar vacia.")
    if any(prob < 0 for _, prob in pares):
        raise ValueError("Las probabilidades no pueden ser negativas.")
    total = sum(prob for _, prob in pares)
    if not isclose(total, 1.0, rel_tol=0, abs_tol=1e-8):
        raise ValueError(f"Las probabilidades deben sumar 1; suman {total}.")
    return pares


def _sortear_categorico(rng: random.Random, distribucion: tuple[tuple[str, float], ...]) -> str:
    u = rng.random()
    acumulada = 0.0
    for valor, probabilidad in distribucion:
        acumulada += probabilidad
        if u <= acumulada:
            return valor
    return distribucion[-1][0]


class GeneradorDemanda:
    def __init__(self, catalogos: Catalogos, raiz: str | Path, escenario: Escenario):
        self.catalogos = catalogos
        self.raiz = Path(raiz)
        self.escenario = escenario
        self.rng = random.Random(escenario.semilla)
        parametros = self.raiz / "Simulador" / "parametros"
        self.lambdas = {
            int(fila["bloque_id"]): float(fila["lambda_poisson"])
            for fila in _leer_csv(parametros, "bloques.csv")
        }
        self.probabilidades_zona = _distribucion(
            _leer_csv(parametros, "probabilidades_zona.csv"), "zona_id", "probabilidad"
        )
        self.probabilidades_prioridad = _distribucion(
            _leer_csv(parametros, "prioridades.csv"), "prioridad_id", "probabilidad"
        )
        self._validar_parametros()

    def _validar_parametros(self) -> None:
        if set(self.lambdas) != set(self.catalogos.bloques):
            raise ValueError("Los lambdas no cubren exactamente los bloques del catalogo.")
        if any(valor <= 0 for valor in self.lambdas.values()):
            raise ValueError("Los lambdas Poisson deben ser positivos.")
        zonas = {zona for zona, _ in self.probabilidades_zona}
        prioridades = {prioridad for prioridad, _ in self.probabilidades_prioridad}
        if zonas != set(self.catalogos.zonas):
            raise ValueError("Las probabilidades de zona no cubren exactamente las zonas.")
        if prioridades != set(self.catalogos.prioridades):
            raise ValueError("Las probabilidades de prioridad no cubren exactamente las prioridades.")

    def _poisson(self, lambda_bloque: float) -> int:
        tiempo = 0.0
        conteo = 0
        while True:
            tiempo += self.rng.expovariate(lambda_bloque)
            if tiempo >= 1.0:
                return conteo
            conteo += 1

    def generar_bloque(self, dia: int, bloque_id: int, primer_indice: int = 1) -> tuple[Llamado, ...]:
        if dia <= 0:
            raise ValueError("El dia debe ser positivo.")
        if bloque_id not in self.catalogos.bloques:
            raise ValueError(f"Bloque desconocido: {bloque_id}.")
        bloque = self.catalogos.bloques[bloque_id]
        cantidad = self._poisson(self.lambdas[bloque_id])
        instantes = sorted(
            self.rng.uniform(bloque.inicio_min, bloque.fin_min)
            for _ in range(cantidad)
        )
        llamados = []
        for offset, instante in enumerate(instantes):
            zona_id = _sortear_categorico(self.rng, self.probabilidades_zona)
            prioridad_id = _sortear_categorico(self.rng, self.probabilidades_prioridad)
            zona = self.catalogos.zonas[zona_id]
            x = self.rng.uniform(zona.limites.x_min, zona.limites.x_max)
            y = self.rng.uniform(zona.limites.y_min, zona.limites.y_max)
            llamado_id = f"SIM-D{dia:03d}-A{primer_indice + offset:05d}"
            llamados.append(
                Llamado(
                    id=llamado_id,
                    recepcion_min=instante,
                    bloque_recepcion=bloque_id,
                    zona_id=zona_id,
                    posicion=Punto(x, y),
                    prioridad_id=prioridad_id,
                )
            )
        return tuple(llamados)

    def generar_jornada(self, dia: int) -> DemandaGenerada:
        llamados = []
        siguiente = 1
        for bloque_id in sorted(self.catalogos.bloques):
            bloque = self.generar_bloque(dia, bloque_id, siguiente)
            llamados.extend(bloque)
            siguiente += len(bloque)
        return DemandaGenerada(self.escenario, dia, tuple(llamados))
