"""Evidencia del ciclo individual; no sustituye el contrato futuro de etapa 9."""
from dataclasses import dataclass

from Simulador.etapa_1.modelos import Atencion, EstadoAmbulancia, EstadoLlamado, Punto
from Simulador.etapa_3 import DuracionGenerada
from Simulador.etapa_4 import Viaje


@dataclass(frozen=True)
class RegistroTransicion:
    tipo: str
    minuto: float
    secuencia_evento: int | None
    llamado_id: str
    ambulancia_id: str
    estado_unidad: EstadoAmbulancia
    estado_llamado: EstadoLlamado
    posicion: Punto
    destino_id: str | None


@dataclass(frozen=True)
class ResultadoAtencion:
    atencion: Atencion
    registros: tuple[RegistroTransicion, ...]
    viaje_paciente: Viaje
    viaje_destino: Viaje
    retorno: Viaje
    escena: DuracionGenerada
    entrega: DuracionGenerada
