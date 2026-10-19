"""Un único cálculo determinista para ETA, traslados y retornos."""
import json
from hashlib import sha256
from math import fsum, isfinite
from pathlib import Path

from Simulador.etapa_1.modelos import Catalogos, Llamado, Punto
from .geometria import Geometria
from .modelos import Ruta, Segmento, Viaje


class CalculadorViajes:
    def __init__(self, catalogos: Catalogos, raiz: str | Path):
        self.catalogos = catalogos
        self.geometria = Geometria(catalogos)
        archivo = Path(raiz) / "Simulador" / "parametros" / "constantes.json"
        contenido = archivo.read_bytes()
        constantes = json.loads(contenido)
        esperadas = {"velocidad_base_kmh": 50, "velocidad_minima_kmh": 22,
                     "velocidad_maxima_kmh": 80, "multiplicador_retorno": 1}
        for clave, valor in esperadas.items():
            if type(constantes.get(clave)) not in (int, float) or constantes[clave] != valor:
                raise ValueError(f"{clave}: constante incompatible con etapa 0.")
        self.velocidad_base = constantes["velocidad_base_kmh"]
        self.velocidad_minima = constantes["velocidad_minima_kmh"]
        self.velocidad_maxima = constantes["velocidad_maxima_kmh"]
        self.multiplicador_retorno = constantes["multiplicador_retorno"]
        self.huella_constantes = sha256(contenido).hexdigest()

    def calcular_ruta(self, origen: Punto, destino: Punto, bloque_id: int,
                      multiplicador: float, orientacion: str) -> Ruta:
        if type(bloque_id) is not int or bloque_id not in self.catalogos.bloques:
            raise ValueError("Bloque inexistente.")
        if isinstance(multiplicador, bool) or not isfinite(multiplicador) or multiplicador <= 0:
            raise ValueError("El multiplicador debe ser finito y positivo.")
        if orientacion not in ("HV", "VH"):
            raise ValueError("La orientación debe ser HV o VH.")
        giro = Punto(destino.x, origen.y) if orientacion == "HV" else Punto(origen.x, destino.y)
        geometria = (self.geometria.segmentar(origen, giro)
                     + self.geometria.segmentar(giro, destino))
        segmentos = []
        for a, b, zona, distancia in geometria:
            factor = self.catalogos.congestion.get((zona, bloque_id))
            if factor is None or not isfinite(factor) or factor <= 0:
                raise ValueError(f"Congestión ausente o inválida: {zona}, bloque {bloque_id}.")
            segmentos.append(Segmento(a, b, zona, distancia, factor))
        distancia = fsum(s.distancia_km for s in segmentos)
        congestion = velocidad = None
        duracion = 0.0
        if distancia > 0:
            congestion = fsum(s.distancia_km * s.factor_congestion for s in segmentos) / distancia
            velocidad = min(self.velocidad_maxima, max(self.velocidad_minima,
                            self.velocidad_base / congestion * multiplicador))
            duracion = 60 * distancia / velocidad
        return Ruta(orientacion, origen, destino, bloque_id, multiplicador,
                    tuple(segmentos), distancia, congestion, velocidad, duracion)

    def calcular(self, origen: Punto, destino: Punto, bloque_id: int,
                 multiplicador: float) -> Ruta:
        """Menor tiempo entre HV/VH; empate exacto por identificador (HV primero)."""
        rutas = (self.calcular_ruta(origen, destino, bloque_id, multiplicador, sentido)
                 for sentido in ("HV", "VH"))
        return min(rutas, key=lambda r: (r.duracion_min, r.orientacion))

    def calcular_atencion(self, origen: Punto, destino: Punto, llamado: Llamado) -> Ruta:
        """Usar tanto para ETA al paciente como para traslado al destino."""
        if llamado.prioridad_id not in self.catalogos.prioridades:
            raise ValueError("Prioridad inexistente.")
        prioridad = self.catalogos.prioridades[llamado.prioridad_id]
        return self.calcular(origen, destino, llamado.bloque_recepcion,
                             prioridad.multiplicador_velocidad)

    def crear_retorno(self, origen: Punto, base_inicial_id: str, inicio_min: float) -> Viaje:
        """Fija bloque al comenzar; no modifica el estado ni libera la unidad."""
        if base_inicial_id not in self.catalogos.bases:
            raise ValueError("Base inicial inexistente.")
        bloque = self.catalogos.bloque_en(inicio_min)
        ruta = self.calcular(origen, self.catalogos.bases[base_inicial_id].posicion,
                             bloque, self.multiplicador_retorno)
        return Viaje(ruta, inicio_min)
