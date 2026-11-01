"""Tests del recorte de caras y del dibujo de cajas y caritas."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from dibujo_felicidad import crear_caritas, dibujar, recortar_cara  # noqa: E402

ALTO, ANCHO = 200, 300


def cuadro():
    return np.full((ALTO, ANCHO, 3), 40, dtype=np.uint8)


def test_recorte_normal_tiene_el_tamano_esperado():
    # Caja de 100x80 px; con margen 0.15 crece 15 px a cada lado en x y 12 en y.
    caja = (100 / ANCHO, 60 / ALTO, 200 / ANCHO, 140 / ALTO)
    recorte = recortar_cara(cuadro(), caja, margen=0.15)
    assert recorte.shape == (80 + 24, 100 + 30, 3)


def test_recorte_en_el_borde_se_acota():
    for caja in [(-0.1, -0.1, 0.2, 0.3), (0.8, 0.7, 1.1, 1.1)]:
        recorte = recortar_cara(cuadro(), caja)
        assert recorte is not None
        assert recorte.shape[0] <= ALTO and recorte.shape[1] <= ANCHO


def test_recorte_degenerado_devuelve_none():
    assert recortar_cara(cuadro(), (0.5, 0.5, 0.5, 0.5), margen=0.0) is None


def test_recorte_es_una_copia():
    frame = cuadro()
    recorte = recortar_cara(frame, (0.2, 0.2, 0.6, 0.6))
    recorte[:] = 255
    assert frame.max() == 40


def test_crear_caritas_devuelve_cinco_distintas():
    caritas = crear_caritas(48)
    assert len(caritas) == 5
    assert all(c.size == (48, 48) for c in caritas)
    imagenes = {c.tobytes() for c in caritas}
    assert len(imagenes) == 5


def test_dibujar_sin_detecciones_no_cambia_el_cuadro():
    frame = cuadro()
    salida = dibujar(frame, [], [], crear_caritas(32))
    assert np.array_equal(salida, frame)
    assert salida is not frame


def test_dibujar_no_modifica_el_cuadro_recibido():
    frame = cuadro()
    dibujar(frame, [(0.1, 0.1, 0.5, 0.9)], [((0.2, 0.3, 0.4, 0.5), 4)], crear_caritas(32))
    assert frame.max() == 40


def test_dibujar_carita_en_el_borde_no_lanza():
    caritas = crear_caritas(32)
    for caja in [(0.0, 0.0, 0.1, 0.1), (0.9, 0.9, 1.0, 1.0), (0.0, 0.9, 0.1, 1.0)]:
        salida = dibujar(cuadro(), [], [(caja, 3)], caritas)
        assert salida.shape == (ALTO, ANCHO, 3)


def test_dibujar_persona_sin_cara_no_dibuja_carita():
    caja = (0.4, 0.5, 0.6, 0.8)
    caritas = crear_caritas(32)
    con = dibujar(cuadro(), [], [(caja, 4)], caritas)
    sin = dibujar(cuadro(), [], [(caja, None)], caritas)
    # La carita va justo arriba de la caja: esa franja queda intacta sin nivel.
    franja = (slice(int(0.5 * ALTO) - 34, int(0.5 * ALTO) - 2), slice(int(0.4 * ANCHO), int(0.4 * ANCHO) + 32))
    assert np.array_equal(sin[franja], cuadro()[franja])
    assert not np.array_equal(con[franja], cuadro()[franja])
