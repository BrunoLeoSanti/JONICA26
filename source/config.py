"""Configuracion central del robot.

Todo lo que se toca al calibrar en la pista vive aca, para no tener que
buscar numeros sueltos repartidos por el codigo.
"""
from pathlib import Path

# --- Pines GPIO (numeracion BCM) ---------------------------------------------
# Contrato con el Arduino. Estos dos pines son la unica comunicacion entre la
# Raspberry y el control de motores, y NO cambiaron respecto de 2025: por eso
# el sketch .ino sigue sirviendo sin modificaciones.
STOP_PIN = 26   # GPIO26 -> pin fisico 37 -> PinPare 12 del Arduino
GO_PIN = 16     # GPIO16 -> pin fisico 36 -> PinSemaforo 13 del Arduino

# --- Modelo -------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
RUTA_HEF = RAIZ / "model" / "yolov8npareysemaforo.hef"

CLASE_PARE = "PARE"
CLASE_VERDE = "semaforoverde"

# El orden importa: es el orden de clases con el que se entreno el modelo y con
# el que se compilo el .hef. Coincide con model/labels.txt.
ETIQUETAS = [CLASE_PARE, CLASE_VERDE]

# --- Umbrales de deteccion ----------------------------------------------------
# Heredados de la version 2025 que funciono en la pista.
UMBRAL_PARE = 0.3
UMBRAL_VERDE = 0.4

# Cuanto tiempo se mantiene activo el pin de PARE una vez disparado.
DURACION_PARE = 5.0  # segundos

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
# 4 pixeles) y llega a 81 FPS. Se fuerza ese modo y se manda tal cual.
MODO_SENSOR = (1640, 1232)
RESOLUCION_STREAM = (1640, 1232)
FPS_CAMARA = 30
# La Pi 5 no tiene codificador de video por hardware: cada JPEG lo comprime la
# CPU. Bajar la calidad alivia CPU y WiFi a costa de la imagen.
CALIDAD_JPEG = 80

# --- Loop ---------------------------------------------------------------------
PAUSA_LOOP = 0.05  # segundos; evita saturar la CPU en el bucle principal

# --- Modo felicidad -----------------------------------------------------------
# Programa aparte (deteccion_felicidad_stream.py): personas, caras y una carita
# por cara segun cuan feliz se ve. No usa GPIO ni toca el Arduino.
RUTA_HEF_PERSONAS = RAIZ / "model" / "personas_yolov8.hef"
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
