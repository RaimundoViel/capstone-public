"""Exportacion de demanda generada."""
import csv
from pathlib import Path

from .modelos import DemandaGenerada


def exportar_demanda_csv(demanda: DemandaGenerada, ruta: str | Path, catalogos) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            "escenario_id", "semilla", "dia", "llamado_id", "recepcion_min",
            "bloque_recepcion", "zona", "macrozona", "x_km", "y_km", "prioridad",
        ])
        for llamado in demanda.llamados:
            zona = catalogos.zonas[llamado.zona_id]
            escritor.writerow([
                demanda.escenario.id,
                demanda.escenario.semilla,
                demanda.dia,
                llamado.id,
                f"{llamado.recepcion_min:.6f}",
                llamado.bloque_recepcion,
                llamado.zona_id,
                zona.macrozona,
                f"{llamado.posicion.x:.6f}",
                f"{llamado.posicion.y:.6f}",
                llamado.prioridad_id,
            ])
