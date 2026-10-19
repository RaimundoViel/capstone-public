"""Selección de destino compartida por el ciclo individual y la gestión de flota."""
def seleccionar_destino(catalogos, configuracion, viajes, llamado):
    prioridad = catalogos.prioridades[llamado.prioridad_id]
    candidatos = (catalogos.hospitales.values() if prioridad.destino == "hospital"
                  else (catalogos.bases[b] for b in configuracion.bases_activas))
    alternativas = [(d, viajes.calcular_atencion(llamado.posicion, d.posicion, llamado))
                    for d in candidatos]
    if not alternativas:
        raise ValueError("No existen destinos elegibles.")
    return min(alternativas, key=lambda par: (par[1].duracion_min, par[0].id))
