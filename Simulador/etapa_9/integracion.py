"""Adaptación retrospectiva del resultado de etapa 7; no modifica el motor."""
import csv
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from Simulador.etapa_1.modelos import Catalogos, EstadoLlamado, EstadoAmbulancia
from Simulador.etapa_7.modelos import ResultadoJornada
from .exportar import exportar_kpis_csv
from .kpis import calcular_kpis
from .modelos import KPIResumen, RegistroAtencion


@dataclass(frozen=True)
class InformeJornada:
    registros_atencion: tuple[RegistroAtencion, ...]
    kpis: KPIResumen
    eventos_clinicos: tuple[dict, ...]
    eventos_internos: tuple[dict, ...]
    historial: tuple[dict, ...]


COMUNES = ["escenario_id", "semilla", "orden_registro", "atencion_id", "ambulancia_id",
           "prioridad_id", "zona_id", "bloque_recepcion", "base_inicial_id", "destino_id"]
CLINICOS = COMUNES + ["secuencia_evento", "tipo", "minuto", "x_km", "y_km"]
INTERNOS = COMUNES + ["tipo", "minuto", "bloque_retorno", "estado_unidad",
                      "estado_llamado", "x_km", "y_km", "duracion_retorno_efectiva_min",
                      "distancia_retorno_efectiva_km"]
HISTORIAL = ["escenario_id", "semilla", "orden_registro", "minuto", "pendientes", "disponibles"]


def adaptar_resultado_jornada(resultado: ResultadoJornada, catalogos: Catalogos) -> InformeJornada:
    """Exige una jornada cerrada y seis eventos concordantes con sus hitos."""
    estado = resultado.estado
    if (estado.cola or any(u.estado != EstadoAmbulancia.DISPONIBLE or u.llamado_id is not None
                          for u in estado.ambulancias.values())):
        raise ValueError("Se requiere una jornada cerrada, sin cola ni unidades ocupadas.")
    registros, marcas = [], {}
    for identificador, a in estado.atenciones.items():
        if (a.fin_retorno_min is None) == (a.interrupcion_retorno_min is None):
            raise ValueError("El retorno debe terminar en llegada o interrupción, exclusivamente.")
        cierre = a.fin_retorno_min if a.fin_retorno_min is not None else a.interrupcion_retorno_min
        tiempos = (a.llamado.recepcion_min, a.despacho_min, a.llegada_escena_min,
                   a.salida_escena_min, a.llegada_destino_min, a.fin_entrega_min,
                   a.inicio_retorno_min, cierre)
        if (a.llamado.id != identificador or a.estado != EstadoLlamado.COMPLETADO
                or a.ambulancia_id not in estado.ambulancias
                or a.destino_id is None
                or any(t is None or not isfinite(t) for t in tiempos)
                or any(x > y for x, y in zip(tiempos, tiempos[1:]))
                or cierre > estado.minuto_actual):
            raise ValueError(f"Atención incompleta o hitos incompatibles: {identificador}.")
        registros.append(RegistroAtencion(identificador, a.llamado.prioridad_id,
            a.llamado.zona_id, a.llamado.recepcion_min, a.despacho_min, a.llegada_escena_min))
        marcas[identificador] = tiempos
    kpis = calcular_kpis(registros, catalogos)
    clinicos, internos, vistos = [], [], set()
    tipos = ("recepcion", "despacho", "inicio_escena", "salida_destino", "llegada_destino", "fin_entrega")
    anterior = 0
    for orden, e in enumerate(resultado.registros):
        if e.llamado_id not in marcas or not isfinite(e.minuto) or e.minuto < anterior:
            raise ValueError("Registro desconocido o reloj no monótono.")
        anterior = e.minuto
        a = estado.atenciones[e.llamado_id]
        u = estado.ambulancias[a.ambulancia_id]
        fila = dict(zip(COMUNES, [estado.escenario.id, estado.escenario.semilla, orden,
            e.llamado_id, a.ambulancia_id, a.llamado.prioridad_id, a.llamado.zona_id,
            a.llamado.bloque_recepcion, u.ambulancia.base_inicial, a.destino_id]))
        fila.update(tipo=e.tipo, minuto=e.minuto, x_km=e.posicion.x, y_km=e.posicion.y)
        clave = (e.llamado_id, e.tipo)
        if clave in vistos:
            raise ValueError("Evento duplicado en la atención.")
        vistos.add(clave)
        if e.secuencia_evento is not None:
            n = e.secuencia_evento
            if (type(n) is not int or not 1 <= n <= 6 or e.tipo != tipos[n - 1]
                    or e.minuto != marcas[e.llamado_id][n - 1]):
                raise ValueError("Evento clínico incompatible con los hitos finales.")
            fila["secuencia_evento"] = n
            clinicos.append(fila)
        else:
            indice = {"inicio_retorno": 6, "llegada_base": 7, "interrupcion_retorno": 7}.get(e.tipo)
            if indice is None or e.minuto != marcas[e.llamado_id][indice]:
                raise ValueError("Evento interno incompatible con los hitos finales.")
            fila.update(bloque_retorno=a.bloque_retorno,
                        estado_unidad=e.estado_unidad.value if e.estado_unidad else None,
                        estado_llamado=e.estado_llamado.value)
            retorno = resultado.viajes[a.llamado.id, "retorno"]
            duracion = e.minuto - a.inicio_retorno_min
            fila.update(duracion_retorno_efectiva_min=duracion,
                        distancia_retorno_efectiva_km=(duracion * retorno.ruta.velocidad_kmh / 60
                                                     if retorno.ruta.velocidad_kmh is not None else 0))
            internos.append(fila)
    esperados = {(i, tipo) for i in marcas for tipo in (*tipos, "inicio_retorno",
        "llegada_base" if estado.atenciones[i].fin_retorno_min is not None else "interrupcion_retorno")}
    if vistos != esperados:
        raise ValueError("Faltan eventos de una o más atenciones.")
    historial = tuple(dict(zip(HISTORIAL, [estado.escenario.id, estado.escenario.semilla,
        orden, h.minuto, h.pendientes, h.disponibles])) for orden, h in enumerate(resultado.historial))
    return InformeJornada(tuple(registros), kpis, tuple(clinicos), tuple(internos), historial)


def exportar_resultado_jornada(resultado: ResultadoJornada, catalogos: Catalogos,
                               carpeta: str | Path) -> InformeJornada:
    """Valida/adapta antes de escribir; exporta una ejecución por carpeta."""
    informe = adaptar_resultado_jornada(resultado, catalogos)
    exportar_kpis_csv(informe.kpis, carpeta)
    for nombre, columnas, filas in (
        ("eventos_clinicos.csv", CLINICOS, informe.eventos_clinicos),
        ("eventos_internos.csv", INTERNOS, informe.eventos_internos),
        ("historial_cola_disponibilidad.csv", HISTORIAL, informe.historial),
    ):
        with (Path(carpeta) / nombre).open("w", encoding="utf-8", newline="") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=columnas)
            escritor.writeheader()
            escritor.writerows(filas)
    return informe
