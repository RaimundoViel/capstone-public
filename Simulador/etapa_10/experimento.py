"""Prepara jornadas reproducibles e invoca un motor nuevo por replica."""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Callable, Protocol

from Simulador.etapa_1 import cargar_catalogos, crear_estado_inicial, ConfiguracionInicial
from Simulador.etapa_1.modelos import Catalogos, Escenario, EstadoSistema, EstadoLlamado, EstadoAmbulancia
from Simulador.etapa_2 import GeneradorDemanda
from Simulador.etapa_4 import CalculadorViajes
from Simulador.etapa_9 import RegistroAtencion
from .aleatoriedad import derivar_semilla, DuracionesReplica
from .modelos import PlanExperimento, RealizacionReplica, ResultadoReplica


ARCHIVOS_PARAMETROS = (
    "bases.csv", "hospitales.csv", "zonas.csv", "macrozonas.csv", "prioridades.csv",
    "bloques.csv", "congestion.csv", "probabilidades_zona.csv", "tiempo_escena.csv",
    "tiempo_entrega.csv", "constantes.json",
)


def huellas_parametros(raiz) -> tuple[tuple[str, str], ...]:
    carpeta = Path(raiz) / "Simulador" / "parametros"
    return tuple((n, sha256((carpeta / n).read_bytes()).hexdigest())
                 for n in sorted(ARCHIVOS_PARAMETROS))


def huellas_codigo() -> tuple[tuple[str, str], ...]:
    carpeta = Path(__file__).resolve().parents[1]
    return tuple((p.relative_to(carpeta).as_posix(), sha256(p.read_bytes()).hexdigest())
                 for p in sorted(carpeta.glob("etapa_*/*.py")))


def preparar_replica(raiz, escenario, numero: int, semilla_maestra: int = 42):
    PlanExperimento((escenario,), 1, semilla_maestra)
    if type(numero) is not int or numero < 1:
        raise ValueError("El numero de replica debe ser un entero positivo.")
    huellas = huellas_parametros(raiz)
    catalogos = cargar_catalogos(raiz)
    demanda = derivar_semilla(semilla_maestra, escenario.id, numero, "demanda")
    duraciones = derivar_semilla(semilla_maestra, escenario.id, numero, "duraciones")
    generador = GeneradorDemanda(catalogos, raiz, Escenario(escenario.id, demanda))
    llamados = generador.generar_jornada(dia=numero).llamados
    if huellas_parametros(raiz) != huellas:
        raise ValueError("Los parametros cambiaron durante la preparacion.")
    return RealizacionReplica(escenario, numero, semilla_maestra, demanda, duraciones,
                              huellas, llamados)


def preparar_experimento(raiz, plan: PlanExperimento) -> tuple[RealizacionReplica, ...]:
    realizaciones = tuple(preparar_replica(raiz, e, n, plan.semilla_maestra)
                         for e in plan.escenarios for n in range(1, plan.replicas + 1))
    if len({r.huellas_parametros for r in realizaciones}) != 1:
        raise ValueError("El experimento contiene versiones distintas de parametros.")
    return realizaciones


@dataclass
class ContextoReplica:
    realizacion: RealizacionReplica
    catalogos: Catalogos
    configuracion: ConfiguracionInicial
    estado: EstadoSistema
    viajes: CalculadorViajes
    duraciones: DuracionesReplica


class MotorReplica(Protocol):
    def ejecutar(self) -> None:
        """Procesa toda la demanda y los retornos, modificando contexto.estado."""
        ...


FabricaMotor = Callable[[ContextoReplica], MotorReplica]


def _validar_demanda(realizacion, catalogos, viajes):
    if not set(realizacion.escenario.bloques_evaluados) <= set(catalogos.bloques):
        raise ValueError("Bloques evaluados desconocidos.")
    ids = set()
    anterior = -1.0
    for l in realizacion.llamados:
        if not l.id or l.id in ids:
            raise ValueError("La demanda contiene IDs vacios o duplicados.")
        ids.add(l.id)
        if (l.recepcion_min < anterior
                or catalogos.bloque_en(l.recepcion_min, recepcion=True) != l.bloque_recepcion
                or l.prioridad_id not in catalogos.prioridades
                or viajes.geometria.zona_en(l.posicion) != l.zona_id):
            raise ValueError(f"Demanda invalida: {l.id}.")
        anterior = l.recepcion_min


