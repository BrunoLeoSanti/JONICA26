# Modelos

| Archivo | Estado |
|---|---|
| `yolov8npareysemaforo.pt` | ✅ presente — modelo entrenado, heredado de JONICA25 |
| `yolov8npareysemaforo.hef` | ⏳ **falta generarlo** |
| `labels.txt` | ✅ presente — orden de clases, tiene que coincidir con el `.hef` |

## Cómo generar el `.hef`

El `.hef` no está versionado todavía porque hay que compilarlo. El
procedimiento está en
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
