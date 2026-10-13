# Modelos

| Archivo | Estado |
|---|---|
| `yolov8npareysemaforo.pt` | modelo entrenado, heredado de JONICA25 |
| `yolov8npareysemaforo.hef` | compilado para **Hailo-8**, listo para usar |
| `labels.txt` | orden de clases, tiene que coincidir con el `.hef` |

## El `.hef` actual

Compilado el **12 de octubre de 2026** con este stack:

| | |
|---|---|
| Dataflow Compiler | 3.33.1 |
| Hailo Model Zoo | v2.18 |
| Target | `hailo8` (26 TOPS) |
| Calibración | 64 imágenes del dataset `pareysemaforo-3` |
| Nivel de optimización | 0 (sin GPU y con menos de 1024 imágenes) |

Verificación contra el `.pt` original sobre 42 imágenes que **no** se usaron
para calibrar: **recall 100 %, precisión 96.2 %**. La cuantización a INT8 no
perdió detecciones.

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
