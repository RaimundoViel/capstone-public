"""Etapa 8: verificación operacional sin reservas ni retención estratégica."""
from .modelos import ErrorConsistencia, InformeVerificacion
from .verificar import verificar_estado, verificar_jornada

__all__ = ["ErrorConsistencia", "InformeVerificacion", "verificar_estado", "verificar_jornada"]
