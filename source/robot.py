"""El robot completo: modo pista o modo felicidad, cambiando con la tecla 2.

Los dos modos no pueden correr a la vez porque comparten camara y Hailo, asi que
este programa no detecta nada: corre uno de los dos programas y, al apretar 2,
lo cierra y arranca el otro.

    pista      -> deteccion_hailo_stream.py   (PARE / GO / MUNECO al Arduino)
    felicidad  -> deteccion_felicidad_stream.py + motores con WASD desde aca

Tambien es el dueno del pin MODO, y en felicidad de los otros tres (los motores).
Nunca hay dos procesos con el mismo pin: el de pista suelta los suyos al cerrar,
y recien ahi se toman para los motores.

Se maneja desde el navegador de la compu, en http://bumblebee.local:8080: ahi se
ve el video y se aprietan las teclas (con la pestana enfocada). El video sigue
saliendo por http://bumblebee.local:8000/stream; cada cambio de modo lo corta
unos segundos mientras el otro programa carga sus modelos. Para OBS conviene
http://bumblebee.local:8080/video, que reconecta sola despues de cada cambio.

Uso:
    python3 source/robot.py
    python3 source/robot.py --fotos   # en pista, ademas fotos para el dataset
"""
import json
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

import config
from gpio_control import MotoresRemotos, PinSalida
from manejo_teclado import ControlTeclado

PISTA, FELICIDAD = "pista", "felicidad"
PROGRAMAS = {
    PISTA: Path(__file__).with_name("deteccion_hailo_stream.py"),
    FELICIDAD: Path(__file__).with_name("deteccion_felicidad_stream.py"),
}

# La pagina repite las teclas cada 100 ms mientras haya alguna apretada: si
# dejan de llegar, se apagan los motores (TIEMPO_SIN_TECLAS en config.py). El
# video se recarga cuando cambia el modo, porque el programa nuevo levanta otro
# servidor y el <img> se queda colgado del que se cerro.
PAGINA = """<!doctype html><html><head><meta charset="utf-8">
<title>JONICA26</title></head>
<body style="margin:0;background:#000;height:100vh;display:flex;align-items:center;justify-content:center">
<img id="v" style="max-width:100%;max-height:100%">
<div id="t" style="position:fixed;bottom:12px;left:12px;color:#fff;font:20px monospace"></div>
<script>
const video = document.getElementById("v");
const URL_VIDEO = "http://" + location.hostname + ":PUERTO_STREAM/stream";
function recargar() { video.src = URL_VIDEO + "?t=" + Date.now(); }
video.onerror = () => setTimeout(recargar, 1000);
recargar();

const apretadas = new Set();
let modo = "?", cambiando = false, version = null;
function mostrar() {
  const teclas = [...apretadas].join("").toUpperCase();
  document.getElementById("t").textContent = cambiando ? "Cambiando de modo..." :
    "Modo " + modo + (modo === "felicidad" ? " | WASD " + teclas : "") + " | 2 cambia de modo";
}
function mandar() {
  mostrar();
  fetch("/teclas", {method: "POST", body: [...apretadas].join("")}).catch(() => {});
}
addEventListener("keydown", e => {
  const k = e.key.toLowerCase();
  if (k === "2" && !e.repeat) { fetch("/modo", {method: "POST"}).catch(() => {}); return; }
  if (k.length !== 1 || !"wasd".includes(k)) return;
  e.preventDefault();
  if (!apretadas.has(k)) { apretadas.add(k); mandar(); }
});
addEventListener("keyup", e => {
  if (apretadas.delete(e.key.toLowerCase())) mandar();
});
// Al cambiar de ventana el keyup no llega: soltar todo.
addEventListener("blur", () => { apretadas.clear(); mandar(); });
setInterval(() => { if (apretadas.size) mandar(); }, 100);

setInterval(async () => {
  try {
    const e = await (await fetch("/estado")).json();
    if (version !== null && e.version !== version) recargar();
    ({modo, cambiando, version} = e);
    mostrar();
  } catch (_) {}
}, 1000);
</script></body></html>""".replace("PUERTO_STREAM", str(config.PUERTO_STREAM)).encode()

# Para la fuente de navegador de OBS: el mismo video, sin texto ni teclas. No
# carga /stream directo porque al cambiar de modo el video se corta y OBS no
# reconecta solo; esta pagina si, como la de arriba.
PAGINA_VIDEO = """<!doctype html><html><head><meta charset="utf-8">
<title>JONICA26 video</title></head>
<body style="margin:0;background:#000;height:100vh;overflow:hidden;display:flex;align-items:center;justify-content:center">
<img id="v" style="max-width:100%;max-height:100%">
<script>
const video = document.getElementById("v");
const URL_VIDEO = "http://" + location.hostname + ":PUERTO_STREAM/stream";
function recargar() { video.src = URL_VIDEO + "?t=" + Date.now(); }
video.onerror = () => setTimeout(recargar, 1000);
recargar();
let version = null;
setInterval(async () => {
  try {
    const e = await (await fetch("/estado")).json();
    if (version !== null && e.version !== version) recargar();
    version = e.version;
  } catch (_) {}
}, 1000);
</script></body></html>""".replace("PUERTO_STREAM", str(config.PUERTO_STREAM)).encode()


