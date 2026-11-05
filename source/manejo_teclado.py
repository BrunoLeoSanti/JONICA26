"""Manejo del robot con WASD en el modo felicidad. Logica pura, sin hardware.

En el modo felicidad los tres pines de senales pasan a manejar los motores (ver
MODO_PIN en config.py): PARE prende el motor izquierdo, GO el derecho y MUNECO
da marcha atras a los que esten prendidos. La velocidad no viaja por los cables:
la pone el Arduino, que acelera de a poco mientras se va recto.

    W       los dos motores          -> adelante
    S       los dos, en reversa      -> atras
    A       solo el derecho          -> gira a la izquierda
    D       solo el izquierdo        -> gira a la derecha
    W+A/W+D/S+A/S+D                  -> diagonal: gira y despues sigue recto
    nada                             -> frena

La diagonal no puede ser una rueda un poco mas rapida que la otra: cada motor
es un cable, prendido o apagado. Entonces se arma en el tiempo: mientras se
mantiene la combinacion, primero gira con una sola rueda TIEMPO_GIRO_DIAGONAL y
despues prende las dos, y el robot sigue en linea recta hacia donde quedo
apuntando (el Arduino ademas acelera de a poco al ir recto).
"""
from typing import Iterable, NamedTuple, Optional

import config

TECLAS_VALIDAS = frozenset("wasd")


class Motores(NamedTuple):
    izquierdo: bool
    derecho: bool
    reversa: bool


QUIETO = Motores(False, False, False)


def _direcciones(teclas: Iterable[str]):
    t = {k.lower() for k in teclas}
    # Teclas opuestas apretadas a la vez se anulan.
    adelante, atras = "w" in t and "s" not in t, "s" in t and "w" not in t
    gira_izq, gira_der = "a" in t and "d" not in t, "d" in t and "a" not in t
    return adelante, atras, gira_izq, gira_der


def es_diagonal(teclas: Iterable[str]) -> bool:
    adelante, atras, gira_izq, gira_der = _direcciones(teclas)
    return (adelante or atras) and (gira_izq or gira_der)


def motores_de_teclas(teclas: Iterable[str]) -> Motores:
    """Los motores al apretar las teclas; la diagonal, en su parte de giro."""
    adelante, atras, gira_izq, gira_der = _direcciones(teclas)
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

    def __init__(
        self,
        tiempo_sin_teclas: float = config.TIEMPO_SIN_TECLAS,
        tiempo_giro_diagonal: float = config.TIEMPO_GIRO_DIAGONAL,
    ) -> None:
        self.tiempo_sin_teclas = tiempo_sin_teclas
        self.tiempo_giro_diagonal = tiempo_giro_diagonal
        self._teclas: frozenset = frozenset()
        self._recibidas: Optional[float] = None
        self._desde: Optional[float] = None  # desde cuando estan estas mismas teclas

    def recibir(self, texto: str, ahora: float) -> None:
        """`texto` son las teclas apretadas juntas, por ejemplo "wa" o ""."""
        teclas = frozenset(texto.lower()) & TECLAS_VALIDAS
        # La pagina repite las mismas teclas cada 100 ms: eso no reinicia el giro.
        if teclas != self._teclas or self._desde is None:
            self._desde = ahora
        self._teclas = teclas
        self._recibidas = ahora

    def motores(self, ahora: float) -> Motores:
        if self._recibidas is None or ahora - self._recibidas > self.tiempo_sin_teclas:
            return QUIETO
        motores = motores_de_teclas(self._teclas)
        if es_diagonal(self._teclas) and ahora - self._desde >= self.tiempo_giro_diagonal:
            # Ya giro: las dos ruedas, en el sentido que corresponda.
            return Motores(True, True, motores.reversa)
        return motores
