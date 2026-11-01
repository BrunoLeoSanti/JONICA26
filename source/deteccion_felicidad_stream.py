"""Modo felicidad: personas, caras y una carita por cara. Video por red.

Con la camara inclinada hacia arriba, detecta personas (YOLOv8 COCO) y caras
(SCRFD) sobre el Hailo-8, estima cuan feliz se ve cada cara (HSEmotion, en la
CPU) y dibuja una carita de 5 niveles pegada a cada caja de cara. El video sale
por el mismo servidor MJPEG del stream de pista, en http://bumblebee.local:8000
(o /stream para cargarlo en OBS).

Es un programa aparte del de pista: no usa GPIO ni habla con el Arduino, y como
comparte camara y chip con el programa de pista, no pueden correr a la vez.

Tres hilos, porque la emocion en la CPU es mucho mas lenta que el Hailo y no
tiene que frenar ni el video ni las cajas:

    captura -> cola de 2 cuadros -> Hailo (personas + caras + ids)
                                         |
                                         +--> emocion (CPU) -> nivel por id
    bucle principal: dibuja lo ultimo que haya y publica el JPEG

Uso:
    python3 source/deteccion_felicidad_stream.py            # video con caritas
    python3 source/deteccion_felicidad_stream.py --valencia # ademas, el numero
        (sirve para calibrar CORTES_VALENCIA en config.py)
"""
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from queue import Empty, Queue

import config
from deteccion_hailo_stream import UltimoJpeg, crear_servidor
from dibujo_felicidad import crear_caritas, dibujar, recortar_cara
from emocion import EstimadorEmocion
from felicidad import SeguidorCaras, nivel_de_valencia
from hailo_multi import SesionHailo


def area(caja) -> float:
    return (caja[2] - caja[0]) * (caja[3] - caja[1])


