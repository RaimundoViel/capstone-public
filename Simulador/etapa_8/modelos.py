"""Resultado de comprobaciones operacionales, no métricas de desempeño."""
from dataclasses import dataclass


class ErrorConsistencia(ValueError):
    """Invariante operacional incumplida; el mensaje identifica su contexto."""


@dataclass(frozen=True)
class InformeVerificacion:
    ambulancias: int
    atenciones: int
    eventos: int
    retornos_interrumpidos: int
    fin_min: float
