"""Construcción de una réplica vacía; todavía no hay motor de eventos."""
from .configuracion import ConfiguracionInicial, FLOTA_TOTAL
from .modelos import Ambulancia, Catalogos, Escenario, EstadoSistema, EstadoUnidad


def crear_estado_inicial(
    catalogos: Catalogos, configuracion: ConfiguracionInicial, escenario: Escenario
) -> EstadoSistema:
    configuracion.validar(catalogos)
    unidades = {}
    for base_id in configuracion.bases_activas:
        for _ in range(configuracion.ambulancias_por_base[base_id]):
            unidad_id = f"A{len(unidades) + 1:03d}"
            unidades[unidad_id] = EstadoUnidad(
                Ambulancia(unidad_id, base_id), catalogos.bases[base_id].posicion
            )
    estado = EstadoSistema(escenario=escenario, ambulancias=unidades)
    verificar_estado_inicial(estado, catalogos, configuracion)
    return estado


def verificar_estado_inicial(estado, catalogos, configuracion) -> None:
    """Control de conservación y localización, exclusivamente al inicio."""
    from collections import Counter
    configuracion.validar(catalogos)
    if len(estado.ambulancias) != FLOTA_TOTAL:
        raise ValueError("La flota inicial no contiene 140 unidades.")
    if estado.minuto_actual != 0 or estado.cola or estado.atenciones:
        raise ValueError("La réplica debe comenzar a las 06:00, sin pendientes.")
    asignacion = Counter()
    for identificador, unidad in estado.ambulancias.items():
        base_id = unidad.ambulancia.base_inicial
        if identificador != unidad.ambulancia.id or base_id not in catalogos.bases:
            raise ValueError("Identificador o base inicial inválidos.")
        asignacion[base_id] += 1
        if (unidad.estado.value != "disponible" or unidad.llamado_id is not None
                or unidad.retorno is not None
                or unidad.posicion != catalogos.bases[base_id].posicion):
            raise ValueError(f"{identificador}: no está disponible en su base inicial.")
    esperado = {b: n for b, n in configuracion.ambulancias_por_base.items() if n > 0}
    if dict(asignacion) != esperado:
        raise ValueError("La flota no respeta la asignación inicial.")