class Robot:
    """El modo actual, el programa que lo corre y los pines que le tocan."""

    def __init__(self) -> None:
        self._pin_modo = PinSalida(config.MODO_PIN)
        self.modo = PISTA
        self.version = 0
        self.teclado = ControlTeclado()
        self._programa: Optional[subprocess.Popen] = None
        self._motores: Optional[MotoresRemotos] = None
        # Lo toman el cambio de modo y el hilo de motores: mientras se cambia,
        # nadie escribe en pines que estan pasando de un proceso al otro.
        self._candado = threading.Lock()
        # Aparte del candado de los pines, que el hilo de motores toma a cada
        # rato: si fuera el mismo, un 2 que cae justo en ese momento se perderia.
        self._cambio = threading.Lock()

    @property
    def cambiando(self) -> bool:
        return self._cambio.locked()

    def arrancar(self) -> None:
        with self._candado:
            self._entrar()

    def cambiar_modo(self) -> bool:
        """Pasa al otro modo. Devuelve False si ya habia un cambio en curso."""
        # Sin esperar: un segundo 2 durante el cambio no tiene que encolar otro.
        if not self._cambio.acquire(blocking=False):
            return False
        try:
            with self._candado:
                self._salir()
                self.modo = FELICIDAD if self.modo == PISTA else PISTA
                self._entrar()
                self.version += 1
        finally:
            self._cambio.release()
        return True

    def hilo_motores(self, corriendo: threading.Event) -> None:
        # Tambien aplica cuando no llega nada: asi vence la ultima orden.
        while corriendo.is_set():
            with self._candado:
                if self._motores is not None:
                    self._motores.aplicar(self.teclado.motores(time.time()))
            time.sleep(0.02)

    def cerrar(self) -> None:
        with self._candado:
            self._salir()
            self._pin_modo.cerrar()

    def _entrar(self) -> None:
        if self.modo == FELICIDAD:
            # Primero los motores en bajo y despues el modo: el Arduino nunca
            # ve el modo felicidad con un motor ya prendido.
            self.teclado.recibir("", time.time())
            self._motores = MotoresRemotos()
            self._pin_modo.escribir(True)
        else:
            self._pin_modo.escribir(False)
        print(f"\n=== Modo {self.modo} ===", flush=True)
        # Las opciones de la linea de comandos (--fotos) son del programa de pista.
        opciones = sys.argv[1:] if self.modo == PISTA else []
        self._programa = subprocess.Popen([sys.executable, str(PROGRAMAS[self.modo])] + opciones)

    def _salir(self) -> None:
        if self._programa is not None:
            if self._programa.poll() is None:
                # Como un Ctrl+C: cada programa suelta camara, Hailo y pines.
                self._programa.send_signal(signal.SIGINT)
            try:
                self._programa.wait(timeout=config.ESPERA_CIERRE)
            except subprocess.TimeoutExpired:
                self._programa.kill()
                self._programa.wait()
            self._programa = None
        if self._motores is not None:
            self._motores.cerrar()
            self._motores = None
        # El modo va ultimo: con los motores ya apagados, volver a pista no
        # puede leerse como un semaforo verde o un PARE a medias.
        self._pin_modo.escribir(False)


def crear_servidor(robot: Robot, puerto: int) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                self._responder(200, "text/html; charset=utf-8", PAGINA)
            elif self.path == "/video":
                self._responder(200, "text/html; charset=utf-8", PAGINA_VIDEO)
            elif self.path == "/estado":
                estado = {"modo": robot.modo, "version": robot.version,
                          "cambiando": robot.cambiando}
                self._responder(200, "application/json", json.dumps(estado).encode())
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/teclas":
                largo = min(int(self.headers.get("Content-Length", 0)), 16)
                robot.teclado.recibir(self.rfile.read(largo).decode("ascii", "ignore"), time.time())
                self._responder(204)
            elif self.path == "/modo":
                # Tarda lo que tarda el programa en cerrar y el otro en arrancar;
                # la pagina no espera la respuesta, consulta /estado.
                self._responder(204 if robot.cambiar_modo() else 409)
            else:
                self.send_error(404)

        def _responder(self, codigo: int, tipo: str = "", cuerpo: bytes = b"") -> None:
            self.send_response(codigo)
            if tipo:
                self.send_header("Content-Type", tipo)
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args) -> None:
            pass  # sin una linea por cada tecla

    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    servidor.daemon_threads = True
    return servidor


def _como_ctrl_c(*_) -> None:
    raise KeyboardInterrupt


def main() -> None:
    # Lanzado en segundo plano por un script, SIGINT llega ignorado y los
    # programas de cada modo lo heredan: no se podria cerrarlos con cuidado al
    # cambiar de modo. Reactivarlo aca alcanza, porque los hijos lo heredan.
    # SIGTERM (pkill, apagado) cierra igual que un Ctrl+C.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, _como_ctrl_c)

    robot = Robot()
    corriendo = threading.Event()
    corriendo.set()
    servidor = crear_servidor(robot, config.PUERTO_CONTROL)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    threading.Thread(target=robot.hilo_motores, args=(corriendo,), daemon=True).start()

    print(f"Control en http://bumblebee.local:{config.PUERTO_CONTROL} "
          f"(2 cambia de modo, WASD maneja en felicidad)", flush=True)
    try:
        robot.arrancar()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # El Ctrl+C de la terminal tambien le llega al programa del modo, que
        # se cierra solo; _salir() lo espera.
        print("\nInterrumpido por el usuario.")
    finally:
        corriendo.clear()
        robot.cerrar()
        servidor.shutdown()
        print("Robot detenido: programas cerrados y pines en bajo.")


if __name__ == "__main__":
    main()
