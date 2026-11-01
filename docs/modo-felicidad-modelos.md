# Modelos del modo felicidad

Todos verificados en la Pi (Hailo-8, HailoRT 4.23.0, firmware 4.23.0) el 1 de noviembre de 2026.

| Archivo | Qué es | Origen |
|---|---|---|
| `model/personas_yolov8.hef` | YOLOv8s COCO, 80 clases, NMS incluido en el chip | Hailo Model Zoo v2.18.0, `hailo8` |
| `model/caras_scrfd.hef` | SCRFD 500m, detector de caras, **sin NMS** | Hailo Model Zoo v2.18.0, `hailo8` |
| `model/emocion_hsemotion.onnx` | HSEmotion `enet_b0_8_va_mtl` (8 emociones + valencia + activación) | [HSE-asavchenko/face-emotion-recognition](https://github.com/HSE-asavchenko/face-emotion-recognition), Apache-2.0 |

Los `.hef` se bajaron de
`https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.18.0/hailo8/<modelo>.hef`.
`yolov8n.hef` (más rápido, menos preciso) y `scrfd_10g.hef` (más preciso)
también existen ahí por si hace falta cambiar. **`scrfd_2_5g.hef` no está
disponible** (el servidor responde 403): por eso se empezó con `scrfd_500m`.

## personas_yolov8.hef

- Entrada: `yolov8s/input_layer1`, UINT8, NHWC 640x640x3 (RGB).
- Salida: un tensor `yolov8s/yolov8_nms_postprocess`, FLOAT32, "NMS by class":
  80 clases, hasta 100 cajas por clase. El mismo formato que el `.hef` propio,
  así que sirve `parsear_salida_nms` con las 80 etiquetas de COCO.
- La clase `person` es el índice **0**.
- El score mínimo con que se compiló es 0.20 y el IoU del NMS es 0.70.

## caras_scrfd.hef

- Entrada: `scrfd_500m/input_layer1`, UINT8, NHWC 640x640x3 (RGB).
- Nueve salidas, tres por escala, todas **UINT8 cuantizadas** (hay que pedir
  `FLOAT32` al armar `OutputVStreamParams` o desceder con scale/zero-point):

| Escala | stride | Cajas (2 anchors x 4) | Scores (2 anchors) | Puntos (2 anchors x 10) |
|---|---|---|---|---|
| 80x80 | 8 | `conv27` 80x80x8 | `conv26` 80x80x2 | `conv25` 80x80x20 |
| 40x40 | 16 | `conv33` 40x40x8 | `conv32` 40x40x2 | `conv34` 40x40x20 |
| 20x20 | 32 | `conv39` 20x20x8 | `conv38` 20x20x2 | `conv40` 20x20x20 |

- La asignación (caja / score / puntos) se dedujo de los canales (8 / 2 / 20);
  hay que confirmarla con una foto real en la Tarea 3. Los de 20 canales vienen
  en formato `FCR`, que no es NHWC común: confirmar la forma que llega a Python.
- No trae NMS ni decodificado: se hace en `source/caras_scrfd.py`.

## emocion_hsemotion.onnx

- Entrada: `input`, float32, `(batch, 3, 224, 224)`. Preprocesado de la
  librería oficial: recorte RGB, redimensionar a 224x224, dividir por 255 y
  normalizar con media `[0.485, 0.456, 0.406]` y desvío `[0.229, 0.224, 0.225]`.
- Salida: `output`, `(batch, 10)`. Los primeros 8 son logits de emoción
  (`Anger, Contempt, Disgust, Fear, Happiness, Neutral, Sadness, Surprise`) y
  los **dos últimos son valencia y activación**. El rango real de la valencia
  se mide en la Tarea 5.

## Dependencias en la Pi

Se usa el Python del sistema (`/usr/bin/python3`, el único con `hailo_platform`
y `picamera2`), no el venv `~/jonica26_env`. `onnxruntime 1.31.1` se instaló con
`pip install --user --break-system-packages onnxruntime`. Pillow 11.1.0 ya estaba.