def main() -> None:
    import cv2
    import simplejpeg
    from libcamera import Transform
    from picamera2 import Picamera2

    mostrar_valencia = "--valencia" in sys.argv

    picam2 = Picamera2()
    picam2.configure(
        picam2.create_video_configuration(
            # La camara va montada al reves en el chasis. Girarla en el ISP de
            # la camara no cuesta CPU; hacerlo con numpy sobre cada cuadro de
            # 1640x1232 si, y cajas y video coinciden sin transformar nada.
            transform=Transform(hflip=config.ROTAR_PREVIEW_180, vflip=config.ROTAR_PREVIEW_180),
            main={"format": config.FORMATO_CAMARA, "size": config.RESOLUCION_STREAM_FELICIDAD},
            lores={"format": config.FORMATO_CAMARA, "size": config.RESOLUCION},
            sensor={"output_size": config.MODO_SENSOR},
            controls={"FrameRate": config.FPS_CAMARA_FELICIDAD},
        )
    )
    picam2.start()

    cola_frames: "Queue" = Queue(maxsize=2)
    corriendo = threading.Event()
    corriendo.set()

    seguidor = SeguidorCaras()
    candado = threading.Lock()  # el seguidor lo usan el hilo del Hailo y el de emocion
    # deteccion: lo ultimo que vio el Hailo. niveles/valencias: lo ultimo que
    # calculo la emocion, por id de cara.
    estado = {"deteccion": None, "niveles": {}, "valencias": {}, "inferencias": 0, "videos": 0}
    # Cuadros ya dibujados esperando su JPEG. De a uno: si el codificador se
    # atrasa, se descarta el viejo en vez de acumular retraso.
    cola_jpeg: "Queue" = Queue(maxsize=1)

    def hilo_captura() -> None:
        while corriendo.is_set():
            # Las dos imagenes del mismo pedido, para que cajas e imagen coincidan.
            (grande, chica), _ = picam2.capture_arrays(["main", "lores"])
            if not cola_frames.full():
                cola_frames.put((grande, chica))

    pool = ThreadPoolExecutor(max_workers=1)

    def hilo_hailo(sesion: SesionHailo) -> None:
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
                # Los dos modelos a la vez: el scheduler los alterna en el chip y
                # asi no se suman las esperas de Python entre uno y otro.
                pendiente = pool.submit(sesion.detectar_personas, chica)
                cajas = [c.bbox for c in sesion.detectar_caras(chica)]
                personas = pendiente.result()
                with candado:
                    ids = seguidor.asignar(cajas)
                estado["deteccion"] = (grande, personas, cajas, ids)
                estado["inferencias"] += 1
            except Exception as error:  # no matar el programa por un frame malo
                print(f"[hailo] error: {error}", flush=True)

    def hilo_emocion(estimador: EstimadorEmocion) -> None:
        visto = None
        while corriendo.is_set():
            time.sleep(config.PAUSA_EMOCION)
            # Se lee despues de la pausa para trabajar con lo mas reciente.
            deteccion = estado["deteccion"]
            if deteccion is None or deteccion is visto:
                continue
            visto = deteccion
            grande, _, cajas, ids = deteccion
            # Solo las caras mas grandes: la emocion corre en la CPU y una
            # multitud frenaria todo. Las demas se dibujan sin carita.
            orden = sorted(range(len(cajas)), key=lambda i: area(cajas[i]), reverse=True)
            niveles, valencias = {}, {}
            try:
                for i in orden[: config.MAX_CARAS_EVALUADAS]:
                    recorte = recortar_cara(grande, cajas[i])
                    if recorte is None:
                        continue
                    # La inferencia (37 ms) va afuera del candado: adentro, el hilo
                    # del Hailo esperaria para asignar ids y bajaria el video.
                    crudo = estimador.valencia(recorte)
                    with candado:
                        v = seguidor.suavizar(ids[i], crudo)
                    valencias[ids[i]] = v
                    niveles[ids[i]] = nivel_de_valencia(v)
                estado["niveles"], estado["valencias"] = niveles, valencias
            except Exception as error:
                print(f"[emocion] error: {error}", flush=True)

    ultimo = UltimoJpeg()

    def hilo_jpeg() -> None:
        # Codificar un cuadro de 1640x1232 cuesta ~37 ms de CPU, mas que dibujarlo.
        # En su propio hilo se solapa con el dibujo del cuadro siguiente.
        while corriendo.is_set():
            try:
                imagen = cola_jpeg.get(timeout=0.2)
            except Empty:
                continue
            ultimo.publicar(simplejpeg.encode_jpeg(
                imagen, quality=config.CALIDAD_JPEG, colorspace="RGB"))
            estado["videos"] += 1

    servidor = crear_servidor(ultimo, config.PUERTO_STREAM)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    caritas = crear_caritas(max(int(config.RESOLUCION_STREAM_FELICIDAD[1] * 0.07), 32))

    try:
        with SesionHailo() as sesion:
            estimador = EstimadorEmocion()
            ancho, alto = config.RESOLUCION_STREAM_FELICIDAD
            print("Modelos cargados: personas + caras en el Hailo, emocion en la CPU", flush=True)
            print(f"Video {ancho}x{alto} en http://bumblebee.local:{config.PUERTO_STREAM}", flush=True)

            hilos = [
                threading.Thread(target=hilo_captura, daemon=True),
                threading.Thread(target=hilo_hailo, args=(sesion,), daemon=True),
                threading.Thread(target=hilo_emocion, args=(estimador,), daemon=True),
                threading.Thread(target=hilo_jpeg, daemon=True),
            ]
            for hilo in hilos:
                hilo.start()

            try:
                fps_inf = fps_video = 0.0
                cuenta_inf = cuenta_video = 0
                t_fps = time.time()
                anterior = None
                while True:
                    ahora = time.time()
                    if ahora - t_fps >= 5:
                        fps_inf = (estado["inferencias"] - cuenta_inf) / (ahora - t_fps)
                        fps_video = (estado["videos"] - cuenta_video) / (ahora - t_fps)
                        cuenta_inf, cuenta_video, t_fps = estado["inferencias"], estado["videos"], ahora
                        print(f"Hailo {fps_inf:.1f} FPS | video {fps_video:.1f} FPS", flush=True)

                    deteccion = estado["deteccion"]
                    if deteccion is None or deteccion is anterior:
                        time.sleep(0.002)
                        continue
                    anterior = deteccion

                    grande, personas, cajas, ids = deteccion
                    niveles, valencias = estado["niveles"], estado["valencias"]
                    imagen = dibujar(
                        grande, personas, [(c, niveles.get(i)) for c, i in zip(cajas, ids)], caritas
                    )
                    escala = imagen.shape[0] / 640
                    grosor = max(2, round(2 * escala))
                    if mostrar_valencia:
                        for c, i in zip(cajas, ids):
                            if i in valencias:
                                cv2.putText(imagen, f"{valencias[i]:+.2f}",
                                            (int(c[0] * imagen.shape[1]), int(c[3] * imagen.shape[0] + 24 * escala)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.7 * escala, (255, 255, 255), grosor)
                    cv2.putText(imagen, f"Hailo {fps_inf:.0f} FPS | video {fps_video:.0f} FPS | "
                                        f"{len(personas)} personas, {len(cajas)} caras",
                                (int(12 * escala), int(34 * escala)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7 * escala, (255, 255, 255), grosor)
                    try:
                        cola_jpeg.get_nowait()  # el cuadro viejo ya no sirve
                    except Empty:
                        pass
                    cola_jpeg.put(imagen)
            finally:
                # Los hilos tienen que soltar el Hailo antes de que la sesion se
                # cierre; si no, uno puede quedar a mitad de una inferencia sobre
                # un stream que ya se libero.
                corriendo.clear()
                for hilo in hilos:
                    hilo.join(timeout=2)

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        corriendo.clear()
        servidor.shutdown()
        servidor.server_close()
        picam2.stop()
        print("Programa finalizado, camara detenida.")


if __name__ == "__main__":
    main()
