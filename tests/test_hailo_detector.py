"""Tests del parseo de la salida NMS del Hailo.

No necesitan el acelerador: el parser se prueba con arrays sinteticos con la
misma forma que devuelve HailoRT. Esto importa porque un parseo mal hecho es
la causa tipica de "el modelo compila pero no detecta nada".
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from hailo_detector import parsear_salida_nms  # noqa: E402

ETIQUETAS = ["PARE", "semaforoverde"]


def test_salida_vacia_no_da_detecciones():
    salida = [np.zeros((0, 5), dtype=np.float32) for _ in ETIQUETAS]
    assert parsear_salida_nms(salida, ETIQUETAS) == []


def test_una_deteccion_se_mapea_a_su_clase():
    salida = [
        np.array([[0.1, 0.2, 0.5, 0.6, 0.87]], dtype=np.float32),  # PARE
        np.zeros((0, 5), dtype=np.float32),
    ]
    dets = parsear_salida_nms(salida, ETIQUETAS)
    assert len(dets) == 1
    assert dets[0].nombre == "PARE"
    assert dets[0].confianza == pytest.approx(0.87, abs=1e-6)


def test_el_bbox_se_reordena_de_yxyx_a_xyxy():
    """HailoRT entrega (y_min, x_min, y_max, x_max); el resto del codigo usa xyxy."""
    salida = [
        np.array([[0.1, 0.2, 0.5, 0.6, 0.9]], dtype=np.float32),
        np.zeros((0, 5), dtype=np.float32),
    ]
    x1, y1, x2, y2 = parsear_salida_nms(salida, ETIQUETAS)[0].bbox
    assert (x1, y1, x2, y2) == pytest.approx((0.2, 0.1, 0.6, 0.5), abs=1e-6)


def test_el_indice_de_clase_sigue_el_orden_de_etiquetas():
    salida = [
        np.zeros((0, 5), dtype=np.float32),
        np.array([[0.0, 0.0, 1.0, 1.0, 0.5]], dtype=np.float32),  # semaforoverde
    ]
    assert parsear_salida_nms(salida, ETIQUETAS)[0].nombre == "semaforoverde"


def test_varias_detecciones_en_varias_clases():
    salida = [
        np.array([[0.0, 0.0, 0.1, 0.1, 0.4],
                  [0.2, 0.2, 0.3, 0.3, 0.6]], dtype=np.float32),
        np.array([[0.5, 0.5, 0.9, 0.9, 0.8]], dtype=np.float32),
    ]
    dets = parsear_salida_nms(salida, ETIQUETAS)
    assert len(dets) == 3
    assert sorted(d.nombre for d in dets) == ["PARE", "PARE", "semaforoverde"]


def test_filtra_por_confianza_minima():
    salida = [
        np.array([[0.0, 0.0, 0.1, 0.1, 0.05]], dtype=np.float32),
        np.zeros((0, 5), dtype=np.float32),
    ]
    assert parsear_salida_nms(salida, ETIQUETAS, conf_minima=0.1) == []


def test_mas_clases_en_la_salida_que_etiquetas_no_explota():
    """Si el .hef se compilo con otra cantidad de clases, queremos un error
    claro y no un IndexError enterrado."""
    salida = [np.zeros((0, 5), dtype=np.float32) for _ in range(80)]
    with pytest.raises(ValueError, match="clases"):
        parsear_salida_nms(salida, ETIQUETAS)


# --- Disposicion transpuesta -------------------------------------------------
# El emulador del Dataflow Compiler entrega (5, max_det) en vez de (N, 5):
# un campo por fila y una deteccion por columna, con relleno de ceros. Leerlo
# como si fuera (N, 5) no da error, da cero detecciones -- indistinguible de
# "el modelo no detecta nada".

def test_acepta_la_disposicion_transpuesta():
    """(5, max_det): cada COLUMNA es una deteccion."""
    arr = np.zeros((5, 100), dtype=np.float32)
    arr[:, 0] = [0.1, 0.2, 0.5, 0.6, 0.87]   # y1, x1, y2, x2, score
    salida = [arr, np.zeros((5, 100), dtype=np.float32)]

    dets = parsear_salida_nms(salida, ETIQUETAS, conf_minima=0.25)
    assert len(dets) == 1
    assert dets[0].nombre == "PARE"
    assert dets[0].confianza == pytest.approx(0.87, abs=1e-6)
    assert dets[0].bbox == pytest.approx((0.2, 0.1, 0.6, 0.5), abs=1e-6)


def test_el_relleno_de_la_transpuesta_no_cuenta():
    """Las columnas vacias son relleno, no detecciones de score cero."""
    arr = np.zeros((5, 100), dtype=np.float32)
    arr[:, 0] = [0.1, 0.1, 0.2, 0.2, 0.9]
    arr[:, 1] = [0.3, 0.3, 0.4, 0.4, 0.8]
    dets = parsear_salida_nms([arr, np.zeros((5, 100), dtype=np.float32)],
                              ETIQUETAS, conf_minima=0.25)
    assert len(dets) == 2


def test_varias_detecciones_transpuestas_en_ambas_clases():
    a = np.zeros((5, 100), dtype=np.float32)
    a[:, 0] = [0.0, 0.0, 0.1, 0.1, 0.6]
    b = np.zeros((5, 100), dtype=np.float32)
    b[:, 0] = [0.5, 0.5, 0.9, 0.9, 0.7]
    dets = parsear_salida_nms([a, b], ETIQUETAS, conf_minima=0.25)
    assert sorted(d.nombre for d in dets) == ["PARE", "semaforoverde"]


def test_la_disposicion_normal_sigue_funcionando():
    """No romper el formato (N, 5) al agregar soporte para el transpuesto."""
    salida = [
        np.array([[0.1, 0.2, 0.5, 0.6, 0.9]], dtype=np.float32),
        np.zeros((0, 5), dtype=np.float32),
    ]
    dets = parsear_salida_nms(salida, ETIQUETAS)
    assert len(dets) == 1
    assert dets[0].bbox == pytest.approx((0.2, 0.1, 0.6, 0.5), abs=1e-6)
