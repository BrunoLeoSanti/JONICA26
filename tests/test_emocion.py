"""Tests del preprocesado del modelo de emocion (la parte que no necesita onnxruntime)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from emocion import EstimadorEmocion, preprocesar  # noqa: E402


def test_preprocesar_forma_y_tipo():
    for alto, ancho in [(60, 80), (500, 400)]:
        recorte = np.random.randint(0, 256, (alto, ancho, 3), dtype=np.uint8)
        x = preprocesar(recorte)
        assert x.shape == (1, 3, 224, 224)
        assert x.dtype == np.float32


def test_preprocesar_normaliza_como_el_modelo_oficial():
    # Un recorte todo blanco da (1 - media) / desvio en cada canal.
    x = preprocesar(np.full((50, 50, 3), 255, dtype=np.uint8))
    esperado = (1.0 - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
    assert x[0, :, 0, 0] == pytest.approx(esperado, abs=1e-4)


def test_preprocesar_no_modifica_la_entrada():
    recorte = np.full((50, 50, 3), 100, dtype=np.uint8)
    preprocesar(recorte)
    assert recorte.max() == 100


def test_falta_el_onnx_da_error_claro(tmp_path):
    ruta = tmp_path / "no_existe.onnx"
    with pytest.raises(FileNotFoundError, match="no_existe.onnx"):
        EstimadorEmocion(ruta)
