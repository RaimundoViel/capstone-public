"""Calculo de KPIs desde registros de atenciones completadas."""
from collections import defaultdict
from statistics import mean

from Simulador.etapa_1.modelos import Catalogos

from .modelos import KPIResumen, RegistroAtencion, ZonaCobertura


def _percentil(valores: list[float], p: float) -> float:
    if not valores:
        raise ValueError("No se puede calcular percentil sin datos.")
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    posicion = (len(ordenados) - 1) * p / 100
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    peso = posicion - inferior
    return ordenados[inferior] * (1 - peso) + ordenados[superior] * peso


def _agrupar(registros: list[RegistroAtencion], atributo: str) -> dict[str, list[RegistroAtencion]]:
    grupos: dict[str, list[RegistroAtencion]] = defaultdict(list)
    for registro in registros:
        grupos[getattr(registro, atributo)].append(registro)
    return dict(grupos)


def _validar_registros(registros: list[RegistroAtencion], catalogos: Catalogos) -> None:
    ids = [registro.atencion_id for registro in registros]
    if len(ids) != len(set(ids)):
        raise ValueError("Los atencion_id deben ser unicos.")
    for registro in registros:
        if registro.prioridad_id not in catalogos.prioridades:
            raise ValueError(f"Prioridad inexistente: {registro.prioridad_id}.")
        if registro.zona_id not in catalogos.zonas:
            raise ValueError(f"Zona inexistente: {registro.zona_id}.")


def calcular_kpis(
    registros: list[RegistroAtencion],
    catalogos: Catalogos,
    umbral_cobertura_zona: float = 0.8,
) -> KPIResumen:
    """Calcula los seis KPIs vigentes desde una tabla de atenciones cerradas."""
    if not 0 <= umbral_cobertura_zona <= 1:
        raise ValueError("umbral_cobertura_zona debe estar entre 0 y 1.")
    registros = list(registros)
    _validar_registros(registros, catalogos)
    if not registros:
        return KPIResumen(0, {}, {}, {}, {}, None, None, {})

    por_prioridad = _agrupar(registros, "prioridad_id")
    por_zona = _agrupar(registros, "zona_id")

    promedio_prioridad = {
        prioridad: mean(r.respuesta_min for r in grupo)
        for prioridad, grupo in sorted(por_prioridad.items())
    }
    promedio_zona = {
        zona: mean(r.respuesta_min for r in grupo)
        for zona, grupo in sorted(por_zona.items())
    }
    cumplimiento_prioridad = {}
    percentiles_prioridad = {}
    for prioridad, grupo in sorted(por_prioridad.items()):
        objetivo = catalogos.prioridades[prioridad].objetivo_min
        cumplimiento_prioridad[prioridad] = (
            100 * sum(r.respuesta_min <= objetivo for r in grupo) / len(grupo)
        )
        respuestas = [r.respuesta_min for r in grupo]
        percentiles_prioridad[prioridad] = {
            "p90": _percentil(respuestas, 90),
            "p95": _percentil(respuestas, 95),
            "p99": _percentil(respuestas, 99),
        }

    porcentaje_espera = 100 * sum(r.espera_recurso > 0 for r in registros) / len(registros)
    cobertura_por_zona = {}
    for zona, grupo in sorted(por_zona.items()):
        prioridad_critica = min(
            {r.prioridad_id for r in grupo},
            key=lambda p: (catalogos.prioridades[p].rango, p),
        )
        grupo_critico = [r for r in grupo if r.prioridad_id == prioridad_critica]
        objetivo = catalogos.prioridades[prioridad_critica].objetivo_min
        cumplimiento = sum(r.respuesta_min <= objetivo for r in grupo_critico) / len(grupo_critico)
        cobertura_por_zona[zona] = ZonaCobertura(
            zona_id=zona,
            prioridad_critica_id=prioridad_critica,
            llamados_prioridad_critica=len(grupo_critico),
            cumplimiento_prioridad_critica_pct=100 * cumplimiento,
            cubierta=cumplimiento >= umbral_cobertura_zona,
        )
    porcentaje_zonas_cubiertas = (
        100 * sum(detalle.cubierta for detalle in cobertura_por_zona.values())
        / len(cobertura_por_zona)
    )

    return KPIResumen(
        total_atenciones=len(registros),
        tiempo_promedio_respuesta_por_prioridad=promedio_prioridad,
        tiempo_promedio_respuesta_por_zona=promedio_zona,
        cumplimiento_objetivo_por_prioridad_pct=cumplimiento_prioridad,
        percentiles_respuesta_por_prioridad=percentiles_prioridad,
        porcentaje_llamadas_con_espera_recurso=porcentaje_espera,
        porcentaje_zonas_cobertura_adecuada=porcentaje_zonas_cubiertas,
        cobertura_por_zona=cobertura_por_zona,
    )
