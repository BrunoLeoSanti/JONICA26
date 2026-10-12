# Conversión del modelo: de `.pt` a `.hef`

El acelerador Hailo no ejecuta PyTorch ni ONNX. Corre un formato propio,
`.hef`, que hay que generar antes de poder usar el modelo en el robot.

El procedimiento ejecutable está en **[`tools/conversion_pt_a_hef.ipynb`](../tools/conversion_pt_a_hef.ipynb)**
(notebook de Google Colab). Este documento explica el *por qué* de cada paso,
que es lo que el notebook no puede contar mientras corre.

## El camino

```
yolov8npareysemaforo.pt          modelo entrenado (PyTorch)
          ↓  ultralytics export
        .onnx                    formato intermedio
          ↓  Hailo Dataflow Compiler
        .har  (parseado)
          ↓  cuantización INT8  ← necesita imágenes de calibración
        .har  (cuantizado)
          ↓  compilación
yolov8npareysemaforo.hef         corre en el Hailo-8
```

## Dónde se puede compilar (y dónde no)

El Hailo Dataflow Compiler corre **sólo en Linux x86_64 con instrucciones
AVX**, y pide Python 3.8–3.10 y 16 GB de RAM.

No se puede compilar en:

- **macOS**, ni Intel ni Apple Silicon.
- **La Raspberry Pi**. El acelerador *ejecuta* modelos `.hef`, pero no los
  *produce*. El compilador es x86.
- Emulación x86 sobre ARM: aunque arranque, falta AVX.

Por eso el notebook está hecho para **Google Colab**, que es x86, gratis, y no
requiere instalar nada localmente.

## El wheel del DFC hay que bajarlo a mano

El compilador no está en PyPI. Se baja de la
[Hailo Developer Zone](https://hailo.ai/developer-zone/), que pide una cuenta
gratuita. **Este paso no se puede automatizar**: la descarga está detrás del
login. Bajá el `.whl` para Python 3.10 y subilo al notebook.

## Por qué el NMS va adentro del `.hef`

El modelo exportado a ONNX **no lleva NMS**. El NMS se agrega en la
compilación y queda dentro del `.hef`, corriendo en el chip.

La alternativa sería hacer el NMS en Python sobre la Raspberry, pero eso
significa traer del acelerador todos los tensores crudos de salida —
miles de cajas candidatas por cuadro — y filtrarlos con la CPU. Justo lo que
estábamos tratando de evitar al poner un acelerador.

Con el NMS compilado adentro, `hailo_detector.py` recibe cajas ya decodificadas
y filtradas, y no tiene nada de postproceso.

## Por qué usamos el Model Zoo y no el DFC directo

El notebook llama a `hailomz` (Hailo Model Zoo) en vez de scriptear el DFC a
mano. La razón es que YOLOv8 tiene dos puntos difíciles que el Model Zoo ya
trae resueltos:

1. **Los end nodes.** Hay que cortar el modelo en los 6 nodos exactos
   anteriores al decode. Si los nombrás mal, el compilador falla con errores
   poco claros — o peor, compila algo que no detecta nada.
2. **La configuración del NMS**, que hay que declarar en un archivo `.alls`.

Si algún día el Model Zoo da problemas con las clases custom, el plan B es
usar el DFC crudo con `runner.translate_onnx_model()` y un `.alls` escrito a
mano. Es más control, y bastante más fácil de romper.

## La calibración es lo que más importa

El `.hef` corre en **INT8**: cada número pasa de 32 bits de punto flotante a
8 bits enteros. Para decidir cómo mapear los rangos, el compilador necesita
ver imágenes reales y medir qué valores toma cada capa.

La documentación de Hailo pide **más de 1024 imágenes**, y tienen que
parecerse a lo que el robot va a ver. Usamos el mismo dataset con el que se
entrenó (`pareysemaforo-3` en Roboflow).

Si la calibración es mala, el modelo compila igual y falla en silencio: menos
detecciones, confianzas más bajas, o directamente nada.

## El target importa y no es intercambiable

```
--hw-arch hailo8      ← AI HAT+ de 26 TOPS  (el nuestro)
--hw-arch hailo8l     ← AI HAT+ de 13 TOPS
```

Un `.hef` compilado para uno **no carga** en el otro. Si no estás seguro de
qué placa tenés:

```bash
hailortcli fw-control identify     # en la Raspberry
```

## Verificar siempre, no es opcional

El riesgo real de este proceso no es que falle la compilación: es que
**funcione y detecte peor**. La cuantización degrada en silencio, y hay
bastantes casos reportados de modelos YOLOv8 custom que compilan perfecto y
después no detectan casi nada en la Pi.

Por eso la verificación está en dos etapas:

1. **En Colab** (paso 5 del notebook): compara el modelo original contra el ya
   cuantizado, usando el emulador del DFC. Detecta el problema sin necesidad
   de tener el hardware.
2. **En la Raspberry**: `tools/verificar_hef.py` repite la comparación contra
   el acelerador real.

Ambos reportan **recall** respecto del `.pt` original:

| Recall | Lectura |
|---|---|
| ≥ 90 % | Bien, listo para la pista |
| 75–90 % | Se perdió algo; probar con cuidado y considerar recalibrar |
| < 75 % | Mal; recompilar con más imágenes o un set más representativo |

## Si hay que recompilar

Las causas típicas de un recall bajo, en orden de probabilidad:

1. **Pocas imágenes de calibración.** Subí a 1024 o más.
2. **Calibración poco representativa.** Si el robot corre con otra luz, otro
   fondo u otra distancia que las fotos del dataset, sacá fotos nuevas con la
   propia Picamera2 en la pista y recalibrá con esas.
3. **Target equivocado** (`hailo8` vs `hailo8l`).
4. Si nada de eso alcanza, el DFC permite dejar algunas capas en 16 bits
   (cuantización mixta) a cambio de algo de velocidad. Sobra margen: el
   Hailo-8 corre YOLOv8n muy por encima de lo que este robot necesita.
