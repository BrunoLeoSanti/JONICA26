# Modelos

| Archivo | Estado |
|---|---|
| `yolov8n_pare_semaforo_muneco.hef` | **el que usa el robot**: PARE, semáforo verde y muñeco, Hailo-8 |
| `yolov8n_pare_semaforo_muneco.pt` | su `.pt`, entrenado en Colab |
| `yolov8npareysemaforo.pt` | modelo de 2 clases, heredado de JONICA25 |
| `yolov8npareysemaforo.hef` | su `.hef`, de respaldo |
| `labels.txt` | orden de clases del modelo en uso, tiene que coincidir con el `.hef` |

## El `.hef` con muñeco

Entrenado y compilado el **5 de noviembre de 2026** con
[`../tools/entrenar_y_convertir.ipynb`](../tools/entrenar_y_convertir.ipynb):
YOLOv8n desde COCO, Ultralytics 8.2.103, 100 épocas con `flipud=0.5` (el
modelo recibe la imagen de la cámara al revés), dataset Roboflow
`deteccion-3o8gk/pareysemaforo-fu6sg` v5 (545 imágenes). DFC 3.33.1 + Model
Zoo v2.18, target `hailo8`, 432 imágenes de calibración.

| | PARE | semáforo verde | muñeco |
|---|---|---|---|
| `.pt` sobre valid (recall) | 100 % | 100 % | 100 % |
| Emulador del DFC vs `.pt` (recall) | 100 % | 100 % | 100 % |

Precisión del cuantizado contra el `.pt`: 98.6 %. Ojo: valid tiene fotos
sacadas una por segundo, muy parecidas a las de train; la prueba que vale es
en la pista. Set de verificación en `docs/muestras_muneco/`:

```bash
python3 tools/verificar_hef.py --imagenes docs/muestras_muneco/muestras --referencia docs/muestras_muneco/referencia_pt.json
```

## El `.hef` de 2025 (2 clases)

Compilado el **12 de octubre de 2026** con este stack:

| | |
|---|---|
| Dataflow Compiler | 3.33.1 |
| Hailo Model Zoo | v2.18 |
| Target | `hailo8` (26 TOPS) |
| Calibración | 64 imágenes del dataset `pareysemaforo-3` |
| Nivel de optimización | 0 (sin GPU y con menos de 1024 imágenes) |

Verificado contra el `.pt` original sobre 42 imágenes que **no** se usaron
para calibrar:

| | Recall | Precisión |
|---|---|---|
| Emulador del DFC | 100 % | 96.2 % |
| **Hailo-8 real** | **100 %** | **100 %** |

La cuantización a INT8 no perdió una sola detección, y las confianzas se
mantienen altas (la mayoría entre 0.95 y 1.00). El falso positivo que aparecía
en el emulador no se reproduce en el hardware.

Para repetir la medición:

```bash
python3 tools/verificar_hef.py --imagenes docs/muestras/ --referencia docs/referencia_pt.json
```

## Cómo regenerarlo

El procedimiento está en
[`../tools/conversion_pt_a_hef.ipynb`](../tools/conversion_pt_a_hef.ipynb)
(Google Colab), explicado en
[`../docs/conversion-modelo.md`](../docs/conversion-modelo.md).

Para correrlo hacen falta dos cosas que no se pueden automatizar:

1. **El wheel del Dataflow Compiler**, que se baja de la
   [Hailo Developer Zone](https://hailo.ai/developer-zone/) con una cuenta
   gratuita (la descarga está detrás del login).
2. **La API key de Roboflow**, para bajar el dataset `pareysemaforo-3` que se
   usa como set de calibración.

Una vez generado, el `.hef` va en esta carpeta con el nombre
`yolov8npareysemaforo.hef`, que es el que espera `source/config.py`.

> Compilado para **`hailo8`** (AI HAT+ de 26 TOPS). Un `.hef` de `hailo8` no
> carga en una placa `hailo8l` de 13 TOPS, ni al revés.
