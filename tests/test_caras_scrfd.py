"""Tests de la decodificacion de SCRFD con tensores sinteticos.

La disposicion (NHWC, 2 anchors por celda, canal = anchor*4 + lado, distancias
l,t,r,b en unidades de stride, scores ya entre 0 y 1) se verifico contra la
salida real del Hailo-8 (ver docs/modo-felicidad-modelos.md).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from caras_scrfd import decodificar_scrfd  # noqa: E402

ENTRADA = (640, 640)


def salidas_vacias():
    """Tres escalas (stride 8, 16, 32) sin ninguna cara, mas los puntos que se ignoran."""
    salidas = {}
    for celdas in (80, 40, 20):
        salidas[f"cajas_{celdas}"] = np.zeros((1, celdas, celdas, 8), np.float32)
        salidas[f"scores_{celdas}"] = np.zeros((1, celdas, celdas, 2), np.float32)
        salidas[f"puntos_{celdas}"] = np.zeros((1, celdas, celdas, 20), np.float32)
    return salidas


def poner_cara(salidas, celdas, fila, col, anchor, score, ltrb):
    salidas[f"scores_{celdas}"][0, fila, col, anchor] = score
    salidas[f"cajas_{celdas}"][0, fila, col, anchor * 4 : anchor * 4 + 4] = ltrb


def test_decodifica_una_cara_conocida():
    salidas = salidas_vacias()
    # Stride 32, celda (10, 10) -> centro en (320, 320) px. Distancias de 2, 3, 2,
    # 3 strides -> caja de 256 a 416 en x y de 224 a 416 en y.
    poner_cara(salidas, 20, 10, 10, 0, 0.9, (2, 3, 2, 3))
    (cara,) = decodificar_scrfd(salidas, ENTRADA)
    assert cara.confianza == pytest.approx(0.9)
    assert cara.bbox == pytest.approx((256 / 640, 224 / 640, 384 / 640, 416 / 640), abs=1e-3)


def test_descarta_bajo_umbral():
    salidas = salidas_vacias()
    poner_cara(salidas, 20, 10, 10, 0, 0.2, (2, 2, 2, 2))
    assert decodificar_scrfd(salidas, ENTRADA, umbral=0.5) == []


def test_nms_une_cajas_superpuestas():
    salidas = salidas_vacias()
    poner_cara(salidas, 20, 10, 10, 0, 0.9, (2, 2, 2, 2))
    poner_cara(salidas, 20, 10, 10, 1, 0.7, (2, 2, 2, 2))
    poner_cara(salidas, 20, 10, 11, 0, 0.6, (2, 2, 2, 2))
    caras = decodificar_scrfd(salidas, ENTRADA)
    assert len(caras) == 1
    assert caras[0].confianza == pytest.approx(0.9)


def test_caras_lejanas_sobreviven_al_nms_y_salen_ordenadas():
    salidas = salidas_vacias()
    poner_cara(salidas, 20, 3, 3, 0, 0.6, (1, 1, 1, 1))
    poner_cara(salidas, 20, 15, 15, 0, 0.9, (1, 1, 1, 1))
    caras = decodificar_scrfd(salidas, ENTRADA)
    assert [round(c.confianza, 1) for c in caras] == [0.9, 0.6]


def test_sin_caras_devuelve_lista_vacia():
    assert decodificar_scrfd(salidas_vacias(), ENTRADA) == []


def test_cajas_se_acotan_al_cuadro():
    salidas = salidas_vacias()
    poner_cara(salidas, 80, 0, 0, 0, 0.9, (3, 3, 3, 3))
    (cara,) = decodificar_scrfd(salidas, ENTRADA)
    x1, y1, x2, y2 = cara.bbox
    assert (x1, y1) == (0.0, 0.0)
    assert 0.0 < x2 <= 1.0 and 0.0 < y2 <= 1.0


def test_acepta_salidas_sin_dimension_de_lote():
    con_lote = salidas_vacias()
    poner_cara(con_lote, 20, 10, 10, 0, 0.9, (2, 2, 2, 2))
    salidas = {k: v[0] for k, v in con_lote.items()}
    assert len(decodificar_scrfd(salidas, ENTRADA)) == 1
