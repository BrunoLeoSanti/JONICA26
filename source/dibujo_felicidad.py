"""Recorte de caras y dibujo de cajas y caritas sobre el cuadro de video.

Las caritas se dibujan a mano con Pillow en vez de usar emojis de fuente: la
Pi puede no tener una fuente con emojis, y asi el resultado no depende del
sistema. Sin hardware, se testea en cualquier maquina
(ver tests/test_dibujo_felicidad.py).
"""
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

from felicidad import Caja

COLOR_PERSONA = (60, 140, 255)
COLOR_CARA = (60, 220, 90)

# De muy triste a muy feliz: azul frio hasta amarillo calido.
COLORES_CARITA = [
    (110, 140, 235),
    (150, 180, 225),
    (225, 225, 170),
    (250, 215, 70),
    (255, 195, 20),
]


def recortar_cara(
    frame: np.ndarray, caja: Caja, margen: float = 0.15
) -> Optional[np.ndarray]:
    """Recorta la cara con un margen proporcional, acotado al cuadro.

    El modelo de emocion rinde mejor con un poco de contexto alrededor de la
    cara, y una cara pegada al borde de la imagen es normal, no un error.
    Devuelve una copia, o None si queda un recorte inservible (menos de 2 px).
    """
    alto, ancho = frame.shape[:2]
    x1, y1, x2, y2 = caja
    mx, my = (x2 - x1) * margen, (y2 - y1) * margen
    px1 = max(int(round((x1 - mx) * ancho)), 0)
    py1 = max(int(round((y1 - my) * alto)), 0)
    px2 = min(int(round((x2 + mx) * ancho)), ancho)
    py2 = min(int(round((y2 + my) * alto)), alto)
    if px2 - px1 < 2 or py2 - py1 < 2:
        return None
    return frame[py1:py2, px1:px2].copy()


def crear_caritas(tamano: int) -> List[Image.Image]:
    """Cinco caritas RGBA de `tamano` px, indice = nivel (0 triste .. 4 feliz)."""
    caritas = []
    for nivel, color in enumerate(COLORES_CARITA):
        img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        grosor = max(tamano // 16, 1)
        d.ellipse([1, 1, tamano - 2, tamano - 2], fill=color + (255,), outline=(40, 40, 40, 255), width=grosor)

        ojo = max(tamano // 10, 1)
        for cx in (tamano * 0.32, tamano * 0.68):
            d.ellipse([cx - ojo, tamano * 0.35 - ojo, cx + ojo, tamano * 0.35 + ojo], fill=(40, 40, 40, 255))

        # Boca: un arco hacia abajo (sonrisa) o hacia arriba (mueca), mas
        # profundo cuanto mas extremo el nivel; el del medio es una recta.
        x1, x2 = tamano * 0.27, tamano * 0.73
        negro = (40, 40, 40, 255)
        if nivel == 2:
            d.line([x1, tamano * 0.70, x2, tamano * 0.70], fill=negro, width=grosor)
        elif nivel >= 3:
            arriba, alto_arco = {3: (0.50, 0.30), 4: (0.46, 0.40)}[nivel]
            d.arc([x1, tamano * arriba, x2, tamano * (arriba + alto_arco)], 20, 160, fill=negro, width=grosor)
        else:
            abajo, alto_arco = {1: (0.85, 0.20), 0: (0.88, 0.32)}[nivel]
            d.arc([x1, tamano * (abajo - alto_arco), x2, tamano * abajo], 200, 340, fill=negro, width=grosor)
        caritas.append(img)
    return caritas


def dibujar(
    frame: np.ndarray,
    personas: Sequence[Caja],
    caras: Sequence[Tuple[Caja, Optional[int]]],
    caritas: Sequence[Image.Image],
) -> np.ndarray:
    """Devuelve una copia del cuadro con las cajas y una carita por cara.

    `caras` trae cada caja junto a su nivel (0-4). Una cara sin nivel, o una
    persona sin cara, se dibuja sin carita: es lo que se vio y nada mas.
    """
    alto, ancho = frame.shape[:2]
    imagen = Image.fromarray(frame.copy())
    d = ImageDraw.Draw(imagen)
    grosor = max(ancho // 400, 2)

    for x1, y1, x2, y2 in personas:
        d.rectangle([x1 * ancho, y1 * alto, x2 * ancho, y2 * alto], outline=COLOR_PERSONA, width=grosor)

    for (x1, y1, x2, y2), nivel in caras:
        px1, py1, px2, py2 = x1 * ancho, y1 * alto, x2 * ancho, y2 * alto
        d.rectangle([px1, py1, px2, py2], outline=COLOR_CARA, width=grosor)
        if nivel is None:
            continue
        carita = caritas[nivel]
        lado = carita.size[0]
        # Arriba de la caja; si no entra (cara pegada al borde superior), abajo.
        y = py1 - lado - 2
        if y < 0:
            y = py2 + 2
        x = min(max(int(px1), 0), max(ancho - lado, 0))
        y = min(max(int(y), 0), max(alto - lado, 0))
        imagen.paste(carita, (x, y), carita)

    return np.array(imagen)
