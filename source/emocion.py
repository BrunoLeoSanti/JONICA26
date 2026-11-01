"""Valencia de una cara con HSEmotion (`enet_b0_8_va_mtl`), en la CPU.

La valencia es continua y va de triste (negativa) a feliz (positiva), asi que
sirve para una escala de caritas. Un clasificador de sonrisa solo dice si
sonrie o no y no distingue una cara neutra de una triste.

El .onnx tiene una sola salida de 10 valores: 8 logits de emocion, la
valencia y la activacion (en ese orden). Preprocesado: el de la libreria
oficial (RGB, 224x224, /255 y normalizacion de ImageNet).
"""
from pathlib import Path

import numpy as np
from PIL import Image

import config

TAMANO = 224
MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DESVIO = np.array([0.229, 0.224, 0.225], dtype=np.float32)
INDICE_VALENCIA = -2


def preprocesar(recorte: np.ndarray) -> np.ndarray:
    """Recorte RGB uint8 -> tensor (1, 3, 224, 224) float32 listo para el modelo."""
    chico = Image.fromarray(recorte).resize((TAMANO, TAMANO), Image.BILINEAR)
    x = (np.asarray(chico, dtype=np.float32) / 255.0 - MEDIA) / DESVIO
    return np.ascontiguousarray(x.transpose(2, 0, 1)[np.newaxis])


class EstimadorEmocion:
    def __init__(self, ruta=config.RUTA_ONNX_EMOCION) -> None:
        ruta = Path(ruta)
        if not ruta.is_file():
            raise FileNotFoundError(f"Falta el modelo de emocion: {ruta}")
        # Import diferido: onnxruntime solo esta en la Pi.
        import onnxruntime

        opciones = onnxruntime.SessionOptions()
        # Por defecto usa los 4 nucleos y le compite al video y a la captura.
        opciones.intra_op_num_threads = config.HILOS_EMOCION
        self._sesion = onnxruntime.InferenceSession(
            str(ruta), sess_options=opciones, providers=["CPUExecutionProvider"]
        )

    def valencia(self, recorte: np.ndarray) -> float:
        """Valencia de la cara, de -1 (triste) a 1 (feliz)."""
        salida = self._sesion.run(None, {"input": preprocesar(recorte)})[0][0]
        return float(np.clip(salida[INDICE_VALENCIA], -1.0, 1.0))
