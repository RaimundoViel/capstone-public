"""Valida la asignación inicial según las decisiones de etapa 0."""
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .modelos import Catalogos

FLOTA_TOTAL = 140
MINIMO_BASE_ACTIVA = 4


@dataclass(frozen=True)
class ConfiguracionInicial:
    ambulancias_por_base: Mapping[str, int]

    def __post_init__(self):
        object.__setattr__(self, "ambulancias_por_base",
                           MappingProxyType(dict(self.ambulancias_por_base)))

    @property
    def bases_activas(self) -> tuple[str, ...]:
        return tuple(sorted(k for k, n in self.ambulancias_por_base.items()
                            if type(n) is int and n > 0))

    def validar(self, catalogos: Catalogos) -> None:
        errores = []
        for base, cantidad in self.ambulancias_por_base.items():
            if base not in catalogos.bases:
                errores.append(f"Base desconocida: {base}.")
            if type(cantidad) is not int:
                errores.append(f"{base}: cantidad debe ser entera (no booleano).")
                continue
            if cantidad < 0 or 0 < cantidad < MINIMO_BASE_ACTIVA:
                errores.append(f"{base}: debe tener 0 o al menos 4 ambulancias.")
            if base in catalogos.bases and cantidad > catalogos.bases[base].capacidad:
                errores.append(f"{base}: excede capacidad inicial "
                               f"{catalogos.bases[base].capacidad}.")
        cantidades = list(self.ambulancias_por_base.values())
        if all(type(n) is int for n in cantidades) and sum(cantidades) != FLOTA_TOTAL:
            errores.append(f"La flota debe sumar exactamente {FLOTA_TOTAL}; "
                           f"suma {sum(cantidades)}.")
        if errores:
            raise ValueError("Configuración inválida:\n- " + "\n- ".join(errores))

    @classmethod
    def desde_json(cls, ruta: str | Path) -> "ConfiguracionInicial":
        def sin_duplicados(pares):
            resultado = {}
            for clave, valor in pares:
                if clave in resultado:
                    raise ValueError(f"Base repetida en JSON: {clave}.")
                resultado[clave] = valor
            return resultado
        datos = json.loads(Path(ruta).read_text(encoding="utf-8-sig"),
                           object_pairs_hook=sin_duplicados)
        if not isinstance(datos, dict):
            raise ValueError("La configuración JSON debe ser un objeto base: cantidad.")
        return cls(datos)
