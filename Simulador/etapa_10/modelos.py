"""Escenarios sin semilla y realizaciones sin estado operacional compartido."""
from dataclasses import dataclass
from math import isfinite

from Simulador.etapa_1.modelos import Llamado
from Simulador.etapa_9 import RegistroAtencion


@dataclass(frozen=True)
class EscenarioSimulacion:
    id: str
    bloques_evaluados: tuple[int, ...] = (1, 2, 3, 4, 5)
    descripcion: str = "Jornada continua con los parametros vigentes."

    def __post_init__(self):
        bloques = tuple(self.bloques_evaluados)
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("El escenario requiere un ID.")
        if (not bloques or any(type(b) is not int or b not in range(1, 6) for b in bloques)
                or len(set(bloques)) != len(bloques)):
            raise ValueError("Elegir bloques distintos entre 1 y 5.")
        object.__setattr__(self, "bloques_evaluados", tuple(sorted(bloques)))


@dataclass(frozen=True)
class PlanExperimento:
    escenarios: tuple[EscenarioSimulacion, ...]
    replicas: int = 30
    semilla_maestra: int = 42
    confianza: float = 0.95

    def __post_init__(self):
        object.__setattr__(self, "escenarios", tuple(self.escenarios))
        ids = [e.id for e in self.escenarios]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("Se requieren escenarios con IDs distintos.")
        if type(self.replicas) is not int or self.replicas < 1:
            raise ValueError("La cantidad de replicas debe ser un entero positivo.")
        if type(self.semilla_maestra) is not int or self.semilla_maestra < 0:
            raise ValueError("La semilla maestra debe ser un entero no negativo.")
        if not isfinite(self.confianza) or not 0 < self.confianza < 1:
            raise ValueError("La confianza debe estar entre 0 y 1.")


@dataclass(frozen=True)
class RealizacionReplica:
    escenario: EscenarioSimulacion
    numero: int
    semilla_maestra: int
    semilla_demanda: int
    semilla_duraciones: int
    huellas_parametros: tuple[tuple[str, str], ...]
    llamados: tuple[Llamado, ...]


@dataclass(frozen=True)
class ResultadoReplica:
    realizacion: RealizacionReplica
    configuracion: tuple[tuple[str, int], ...]
    registros: tuple[RegistroAtencion, ...]
    fin_min: float
    version_motor: str
    huellas_codigo: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Estimacion:
    replicas_totales: int
    replicas_con_datos: int
    media: float | None
    desviacion: float | None
    error_estandar: float | None
    margen: float | None
    ic_inferior: float | None
    ic_superior: float | None
    confianza: float


@dataclass(frozen=True)
class ResumenIndicador:
    escenario_id: str
    ambito: str
    indicador: str
    grupo: str
    unidad: str
    estimacion: Estimacion
