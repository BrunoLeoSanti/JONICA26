"""Manejo del robot con WASD en el modo felicidad. Logica pura, sin hardware.

En el modo felicidad los tres pines de senales pasan a manejar los motores (ver
MODO_PIN en config.py): PARE prende el motor izquierdo, GO el derecho y MUNECO
da marcha atras a los que esten prendidos. La velocidad no viaja por los cables:
la pone el Arduino, que acelera de a poco mientras se va recto.

    W       los dos motores          -> adelante
    S       los dos, en reversa      -> atras
    A       solo el derecho          -> gira a la izquierda
    D       solo el izquierdo        -> gira a la derecha
    S+A/S+D                          -> gira marcha atras
    nada                             -> frena
"""
from typing import Iterable, NamedTuple, Optional

import config

TECLAS_VALIDAS = frozenset("wasd")


class Motores(NamedTuple):
    izquierdo: bool
    derecho: bool
    reversa: bool


QUIETO = Motores(False, False, False)


def motores_de_teclas(teclas: Iterable[str]) -> Motores:
    t = {k.lower() for k in teclas}
    # Teclas opuestas apretadas a la vez se anulan.
    adelante, atras = "w" in t and "s" not in t, "s" in t and "w" not in t
    gira_izq, gira_der = "a" in t and "d" not in t, "d" in t and "a" not in t
    if not (adelante or atras or gira_izq or gira_der):
        return QUIETO
    # Girar es apagar la rueda del lado hacia el que se gira.
    return Motores(izquierdo=not gira_izq, derecho=not gira_der, reversa=atras)


class ControlTeclado:
    """Las ultimas teclas recibidas, con un vencimiento por seguridad.

    La pagina manda las teclas apretadas cada vez que cambian y las repite
    mientras haya alguna. Si dejan de llegar (se corto la red, se cerro la
    pestana con la W apretada), a los `tiempo_sin_teclas` segundos se apagan
    los motores en vez de seguir con la ultima orden.
    """

    def __init__(self, tiempo_sin_teclas: float = config.TIEMPO_SIN_TECLAS) -> None:
        self.tiempo_sin_teclas = tiempo_sin_teclas
        self._teclas: frozenset = frozenset()
        self._recibidas: Optional[float] = None

    def recibir(self, texto: str, ahora: float) -> None:
        """`texto` son las teclas apretadas juntas, por ejemplo "wa" o ""."""
        self._teclas = frozenset(texto.lower()) & TECLAS_VALIDAS
        self._recibidas = ahora

    def motores(self, ahora: float) -> Motores:
        if self._recibidas is None or ahora - self._recibidas > self.tiempo_sin_teclas:
            return QUIETO
        return motores_de_teclas(self._teclas)
