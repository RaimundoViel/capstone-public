"""Exportacion simple de KPIs a CSV."""
import csv
from pathlib import Path

from .modelos import KPIResumen


def _porcentaje(valor):
    return "" if valor is None else f"{valor:.6f}"


def exportar_kpis_csv(resumen: KPIResumen, carpeta: str | Path) -> None:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)

    with (carpeta / "kpi_01_respuesta_por_prioridad.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["prioridad", "respuesta_promedio_min"])
        for prioridad, valor in resumen.tiempo_promedio_respuesta_por_prioridad.items():
            escritor.writerow([prioridad, f"{valor:.6f}"])

    with (carpeta / "kpi_02_respuesta_por_zona.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["zona", "respuesta_promedio_min"])
        for zona, valor in resumen.tiempo_promedio_respuesta_por_zona.items():
            escritor.writerow([zona, f"{valor:.6f}"])

    with (carpeta / "kpi_03_cumplimiento_por_prioridad.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["prioridad", "cumplimiento_objetivo_pct"])
        for prioridad, valor in resumen.cumplimiento_objetivo_por_prioridad_pct.items():
            escritor.writerow([prioridad, f"{valor:.6f}"])

    with (carpeta / "kpi_04_percentiles_por_prioridad.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["prioridad", "p90_min", "p95_min", "p99_min"])
        for prioridad, valores in resumen.percentiles_respuesta_por_prioridad.items():
            escritor.writerow([
                prioridad,
                f"{valores['p90']:.6f}",
                f"{valores['p95']:.6f}",
                f"{valores['p99']:.6f}",
            ])

    with (carpeta / "kpi_05_espera_recurso.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["total_atenciones", "llamadas_con_espera_recurso_pct"])
        escritor.writerow([
            resumen.total_atenciones,
            _porcentaje(resumen.porcentaje_llamadas_con_espera_recurso),
        ])

    with (carpeta / "kpi_06_cobertura_geografica.csv").open(
        "w", encoding="utf-8", newline=""
    ) as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            "zona", "prioridad_critica", "llamados_prioridad_critica",
            "cumplimiento_prioridad_critica_pct", "cubierta",
        ])
        for zona, detalle in resumen.cobertura_por_zona.items():
            escritor.writerow([
                zona,
                detalle.prioridad_critica_id,
                detalle.llamados_prioridad_critica,
                f"{detalle.cumplimiento_prioridad_critica_pct:.6f}",
                int(detalle.cubierta),
            ])

    with (carpeta / "resumen_ejecucion.csv").open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["total_atenciones", "llamadas_con_espera_recurso_pct",
                           "zonas_con_demanda", "zonas_cubiertas", "cobertura_adecuada_pct"])
        escritor.writerow([resumen.total_atenciones,
                           _porcentaje(resumen.porcentaje_llamadas_con_espera_recurso),
                           resumen.zonas_con_demanda, resumen.zonas_cubiertas,
                           _porcentaje(resumen.porcentaje_zonas_cobertura_adecuada)])
