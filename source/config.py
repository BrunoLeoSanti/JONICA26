"""Configuracion central del robot.

Todo lo que se toca al calibrar en la pista vive aca, para no tener que
buscar numeros sueltos repartidos por el codigo.
"""
from pathlib import Path

# --- Pines GPIO (numeracion BCM) ---------------------------------------------
# Contrato con el Arduino: estos cuatro pines son la unica comunicacion entre la
# Raspberry y el control de motores. PARE y GO son los de 2025; MUNECO y MODO
# se sumaron con el modo felicidad, y van al lado (fisicos 38 y 40, con GND en
# el 39) para que los cuatro cables salgan juntos.
#
# MODO elige que significan los otros (lo maneja robot.py, tecla 2):
#   LOW  (pista):     STOP = frena 5 s, GO = arranca, MUNECO = frena 10 s
#   HIGH (felicidad): STOP = motor izquierdo, GO = motor derecho, MUNECO = reversa
STOP_PIN = 26    # GPIO26 -> pin fisico 37 -> PinPare 12 del Arduino
GO_PIN = 16      # GPIO16 -> pin fisico 36 -> PinSemaforo 13 del Arduino
MUNECO_PIN = 20  # GPIO20 -> pin fisico 38 -> PinMuneco 7 del Arduino
MODO_PIN = 21    # GPIO21 -> pin fisico 40 -> PinModo 8 del Arduino

# --- Modelo -------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
# Entrenado con el muneco (tools/entrenar_y_convertir.ipynb). El de 2025, sin
# muneco, sigue en model/yolov8npareysemaforo.hef: para volver a el, cambiar
# esta ruta y sacar CLASE_MUNECO de ETIQUETAS.
RUTA_HEF = RAIZ / "model" / "yolov8n_pare_semaforo_muneco.hef"

CLASE_PARE = "PARE"
CLASE_VERDE = "semaforoverde"
CLASE_MUNECO = "muneco"

# El orden importa: es el orden de clases con el que se entreno el modelo y con
# el que se compilo el .hef. Coincide con model/labels.txt.
ETIQUETAS = [CLASE_PARE, CLASE_VERDE, CLASE_MUNECO]

# --- Umbrales de deteccion ----------------------------------------------------
# Heredados de la version 2025 que funciono en la pista.
UMBRAL_PARE = 0.3
UMBRAL_VERDE = 0.4

UMBRAL_MUNECO = 0.4

# Cuanto tiempo se mantiene activo cada pin una vez disparado. Coinciden con
# lo que frena el Arduino (tiempo_pare y tiempo_muneco en el sketch).
DURACION_PARE = 5.0     # segundos
DURACION_MUNECO = 10.0  # segundos

# --- Camara -------------------------------------------------------------------
# El modelo espera 640x640, asi que la camara se configura directo a esa medida
# y evitamos tener que redimensionar cada frame.
RESOLUCION = (640, 640)

# Ojo con el nombre: en Picamera2 el formato "BGR888" entrega los canales en
# orden R,G,B dentro del array de numpy (la nomenclatura esta invertida respecto
# de lo que uno esperaria). Los modelos del Hailo Model Zoo esperan RGB, asi que
# este es el formato correcto para alimentar al Hailo sin conversion extra.
FORMATO_CAMARA = "BGR888"

# La camara va montada al reves en el chasis.
ROTAR_PREVIEW_180 = True

# --- Video por red ------------------------------------------------------------
# deteccion_hailo_stream.py sirve el video en http://bumblebee.local:PUERTO_STREAM
PUERTO_STREAM = 8000
# La camara saca dos imagenes de cada cuadro: esta para el video y otra de
# RESOLUCION para el Hailo. El sensor imx219 es 4:3; su modo 1920x1080 es un
# recorte del centro, en cambio 1640x1232 ve el campo completo (promedia de a
# 4 pixeles) y llega a 81 FPS. Se fuerza ese modo y el ISP lo achica para el
# video sin recortar.
MODO_SENSOR = (1640, 1232)
# A 1640x1232 y calidad 80 el MJPEG no entraba por el WiFi de la Pi con el robot
# andando: se encolaban 3.5 MB y el video llegaba a los saltos. Asi pesa menos de
# la mitad, y en YouTube no se nota porque igual lo recomprime a 4.5 Mbps.
RESOLUCION_STREAM = (1280, 960)
FPS_CAMARA = 30
# La Pi 5 no tiene codificador de video por hardware: cada JPEG lo comprime la
# CPU. Bajar la calidad alivia CPU y WiFi a costa de la imagen.
CALIDAD_JPEG = 60

# --- Loop ---------------------------------------------------------------------
PAUSA_LOOP = 0.05  # segundos; evita saturar la CPU en el bucle principal

