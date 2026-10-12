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
    """Que tiene que valer cada pin en este instante."""
    pare: bool
    go: bool


class ControlSenales:
    """Decide el estado de los pines PARE y GO a partir de las detecciones.

    Las dos senales se comportan distinto, y es a proposito:

    - El semaforo verde es *instantaneo*: el pin sigue a la deteccion. Mientras
      se vea el verde el robot arranca; si deja de verse, se apaga.
    - El PARE se *engancha*: apenas se detecta, el pin queda activo una
      duracion fija aunque el cartel salga de cuadro. Si no fuera asi el robot
      dejaria de ver el cartel al acercarse y saldria disparando antes de
      terminar de frenar.
    """

    def __init__(
        self,
        duracion_pare: float = config.DURACION_PARE,
        umbral_pare: float = config.UMBRAL_PARE,
        umbral_verde: float = config.UMBRAL_VERDE,
    ) -> None:
        self.duracion_pare = duracion_pare
        self.umbral_pare = umbral_pare
        self.umbral_verde = umbral_verde

        self._pare_activo = False
        self._pare_inicio: Optional[float] = None

    @property
    def pare_activo(self) -> bool:
        return self._pare_activo

    def actualizar(
        self, detecciones: Optional[Iterable[Deteccion]], ahora: float
    ) -> EstadoSalidas:
        """Procesa un ciclo y devuelve el estado que deben tomar los pines.

        `detecciones` puede ser None cuando el hilo de inferencia todavia no
        produjo ningun resultado.
        """
        dets: Sequence[Deteccion] = list(detecciones) if detecciones else []

        ve_pare = any(
            d.nombre.lower() == config.CLASE_PARE.lower()
            and d.confianza > self.umbral_pare
            for d in dets
        )
        ve_verde = any(
            d.nombre.lower() == config.CLASE_VERDE.lower()
            and d.confianza > self.umbral_verde
            for d in dets
        )

        # PARE: solo dispara en el flanco, no mientras ya esta activo. Volver a
        # ver el cartel a mitad de la parada no extiende el tiempo.
        if ve_pare and not self._pare_activo:
            self._pare_activo = True
            self._pare_inicio = ahora

        if self._pare_activo and self._pare_inicio is not None:
            if ahora - self._pare_inicio >= self.duracion_pare:
                self._pare_activo = False
                self._pare_inicio = None

        return EstadoSalidas(pare=self._pare_activo, go=ve_verde)
