"""Adaptador del motor operacional de etapa 7 al contrato de réplicas."""
from dataclasses import replace

from Simulador.etapa_7 import MotorJornada
from Simulador.etapa_8 import verificar_jornada
from Simulador.etapa_9 import adaptar_resultado_jornada


class MotorOperacional:
    def __init__(self, contexto):
        self.contexto = contexto
        self.resultado = None
        self.verificacion = None
        self.informe = None

    def ejecutar(self):
        if self.resultado is not None:
            raise ValueError("El adaptador requiere una instancia nueva por réplica.")
        c = self.contexto
        motor = MotorJornada(c.catalogos, c.configuracion, c.viajes, c.duraciones)
        resultado = motor.ejecutar(c.realizacion.llamados, c.estado.escenario)
        self.verificacion = verificar_jornada(resultado, c.catalogos, c.configuracion)
        # Preserva la identidad del estado exigida por el ejecutor de etapa 10.
        c.estado.ambulancias = resultado.estado.ambulancias
        c.estado.atenciones = resultado.estado.atenciones
        c.estado.cola = resultado.estado.cola
        c.estado.minuto_actual = resultado.estado.minuto_actual
        self.resultado = replace(resultado, estado=c.estado)
        self.informe = adaptar_resultado_jornada(self.resultado, c.catalogos)


def crear_motor(contexto):
    return MotorOperacional(contexto)
