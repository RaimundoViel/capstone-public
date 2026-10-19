"""Salidas operacionales de una jornada; sin calcular KPIs ni exportar archivos."""
from dataclasses import dataclass

from Simulador.etapa_1.modelos import EstadoSistema, EstadoAmbulancia, EstadoLlamado, Punto
from Simulador.etapa_3 import DuracionGenerada
from Simulador.etapa_4 import Viaje


@dataclass(frozen=True)
class RegistroEvento:
    tipo: str
    minuto: float
    secuencia_evento: int | None
    llamado_id: str
    ambulancia_id: str | None
    estado_unidad: EstadoAmbulancia | None
    estado_llamado: EstadoLlamado
    posicion: Punto
    destino_id: str | None


@dataclass(frozen=True)
class EstadoTemporal:
    minuto: float
    pendientes: int
    disponibles: int


@dataclass(frozen=True)
class ResultadoJornada:
    estado: EstadoSistema
    registros: tuple[RegistroEvento, ...]
    historial: tuple[EstadoTemporal, ...]
    viajes: dict[tuple[str, str], Viaje]
    duraciones: dict[tuple[str, str], DuracionGenerada]
