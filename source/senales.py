"""Maquina de estados que traduce detecciones en estado de los pines GPIO.

Esta logica estaba mezclada dentro del bucle principal en la version 2025.
Separarla tiene dos ventajas: el bucle queda legible, y esto se puede testear
en cualquier computadora sin Raspberry, sin camara y sin Hailo
(ver tests/test_senales.py).

No importa nada de hardware a proposito. Recibe detecciones y el tiempo
actual, y devuelve que deberia valer cada pin.
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import config


@dataclass(frozen=True)
class Deteccion:
    """Una deteccion, independiente del motor de inferencia que la produjo."""
    nombre: str
    confianza: float
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) normalizado 0-1


def proporcion_caja(d: Deteccion) -> float:
    """Alto / ancho de la caja en pixeles reales.

    La caja viene normalizada 0-1 y la imagen es 4:3 (la del Hailo se estira a
    640x640, pero sale del mismo campo del sensor): sin pasar a pixeles, una
    caja cuadrada en la realidad daria 0.75.
    """
    x1, y1, x2, y2 = d.bbox
    ancho_sensor, alto_sensor = config.MODO_SENSOR
    ancho = (x2 - x1) * ancho_sensor
    return (y2 - y1) * alto_sensor / ancho if ancho > 0 else 0.0


@dataclass(frozen=True)
class EstadoSalidas:
    """Que tiene que valer cada pin en este instante (modo pista)."""
    pare: bool
    go: bool
    muneco: bool = False


class Enganche:
    """Un pin que, al dispararse, queda activo una duracion fija.

    Solo dispara en el flanco: volver a ver la senal mientras ya esta activo no
    extiende el tiempo.
    """

    def __init__(self, duracion: float) -> None:
        self.duracion = duracion
        self._inicio: Optional[float] = None

    @property
    def activo(self) -> bool:
        return self._inicio is not None

    def actualizar(self, disparo: bool, ahora: float) -> bool:
        if disparo and self._inicio is None:
            self._inicio = ahora
        if self._inicio is not None and ahora - self._inicio >= self.duracion:
            self._inicio = None
        return self.activo


class ControlSenales:
    """Decide el estado de los pines PARE, GO y MUNECO a partir de las detecciones.

    Las senales se comportan distinto, y es a proposito:

    - El semaforo verde es *instantaneo*: el pin sigue a la deteccion. Mientras
      se vea el verde el robot arranca; si deja de verse, se apaga.
    - El PARE y el muneco se *enganchan*: apenas se detectan, el pin queda
      activo una duracion fija aunque salgan de cuadro. Si no fuera asi el robot
      dejaria de verlos al acercarse y saldria disparando antes de terminar de
      frenar.

    Ademas cada senal cuenta recien cuando su caja tiene un alto minimo: asi el
    robot frena a la distancia del cartel y no apenas lo ve a lo lejos. Y la del
    muneco tiene que tener su forma, angosta y alta: si no, una persona de cerca
    lo dispara.
    """

    def __init__(
        self,
        duracion_pare: float = config.DURACION_PARE,
        umbral_pare: float = config.UMBRAL_PARE,
        umbral_verde: float = config.UMBRAL_VERDE,
        duracion_muneco: float = config.DURACION_MUNECO,
        umbral_muneco: float = config.UMBRAL_MUNECO,
        alto_min_pare: float = config.ALTO_MIN_PARE,
        alto_min_verde: float = config.ALTO_MIN_VERDE,
        alto_min_muneco: float = config.ALTO_MIN_MUNECO,
        proporcion_muneco: Optional[Tuple[float, float]] = config.PROPORCION_MUNECO,
    ) -> None:
        self.proporcion_muneco = proporcion_muneco
        self.umbral_pare = umbral_pare
        self.umbral_verde = umbral_verde
        self.umbral_muneco = umbral_muneco
        self.alto_min_pare = alto_min_pare
        self.alto_min_verde = alto_min_verde
        self.alto_min_muneco = alto_min_muneco

        self._pare = Enganche(duracion_pare)
        self._muneco = Enganche(duracion_muneco)

    @property
    def pare_activo(self) -> bool:
        return self._pare.activo

    @property
    def muneco_activo(self) -> bool:
        return self._muneco.activo

    def actualizar(
        self, detecciones: Optional[Iterable[Deteccion]], ahora: float
    ) -> EstadoSalidas:
        """Procesa un ciclo y devuelve el estado que deben tomar los pines.

        `detecciones` puede ser None cuando el hilo de inferencia todavia no
        produjo ningun resultado.
        """
        dets: Sequence[Deteccion] = list(detecciones) if detecciones else []

        def ve(clase: str, umbral: float, alto_min: float, proporcion=None) -> bool:
            return any(
                d.nombre.lower() == clase.lower() and d.confianza > umbral
                and d.bbox[3] - d.bbox[1] >= alto_min
                and (proporcion is None or proporcion[0] <= proporcion_caja(d) <= proporcion[1])
                for d in dets
            )

        pare = ve(config.CLASE_PARE, self.umbral_pare, self.alto_min_pare)
        muneco = ve(config.CLASE_MUNECO, self.umbral_muneco, self.alto_min_muneco,
                    self.proporcion_muneco)
        return EstadoSalidas(
            pare=self._pare.actualizar(pare, ahora),
            go=ve(config.CLASE_VERDE, self.umbral_verde, self.alto_min_verde),
            muneco=self._muneco.actualizar(muneco, ahora),
        )
