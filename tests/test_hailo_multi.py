"""Tests de la parte pura de hailo_multi (el filtrado de personas del YOLO COCO)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from hailo_multi import personas_de_salida_nms  # noqa: E402


def salida_coco(por_clase):
    """80 clases vacias, con las detecciones dadas {indice: filas (N,5) yxyx+score}."""
    salida = [np.zeros((0, 5), np.float32) for _ in range(80)]
    for indice, filas in por_clase.items():
        salida[indice] = np.array(filas, dtype=np.float32)
    return salida


def test_deja_solo_la_clase_person():
    salida = salida_coco({
        0: [[0.1, 0.2, 0.9, 0.4, 0.8]],     # person
        2: [[0.0, 0.0, 0.5, 0.5, 0.99]],    # car: no tiene que salir
    })
    assert personas_de_salida_nms(salida) == [pytest.approx((0.2, 0.1, 0.4, 0.9))]


def test_descarta_personas_bajo_el_umbral():
    salida = salida_coco({0: [[0.1, 0.2, 0.9, 0.4, 0.2]]})
    assert personas_de_salida_nms(salida, umbral=0.4) == []


def test_sin_nadie_devuelve_lista_vacia():
    assert personas_de_salida_nms(salida_coco({})) == []


def test_acepta_la_disposicion_transpuesta():
    # (5, max_det) con relleno de ceros, como entrega el emulador del DFC.
    transpuesta = np.zeros((5, 100), np.float32)
    transpuesta[:, 0] = [0.1, 0.2, 0.9, 0.4, 0.8]
    salida = salida_coco({})
    salida[0] = transpuesta
    assert len(personas_de_salida_nms(salida)) == 1
