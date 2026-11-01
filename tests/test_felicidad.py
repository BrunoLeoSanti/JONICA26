"""Tests de la logica pura del modo felicidad (sin Raspberry ni Hailo)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import config
from felicidad import SeguidorCaras, iou, nivel_de_valencia, persona_de_cara


def test_iou_cajas_iguales_es_uno():
    assert iou((0, 0, 1, 1), (0, 0, 1, 1)) == pytest.approx(1.0)


def test_iou_cajas_disjuntas_es_cero():
    assert iou((0, 0, 0.2, 0.2), (0.5, 0.5, 0.9, 0.9)) == 0.0


def test_iou_media_superposicion():
    assert iou((0, 0, 1, 1), (0.5, 0, 1.5, 1)) == pytest.approx(1 / 3)


def test_nivel_extremos():
    assert nivel_de_valencia(-1.0) == 0
    assert nivel_de_valencia(1.0) == 4


def test_nivel_en_cada_corte():
    eps = 1e-6
    for indice, corte in enumerate(config.CORTES_VALENCIA):
        assert nivel_de_valencia(corte - eps) == indice
        assert nivel_de_valencia(corte + eps) == indice + 1


def test_nivel_nan_y_fuera_de_rango():
    assert nivel_de_valencia(float("nan")) == 2
    assert nivel_de_valencia(5.0) == 4
    assert nivel_de_valencia(-5.0) == 0


def cara(x, y, lado=0.2):
    return (x, y, x + lado, y + lado)


def test_seguidor_mantiene_id_con_cara_que_se_mueve_poco():
    seguidor = SeguidorCaras()
    primero = seguidor.asignar([cara(0.3, 0.3)])
    segundo = seguidor.asignar([cara(0.31, 0.32)])
    assert primero == segundo


def test_seguidor_ids_distintos_para_caras_distintas():
    seguidor = SeguidorCaras()
    ids = seguidor.asignar([cara(0.1, 0.1), cara(0.6, 0.6)])
    assert len(set(ids)) == 2


def test_seguidor_no_intercambia_ids_en_cruce_corto():
    seguidor = SeguidorCaras()
    a, b = seguidor.asignar([cara(0.1, 0.4), cara(0.45, 0.4)])
    # Se acercan, pero cada una sigue pisando mas a su posicion anterior que a
    # la de la otra, y entre ellas casi no se superponen.
    a2, b2 = seguidor.asignar([cara(0.2, 0.4), cara(0.35, 0.4)])
    assert (a2, b2) == (a, b)


def test_seguidor_tolera_cuadro_sin_caras():
    seguidor = SeguidorCaras()
    (antes,) = seguidor.asignar([cara(0.3, 0.3)])
    assert seguidor.asignar([]) == []
    (despues,) = seguidor.asignar([cara(0.3, 0.3)])
    assert despues == antes


def test_seguidor_descarta_id_tras_cuadros_perdidos_max():
    seguidor = SeguidorCaras()
    (antes,) = seguidor.asignar([cara(0.3, 0.3)])
    for _ in range(config.CUADROS_PERDIDOS_MAX + 1):
        seguidor.asignar([])
    (despues,) = seguidor.asignar([cara(0.3, 0.3)])
    assert despues != antes


def test_suavizado_promedia_ultimas_valencias():
    seguidor = SeguidorCaras()
    (id_cara,) = seguidor.asignar([cara(0.3, 0.3)])
    resultado = None
    for valencia in (0, 0, 0, 0, 1):
        resultado = seguidor.suavizar(id_cara, valencia)
    assert resultado == pytest.approx(0.2)
    # La sexta empuja la primera fuera de la ventana de 5.
    assert seguidor.suavizar(id_cara, 1) == pytest.approx(0.4)


def test_suavizado_ignora_nan():
    seguidor = SeguidorCaras()
    (id_cara,) = seguidor.asignar([cara(0.3, 0.3)])
    seguidor.suavizar(id_cara, 0.5)
    assert seguidor.suavizar(id_cara, float("nan")) == pytest.approx(0.5)


def test_persona_de_cara_elige_la_mas_chica_que_la_contiene():
    personas = [(0.0, 0.0, 1.0, 1.0), (0.2, 0.1, 0.6, 0.9)]
    assert persona_de_cara((0.3, 0.15, 0.5, 0.3), personas) == 1


def test_persona_de_cara_sin_persona_devuelve_none():
    assert persona_de_cara((0.8, 0.8, 0.9, 0.9), [(0.0, 0.0, 0.3, 0.3)]) is None
    assert persona_de_cara((0.8, 0.8, 0.9, 0.9), []) is None
