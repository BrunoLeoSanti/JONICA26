"""Decodificacion de las salidas crudas de SCRFD (detector de caras).

El .hef del Model Zoo no trae decodificado ni NMS: devuelve, por cada una de
tres escalas, cajas, scores y puntos de la cara. Aca se convierten en cajas.
No toca el hardware, asi que se testea en cualquier maquina
(ver tests/test_caras_scrfd.py).

Disposicion verificada contra el Hailo-8 real (docs/modo-felicidad-modelos.md):

- Un tensor NHWC por salida; la escala se deduce de su tamano (entrada / celdas)
  en vez de depender de los nombres `convNN`, que cambian entre scrfd_500m y
  scrfd_10g.
- 2 anchors por celda. En las cajas el canal es `anchor * 4 + lado`, con las
  distancias (izquierda, arriba, derecha, abajo) al centro del anchor, medidas
  en strides. El centro del anchor es `celda * stride`, sin medio pixel.
- Los scores ya vienen entre 0 y 1 (el chip aplica la sigmoide).
- Los tensores de 20 canales son los 5 puntos de la cara; no se usan.
"""
from dataclasses import dataclass
from typing import List, Mapping, Tuple

import numpy as np

import config
from felicidad import Caja, iou

ANCHORS_POR_CELDA = 2


@dataclass(frozen=True)
class CaraDetectada:
    bbox: Caja  # (x1, y1, x2, y2) normalizado 0-1
    confianza: float


def decodificar_scrfd(
    salidas: Mapping[str, np.ndarray],
    tam_entrada: Tuple[int, int],
    umbral: float = config.UMBRAL_CARA,
    iou_nms: float = 0.4,
) -> List[CaraDetectada]:
    """Devuelve las caras halladas, de mayor a menor confianza.

    `tam_entrada` es (alto, ancho) de la imagen que se le dio al modelo.
    """
    alto, ancho = tam_entrada
    cajas_crudas: List[Tuple[float, Caja]] = []

    tensores = [np.asarray(t, dtype=np.float32) for t in salidas.values()]
    tensores = [t[0] if t.ndim == 4 else t for t in tensores]
    cajas = {t.shape[:2]: t for t in tensores if t.shape[2] == ANCHORS_POR_CELDA * 4}
    scores = {t.shape[:2]: t for t in tensores if t.shape[2] == ANCHORS_POR_CELDA}

    for celdas, mapa_cajas in cajas.items():
        mapa_scores = scores.get(celdas)
        if mapa_scores is None:
            continue
        stride_y, stride_x = alto / celdas[0], ancho / celdas[1]
        filas, cols, anchors = np.where(mapa_scores > umbral)
        for fila, col, anchor in zip(filas, cols, anchors):
            izq, arr, der, aba = mapa_cajas[fila, col, anchor * 4 : anchor * 4 + 4]
            cx, cy = col * stride_x, fila * stride_y
            x1 = min(max((cx - izq * stride_x) / ancho, 0.0), 1.0)
            y1 = min(max((cy - arr * stride_y) / alto, 0.0), 1.0)
            x2 = min(max((cx + der * stride_x) / ancho, 0.0), 1.0)
            y2 = min(max((cy + aba * stride_y) / alto, 0.0), 1.0)
            cajas_crudas.append(
                (float(mapa_scores[fila, col, anchor]), (float(x1), float(y1), float(x2), float(y2)))
            )

    # NMS: la misma cara la proponen varios anchors y varias escalas a la vez.
    cajas_crudas.sort(key=lambda par: par[0], reverse=True)
    elegidas: List[CaraDetectada] = []
    for score, caja in cajas_crudas:
        if all(iou(caja, e.bbox) < iou_nms for e in elegidas):
            elegidas.append(CaraDetectada(bbox=caja, confianza=score))
    return elegidas
