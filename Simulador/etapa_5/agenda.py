"""Agenda determinista reutilizable; no contiene políticas de despacho."""
from dataclasses import dataclass, field
from heapq import heappop, heappush, heapify
from math import isfinite


@dataclass(frozen=True, order=True)
class Evento:
    minuto: float
    entidad_id: str
    orden: int
    tipo: str = field(compare=False)


class AgendaEventos:
    def __init__(self, inicio_min: float = 0):
        if not isfinite(inicio_min) or inicio_min < 0:
            raise ValueError("Inicio de agenda inválido.")
        self.minuto_actual = inicio_min
        self._eventos = []
        self._orden = 0

    def __bool__(self):
        return bool(self._eventos)

    def cancelar(self, tipo: str, entidad_id: str) -> int:
        """Retira eventos invalidados sin avanzar el reloj hacia ellos."""
        cantidad = len(self._eventos)
        self._eventos = [e for e in self._eventos if (e.tipo, e.entidad_id) != (tipo, entidad_id)]
        heapify(self._eventos)
        return cantidad - len(self._eventos)

    def programar(self, minuto: float, tipo: str, entidad_id: str) -> Evento:
        if not isfinite(minuto) or minuto < self.minuto_actual:
            raise ValueError("No se pueden programar eventos no finitos o en el pasado.")
        if not tipo or not entidad_id:
            raise ValueError("El evento requiere tipo e identificador.")
        evento = Evento(minuto, entidad_id, self._orden, tipo)
        self._orden += 1
        heappush(self._eventos, evento)
        return evento

    def procesar_instante(self, manejar) -> tuple[Evento, ...]:
        """Drena también eventos de duración cero creados por el manejador.

        El futuro despachador debe actuar después de este método, nunca dentro
        del manejador de una llegada/disponibilidad individual.
        """
        if not self._eventos:
            return ()
        self.minuto_actual = self._eventos[0].minuto
        procesados = []
        while self._eventos and self._eventos[0].minuto == self.minuto_actual:
            evento = heappop(self._eventos)
            manejar(evento)
            procesados.append(evento)
        return tuple(procesados)
