"""Logica pura del modo felicidad: de valencia a carita, y seguimiento de caras.

No importa nada de hardware, asi que se testea en cualquier maquina
(ver tests/test_felicidad.py).

Las cajas son (x1, y1, x2, y2) normalizadas 0-1, igual que en `senales.py`.
"""
import math
from collections import deque
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import config

Caja = Tuple[float, float, float, float]


def iou(a: Caja, b: Caja) -> float:
    """Superposicion entre dos cajas: interseccion sobre union, de 0 a 1."""
    ancho = min(a[2], b[2]) - max(a[0], b[0])
    alto = min(a[3], b[3]) - max(a[1], b[1])
    if ancho <= 0 or alto <= 0:
        return 0.0
    interseccion = ancho * alto
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1])
    return interseccion / (union - interseccion)


def nivel_de_valencia(
    valencia: float, cortes: Sequence[float] = config.CORTES_VALENCIA
) -> int:
    """Convierte la valencia en el nivel de carita: 0 muy triste .. 4 muy feliz.

    Un NaN (un recorte raro puede producirlo) cae en el nivel del medio en vez
    de propagarse: es mas honesto mostrar una cara neutra que una al azar.
    """
    if math.isnan(valencia):
        return len(cortes) // 2
    return sum(1 for corte in cortes if valencia >= corte)


class SeguidorCaras:
    """Le da a cada cara un id estable entre cuadros y suaviza su valencia.

    Sin id estable no hay suavizado posible, y sin suavizado la carita parpadea
    entre niveles con cada cuadro. El emparejamiento es por superposicion de
    cajas: alcanza porque la camara va fija y las caras se mueven poco entre
    cuadros.
    """

    def __init__(
        self,
        iou_minimo: float = config.IOU_SEGUIMIENTO,
        perdidos_max: int = config.CUADROS_PERDIDOS_MAX,
        ventana: int = config.VENTANA_SUAVIZADO,
    ) -> None:
        self._iou_minimo = iou_minimo
        self._perdidos_max = perdidos_max
        self._ventana = ventana
        self._siguiente_id = 0
        self._cajas: Dict[int, Caja] = {}
        self._perdidos: Dict[int, int] = {}
        self._historial: Dict[int, Deque[float]] = {}

    def asignar(self, cajas: Sequence[Caja]) -> List[int]:
        """Devuelve un id por caja, reutilizando el de la cara del cuadro anterior."""
        pares = sorted(
            (
                (iou(caja, previa), indice, id_cara)
                for indice, caja in enumerate(cajas)
                for id_cara, previa in self._cajas.items()
            ),
            reverse=True,
        )
        ids: List[Optional[int]] = [None] * len(cajas)
        usados = set()
        for superposicion, indice, id_cara in pares:
            if superposicion < self._iou_minimo:
                break
            if ids[indice] is None and id_cara not in usados:
                ids[indice] = id_cara
                usados.add(id_cara)

        for id_cara in list(self._cajas):
            if id_cara in usados:
                self._perdidos[id_cara] = 0
                continue
            self._perdidos[id_cara] += 1
            if self._perdidos[id_cara] > self._perdidos_max:
                del self._cajas[id_cara], self._perdidos[id_cara]
                del self._historial[id_cara]

        resultado: List[int] = []
        for indice, caja in enumerate(cajas):
            id_cara = ids[indice]
            if id_cara is None:
                id_cara = self._siguiente_id
                self._siguiente_id += 1
                self._perdidos[id_cara] = 0
                self._historial[id_cara] = deque(maxlen=self._ventana)
            self._cajas[id_cara] = caja
            resultado.append(id_cara)
        return resultado

    def suavizar(self, id_cara: int, valencia: float) -> float:
        """Promedio de las ultimas valencias de esa cara (ignora los NaN).

        Si el id ya se olvido (el hilo de emocion trabaja con ids de un cuadro
        viejo mientras el seguimiento avanza) no hay historial que promediar:
        se devuelve el valor tal cual, y 0.0 si ni eso sirve.
        """
        historial = self._historial.get(id_cara)
        if historial is None:
            return 0.0 if math.isnan(valencia) else valencia
        if not math.isnan(valencia):
            historial.append(valencia)
        return sum(historial) / len(historial) if historial else 0.0


def persona_de_cara(cara: Caja, personas: Sequence[Caja]) -> Optional[int]:
    """Indice de la persona mas chica que contiene el centro de la cara.

    Se elige la mas chica para que, si una persona queda parada delante de
    otra, la cara se asigne a la de adelante y no a la caja grande de atras.
    """
    cx, cy = (cara[0] + cara[2]) / 2, (cara[1] + cara[3]) / 2
    mejor, area_mejor = None, math.inf
    for indice, p in enumerate(personas):
        if p[0] <= cx <= p[2] and p[1] <= cy <= p[3]:
            area = (p[2] - p[0]) * (p[3] - p[1])
            if area < area_mejor:
                mejor, area_mejor = indice, area
    return mejor
