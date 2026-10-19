"""Modelos ajustados y duraciones generadas."""
from dataclasses import dataclass
from math import exp, pi, sqrt


@dataclass(frozen=True)
class ModeloDuracion:
    tipo: str
    prioridad_id: str
    macrozona_destino_id: str | None
    familia: str
    parametros: dict[str, float]
    n_ajuste: int

    @property
    def clave(self) -> tuple[str, str | None]:
        return (self.prioridad_id, self.macrozona_destino_id)

    def media_teorica_seg(self) -> float:
        loc = self.parametros["loc"]
        scale = self.parametros["scale"]
        if self.familia == "norm":
            return loc
        if self.familia == "gamma":
            return loc + self.parametros["a"] * scale
        if self.familia == "lognorm":
            return loc + scale * exp((self.parametros["s"] ** 2) / 2)
        if self.familia == "rayleigh":
            return loc + scale * sqrt(pi / 2)
        if self.familia == "chi2":
            return loc + self.parametros["df"] * scale
        raise ValueError(f"Familia no soportada: {self.familia}.")


@dataclass(frozen=True)
class DuracionGenerada:
    tipo: str
    duracion_seg: float
    duracion_min: float
    modelo: ModeloDuracion
    intentos: int