def ejecutar_replica(raiz, realizacion: RealizacionReplica, configuracion: ConfiguracionInicial,
                    fabrica_motor: FabricaMotor, *, version_motor: str) -> ResultadoReplica:
    if not version_motor.strip():
        raise ValueError("Identificar la version del motor (por ejemplo, commit Git).")
    if huellas_parametros(raiz) != realizacion.huellas_parametros:
        raise ValueError("Los parametros difieren de los usados para preparar la replica.")
    codigo = huellas_codigo()
    catalogos = cargar_catalogos(raiz)
    viajes = CalculadorViajes(catalogos, raiz)
    _validar_demanda(realizacion, catalogos, viajes)
    etiqueta = Escenario(f"{realizacion.escenario.id}/replica-{realizacion.numero}",
                         realizacion.semilla_demanda)
    estado = crear_estado_inicial(catalogos, configuracion, etiqueta)
    flota_inicial = {i: u.ambulancia for i, u in estado.ambulancias.items()}
    contexto = ContextoReplica(realizacion, catalogos, configuracion, estado, viajes,
                               DuracionesReplica(raiz, realizacion.semilla_duraciones))
    motor = fabrica_motor(contexto)
    motor.ejecutar()
    if contexto.estado is not estado:
        raise ValueError("El motor debe actualizar el estado recibido, no reemplazarlo.")
    registros = _cerrar_replica(contexto, flota_inicial)
    if huellas_parametros(raiz) != realizacion.huellas_parametros or huellas_codigo() != codigo:
        raise ValueError("Las entradas o el codigo cambiaron durante la ejecucion.")
    return ResultadoReplica(realizacion, tuple(sorted(configuracion.ambulancias_por_base.items())),
                            registros, estado.minuto_actual, version_motor, codigo)


def _cerrar_replica(contexto, flota_inicial):
    estado, catalogos = contexto.estado, contexto.catalogos
    if (not isfinite(estado.minuto_actual) or estado.minuto_actual < 1080 or estado.cola
            or {i: u.ambulancia for i, u in estado.ambulancias.items()} != flota_inicial):
        raise ValueError("Replica incompleta: revisar reloj, cola y conservacion de flota.")
    for u in estado.ambulancias.values():
        if (u.estado != EstadoAmbulancia.DISPONIBLE or u.llamado_id is not None or u.retorno is not None
                or u.posicion != catalogos.bases[u.ambulancia.base_inicial].posicion):
            raise ValueError("La replica debe finalizar con toda la flota disponible en base.")
    llamados = contexto.realizacion.llamados
    if set(estado.atenciones) != {l.id for l in llamados}:
        raise ValueError("Los resultados deben cubrir exactamente los llamados generados.")
    registros, ocupaciones = [], {}
    for l in llamados:
        a = estado.atenciones[l.id]
        if (a.fin_retorno_min is None) == (a.interrupcion_retorno_min is None):
            raise ValueError(f"Retorno sin cierre exclusivo por llegada o interrupcion: {l.id}.")
        cierre = a.fin_retorno_min if a.fin_retorno_min is not None else a.interrupcion_retorno_min
        tiempos = (l.recepcion_min, a.despacho_min, a.llegada_escena_min, a.salida_escena_min,
                   a.llegada_destino_min, a.fin_entrega_min, a.inicio_retorno_min, cierre)
        if (a.llamado != l or a.estado != EstadoLlamado.COMPLETADO
                or a.ambulancia_id not in flota_inicial
                or any(t is None or not isfinite(t) for t in tiempos)
                or any(x > y for x, y in zip(tiempos, tiempos[1:]))
                or tiempos[-1] > estado.minuto_actual):
            raise ValueError(f"Atencion incompleta o incompatible: {l.id}.")
        destinos = (catalogos.hospitales if catalogos.prioridades[l.prioridad_id].destino == "hospital"
                    else contexto.configuracion.bases_activas)
        if a.destino_id not in destinos:
            raise ValueError(f"Destino incompatible: {l.id}.")
        ocupaciones.setdefault(a.ambulancia_id, []).append((a.despacho_min, a.fin_entrega_min))
        registros.append(RegistroAtencion(l.id, l.prioridad_id, l.zona_id, l.recepcion_min,
                                          a.despacho_min, a.llegada_escena_min))
    for intervalos in ocupaciones.values():
        intervalos.sort()
        if any(anterior[1] > siguiente[0] for anterior, siguiente in zip(intervalos, intervalos[1:])):
            raise ValueError("Una ambulancia tiene atenciones clinicas superpuestas.")
    return tuple(registros)


def ejecutar_experimento(raiz, realizaciones, configuracion, fabrica_motor, *, version_motor,
                         al_completar_replica: Callable[[int, int], None] | None = None):
    """Ejecuta en orden y notifica (completadas, total) tras cada cierre válido."""
    realizaciones = tuple(realizaciones)
    claves = [(r.escenario.id, r.numero) for r in realizaciones]
    if not claves or len(claves) != len(set(claves)):
        raise ValueError("Se requieren realizaciones distintas.")
    if len({r.huellas_parametros for r in realizaciones}) != 1:
        raise ValueError("No mezclar versiones de parametros en un experimento.")
    resultados = []
    for r in realizaciones:
        resultados.append(ejecutar_replica(raiz, r, configuracion, fabrica_motor,
                                          version_motor=version_motor))
        if al_completar_replica is not None:
            al_completar_replica(len(resultados), len(realizaciones))
    return tuple(resultados)
