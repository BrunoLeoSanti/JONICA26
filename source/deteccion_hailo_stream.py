"""Igual que deteccion_hailo.py pero mandando el video por red. Version de banco.

Reemplaza a la ventana de deteccion_hailo_preview.py cuando no hay pantalla:
el video con las cajas dibujadas se ve desde cualquier navegador de la misma
red, en http://bumblebee.local:8000 (o /stream para el video solo, que es lo
que se carga en OBS para transmitir).

La camara entrega dos imagenes de cada cuadro, escaladas por su propio ISP sin
gastar CPU: una grande (RESOLUCION_STREAM) para el video y una de 640x640 para
el Hailo. Como salen del mismo cuadro, las cajas normalizadas del modelo caen
justo sobre la imagen grande.

Se sirve como MJPEG (una seguidilla de JPEG) y no como H.264 porque la Pi 5 no
tiene codificador de video por hardware, y el Hailo-8 tampoco: H.264 por
software costaria mucho mas CPU, y MJPEG lo abre cualquier navegador u OBS sin
instalar nada.

Encima del video se muestran los FPS de inferencia y de video, para ver si el
streaming le esta robando tiempo a la deteccion.

Con --fotos ademas guarda cada INTERVALO_FOTOS segundos la imagen que recibe el
Hailo, para armar el dataset del muneco (ver CARPETA_DATASET en config.py).

Uso:
    python3 source/deteccion_hailo_stream.py
    python3 source/deteccion_hailo_stream.py --fotos
"""
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue

import numpy as np

import config
from gpio_control import SalidasRobot
from hailo_detector import DetectorHailo
from senales import ControlSenales

# El frame viene en orden RGB (ver FORMATO_CAMARA en config.py)
COLORES = {config.CLASE_PARE: (255, 0, 0), config.CLASE_VERDE: (0, 255, 0)}

PAGINA = b"""<!doctype html><html><head><meta charset="utf-8">
<title>JONICA26</title></head>
<body style="margin:0;background:#000;height:100vh;display:flex;align-items:center;justify-content:center">
<img src="/stream" style="max-width:100%;max-height:100%"></body></html>"""


class UltimoJpeg:
    """El JPEG mas reciente, compartido entre el bucle y los clientes HTTP.

    Cada cliente espera al siguiente cuadro en vez de recibir siempre el mismo:
    asi un navegador lento no fuerza a codificar de mas, y uno rapido no recibe
    cuadros repetidos.
    """

    def __init__(self) -> None:
        self._condicion = threading.Condition()
        self._jpeg = None
        self._numero = 0

    def publicar(self, jpeg: bytes) -> None:
        with self._condicion:
            self._jpeg = jpeg
            self._numero += 1
            self._condicion.notify_all()

    def esperar(self, ultimo_visto: int, timeout: float = 2.0):
        with self._condicion:
            self._condicion.wait_for(lambda: self._numero != ultimo_visto, timeout)
            return self._jpeg, self._numero


