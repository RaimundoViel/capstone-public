"""Semillas estables y duraciones asociadas al llamado, no al orden de despacho."""
from copy import copy
from hashlib import sha256
import json
import random

from Simulador.etapa_1.modelos import Escenario, Llamado
from Simulador.etapa_3 import GeneradorDuraciones


VERSION_SEMILLAS = "sha256-v1"


def derivar_semilla(semilla: int, *claves: str | int) -> int:
    contenido = json.dumps([VERSION_SEMILLAS, semilla, *claves], ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return int.from_bytes(sha256(contenido).digest(), "big")


class DuracionesReplica:
    def __init__(self, raiz, semilla: int):
        self.semilla = semilla
        self._generador = GeneradorDuraciones(raiz, Escenario("duraciones", semilla))

    def para_llamado(self, llamado: Llamado):
        return _DuracionesLlamado(self._generador, self.semilla, llamado)


class _DuracionesLlamado:
    def __init__(self, generador, semilla, llamado):
        self.generador = generador
        self.semilla = semilla
        self.llamado = llamado

    def _fuente(self, prioridad, tipo, macrozona=""):
        if prioridad != self.llamado.prioridad_id:
            raise ValueError("La prioridad del sorteo no corresponde al llamado.")
        # Copia el proveedor y reemplaza solo su RNG; sus modelos no se modifican.
        fuente = copy(self.generador)
        fuente.rng = random.Random(derivar_semilla(
            self.semilla, self.llamado.id, tipo, prioridad, macrozona))
        return fuente

    def generar_escena(self, prioridad_id):
        return self._fuente(prioridad_id, "escena").generar_escena(prioridad_id)

    def generar_entrega(self, prioridad_id, macrozona_destino_id):
        return self._fuente(prioridad_id, "entrega", macrozona_destino_id).generar_entrega(
            prioridad_id, macrozona_destino_id)
