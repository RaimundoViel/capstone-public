"""Estructuras minimas para calcular KPIs desde atenciones cerradas."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RegistroAtencion:
    atencion_id: str
    prioridad_id: str
    zona_id: str
    recepcion_min: float
    despacho_min: float
    llegada_escena_min: float
    espera_recurso_min: float | None = None

    def __post_init__(self):
        if not self.atencion_id:
            raise ValueError("atencion_id es requerido.")
        if not self.prioridad_id:
            raise ValueError("prioridad_id es requerido.")
        if not self.zona_id:
            raise ValueError("zona_id es requerido.")
        tiempos = (self.recepcion_min, self.despacho_min, self.llegada_escena_min)
        if not all(isfinite(t) for t in tiempos):
            raise ValueError("Los tiempos deben ser finitos.")
        if not (self.recepcion_min <= self.despacho_min <= self.llegada_escena_min):
            raise ValueError("Los tiempos deben cumplir recepcion <= despacho <= llegada_escena.")
        if self.espera_recurso_min is not None:
            if not isfinite(self.espera_recurso_min) or self.espera_recurso_min < 0:
                raise ValueError("espera_recurso_min debe ser finita y no negativa.")

    @property
    def respuesta_min(self) -> float:
        return self.llegada_escena_min - self.recepcion_min

    @property
    def espera_recurso(self) -> float:
        if self.espera_recurso_min is not None:
            return self.espera_recurso_min
        return self.despacho_min - self.recepcion_min


@dataclass(frozen=True)
class ZonaCobertura:
    zona_id: str
    prioridad_critica_id: str
    llamados_prioridad_critica: int
    cumplimiento_prioridad_critica_pct: float
    cubierta: bool


@dataclass(frozen=True)
class KPIResumen:
    total_atenciones: int
    tiempo_promedio_respuesta_por_prioridad: dict[str, float]
    tiempo_promedio_respuesta_por_zona: dict[str, float]
    cumplimiento_objetivo_por_prioridad_pct: dict[str, float]
    percentiles_respuesta_por_prioridad: dict[str, dict[str, float]]
    porcentaje_llamadas_con_espera_recurso: float | None
    porcentaje_zonas_cobertura_adecuada: float | None
    cobertura_por_zona: dict[str, ZonaCobertura]

    @property
    def zonas_con_demanda(self) -> int:
        return len(self.cobertura_por_zona)

    @property
    def zonas_cubiertas(self) -> int:
        return sum(z.cubierta for z in self.cobertura_por_zona.values())