def crear_servidor(ultimo: UltimoJpeg, puerto: int) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(PAGINA)
                return
            # Sin el "?t=..." que agrega la pagina de robot.py para reconectar.
            if self.path.split("?")[0] != "/stream":
                self.send_error(404)
                return

            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF,
                                       config.BUFFER_ENVIO_VIDEO)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=cuadro")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            visto = 0
            try:
                while True:
                    jpeg, visto = ultimo.esperar(visto)
                    if jpeg is None:
                        continue
                    self.wfile.write(b"--cuadro\r\nContent-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass  # el navegador se cerro

        def log_message(self, *args) -> None:
            pass  # sin una linea por cada pedido

    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    servidor.daemon_threads = True
    return servidor


def dibujar(frame: np.ndarray, detecciones, fps_inferencia: float,
            fps_video: float) -> np.ndarray:
    import cv2

    imagen = cv2.rotate(frame, cv2.ROTATE_180) if config.ROTAR_PREVIEW_180 else frame.copy()
    alto, ancho = imagen.shape[:2]
    # Trazos proporcionales a la imagen, para que se lean igual en 640 que en 1080
    escala = alto / 640
    grosor = max(2, round(3 * escala))

    for det in detecciones or []:
        # bbox viene normalizado 0-1 -> pasar a pixeles de la imagen grande.
        x1, y1, x2, y2 = det.bbox
        x1, x2 = x1 * ancho, x2 * ancho
        y1, y2 = y1 * alto, y2 * alto
        if config.ROTAR_PREVIEW_180:
            # La imagen se roto 180 grados, las cajas tambien.
            x1, x2 = ancho - x2, ancho - x1
            y1, y2 = alto - y2, alto - y1
        color = COLORES.get(det.nombre, (255, 255, 0))
        cv2.rectangle(imagen, (int(x1), int(y1)), (int(x2), int(y2)), color, grosor)
        cv2.putText(imagen, f"{det.nombre} {det.confianza:.2f}",
                    (int(x1), max(int(30 * escala), int(y1 - 10 * escala))),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8 * escala, color, grosor)

    cv2.putText(imagen, f"Hailo {fps_inferencia:.0f} FPS | video {fps_video:.0f} FPS",
                (int(12 * escala), int(34 * escala)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7 * escala, (255, 255, 255), grosor)
    return imagen


def main() -> None:
    import simplejpeg
    from picamera2 import Picamera2

    picam2 = Picamera2()
    picam2.configure(
        picam2.create_video_configuration(
            main={"format": config.FORMATO_CAMARA, "size": config.RESOLUCION_STREAM},
            lores={"format": config.FORMATO_CAMARA, "size": config.RESOLUCION},
            sensor={"output_size": config.MODO_SENSOR},
            controls={"FrameRate": config.FPS_CAMARA},
        )
    )
    picam2.start()

    cola_frames: "Queue" = Queue(maxsize=2)
    estado = {"detecciones": None, "ultimo_frame": None, "ultima_chica": None, "inferencias": 0}
    corriendo = threading.Event()
    corriendo.set()

    def hilo_captura() -> None:
        while corriendo.is_set():
            # Las dos imagenes del mismo pedido, para que cajas e imagen coincidan.
            (grande, chica), _ = picam2.capture_arrays(["main", "lores"])
            if not cola_frames.full():
                cola_frames.put((grande, chica))

    def hilo_inferencia(detector: DetectorHailo) -> None:
        while corriendo.is_set():
            if cola_frames.empty():
                time.sleep(0.001)
                continue
            par = None
            while not cola_frames.empty():
                par = cola_frames.get()
            if par is None:
                continue
            grande, chica = par
            try:
                estado["detecciones"] = detector.detectar(chica)
                estado["ultimo_frame"] = grande
                estado["ultima_chica"] = chica
                estado["inferencias"] += 1
            except Exception as error:  # no matar el robot por un frame malo
                print(f"[inferencia] error: {error}", flush=True)

    ultimo = UltimoJpeg()
    servidor = crear_servidor(ultimo, config.PUERTO_STREAM)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    control = ControlSenales()

    carpeta_fotos = None
    if "--fotos" in sys.argv:
        sesion = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        carpeta_fotos = config.CARPETA_DATASET / sesion
        carpeta_fotos.mkdir(parents=True, exist_ok=True)
    fotos = 0
    t_foto = 0.0

    try:
        with DetectorHailo() as detector, SalidasRobot() as salidas:
            print(f"Modelo cargado: {detector.ruta_hef}", flush=True)
            ancho, alto = config.RESOLUCION_STREAM
            print(f"Video {ancho}x{alto} en http://bumblebee.local:{config.PUERTO_STREAM}",
                  flush=True)

            if carpeta_fotos:
                print(f"Guardando una foto cada {config.INTERVALO_FOTOS:g} s en {carpeta_fotos}",
                      flush=True)

            threading.Thread(target=hilo_captura, daemon=True).start()
            threading.Thread(
                target=hilo_inferencia, args=(detector,), daemon=True
            ).start()

            fps_inf = fps_video = 0.0
            cuenta_inf = cuenta_video = videos = 0
            t_fps = time.time()
            frame_anterior = None
            pare_anterior = False
            while True:
                salida = control.actualizar(estado["detecciones"], time.time())
                salidas.aplicar(salida)
                if salida.pare and not pare_anterior:
                    print("PARE detectado -> frenando "
                          f"{config.DURACION_PARE:.0f}s", flush=True)
                pare_anterior = salida.pare

                ahora = time.time()
                if ahora - t_fps >= 5:
                    fps_inf = (estado["inferencias"] - cuenta_inf) / (ahora - t_fps)
                    fps_video = (videos - cuenta_video) / (ahora - t_fps)
                    cuenta_inf, cuenta_video, t_fps = estado["inferencias"], videos, ahora
                    print(f"Hailo {fps_inf:.1f} FPS | video {fps_video:.1f} FPS"
                          + (f" | {fotos} fotos" if carpeta_fotos else ""), flush=True)

                chica = estado["ultima_chica"]
                if carpeta_fotos and chica is not None and ahora - t_foto >= config.INTERVALO_FOTOS:
                    # El nombre lleva la sesion: al juntar varias en Roboflow no se pisan.
                    nombre = carpeta_fotos / f"{carpeta_fotos.name}_{fotos:04d}.jpg"
                    # Derecha, como se ve en el video: la camara va montada al reves.
                    if config.ROTAR_PREVIEW_180:
                        chica = np.ascontiguousarray(chica[::-1, ::-1])
                    nombre.write_bytes(simplejpeg.encode_jpeg(
                        chica, quality=config.CALIDAD_FOTOS, colorspace="RGB"))
                    fotos += 1
                    t_foto = ahora

                frame = estado["ultimo_frame"]
                if frame is None or frame is frame_anterior:
                    time.sleep(0.002)
                    continue
                frame_anterior = frame

                imagen = dibujar(frame, estado["detecciones"], fps_inf, fps_video)
                ultimo.publicar(simplejpeg.encode_jpeg(
                    imagen, quality=config.CALIDAD_JPEG, colorspace="RGB"))
                videos += 1

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        corriendo.clear()
        servidor.shutdown()
        picam2.stop()
        if carpeta_fotos:
            print(f"{fotos} fotos en {carpeta_fotos}")
        print("Programa finalizado, camara detenida y GPIO en bajo.")


if __name__ == "__main__":
    main()
