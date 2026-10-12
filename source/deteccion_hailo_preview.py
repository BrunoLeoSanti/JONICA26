"""Igual que deteccion_hailo.py pero con ventana de preview. Version de banco.

Equivalente 2026 de `deteccionygpio4.py` del repo JONICA25. Sirve para ajustar
la camara, verificar encuadre y confirmar que el modelo detecta antes de
mandar el robot a la pista. No usarla en competencia: dibujar cuesta tiempo.

Necesita un escritorio conectado (o VNC). Uso:
    python3 source/deteccion_hailo_preview.py
"""
import threading
import time
from queue import Queue

import config
from gpio_control import SalidasRobot
from hailo_detector import DetectorHailo
from senales import ControlSenales

COLORES = {config.CLASE_PARE: "red", config.CLASE_VERDE: "lime"}


def main() -> None:
    import pygame
    from PIL import Image, ImageDraw
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
            frame = None
            while not cola_frames.empty():
                frame = cola_frames.get()
            if frame is None:
                continue
            try:
                estado["detecciones"] = detector.detectar(frame)
                estado["ultimo_frame"] = frame
            except Exception as error:
                print(f"[inferencia] error: {error}")

    pygame.init()
    pantalla = pygame.display.set_mode(config.RESOLUCION)
    pygame.display.set_caption("JONICA26 - deteccion Hailo")

    control = ControlSenales()
    ancho, alto = config.RESOLUCION

    try:
        with DetectorHailo() as detector, SalidasRobot() as salidas:
            threading.Thread(target=hilo_captura, daemon=True).start()
            threading.Thread(
                target=hilo_inferencia, args=(detector,), daemon=True
            ).start()

            while corriendo.is_set():
                for evento in pygame.event.get():
                    if evento.type == pygame.QUIT:
                        corriendo.clear()

                frame = estado.get("ultimo_frame")
                if frame is None:
                    time.sleep(0.01)
                    continue

                detecciones = estado["detecciones"]
                salidas.aplicar(control.actualizar(detecciones, time.time()))

                imagen = Image.fromarray(frame)
                if config.ROTAR_PREVIEW_180:
                    imagen = imagen.rotate(180)
                dibujo = ImageDraw.Draw(imagen)

                for det in detecciones or []:
                    # bbox viene normalizado 0-1 -> pasar a pixeles.
                    x1, y1, x2, y2 = det.bbox
                    x1, x2 = x1 * ancho, x2 * ancho
                    y1, y2 = y1 * alto, y2 * alto
                    if config.ROTAR_PREVIEW_180:
                        # La imagen se roto 180 grados, las cajas tambien.
                        x1, x2 = ancho - x2, ancho - x1
                        y1, y2 = alto - y2, alto - y1
                    color = COLORES.get(det.nombre, "yellow")
                    dibujo.rectangle([x1, y1, x2, y2], outline=color, width=2)
                    dibujo.text(
                        (x1, max(0, y1 - 10)),
                        f"{det.nombre} {det.confianza:.2f}",
                        fill=color,
                    )

                superficie = pygame.image.fromstring(
                    imagen.tobytes(), imagen.size, imagen.mode
                )
                pantalla.blit(superficie, (0, 0))
                pygame.display.update()

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        corriendo.clear()
        picam2.stop()
        pygame.quit()
        print("Programa finalizado, camara detenida y GPIO en bajo.")


if __name__ == "__main__":
    main()
