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
    """

    def __init__(
        self,
        duracion_pare: float = config.DURACION_PARE,
        umbral_pare: float = config.UMBRAL_PARE,
        umbral_verde: float = config.UMBRAL_VERDE,
        duracion_muneco: float = config.DURACION_MUNECO,
        umbral_muneco: float = config.UMBRAL_MUNECO,
    ) -> None:
        self.umbral_pare = umbral_pare
        self.umbral_verde = umbral_verde
        self.umbral_muneco = umbral_muneco

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

        def ve(clase: str, umbral: float) -> bool:
            return any(
                d.nombre.lower() == clase.lower() and d.confianza > umbral
                for d in dets
            )

        return EstadoSalidas(
            pare=self._pare.actualizar(ve(config.CLASE_PARE, self.umbral_pare), ahora),
            go=ve(config.CLASE_VERDE, self.umbral_verde),
            muneco=self._muneco.actualizar(ve(config.CLASE_MUNECO, self.umbral_muneco), ahora),
        )
