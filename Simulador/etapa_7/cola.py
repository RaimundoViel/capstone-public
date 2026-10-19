"""Cola de pacientes independiente de la agenda de eventos futuros."""
from Simulador.etapa_1.modelos import Atencion


class GestorCola:
    def __init__(self, flota):
        self.flota = flota

    def recibir(self, estado, llamado):
        self.flota._validar_llamado(llamado)
        if llamado.recepcion_min != estado.minuto_actual:
            raise ValueError("La recepción debe incorporarse en su instante exacto.")
        if llamado.id in estado.atenciones:
            raise ValueError("Llamado repetido.")
        estado.atenciones[llamado.id] = Atencion(llamado)
        estado.cola.append(llamado.id)

    def ordenados(self, estado):
        def clave(identificador):
            llamado = estado.atenciones[identificador].llamado
            return (self.flota.catalogos.prioridades[llamado.prioridad_id].rango,
                    llamado.recepcion_min, llamado.id)
        return tuple(sorted(estado.cola, key=clave))

    def despachar_pendientes(self, estado):
        """Devuelve despachos; solo retira de la cola asignaciones exitosas."""
        despachos = []
        for identificador in self.ordenados(estado):
            despacho = self.flota.despachar(estado, identificador)
            if despacho is None:
                break  # La elegibilidad de unidades es común a P1–P5.
            estado.cola.remove(identificador)
            despachos.append(despacho)
        return tuple(despachos)
