"""Resultados de selección; ETA es duración de viaje en minutos."""
from dataclasses import dataclass

from Simulador.etapa_1.modelos import Base, Hospital
from Simulador.etapa_4 import Ruta, Viaje


@dataclass(frozen=True)
class CandidatoAmbulancia:
    ambulancia_id: str
    ruta: Ruta

    @property
    def eta_min(self) -> float:
        return self.ruta.duracion_min


@dataclass(frozen=True)
class Despacho:
    llamado_id: str
    ambulancia_id: str
    viaje: Viaje
    retorno_interrumpido_id: str | None = None


@dataclass(frozen=True)
class DestinoSeleccionado:
    instalacion: Base | Hospital
    ruta: Ruta
