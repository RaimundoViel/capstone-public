"""Etapa 10: escenarios, replicas reproducibles e intervalos entre jornadas."""
from .modelos import EscenarioSimulacion, PlanExperimento, RealizacionReplica, ResultadoReplica
from .experimento import (
    ContextoReplica, MotorReplica, preparar_replica, preparar_experimento,
    ejecutar_replica, ejecutar_experimento,
)
from .estadisticas import estimar, resumir_resultados
from .exportar import guardar_realizacion, cargar_realizacion, exportar_experimento

__all__ = [
    "EscenarioSimulacion", "PlanExperimento", "RealizacionReplica", "ResultadoReplica",
    "ContextoReplica", "MotorReplica", "preparar_replica", "preparar_experimento",
    "ejecutar_replica", "ejecutar_experimento", "estimar", "resumir_resultados",
    "guardar_realizacion", "cargar_realizacion", "exportar_experimento",
]
