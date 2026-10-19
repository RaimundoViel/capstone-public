"""Verificación sin mutaciones del estado y del historial de una jornada."""
from collections import Counter, defaultdict
from itertools import groupby
from math import isclose, isfinite

from Simulador.etapa_1.modelos import EstadoAmbulancia as EU, EstadoLlamado as EL
from .modelos import ErrorConsistencia, InformeVerificacion


def _exigir(condicion, mensaje):
    if not condicion:
        raise ErrorConsistencia(mensaje)


def _igual(a, b):
    # Solo para cotejar resultados aritméticos; no agrupa eventos ni decide empates.
    return isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def _punto(a, b):
    return _igual(a.x, b.x) and _igual(a.y, b.y)


def verificar_estado(estado, catalogos, configuracion, *, cerrado=False):
    """Comprueba una instantánea estable (fuera de una transición parcial)."""
    configuracion.validar(catalogos)
    _exigir(isfinite(estado.minuto_actual) and estado.minuto_actual >= 0, "Reloj inválido.")
    esperada = {b: configuracion.ambulancias_por_base[b] for b in configuracion.bases_activas}
    real = Counter(u.ambulancia.base_inicial for u in estado.ambulancias.values())
    _exigir(len(estado.ambulancias) == 140 and dict(real) == esperada,
            "Flota: cantidad o asignación inicial incompatible.")
    _exigir(len(estado.cola) == len(set(estado.cola)), "Cola: identificadores duplicados.")
    pendientes = {i for i, a in estado.atenciones.items() if a.estado == EL.EN_COLA}
    _exigir(set(estado.cola) == pendientes, "Cola y atenciones pendientes no coinciden.")
    fases = {EU.VIAJE_PACIENTE: EL.ASIGNADO, EU.EN_ESCENA: EL.EN_ESCENA,
             EU.VIAJE_DESTINO: EL.EN_TRASLADO, EU.EN_ENTREGA: EL.EN_ENTREGA,
             EU.RETORNANDO: EL.COMPLETADO}
    for i, u in estado.ambulancias.items():
        _exigir(i == u.ambulancia.id, f"Unidad {i}: identificador incompatible.")
        if u.estado == EU.DISPONIBLE:
            _exigir(u.llamado_id is None and u.retorno is None
                    and u.posicion == catalogos.bases[u.ambulancia.base_inicial].posicion,
                    f"Unidad {i}: disponible en base con posición o asignación inválida.")
        else:
            a = estado.atenciones.get(u.llamado_id)
            _exigir(a is not None and a.ambulancia_id == i and a.estado == fases.get(u.estado),
                    f"Unidad {i}: fase o vínculo con atención inválido.")
            if u.estado == EU.RETORNANDO:
                _exigir(u.retorno is not None and a.fin_entrega_min is not None
                        and a.fin_retorno_min is None and a.interrupcion_retorno_min is None,
                        f"Unidad {i}: retorno vigente inválido.")
                _exigir(u.retorno.inicio_min <= estado.minuto_actual <= u.retorno.fin_min,
                        f"Unidad {i}: retorno fuera de su intervalo.")
            else:
                _exigir(u.retorno is None, f"Unidad {i}: atención clínica con retorno vigente.")
    for i, a in estado.atenciones.items():
        _exigir(i == a.llamado.id and a.llamado.recepcion_min <= estado.minuto_actual,
                f"Atención {i}: identificador o recepción futura inválidos.")
        if a.estado == EL.EN_COLA:
            _exigir(a.ambulancia_id is None and a.despacho_min is None,
                    f"Atención {i}: pendiente ya asignado.")
        elif a.estado != EL.COMPLETADO:
            u = estado.ambulancias.get(a.ambulancia_id)
            _exigir(u is not None and u.llamado_id == i and not u.disponible,
                    f"Atención {i}: unidad clínica compartida o ausente.")
    if cerrado:
        _exigir(estado.minuto_actual >= 1080 and not estado.cola
                and all(u.estado == EU.DISPONIBLE for u in estado.ambulancias.values())
                and all(a.estado == EL.COMPLETADO for a in estado.atenciones.values()),
                "Cierre: jornada incompleta o flota fuera de base.")


