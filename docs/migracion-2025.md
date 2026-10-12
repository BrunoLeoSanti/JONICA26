# Qué cambió respecto de JONICA25

El proyecto es el mismo robot seguidor de línea con visión por computadora.
Lo que cambió este año es **el cerebro**, no el comportamiento.

## El cambio de hardware

| | 2025 | 2026 |
|---|---|---|
| Computadora | Raspberry Pi 4 — 8 GB | Raspberry Pi 5 — 8 GB |
| Acelerador de IA | ninguno | AI HAT+ 26 TOPS (Hailo-8) |
| Dónde corre la inferencia | CPU | chip Hailo dedicado |
| Formato del modelo | NCNN | HEF (INT8) |
| Librería de inferencia | Ultralytics + NCNN | HailoRT |
| Librería de GPIO | `RPi.GPIO` | `gpiozero` + lgpio |
| Control de motores | Arduino | Arduino *(sin cambios)* |

En 2025 no había acelerador, así que la inferencia salía por CPU y hubo que
exportar el modelo a NCNN para que entrara en tiempo real. Con el Hailo-8 eso
deja de ser necesario: la detección se va a un chip dedicado y la CPU de la
Pi queda libre.

## Lo que hubo que tocar en el código

Dos cosas, y nada más.

### 1. El modelo ya no es NCNN

```python
# 2025
from ultralytics import YOLO
model = YOLO("yolov8npareysemaforo_ncnn_model", task="detect")
results = model.track(frame, verbose=False)

# 2026
from hailo_detector import DetectorHailo
with DetectorHailo() as detector:
    detecciones = detector.detectar(frame)
```

El `.hef` se compila con el NMS adentro, así que el chip devuelve cajas ya
decodificadas y filtradas. No queda postproceso en Python.

El procedimiento completo de conversión está en `conversion-modelo.md`.

### 2. `RPi.GPIO` no funciona en la Raspberry Pi 5

Este fue el cambio menos esperado y vale la pena entenderlo.

`RPi.GPIO` escribe directamente sobre los registros de hardware del
procesador, a través de `/dev/mem`. En la Pi 5 los pines GPIO ya no cuelgan
del SoC sino de un chip aparte, el **RP1**, así que la librería termina
escribiendo en una dirección de memoria que no controla nada. No tira error:
simplemente los pines nunca cambian de estado.

Se migró a `gpiozero` (que en Pi 5 usa lgpio por debajo):

```python
# 2025
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(STOP_PIN, GPIO.OUT)
GPIO.output(STOP_PIN, 1)

# 2026
from gpiozero import DigitalOutputDevice
stop = DigitalOutputDevice(STOP_PIN, initial_value=False)
stop.on()
```

Existía una alternativa más rápida: el paquete `rpi-lgpio`, que es un
reemplazo drop-in y deja correr el código viejo sin tocarlo. Se descartó a
propósito — preferimos la librería que Raspberry Pi mantiene a futuro antes
que una capa de compatibilidad sobre una librería discontinuada.

## Lo que NO cambió

**El Arduino no se tocó.** Ni una línea del `.ino`.

Eso no es casualidad, y es la parte del diseño que más vale la pena mirar:
la Raspberry y el Arduino se comunican por **exactamente dos cables**
(GPIO26 = PARE, GPIO16 = GO). Toda la visión por computadora vive de un lado
de esa frontera y todo el control PID vive del otro.

Cambiar la computadora, el acelerador, el formato del modelo y la librería de
GPIO no cruzó esa frontera ni una sola vez. Por eso se pudo reemplazar el
cerebro del robot entero sin volver a calibrar el PID.

Tampoco cambiaron:

- Los **pines** (26 y 16), así que sirve el cableado del año pasado.
- Los **umbrales** de confianza (0.3 para PARE, 0.4 para el semáforo).
- La **duración del PARE** (5 segundos).
- La **arquitectura de hilos**: captura, inferencia y control siguen separados.
- El **modelo entrenado**: es el mismo `.pt` de 2025, sólo cambia el formato
  en el que se ejecuta.

## Mejoras aprovechando la reescritura

- La lógica del timer de PARE estaba mezclada dentro del bucle principal.
  Ahora vive en `source/senales.py` como máquina de estados, y tiene tests que
  corren en cualquier computadora, sin Raspberry.
- Los números de calibración (pines, umbrales, tiempos) estaban repartidos por
  los scripts. Ahora están todos juntos en `source/config.py`.
- Se agregó `tools/verificar_hef.py`, que mide cuánta precisión se perdió al
  cuantizar. En 2025 no hacía falta porque NCNN corría en punto flotante.
