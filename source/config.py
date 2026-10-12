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

# --- Loop ---------------------------------------------------------------------
PAUSA_LOOP = 0.05  # segundos; evita saturar la CPU en el bucle principal