def verificar_jornada(resultado, catalogos, configuracion):
    """Verifica hitos, viajes, transiciones, precedencia y conteos temporales."""
    estado = resultado.estado
    verificar_estado(estado, catalogos, configuracion, cerrado=True)
    tipos = ("recepcion", "despacho", "inicio_escena", "salida_destino",
             "llegada_destino", "fin_entrega", "inicio_retorno")
    por_atencion = defaultdict(list)
    anterior = 0
    for e in resultado.registros:
        _exigir(isfinite(e.minuto) and anterior <= e.minuto <= estado.minuto_actual,
                "Eventos: reloj no monótono o fuera de jornada.")
        _exigir(e.llamado_id in estado.atenciones, "Evento de atención desconocida.")
        anterior = e.minuto
        por_atencion[e.llamado_id].append(e)
    _exigir(set(por_atencion) == set(estado.atenciones), "Eventos: faltan atenciones.")
    for i, a in estado.atenciones.items():
        l = a.llamado
        _exigir(l.prioridad_id in catalogos.prioridades and l.zona_id in catalogos.zonas,
                f"Atención {i}: prioridad o zona desconocida.")
        _exigir(catalogos.bloque_en(l.recepcion_min, recepcion=True) == l.bloque_recepcion,
                f"Atención {i}: bloque de recepción incorrecto.")
        _exigir((a.fin_retorno_min is None) != (a.interrupcion_retorno_min is None),
                f"Retorno {i}: requiere llegada o interrupción exclusivamente.")
        cierre = a.fin_retorno_min if a.fin_retorno_min is not None else a.interrupcion_retorno_min
        tiempos = (l.recepcion_min, a.despacho_min, a.llegada_escena_min, a.salida_escena_min,
                   a.llegada_destino_min, a.fin_entrega_min, a.inicio_retorno_min, cierre)
        _exigir(all(t is not None and isfinite(t) and t >= 0 for t in tiempos),
                f"Atención {i}: hitos incompletos o no finitos.")
        _exigir(all(x <= y for x, y in zip(tiempos, tiempos[1:])), f"Atención {i}: hitos desordenados.")
        ultimo = "llegada_base" if a.fin_retorno_min is not None else "interrupcion_retorno"
        eventos = por_atencion[i]
        _exigir(tuple(e.tipo for e in eventos) == (*tipos, ultimo), f"Atención {i}: secuencia inválida.")
        _exigir(tuple(e.secuencia_evento for e in eventos) == (1, 2, 3, 4, 5, 6, None, None),
                f"Atención {i}: numeración clínica inválida.")
        _exigir(all(e.minuto == t for e, t in zip(eventos, tiempos)), f"Atención {i}: marcas no coinciden.")
        _exigir(eventos[0].ambulancia_id is None and eventos[0].estado_unidad is None,
                f"Atención {i}: asignación anticipada en recepción.")
        _exigir(all(e.ambulancia_id == a.ambulancia_id for e in eventos[1:]),
                f"Atención {i}: cambia la unidad asignada.")
        prioridad = catalogos.prioridades[l.prioridad_id]
        destinos = catalogos.hospitales if prioridad.destino == "hospital" else {
            b: catalogos.bases[b] for b in configuracion.bases_activas}
        _exigir(a.destino_id in destinos, f"Atención {i}: destino no elegible.")
        _exigir(all(e.destino_id is None for e in eventos[:3])
                and all(e.destino_id == a.destino_id for e in eventos[3:]),
                f"Atención {i}: destino anticipado o inconsistente.")
        for fase, ini, fin in (("paciente", a.despacho_min, a.llegada_escena_min),
                               ("destino", a.salida_escena_min, a.llegada_destino_min),
                               ("retorno", a.inicio_retorno_min, cierre)):
            viaje = resultado.viajes.get((i, fase))
            _exigir(viaje is not None, f"Viaje {i}/{fase}: ausente.")
            _exigir(viaje.inicio_min == ini, f"Viaje {i}/{fase}: inicio incorrecto.")
            bloque = catalogos.bloque_en(ini) if fase == "retorno" else l.bloque_recepcion
            multiplicador = 1 if fase == "retorno" else prioridad.multiplicador_velocidad
            _exigir(viaje.ruta.bloque_id == bloque and viaje.ruta.multiplicador == multiplicador,
                    f"Viaje {i}/{fase}: factores temporales incorrectos.")
            if fase == "retorno" and ultimo == "interrupcion_retorno":
                _exigir(ini <= fin < viaje.fin_min, f"Retorno {i}: interrupción fuera del recorrido.")
            else:
                _exigir(_igual(viaje.fin_min, fin), f"Viaje {i}/{fase}: llegada incorrecta.")
            origen = eventos[1 if fase == "paciente" else 3 if fase == "destino" else 6].posicion
            destino = l.posicion if fase == "paciente" else destinos[a.destino_id].posicion if fase == "destino" else catalogos.bases[estado.ambulancias[a.ambulancia_id].ambulancia.base_inicial].posicion
            _exigir(_punto(viaje.ruta.origen, origen) and _punto(viaje.ruta.destino, destino),
                    f"Viaje {i}/{fase}: extremos incorrectos.")
            llegada = eventos[2 if fase == "paciente" else 4 if fase == "destino" else 7].posicion
            _exigir(_punto(viaje.posicion_en(fin), llegada), f"Viaje {i}/{fase}: posición final incorrecta.")
        _exigir(a.fin_entrega_min == a.inicio_retorno_min
                and a.bloque_retorno == catalogos.bloque_en(a.inicio_retorno_min),
                f"Retorno {i}: inicio o bloque incorrecto.")
        for fase, duracion in (("escena", a.salida_escena_min - a.llegada_escena_min),
                               ("entrega", a.fin_entrega_min - a.llegada_destino_min)):
            sorteo = resultado.duraciones.get((i, fase))
            _exigir(sorteo is not None and duracion > 0 and _igual(sorteo.duracion_min, duracion),
                    f"Duración {i}/{fase}: sorteo incompatible.")

    # Reconstruye la asignación y los conteos sin reutilizar la lógica de despacho.
    fases = {i: EU.DISPONIBLE for i in estado.ambulancias}
    dueños, pendientes = {}, set()
    posteriores = {}
    cambios = {
        "despacho": (EU.DISPONIBLE, EU.VIAJE_PACIENTE, EL.ASIGNADO),
        "inicio_escena": (EU.VIAJE_PACIENTE, EU.EN_ESCENA, EL.EN_ESCENA),
        "salida_destino": (EU.EN_ESCENA, EU.VIAJE_DESTINO, EL.EN_TRASLADO),
        "llegada_destino": (EU.VIAJE_DESTINO, EU.EN_ENTREGA, EL.EN_ENTREGA),
        "fin_entrega": (EU.EN_ENTREGA, EU.EN_ENTREGA, EL.COMPLETADO),
        "inicio_retorno": (EU.EN_ENTREGA, EU.RETORNANDO, EL.COMPLETADO),
        "llegada_base": (EU.RETORNANDO, EU.DISPONIBLE, EL.COMPLETADO),
        "interrupcion_retorno": (EU.RETORNANDO, EU.DISPONIBLE, EL.COMPLETADO),
    }
    def clave(i):
        l = estado.atenciones[i].llamado
        return catalogos.prioridades[l.prioridad_id].rango, l.recepcion_min, i
    interrupciones = {}
    for minuto, grupo in groupby(resultado.registros, key=lambda e: e.minuto):
        grupo = list(grupo)
        for n, e in enumerate(grupo):
            i, u = e.llamado_id, e.ambulancia_id
            if e.tipo == "recepcion":
                _exigir(e.estado_llamado == EL.EN_COLA, f"Recepción {i}: estado incorrecto.")
                pendientes.add(i)
                continue
            if e.tipo == "despacho":
                _exigir(not any(x.tipo in ("recepcion", "fin_entrega", "llegada_base") for x in grupo[n + 1:]),
                        f"Despacho {i}: anterior a recepciones o disponibilidades simultáneas.")
                _exigir(pendientes and i == min(pendientes, key=clave), f"Despacho {i}: precedencia incorrecta.")
                pendientes.remove(i)
                _exigir(u not in dueños, f"Despacho {i}: unidad {u} ya asignada.")
                if u in interrupciones:
                    t, p = interrupciones.pop(u)
                    _exigir(t == minuto and _punto(p, e.posicion), f"Despacho {i}: discontinuidad tras interrupción.")
                else:
                    _exigir(_punto(e.posicion, catalogos.bases[estado.ambulancias[u].ambulancia.base_inicial].posicion),
                            f"Despacho {i}: origen fuera de base sin retorno interrumpido.")
                dueños[u] = i
            _exigir(u in fases and dueños.get(u) == i, f"Evento {i}/{e.tipo}: unidad o asignación incompatible.")
            antes, despues, llamado = cambios[e.tipo]
            _exigir(fases[u] == antes and e.estado_llamado == llamado,
                    f"Evento {i}/{e.tipo}: transición inválida.")
            esperado = EU.RETORNANDO if e.tipo == "interrupcion_retorno" else despues
            _exigir(e.estado_unidad == esperado, f"Evento {i}/{e.tipo}: fase registrada incorrecta.")
            fases[u] = despues
            if e.tipo in ("llegada_base", "interrupcion_retorno"):
                del dueños[u]
            if e.tipo == "interrupcion_retorno":
                interrupciones[u] = (minuto, e.posicion)
        disponibles = sum(f in (EU.DISPONIBLE, EU.RETORNANDO) for f in fases.values())
        _exigir(not pendientes or disponibles == 0, "Cola esperando con recursos disponibles.")
        posteriores[minuto] = (len(pendientes), disponibles)
    _exigir(not pendientes and not dueños and not interrupciones, "Reconstrucción termina con pendientes.")
    historial = {}
    anterior = 0
    for h in resultado.historial:
        _exigir(isfinite(h.minuto) and anterior <= h.minuto <= estado.minuto_actual
                and type(h.pendientes) is int and 0 <= h.pendientes <= len(estado.atenciones)
                and type(h.disponibles) is int and 0 <= h.disponibles <= 140,
                "Historial: tiempos o conteos inválidos.")
        anterior = h.minuto
        historial[h.minuto] = (h.pendientes, h.disponibles)
    _exigir(resultado.historial and resultado.historial[0].minuto == 0
            and resultado.historial[0].pendientes == 0 and resultado.historial[0].disponibles == 140,
            "Historial: falta estado inicial.")
    for t, conteos in posteriores.items():
        _exigir(historial.get(t) == conteos, f"Historial: conteos incompatibles en minuto {t}.")
    _exigir(historial.get(estado.minuto_actual) == (0, 140), "Historial: cierre incorrecto.")
    return InformeVerificacion(140, len(estado.atenciones), len(resultado.registros),
        sum(a.interrupcion_retorno_min is not None for a in estado.atenciones.values()), estado.minuto_actual)
