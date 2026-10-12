"""Salidas GPIO hacia el Arduino.

POR QUE CAMBIO RESPECTO DE 2025
-------------------------------
La version 2025 usaba `RPi.GPIO`, que en la Raspberry Pi 5 **no funciona**: esa
libreria escribe directo sobre los registros del SoC via /dev/mem, pero en la
Pi 5 los GPIO cuelgan del chip RP1, asi que termina escribiendo en la direccion
equivocada y los pines nunca cambian de estado.

Se migro a `gpiozero` (con backend lgpio), que es la via soportada en Pi 5 y
Raspberry Pi OS Bookworm. La alternativa era `rpi-lgpio`, un reemplazo
drop-in que mantiene la API vieja, pero preferimos la libreria soportada a
futuro antes que una capa de compatibilidad.

Lo que NO cambio son los numeros de pin: 26 y 16 siguen siendo PARE y GO, asi
que el sketch del Arduino sirve sin tocar una linea.
"""
import config


class SalidasRobot:
    """Los dos pines con los que la Raspberry le habla al Arduino.

    Se usa como context manager para que los pines queden siempre apagados al
    terminar, incluso si el programa corta por una excepcion:

        with SalidasRobot() as salidas:
            salidas.aplicar(estado)
    """

    def __init__(self, stop_pin: int = config.STOP_PIN, go_pin: int = config.GO_PIN):
        # Import diferido para poder importar este modulo fuera de la Raspberry.
        from gpiozero import DigitalOutputDevice

        self._stop = DigitalOutputDevice(stop_pin, initial_value=False)
        self._go = DigitalOutputDevice(go_pin, initial_value=False)

    def aplicar(self, estado) -> None:
        """Vuelca un `EstadoSalidas` a los pines fisicos."""
        self._stop.value = bool(estado.pare)
        self._go.value = bool(estado.go)

    def apagar(self) -> None:
        self._stop.off()
        self._go.off()

    def cerrar(self) -> None:
        self.apagar()
        self._stop.close()
        self._go.close()

    def __enter__(self) -> "SalidasRobot":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()
