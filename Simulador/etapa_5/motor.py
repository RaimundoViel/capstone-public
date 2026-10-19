"""Una atención completa con unidad explícita; sin cola ni despacho de flota."""
from math import isfinite
from typing import Protocol

from Simulador.etapa_1 import ConfiguracionInicial
from Simulador.etapa_1.modelos import (
    Atencion, Catalogos, EstadoAmbulancia as EU, EstadoLlamado as EL,
    EstadoSistema, Llamado,
)
from Simulador.etapa_3 import DuracionGenerada
from Simulador.etapa_4 import CalculadorViajes, Viaje
from .agenda import AgendaEventos
from .destinos import seleccionar_destino
from .modelos import RegistroTransicion, ResultadoAtencion


class FuenteDuraciones(Protocol):
    def generar_escena(self, prioridad_id: str) -> DuracionGenerada: ...
    def generar_entrega(self, prioridad_id: str, macrozona_destino_id: str) -> DuracionGenerada: ...


class MotorUnaAtencion:
    def __init__(self, catalogos: Catalogos, configuracion: ConfiguracionInicial,
                 viajes: CalculadorViajes, duraciones: FuenteDuraciones):
        configuracion.validar(catalogos)
        if viajes.catalogos is not catalogos:
            raise ValueError("El motor y viajes deben compartir el mismo catálogo.")
        self.catalogos = catalogos
        self.configuracion = configuracion
        self.viajes = viajes
        self.duraciones = duraciones

    def ejecutar(self, estado: EstadoSistema, llamado: Llamado,
                 ambulancia_id: str) -> ResultadoAtencion:
        """Despacha al recibir, procesa hasta regreso y modifica el estado recibido.

        Es un arnés individual, no un motor de jornada. Rechaza estados ocupados:
        no adelanta el reloj sobre actividades ajenas ni inventa esperas.
        """
        self._validar(estado, llamado, ambulancia_id)
        unidad = estado.ambulancias[ambulancia_id]
        atencion = Atencion(llamado)
        agenda = AgendaEventos(estado.minuto_actual)
        registros = []
        tramos = {}
        sorteos = {}
        destino = None

        def registrar(tipo, secuencia=None):
            registros.append(RegistroTransicion(
                tipo, estado.minuto_actual, secuencia, llamado.id, ambulancia_id,
                unidad.estado, atencion.estado, unidad.posicion, atencion.destino_id))

        def programar(duracion, tipo):
            if not isfinite(duracion) or duracion < 0:
                raise ValueError("Duración de evento inválida.")
            agenda.programar(estado.minuto_actual + duracion, tipo, llamado.id)

        def sortear(tipo):
            valor = (self.duraciones.generar_escena(llamado.prioridad_id)
                     if tipo == "escena" else
                     self.duraciones.generar_entrega(llamado.prioridad_id, destino.macrozona))
            if not isfinite(valor.duracion_min) or valor.duracion_min <= 0:
                raise ValueError("Escena y entrega requieren duraciones positivas finitas.")
            sorteos[tipo] = valor
            return valor.duracion_min

        def manejar(evento):
            nonlocal destino
            t = evento.minuto
            estado.minuto_actual = t
            if evento.tipo == "recepcion":
                estado.atenciones[llamado.id] = atencion
                registrar("recepcion", 1)
                # En este arnés solo hay una llegada y la unidad está disponible.
                programar(0, "despacho")
            elif evento.tipo == "despacho":
                ruta = self.viajes.calcular_atencion(unidad.posicion, llamado.posicion, llamado)
                tramos["paciente"] = Viaje(ruta, t)
                atencion.ambulancia_id = ambulancia_id
                atencion.despacho_min = t
                atencion.estado = EL.ASIGNADO
                unidad.llamado_id = llamado.id
                unidad.estado = EU.VIAJE_PACIENTE
                registrar("despacho", 2)
                programar(ruta.duracion_min, "inicio_escena")
            elif evento.tipo == "inicio_escena":
                unidad.posicion = llamado.posicion
                unidad.estado = EU.EN_ESCENA
                atencion.estado = EL.EN_ESCENA
                atencion.llegada_escena_min = t
                registrar("inicio_escena", 3)
                programar(sortear("escena"), "salida_destino")
            elif evento.tipo == "salida_destino":
                destino, ruta = seleccionar_destino(
                    self.catalogos, self.configuracion, self.viajes, llamado)
                atencion.destino_id = destino.id
                atencion.salida_escena_min = t
                atencion.estado = EL.EN_TRASLADO
                unidad.estado = EU.VIAJE_DESTINO
                tramos["destino"] = Viaje(ruta, t)
                registrar("salida_destino", 4)
                programar(ruta.duracion_min, "llegada_destino")
            elif evento.tipo == "llegada_destino":
                unidad.posicion = destino.posicion
                unidad.estado = EU.EN_ENTREGA
                atencion.estado = EL.EN_ENTREGA
                atencion.llegada_destino_min = t
                registrar("llegada_destino", 5)
                programar(sortear("entrega"), "fin_entrega")
            elif evento.tipo == "fin_entrega":
                atencion.fin_entrega_min = t
                atencion.estado = EL.COMPLETADO
                registrar("fin_entrega", 6)
                retorno = self.viajes.crear_retorno(unidad.posicion, unidad.ambulancia.base_inicial, t)
                tramos["retorno"] = retorno
                atencion.inicio_retorno_min = t
                atencion.bloque_retorno = retorno.ruta.bloque_id
                unidad.estado = EU.RETORNANDO
                unidad.retorno = retorno
                registrar("inicio_retorno")
                programar(retorno.ruta.duracion_min, "llegada_base")
            elif evento.tipo == "llegada_base":
                unidad.posicion = tramos["retorno"].ruta.destino
                unidad.estado = EU.DISPONIBLE
                unidad.llamado_id = None
                unidad.retorno = None
                atencion.fin_retorno_min = t
                registrar("llegada_base")
            else:
                raise ValueError(f"Evento desconocido: {evento.tipo}.")

        agenda.programar(llamado.recepcion_min, "recepcion", llamado.id)
        while agenda:
            agenda.procesar_instante(manejar)
        return ResultadoAtencion(atencion, tuple(registros), tramos["paciente"],
                                 tramos["destino"], tramos["retorno"],
                                 sorteos["escena"], sorteos["entrega"])

    def _validar(self, estado, llamado, ambulancia_id):
        if not isfinite(estado.minuto_actual) or estado.minuto_actual < 0:
            raise ValueError("Reloj inválido.")
        if llamado.id in estado.atenciones or not llamado.id:
            raise ValueError("Identificador de llamado vacío o repetido.")
        if (llamado.recepcion_min < estado.minuto_actual
                or self.catalogos.bloque_en(llamado.recepcion_min, recepcion=True) != llamado.bloque_recepcion):
            raise ValueError("Recepción pasada o bloque incompatible.")
        if llamado.prioridad_id not in self.catalogos.prioridades:
            raise ValueError("Prioridad desconocida.")
        if self.viajes.geometria.zona_en(llamado.posicion) != llamado.zona_id:
            raise ValueError("La posición no pertenece a la zona declarada.")
        if ambulancia_id not in estado.ambulancias:
            raise ValueError("Ambulancia inexistente.")
        if (estado.cola or any(u.estado != EU.DISPONIBLE or u.llamado_id is not None
                              for u in estado.ambulancias.values())
                or any(a.fin_retorno_min is None for a in estado.atenciones.values())):
            raise ValueError("El arnés individual requiere un estado sin actividades pendientes.")
        from collections import Counter
        asignacion = Counter(u.ambulancia.base_inicial for u in estado.ambulancias.values())
        esperada = {b: self.configuracion.ambulancias_por_base[b] for b in self.configuracion.bases_activas}
        if dict(asignacion) != esperada:
            raise ValueError("La flota no corresponde a la configuración.")
        for identificador, u in estado.ambulancias.items():
            if (u.ambulancia.id != identificador
                    or u.posicion != self.catalogos.bases[u.ambulancia.base_inicial].posicion):
                raise ValueError("Unidad fuera de su base inicial o identificador incompatible.")
