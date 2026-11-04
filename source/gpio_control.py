"""Salidas GPIO hacia el Arduino.

POR QUE CAMBIO RESPECTO DE 2025
-------------------------------
La version 2025 usaba `RPi.GPIO`, que en la Raspberry Pi 5 **no funciona**: esa
libreria escribe directo sobre los registros del SoC via /dev/mem, pero en la
Pi 5 los GPIO cuelgan del chip RP1, asi que termina escribiendo en la direccion
equivocada y los pines nunca cambian de estado.

Primero se migro a `gpiozero`, y despues a `lgpio` directo (que es lo que
gpiozero usa por debajo) porque al cerrar un pin gpiozero lo deja como entrada
*sin pull*, flotando, y lo sigue reteniendo hasta que termina el proceso. Lo
primero hace que el Arduino (que lee sin pullup) vea cualquier cosa; lo segundo
impide que robot.py le pase los pines al programa de pista ("GPIO busy").

26 y 16 siguen siendo PARE y GO como en 2025. Con el modo felicidad se sumaron
MUNECO y MODO; el significado de cada pin segun el modo esta en config.py.

El pin MODO no esta en estas clases: lo maneja robot.py, que es el que cambia de
modo. Si un programa de pista corre solo, MODO queda con el pull-down de la Pi,
en bajo, que es justamente el modo pista.
"""
import config


def _chip_rp1(lgpio) -> int:
    """El gpiochip de los GPIO del conector: segun el kernel es el 0 o el 4."""
    for numero in range(16):
        try:
            h = lgpio.gpiochip_open(numero)
        except lgpio.error:
            continue
        try:
            if "rp1" in lgpio.gpio_get_chip_info(h)[3]:
                return numero
        finally:
            lgpio.gpiochip_close(h)
    return 0


class PinSalida:
    """Un pin de salida que, al cerrarse, queda libre y con pull-down."""

    def __init__(self, numero: int, valor: bool = False) -> None:
        # Import diferido para poder importar este modulo fuera de la Raspberry.
        import lgpio

        self._lgpio = lgpio
        self.numero = numero
        self._chip = lgpio.gpiochip_open(_chip_rp1(lgpio))
        lgpio.gpio_claim_output(self._chip, numero, int(valor))

    def escribir(self, valor: bool) -> None:
        self._lgpio.gpio_write(self._chip, self.numero, int(bool(valor)))

    def cerrar(self) -> None:
        # Entrada con pull-down y libre: el Arduino lee LOW y otro proceso puede
        # tomar el pin. El pull-down sigue puesto despues de soltarlo.
        self._lgpio.gpio_claim_input(self._chip, self.numero, self._lgpio.SET_PULL_DOWN)
        self._lgpio.gpio_free(self._chip, self.numero)
        self._lgpio.gpiochip_close(self._chip)


class SalidasRobot:
    """Modo pista: los pines PARE, GO y MUNECO.

    Se usa como context manager para que los pines queden siempre apagados al
    terminar, incluso si el programa corta por una excepcion:

        with SalidasRobot() as salidas:
            salidas.aplicar(estado)
    """

    def __init__(
        self,
        stop_pin: int = config.STOP_PIN,
        go_pin: int = config.GO_PIN,
        muneco_pin: int = config.MUNECO_PIN,
    ) -> None:
        self._stop = PinSalida(stop_pin)
        self._go = PinSalida(go_pin)
        self._muneco = PinSalida(muneco_pin)

    def aplicar(self, estado) -> None:
        """Vuelca un `EstadoSalidas` a los pines fisicos."""
        self._stop.escribir(estado.pare)
        self._go.escribir(estado.go)
        self._muneco.escribir(estado.muneco)

    def apagar(self) -> None:
        for pin in (self._stop, self._go, self._muneco):
            pin.escribir(False)

    def cerrar(self) -> None:
        self.apagar()
        for pin in (self._stop, self._go, self._muneco):
            pin.cerrar()

    def __enter__(self) -> "SalidasRobot":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()


class MotoresRemotos(SalidasRobot):
    """Modo felicidad: los mismos tres pines, pero manejando los motores.

    PARE = motor izquierdo, GO = motor derecho, MUNECO = reversa.
    """

    def aplicar(self, motores) -> None:
        """Vuelca un `manejo_teclado.Motores` a los pines fisicos."""
        self._stop.escribir(motores.izquierdo)
        self._go.escribir(motores.derecho)
        self._muneco.escribir(motores.reversa)
