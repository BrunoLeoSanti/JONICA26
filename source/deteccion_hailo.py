"""Deteccion de senales en la Raspberry Pi 5 + AI HAT+ (Hailo-8). Version de pista.

Equivalente 2026 de `deteccionygpio5.py` del repo JONICA25: sin ventana, sin
interfaz grafica, pensado para correr con el robot andando.

Conserva la misma arquitectura de tres partes que la version 2025, porque
funcionaba bien:

    hilo de captura  ->  cola de 2 frames  ->  hilo de inferencia
                                                      |
                                       bucle principal -> pines GPIO

La cola corta (maxsize=2) y el descarte de frames viejos son a proposito: nos
interesa el cuadro *mas reciente*, no procesarlos todos. Mejor una deteccion
actualizada que una cola de cuadros atrasados.

Uso:
    python3 source/deteccion_hailo.py
"""
import threading
import time
from queue import Queue

import config
from gpio_control import SalidasRobot
from hailo_detector import DetectorHailo
from senales import ControlSenales


def main() -> None:
    from picamera2 import Picamera2

    picam2 = Picamera2()
    picam2.configure(
        picam2.create_preview_configuration(
            main={"format": config.FORMATO_CAMARA, "size": config.RESOLUCION}
        )
    )
    picam2.start()

    cola_frames: "Queue" = Queue(maxsize=2)
    estado = {"detecciones": None}
    corriendo = threading.Event()
    corriendo.set()

    def hilo_captura() -> None:
        while corriendo.is_set():
            frame = picam2.capture_array()
            if not cola_frames.full():
                cola_frames.put(frame)

    def hilo_inferencia(detector: DetectorHailo) -> None:
        while corriendo.is_set():
            if cola_frames.empty():
                time.sleep(0.001)
                continue
            # Vaciar la cola y quedarse con el frame mas nuevo.
            frame = None
            while not cola_frames.empty():
                frame = cola_frames.get()
            if frame is None:
                continue
            try:
                estado["detecciones"] = detector.detectar(frame)
            except Exception as error:  # no matar el robot por un frame malo
                print(f"[inferencia] error: {error}")
                estado["detecciones"] = None

    control = ControlSenales()

    try:
        with DetectorHailo() as detector, SalidasRobot() as salidas:
            print(f"Modelo cargado: {detector.ruta_hef}")
            print(f"Clases: {', '.join(detector.etiquetas)}")
            print(f"Pines -> PARE: GPIO{config.STOP_PIN}  GO: GPIO{config.GO_PIN}")
            print("Listo. Ctrl+C para terminar.")

            threading.Thread(target=hilo_captura, daemon=True).start()
            threading.Thread(
                target=hilo_inferencia, args=(detector,), daemon=True
            ).start()

            pare_anterior = False
            while True:
                salida = control.actualizar(estado["detecciones"], time.time())
                salidas.aplicar(salida)

                # Avisar solo en los cambios, para no inundar la consola.
                if salida.pare and not pare_anterior:
                    print("PARE detectado -> frenando "
                          f"{config.DURACION_PARE:.0f}s")
                elif pare_anterior and not salida.pare:
                    print("Fin del PARE -> se reanuda la deteccion")
                pare_anterior = salida.pare

                time.sleep(config.PAUSA_LOOP)

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        corriendo.clear()
        picam2.stop()
        print("Programa finalizado, camara detenida y GPIO en bajo.")


if __name__ == "__main__":
    main()
