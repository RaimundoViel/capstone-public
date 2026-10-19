"""Motor concurrente con cola y despacho desde retornos."""
from math import isfinite

from Simulador.etapa_1 import crear_estado_inicial
from Simulador.etapa_1.modelos import EstadoAmbulancia as EU, EstadoLlamado as EL
from Simulador.etapa_4 import Viaje
from Simulador.etapa_5 import AgendaEventos
from Simulador.etapa_6 import GestorFlota
from .cola import GestorCola
from .modelos import RegistroEvento, EstadoTemporal, ResultadoJornada


class MotorJornada:
    def __init__(self, catalogos, configuracion, viajes, duraciones):
        self.flota = GestorFlota(catalogos, configuracion, viajes)
        self.cola = GestorCola(self.flota)
        self.catalogos = catalogos
        self.configuracion = configuracion
        self.viajes = viajes
        self.duraciones = duraciones
        self._ejecutado = False

    def ejecutar(self, llamados, escenario) -> ResultadoJornada:
        """Una instancia por réplica, con proveedor de duraciones nuevo.

        Los llamados futuros solo entran al estado cuando ocurre su recepción.
        Un fallo de proveedor aborta la ejecución; no se reanuda estado parcial.
        """
        if self._ejecutado:
            raise ValueError("Crear un motor y proveedor de duraciones nuevos por réplica.")
        fuente_escenario = getattr(self.duraciones, "escenario", escenario)
        if fuente_escenario != escenario:
            raise ValueError("El generador de duraciones corresponde a otro escenario.")
        entradas = {}
        for llamado in llamados:
            self.flota._validar_llamado(llamado)
            if llamado.id in entradas:
                raise ValueError("Identificador de llamado repetido.")
            entradas[llamado.id] = llamado
        estado = crear_estado_inicial(self.catalogos, self.configuracion, escenario)
        self._ejecutado = True
        agenda = AgendaEventos()
        registros, historial = [], []
        tramos, sorteos, destinos = {}, {}, {}

        def instantanea():
            historial.append(EstadoTemporal(estado.minuto_actual, len(estado.cola),
                                            sum(u.disponible for u in estado.ambulancias.values())))

        def registrar(tipo, atencion, secuencia=None, fase=None):
            unidad = (estado.ambulancias[atencion.ambulancia_id]
                      if atencion.ambulancia_id is not None else None)
            registros.append(RegistroEvento(
                tipo, estado.minuto_actual, secuencia, atencion.llamado.id,
                atencion.ambulancia_id, fase or (unidad.estado if unidad else None),
                atencion.estado, unidad.posicion if unidad else atencion.llamado.posicion,
                atencion.destino_id))
            instantanea()

        def programar(minuto, tipo, identificador):
            agenda.programar(minuto, tipo, identificador)

        def sortear(atencion, tipo):
            l = atencion.llamado
            fuente = (self.duraciones.para_llamado(l) if hasattr(self.duraciones, "para_llamado")
                      else self.duraciones)
            valor = (fuente.generar_escena(l.prioridad_id) if tipo == "escena"
                     else fuente.generar_entrega(l.prioridad_id, destinos[l.id].macrozona))
            if not isfinite(valor.duracion_min) or valor.duracion_min <= 0:
                raise ValueError("Escena y entrega requieren duración positiva finita.")
            fin = estado.minuto_actual + valor.duracion_min
            if not isfinite(fin) or fin <= estado.minuto_actual:
                raise ValueError("La duración no permite avanzar el reloj numérico.")
            sorteos[l.id, tipo] = valor
            return fin

        def manejar(evento):
            if (evento.tipo == "llegada_base"
                    and estado.atenciones[evento.entidad_id].interrupcion_retorno_min is not None):
                return  # Protección adicional frente a una llegada invalidada.
            estado.minuto_actual = evento.minuto
            identificador, t = evento.entidad_id, evento.minuto
            if evento.tipo == "recepcion":
                self.cola.recibir(estado, entradas[identificador])
                registrar("recepcion", estado.atenciones[identificador], 1)
                return
            a = estado.atenciones[identificador]
            u = estado.ambulancias[a.ambulancia_id]
            esperados = {"inicio_escena": EU.VIAJE_PACIENTE, "salida_destino": EU.EN_ESCENA,
                         "llegada_destino": EU.VIAJE_DESTINO, "fin_entrega": EU.EN_ENTREGA,
                         "llegada_base": EU.RETORNANDO}
            if u.llamado_id != identificador or u.estado != esperados.get(evento.tipo):
                raise RuntimeError("Evento incompatible con la asignación o fase de la unidad.")
            if evento.tipo == "inicio_escena":
                u.posicion, u.estado = a.llamado.posicion, EU.EN_ESCENA
                a.estado, a.llegada_escena_min = EL.EN_ESCENA, t
                registrar(evento.tipo, a, 3)
                programar(sortear(a, "escena"), "salida_destino", identificador)
            elif evento.tipo == "salida_destino":
                elegido = self.flota.seleccionar_destino(a.llamado)
                destinos[identificador] = elegido.instalacion
                a.destino_id, a.salida_escena_min = elegido.instalacion.id, t
                a.estado, u.estado = EL.EN_TRASLADO, EU.VIAJE_DESTINO
                viaje = Viaje(elegido.ruta, t)
                tramos[identificador, "destino"] = viaje
                registrar(evento.tipo, a, 4)
                programar(viaje.fin_min, "llegada_destino", identificador)
            elif evento.tipo == "llegada_destino":
                u.posicion = destinos[identificador].posicion
                u.estado, a.estado = EU.EN_ENTREGA, EL.EN_ENTREGA
                a.llegada_destino_min = t
                registrar(evento.tipo, a, 5)
                programar(sortear(a, "entrega"), "fin_entrega", identificador)
            elif evento.tipo == "fin_entrega":
                a.fin_entrega_min, a.estado = t, EL.COMPLETADO
                registrar(evento.tipo, a, 6)
                retorno = self.viajes.crear_retorno(u.posicion, u.ambulancia.base_inicial, t)
                tramos[identificador, "retorno"] = retorno
                a.inicio_retorno_min, a.bloque_retorno = t, retorno.ruta.bloque_id
                u.estado = EU.RETORNANDO
                u.retorno = retorno
                registrar("inicio_retorno", a)
                programar(retorno.fin_min, "llegada_base", identificador)
            elif evento.tipo == "llegada_base":
                u.posicion = tramos[identificador, "retorno"].ruta.destino
                u.estado, u.llamado_id = EU.DISPONIBLE, None
                u.retorno = None
                a.fin_retorno_min = t
                registrar(evento.tipo, a)

        instantanea()
        for llamado in entradas.values():
            programar(llamado.recepcion_min, "recepcion", llamado.id)
        while agenda:
            agenda.procesar_instante(manejar)
            # Barrera temporal: ya entraron TODAS las llegadas y disponibilidades.
            for despacho in self.cola.despachar_pendientes(estado):
                if despacho.retorno_interrumpido_id is not None:
                    anterior = despacho.retorno_interrumpido_id
                    agenda.cancelar("llegada_base", anterior)
                    registrar("interrupcion_retorno", estado.atenciones[anterior], fase=EU.RETORNANDO)
                tramos[despacho.llamado_id, "paciente"] = despacho.viaje
                registrar("despacho", estado.atenciones[despacho.llamado_id], 2)
                programar(despacho.viaje.fin_min, "inicio_escena", despacho.llamado_id)
        if estado.cola or any(u.estado != EU.DISPONIBLE or u.retorno is not None
                              or u.llamado_id is not None
                              or u.posicion != self.catalogos.bases[u.ambulancia.base_inicial].posicion
                              for u in estado.ambulancias.values()):
            raise RuntimeError("Agenda agotada con pacientes o unidades pendientes.")
        # Incluye el intervalo ocioso final de la ventana de admisión, incluso sin demanda.
        estado.minuto_actual = max(1080, estado.minuto_actual)
        instantanea()
        return ResultadoJornada(estado, tuple(registros), tuple(historial), tramos, sorteos)
