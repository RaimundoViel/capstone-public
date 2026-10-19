"""Segmentación HV/VH adaptada de Trayectos.ipynb, sin ejecutar el notebook."""
from bisect import bisect_right

from Simulador.etapa_1.modelos import Catalogos, Punto


class Geometria:
    def __init__(self, catalogos: Catalogos):
        zonas = tuple(catalogos.zonas.values())
        if not zonas:
            raise ValueError("Se requiere un catálogo de zonas.")
        self.x_bordes = tuple(sorted({v for z in zonas
                                     for v in (z.limites.x_min, z.limites.x_max)}))
        self.y_bordes = tuple(sorted({v for z in zonas
                                     for v in (z.limites.y_min, z.limites.y_max)}))
        self._celdas = {}
        for z in zonas:
            r = z.limites
            columna = self.x_bordes.index(r.x_min)
            fila = self.y_bordes.index(r.y_min)
            if (self.x_bordes[columna + 1] != r.x_max
                    or self.y_bordes[fila + 1] != r.y_max
                    or (fila, columna) in self._celdas):
                raise ValueError("Las zonas deben formar una grilla rectangular sin solapes.")
            self._celdas[fila, columna] = z.id
        if len(self._celdas) != (len(self.x_bordes) - 1) * (len(self.y_bordes) - 1):
            raise ValueError("La grilla territorial tiene celdas ausentes.")

    def zona_en(self, punto: Punto) -> str:
        if not (self.x_bordes[0] <= punto.x <= self.x_bordes[-1]
                and self.y_bordes[0] <= punto.y <= self.y_bordes[-1]):
            raise ValueError("Punto fuera del territorio del catálogo.")
        # Bordes internos: celda superior/derecha. Borde exterior: última celda.
        columna = min(bisect_right(self.x_bordes, punto.x) - 1, len(self.x_bordes) - 2)
        fila = min(bisect_right(self.y_bordes, punto.y) - 1, len(self.y_bordes) - 2)
        return self._celdas[fila, columna]

    def segmentar(self, origen: Punto, destino: Punto):
        """Devuelve (origen, destino, zona, distancia) en orden de recorrido."""
        self.zona_en(origen)
        self.zona_en(destino)
        if origen == destino:
            return ()
        horizontal = origen.y == destino.y
        if not horizontal and origen.x != destino.x:
            raise ValueError("Solo se segmentan líneas horizontales o verticales.")
        a, b = (origen.x, destino.x) if horizontal else (origen.y, destino.y)
        bordes = self.x_bordes if horizontal else self.y_bordes
        cortes = sorted([a, b] + [v for v in bordes if min(a, b) < v < max(a, b)],
                        reverse=b < a)
        puntos = [Punto(v, origen.y) if horizontal else Punto(origen.x, v)
                  for v in cortes]
        return tuple((p, q, self.zona_en(Punto((p.x + q.x) / 2, (p.y + q.y) / 2)),
                      abs(q.x - p.x) + abs(q.y - p.y))
                     for p, q in zip(puntos, puntos[1:]))
