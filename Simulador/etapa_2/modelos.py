"""Estructuras de salida para la demanda generada."""
from dataclasses import dataclass

from Simulador.etapa_1.modelos import Escenario, Llamado


@dataclass(frozen=True)
class DemandaGenerada:
    escenario: Escenario
    dia: int
    llamados: tuple[Llamado, ...]

    def por_bloque(self) -> dict[int, int]:
        conteos = {bloque: 0 for bloque in range(1, 6)}
        for llamado in self.llamados:
            conteos[llamado.bloque_recepcion] = conteos.get(llamado.bloque_recepcion, 0) + 1
        return conteos
