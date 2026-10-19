"""Unidades internas: kilómetros y minutos transcurridos desde las 06:00."""
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from Simulador.etapa_4 import Viaje


@dataclass(frozen=True)
class Punto:
    x: float
    y: float

    def __post_init__(self):
        if not all(isfinite(v) for v in (self.x, self.y)):
            raise ValueError("Las coordenadas deben ser finitas.")


@dataclass(frozen=True)
class Rectangulo:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self):
        if not all(isfinite(v) for v in (
            self.x_min, self.x_max, self.y_min, self.y_max
        )) or not (self.x_min < self.x_max and self.y_min < self.y_max):
            raise ValueError("Límites territoriales inválidos.")


@dataclass(frozen=True)
class Base:
    id: str
    posicion: Punto
    macrozona: str
    capacidad: int


@dataclass(frozen=True)
class Hospital:
    id: str
    posicion: Punto
    macrozona: str


@dataclass(frozen=True)
class Zona:
    id: str
    fila: int
    columna: int
    limites: Rectangulo
    centroide: Punto
    macrozona: str


@dataclass(frozen=True)
class Macrozona:
    id: str
    fila: int
    columna: int
    limites: Rectangulo


@dataclass(frozen=True)
class Prioridad:
    id: str
    rango: int
    objetivo_min: float
    destino: str
    multiplicador_velocidad: float


@dataclass(frozen=True)
class Bloque:
    id: int
    inicio_min: float
    fin_min: float

    def contiene(self, minuto: float) -> bool:
        return self.inicio_min <= minuto < self.fin_min


@dataclass(frozen=True)
class Catalogos:
    bases: Mapping[str, Base]
    hospitales: Mapping[str, Hospital]
    zonas: Mapping[str, Zona]
    macrozonas: Mapping[str, Macrozona]
    prioridades: Mapping[str, Prioridad]
    bloques: Mapping[int, Bloque]
    congestion: Mapping[tuple[str, int], float]
    huellas_fuentes: Mapping[str, str]

    def __post_init__(self):
        # Copia defensiva: tampoco el diccionario de quien construye puede mutarnos.
        for nombre in self.__dataclass_fields__:
            object.__setattr__(self, nombre, MappingProxyType(dict(getattr(self, nombre))))

    def bloque_en(self, minuto: float, *, recepcion: bool = False) -> int:
        """En recepción rechaza medianoche; para el calendario prolonga bloque 5."""
        if not isfinite(minuto) or minuto < 0:
            raise ValueError("El instante debe ser finito y posterior a las 06:00.")
        for bloque in sorted(self.bloques.values(), key=lambda b: b.inicio_min):
            if bloque.contiene(minuto):
                return bloque.id
        ultimo = max(self.bloques.values(), key=lambda b: b.fin_min)
        if not recepcion and minuto >= ultimo.fin_min:
            return ultimo.id
        raise ValueError("No se admiten recepciones a partir de medianoche.")


class EstadoAmbulancia(str, Enum):
    DISPONIBLE = "disponible"
    VIAJE_PACIENTE = "viaje_paciente"
    EN_ESCENA = "en_escena"
    VIAJE_DESTINO = "viaje_destino"
    EN_ENTREGA = "en_entrega"
    RETORNANDO = "retornando"


class EstadoLlamado(str, Enum):
    EN_COLA = "en_cola"
    ASIGNADO = "asignado"
    EN_ESCENA = "en_escena"
    EN_TRASLADO = "en_traslado"
    EN_ENTREGA = "en_entrega"
    COMPLETADO = "completado"


@dataclass(frozen=True)
class Ambulancia:
    id: str
    base_inicial: str


@dataclass
class EstadoUnidad:
    ambulancia: Ambulancia
    posicion: Punto
    estado: EstadoAmbulancia = EstadoAmbulancia.DISPONIBLE
    llamado_id: str | None = None
    retorno: "Viaje | None" = None

    @property
    def disponible(self) -> bool:
        return self.estado in (EstadoAmbulancia.DISPONIBLE, EstadoAmbulancia.RETORNANDO)


@dataclass(frozen=True)
class Llamado:
    id: str
    recepcion_min: float
    bloque_recepcion: int
    zona_id: str
    posicion: Punto
    prioridad_id: str


@dataclass
class Atencion:
    llamado: Llamado
    estado: EstadoLlamado = EstadoLlamado.EN_COLA
    ambulancia_id: str | None = None
    destino_id: str | None = None
    despacho_min: float | None = None
    llegada_escena_min: float | None = None
    salida_escena_min: float | None = None
    llegada_destino_min: float | None = None
    fin_entrega_min: float | None = None
    inicio_retorno_min: float | None = None
    bloque_retorno: int | None = None
    fin_retorno_min: float | None = None
    interrupcion_retorno_min: float | None = None


@dataclass(frozen=True)
class Escenario:
    id: str
    semilla: int

    def __post_init__(self):
        if not self.id or type(self.semilla) is not int or self.semilla < 0:
            raise ValueError("El escenario requiere ID y semilla entera no negativa.")


@dataclass
class EstadoSistema:
    escenario: Escenario
    ambulancias: dict[str, EstadoUnidad]
    minuto_actual: float = 0.0
    atenciones: dict[str, Atencion] = field(default_factory=dict)
    cola: list[str] = field(default_factory=list)
