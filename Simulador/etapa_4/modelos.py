"""Resultados inmutables de viajes: kilómetros, km/h y minutos desde las 06:00."""
from dataclasses import dataclass
from math import isfinite

from Simulador.etapa_1.modelos import Punto


@dataclass(frozen=True)
class Segmento:
    origen: Punto
    destino: Punto
    zona_id: str
    distancia_km: float
    factor_congestion: float


@dataclass(frozen=True)
class Ruta:
    orientacion: str
    origen: Punto
    destino: Punto
    bloque_id: int
    multiplicador: float
    segmentos: tuple[Segmento, ...]
    distancia_km: float
    congestion: float | None
    velocidad_kmh: float | None
    duracion_min: float

    def posicion(self, transcurrido_min: float) -> Punto:
        """Posición sobre la polilínea; después del arribo permanece en destino."""
        if not isfinite(transcurrido_min) or transcurrido_min < 0:
            raise ValueError("El tiempo transcurrido debe ser finito y no negativo.")
        if transcurrido_min >= self.duracion_min:
            return self.destino
        if transcurrido_min == 0:
            return self.origen
        restante = self.distancia_km * (transcurrido_min / self.duracion_min)
        for segmento in self.segmentos:
            if restante <= segmento.distancia_km:
                fraccion = restante / segmento.distancia_km
                a, b = segmento.origen, segmento.destino
                return Punto(a.x + fraccion * (b.x - a.x),
                             a.y + fraccion * (b.y - a.y))
            restante -= segmento.distancia_km
        return self.destino  # Redondeo de coma flotante junto al arribo.


@dataclass(frozen=True)
class Viaje:
    ruta: Ruta
    inicio_min: float

    def __post_init__(self):
        if not isfinite(self.inicio_min) or self.inicio_min < 0:
            raise ValueError("El inicio debe ser finito y no negativo.")

    @property
    def fin_min(self) -> float:
        return self.inicio_min + self.ruta.duracion_min

    def posicion_en(self, minuto: float) -> Punto:
        if not isfinite(minuto) or minuto < self.inicio_min:
            raise ValueError("La consulta debe ser finita y no anterior al inicio.")
        if minuto >= self.fin_min:
            return self.ruta.destino
        return self.ruta.posicion(minuto - self.inicio_min)