# --- Modo felicidad -----------------------------------------------------------
# Programa aparte (deteccion_felicidad_stream.py): personas, caras y una carita
# por cara segun cuan feliz se ve. No usa GPIO: en este modo los motores los
# maneja robot.py con WASD.
RUTA_HEF_PERSONAS = RAIZ / "model" / "personas_yolov8n.hef"
RUTA_HEF_CARAS = RAIZ / "model" / "caras_scrfd.hef"
RUTA_ONNX_EMOCION = RAIZ / "model" / "emocion_hsemotion.onnx"

# Indice de la clase "person" en las 80 de COCO.
INDICE_PERSONA_COCO = 0
UMBRAL_PERSONA = 0.4
UMBRAL_CARA = 0.5

# Cortes de la valencia (-1 triste .. 1 feliz) que separan las 5 caritas.
# Son valores iniciales: se ajustan midiendo el modelo con tools/medir_valencia.py.
CORTES_VALENCIA = (-0.5, -0.1, 0.2, 0.5)

# Cuantos cuadros se promedian para que la carita no parpadee.
VENTANA_SUAVIZADO = 5
# Superposicion minima entre dos cuadros para decir "es la misma cara".
IOU_SEGUIMIENTO = 0.3
# Cuadros seguidos sin ver una cara antes de olvidar su id.
CUADROS_PERDIDOS_MAX = 10
# Tope de caras a las que se les calcula la emocion por cuadro: la emocion corre
# en la CPU y con una multitud frenaria el video.
MAX_CARAS_EVALUADAS = 6
# Pausa entre evaluaciones de emocion. Sin pausa el hilo se come la CPU entera y
# la Pi se calienta hasta frenarse; con 0.15 s la carita tardaba ~1 s en
# reaccionar (la ventana de suavizado son 5 mediciones). Con una cara en cuadro,
# 0.03 s da ~29 FPS y ~0.3 s de reaccion, pero la Pi llega a 86 C sin ventilador;
# 0.06 s es un punto medio y 0.08 s ~37 FPS. Elegido 0.03 s: prioriza la reaccion.
# Sin caras la emocion no corre y el video llega a ~39 FPS.
PAUSA_EMOCION = 0.03   # segundos entre evaluaciones
HILOS_EMOCION = 2      # nucleos de onnxruntime; los otros quedan para video
# Resolucion del video del modo felicidad. Mas chica que RESOLUCION_STREAM porque
# el JPEG lo comprime la CPU: a 1640x1232 tarda ~37 ms por cuadro y a 1280x960
# ~20 ms. El sensor sigue en MODO_SENSOR (campo completo); el ISP de la camara
# escala sin costo de CPU. Las cajas son normalizadas, asi que no se afectan.
RESOLUCION_STREAM_FELICIDAD = (1280, 960)
# FPS pedidos a la camara en el modo felicidad. Medido en la Pi con yolov8n +
# scrfd_500m: con el dibujo de Pillow, subir la camara sobre 30 no servia (el
# video bajaba a ~27 porque dibujo y JPEG competian por el GIL). Con el dibujo
# en OpenCV (~1 ms por cuadro en vez de ~12) sale ~39 FPS de inferencia y de
# video con la CPU al 35%; ahora el tope lo pone el Hailo con los dos modelos.
FPS_CAMARA_FELICIDAD = 60

# --- Fotos para el dataset del muneco ----------------------------------------
# deteccion_hailo_stream.py --fotos (o robot.py --fotos) guarda, mientras anda
# normal, la imagen de 640x640 que recibe el Hailo: el modelo se entrena con lo
# mismo que despues ve en la pista. Una carpeta por sesion.
CARPETA_DATASET = Path.home() / "dataset_muneco"
INTERVALO_FOTOS = 1.0  # segundos; mas seguido salen fotos casi iguales
CALIDAD_FOTOS = 95     # JPEG; alta, porque es para entrenar

# --- robot.py: cambio de modo y manejo con WASD -------------------------------
# Pagina de control: http://bumblebee.local:PUERTO_CONTROL. El video sigue en
# PUERTO_STREAM, que es lo que carga OBS.
PUERTO_CONTROL = 8080
# Cuanto se espera a que un programa termine al cambiar de modo antes de matarlo.
ESPERA_CIERRE = 10.0  # segundos

# Si la pagina deja de mandar teclas por este tiempo, se apagan los motores. La
# pagina las repite cada 100 ms mientras haya una apretada: si se cae el WiFi o
# se cierra la pestana con la W apretada, el robot no sigue de largo.
TIEMPO_SIN_TECLAS = 0.4  # segundos
