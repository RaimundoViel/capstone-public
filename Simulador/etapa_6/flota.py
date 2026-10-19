"""Selección global y asignación secuencial, sin política de cola."""
from math import isfinite

from Simulador.etapa_1 import ConfiguracionInicial
from Simulador.etapa_1.modelos import (
    Catalogos, EstadoSistema, Llamado, EstadoAmbulancia as EU, EstadoLlamado as EL,
)
from Simulador.etapa_4 import CalculadorViajes, Viaje
from Simulador.etapa_5.destinos import seleccionar_destino
from .modelos import CandidatoAmbulancia, Despacho, DestinoSeleccionado


class GestorFlota:
    def __init__(self, catalogos: Catalogos, configuracion: ConfiguracionInicial,
                 viajes: CalculadorViajes):
        configuracion.validar(catalogos)
        if viajes.catalogos is not catalogos:
            raise ValueError("Flota y viajes deben compartir catálogo.")
        self.catalogos = catalogos
        self.configuracion = configuracion
        self.viajes = viajes

    def _validar_llamado(self, llamado):
        if not llamado.id or llamado.prioridad_id not in self.catalogos.prioridades:
            raise ValueError("Identificador o prioridad de llamado inválidos.")
        if (self.catalogos.bloque_en(llamado.recepcion_min, recepcion=True)
                != llamado.bloque_recepcion):
            raise ValueError("Bloque de recepción incompatible.")
        if self.viajes.geometria.zona_en(llamado.posicion) != llamado.zona_id:
            raise ValueError("Zona y posición del llamado incompatibles.")

    def evaluar_disponibles(self, estado: EstadoSistema, llamado: Llamado
                           ) -> tuple[CandidatoAmbulancia, ...]:
        """Consulta sin mutar; ordena por ETA exacto y luego ID estable."""
        self._validar_llamado(llamado)
        if not isfinite(estado.minuto_actual) or estado.minuto_actual < llamado.recepcion_min:
            raise ValueError("No se puede evaluar una recepción futura o un reloj inválido.")
        # Solo las atenciones clínicas pendientes impiden despachar.
        ocupadas = {a.ambulancia_id for a in estado.atenciones.values()
                    if a.ambulancia_id is not None and a.fin_entrega_min is None}
        candidatos = []
        for identificador, unidad in estado.ambulancias.items():
            if not unidad.disponible:
                continue
            if identificador in ocupadas:
                raise ValueError("Unidad marcada disponible con una asignación pendiente.")
            base = unidad.ambulancia.base_inicial
            if (identificador != unidad.ambulancia.id
                    or base not in self.configuracion.bases_activas
                    ):
                raise ValueError("Unidad disponible fuera de su base activa inicial o ID inválido.")
            if unidad.estado == EU.RETORNANDO:
                anterior = estado.atenciones.get(unidad.llamado_id)
                if (unidad.retorno is None or anterior is None
                        or anterior.ambulancia_id != identificador
                        or anterior.estado != EL.COMPLETADO
                        or anterior.fin_entrega_min is None
                        or anterior.fin_retorno_min is not None
                        or anterior.interrupcion_retorno_min is not None):
                    raise ValueError("Retorno sin viaje o atención válida.")
                posicion = unidad.retorno.posicion_en(estado.minuto_actual)
            else:
                if (unidad.llamado_id is not None or unidad.retorno is not None
                        or unidad.posicion != self.catalogos.bases[base].posicion):
                    raise ValueError("Unidad disponible inconsistente con su base inicial.")
                posicion = unidad.posicion
            ruta = self.viajes.calcular_atencion(posicion, llamado.posicion, llamado)
            candidatos.append(CandidatoAmbulancia(identificador, ruta))
        return tuple(sorted(candidatos, key=lambda c: (c.eta_min, c.ambulancia_id)))

    def seleccionar_ambulancia(self, estado: EstadoSistema, llamado: Llamado
                              ) -> CandidatoAmbulancia | None:
        candidatos = self.evaluar_disponibles(estado, llamado)
        return candidatos[0] if candidatos else None

    def despachar(self, estado: EstadoSistema, llamado_id: str) -> Despacho | None:
        """Asigna el llamado ya registrado. Sin recursos devuelve None sin mutar.

        El motor llama después de drenar el instante; etapa 7 elige qué llamado
        atender primero y retira de su cola los despachos exitosos.
        """
        if llamado_id not in estado.atenciones:
            raise ValueError("El llamado debe estar registrado antes de despachar.")
        atencion = estado.atenciones[llamado_id]
        if atencion.llamado.id != llamado_id:
            raise ValueError("Identificador de atención incompatible.")
        hitos = (atencion.despacho_min, atencion.llegada_escena_min,
                 atencion.salida_escena_min, atencion.llegada_destino_min,
                 atencion.fin_entrega_min, atencion.inicio_retorno_min, atencion.fin_retorno_min,
                 atencion.interrupcion_retorno_min)
        if (atencion.estado != EL.EN_COLA or atencion.ambulancia_id is not None
                or atencion.destino_id is not None or any(h is not None for h in hitos)):
            raise ValueError("El llamado ya fue asignado o contiene hitos incompatibles.")
        candidato = self.seleccionar_ambulancia(estado, atencion.llamado)
        if candidato is None:
            return None
        viaje = Viaje(candidato.ruta, estado.minuto_actual)
        unidad = estado.ambulancias[candidato.ambulancia_id]
        # Todas las validaciones y cálculos preceden a la mutación.
        anterior_id = unidad.llamado_id if unidad.estado == EU.RETORNANDO else None
        if anterior_id is not None:
            estado.atenciones[anterior_id].interrupcion_retorno_min = estado.minuto_actual
        unidad.posicion = candidato.ruta.origen
        unidad.retorno = None
        atencion.ambulancia_id = candidato.ambulancia_id
        atencion.despacho_min = estado.minuto_actual
        atencion.estado = EL.ASIGNADO
        unidad.llamado_id = llamado_id
        unidad.estado = EU.VIAJE_PACIENTE
        return Despacho(llamado_id, candidato.ambulancia_id, viaje, anterior_id)

    def seleccionar_destino(self, llamado: Llamado) -> DestinoSeleccionado:
        """Consulta pura para invocar al finalizar escena, sin límites de ocupación."""
        self._validar_llamado(llamado)
        instalacion, ruta = seleccionar_destino(
            self.catalogos, self.configuracion, self.viajes, llamado)
        return DestinoSeleccionado(instalacion, ruta)
