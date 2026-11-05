"""Transmite el video del robot a YouTube desde la compu (Mac o Windows).

La Pi manda el video UNA sola vez, a este programa, y este lo reparte: a ffmpeg,
que lo comprime y lo sube a YouTube, y al navegador de la compu. Si el navegador
y ffmpeg lo pidieran cada uno a la Pi, el WiFi de la Pi tendria que llevar dos
copias de un MJPEG de 60-100 Mbps, y el video llega a los saltos.

Para eso levanta en la compu los mismos dos puertos que la Pi:

    http://localhost:8000/stream   el video, para ffmpeg
    http://localhost:8080          la pagina de control (se reenvia a la Pi)

La pagina de control arma la URL del video con el nombre del host, asi que
abierta como localhost:8080 toma el video de aca y no de la Pi. No hay que
cambiar nada en la Pi.

Al cambiar de modo la Pi corta el video unos segundos. Mientras tanto se repite
el ultimo cuadro: ffmpeg no se entera del corte y YouTube no se cae.

Necesita ffmpeg (Mac: brew install ffmpeg; Windows: winget install ffmpeg).
La clave de emision esta en YouTube Studio -> Emitir en directo -> Transmision.

Uso:
    python3 tools/transmitir_youtube.py
    python3 tools/transmitir_youtube.py --pi 192.168.100.138
"""
import argparse
import getpass
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

import config  # noqa: E402

YOUTUBE = "rtmp://a.rtmp.youtube.com/live2/"
# Sin cuadro nuevo en este tiempo se repite el ultimo, para que el corte del
# cambio de modo no le llegue a ffmpeg.
REPETIR_CADA = 0.5


class UltimoJpeg:
    """El JPEG mas reciente. Igual al de deteccion_hailo_stream.py, copiado para
    no arrastrar numpy ni el resto del programa de la Pi a la compu."""

    def __init__(self) -> None:
        self._condicion = threading.Condition()
        self._jpeg = None
        self._numero = 0

    def publicar(self, jpeg: bytes) -> None:
        with self._condicion:
            self._jpeg = jpeg
            self._numero += 1
            self._condicion.notify_all()

    def esperar(self, ultimo_visto: int, timeout: float):
        with self._condicion:
            self._condicion.wait_for(lambda: self._numero != ultimo_visto, timeout)
            return self._jpeg, self._numero


def leer_de_la_pi(url: str, ultimo: UltimoJpeg) -> None:
    """Baja el MJPEG de la Pi y publica cada JPEG. Reconecta si se corta."""
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as respuesta:
                print(f"Recibiendo video de {url}", flush=True)
                largo = None
                while True:
                    linea = respuesta.readline()
                    if not linea:
                        break  # la Pi cerro: cambio de modo o se apago
                    if linea.lower().startswith(b"content-length:"):
                        largo = int(linea.split(b":")[1])
                    elif linea in (b"\r\n", b"\n") and largo:
                        ultimo.publicar(respuesta.read(largo))
                        largo = None
        except (OSError, ValueError):
            pass
        time.sleep(1)


def servidor_video(ultimo: UltimoJpeg, puerto: int) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            # Con o sin el "?t=..." que agrega la pagina de control.
            if self.path.split("?")[0] != "/stream":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=cuadro")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            visto = 0
            try:
                while True:
                    # Si vence la espera devuelve el mismo cuadro: se repite.
                    jpeg, visto = ultimo.esperar(visto, timeout=REPETIR_CADA)
                    if jpeg is None:
                        continue
                    self.wfile.write(b"--cuadro\r\nContent-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    servidor.daemon_threads = True
    return servidor


def servidor_control(pi: str, puerto: int) -> ThreadingHTTPServer:
    """Reenvia la pagina de control y sus pedidos (teclas, modo) a la Pi."""
    base = f"http://{pi}:{config.PUERTO_CONTROL}"

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._reenviar(None)

        def do_POST(self) -> None:
            largo = min(int(self.headers.get("Content-Length", 0)), 1024)
            self._reenviar(self.rfile.read(largo))

        def _reenviar(self, cuerpo) -> None:
            pedido = urllib.request.Request(base + self.path, data=cuerpo,
                                            method=self.command)
            try:
                # Largo porque /modo responde recien cuando termino el cambio.
                with urllib.request.urlopen(pedido, timeout=30) as r:
                    codigo, tipo, datos = r.status, r.headers.get("Content-Type"), r.read()
            except urllib.error.HTTPError as error:
                codigo, tipo, datos = error.code, None, b""
            except OSError:
                self.send_error(502)
                return
            self.send_response(codigo)
            if tipo:
                self.send_header("Content-Type", tipo)
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *args) -> None:
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    servidor.daemon_threads = True
    return servidor


def comando_ffmpeg(entrada: str, clave: str) -> list:
    if sys.platform == "darwin":
        # El chip de video de la Mac: casi no usa CPU.
        codificador = ["-c:v", "h264_videotoolbox", "-b:v", "4500k"]
    else:
        codificador = ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "4500k",
                       "-maxrate", "4500k", "-bufsize", "9000k"]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats",
        # El MJPEG no trae tiempos: se usa la hora de llegada de cada cuadro.
        "-use_wallclock_as_timestamps", "1", "-f", "mpjpeg", "-i", entrada,
        # YouTube exige una pista de audio: va muda.
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a",
        # 4:3 centrado en 1920x1080 con bandas negras.
        "-vf", "fps=30,scale=-2:1080,pad=1920:1080:(ow-iw)/2:0,format=yuv420p",
        *codificador, "-g", "60", "-c:a", "aac", "-b:a", "128k",
        "-f", "flv", YOUTUBE + clave,
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pi", default="bumblebee.local", help="nombre o IP de la Pi")
    args = parser.parse_args()

    ultimo = UltimoJpeg()
    origen = f"http://{args.pi}:{config.PUERTO_STREAM}/stream"
    threading.Thread(target=leer_de_la_pi, args=(origen, ultimo), daemon=True).start()
    for servidor in (servidor_video(ultimo, config.PUERTO_STREAM),
                     servidor_control(args.pi, config.PUERTO_CONTROL)):
        threading.Thread(target=servidor.serve_forever, daemon=True).start()

    clave = getpass.getpass("Clave de emision de YouTube: ").strip()
    print(f"\nPara manejar y ver el video: http://localhost:{config.PUERTO_CONTROL}\n"
          "Ctrl+C para cortar la transmision.\n", flush=True)
    entrada = f"http://127.0.0.1:{config.PUERTO_STREAM}/stream"
    try:
        while True:
            subprocess.run(comando_ffmpeg(entrada, clave))
            # Se corta si se cae internet o YouTube rechaza la clave.
            print("ffmpeg se corto, reintentando en 2 s...", flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nTransmision cortada.")


if __name__ == "__main__":
    main()
