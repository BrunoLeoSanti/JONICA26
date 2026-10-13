# JONICA26 — contexto del proyecto

Documento de contexto para retomar el trabajo sin historia previa.
Última actualización: **12 de octubre de 2026**.

---

## Qué es

Robot autónomo para feria de ciencias. Sigue una línea con un controlador PID
y, en paralelo, detecta señales de tránsito con una red neuronal: frena ante
un cartel de **PARE** y arranca ante un **semáforo en verde**.

Es la edición 2026 de un proyecto que viene de años anteriores:

- [JONICA24](https://github.com/BrunoLeoSanti/JONICA24) — detección básica de frames
- [JONICA25](https://github.com/BrunoLeoSanti/JONICA25) — Raspberry Pi 4 + NCNN
- **JONICA26** (este) — Raspberry Pi 5 + acelerador Hailo

Repo: https://github.com/BrunoLeoSanti/JONICA26 (público)
Colaboradores: `BrunoLeoSanti` (admin), `Malvaso` (write).

### Qué cambió este año

Sólo el hardware de inferencia. El comportamiento del robot es el mismo.

| | 2025 | 2026 |
|---|---|---|
| Computadora | Raspberry Pi 4 — 8 GB | Raspberry Pi 5 — 8 GB |
| Acelerador | ninguno | AI HAT+ 26 TOPS (Hailo-8) |
| Inferencia | CPU, NCNN | chip Hailo dedicado, HEF INT8 |
| Librería | Ultralytics + NCNN | HailoRT |
| GPIO | `RPi.GPIO` | `gpiozero` + lgpio |
| Arduino | — | **sin cambios** |

---

## Arquitectura

Dos cerebros, y entre ellos **exactamente dos cables**:

```
RASPBERRY PI 5 + AI HAT+ (Hailo-8)        ARDUINO UNO
  camara -> YOLOv8n en el Hailo             5 sensores IR -> PID -> motores
       |                                         ^        ^
       +-- GPIO26 (PARE) ------------------------+        |
       +-- GPIO16 (GO) ---------------------------------- +
```

**La Raspberry ve. El Arduino maneja.** La Pi no sabe nada de motores; el
Arduino no sabe nada de redes neuronales.

> **Esta frontera de dos pines es la decisión de diseño más importante del
> proyecto.** Es la razón por la que se pudo cambiar computadora, acelerador,
> formato de modelo y librería de GPIO sin tocar una línea del Arduino ni
> recalibrar el PID. Cualquier cambio futuro debería respetarla: si algo
> necesita cruzar más información entre los dos, pensarlo dos veces.

### Las dos señales se comportan distinto, a propósito

- **Semáforo verde**: instantáneo. El pin sigue a la detección.
- **PARE**: se engancha 5 segundos. Si siguiera a la detección, el robot
  dejaría de ver el cartel al acercarse y saldría disparando antes de frenar.

---

## Hardware real

| | |
|---|---|
| Placa | Raspberry Pi 5 Model B Rev 1.1, 8 GB |
| Acelerador | AI HAT+ 26 TOPS — **Hailo-8** (no 8L) |
| Cámara | imx219 (Camera Module v2) |
| Sistema | Debian 13 **trixie**, 64 bits, kernel 6.18 |
| Python | 3.13.5 |
| HailoRT | **4.23.0** |
| Microcontrolador | Arduino UNO, 5 sensores IR (A0–A4), 2 motores DC |

### Acceso

```bash
ssh jonica            # alias ya configurado en ~/.ssh/config del Mac
```

Host `Bumblebee`, usuario `jonica`, IP `192.168.100.138` (ethernet; también
responde `bumblebee.local`). Hay una IP WiFi `.137` pero con 212 ms de
latencia — **usar siempre ethernet**. Autenticación por clave, sin contraseña.

La máquina de desarrollo es un **MacBook Air M5 (arm64)**. Esto importa: no
puede compilar modelos para Hailo (ver más abajo).

---

## Estado actual

### Terminado

- Repo creado con estructura, documentación y README.
- Código de la Pi migrado a Pi 5 + HailoRT.
- 19 tests pasando (lógica pura, corren en cualquier máquina).
- **Raspberry 100 % provisionada y verificada**: `hailo-all` 5.1.1,
  `hailort` 4.23.0, `/dev/hailo0` presente, `hailortcli` reporta `HAILO8`,
  PCIe en Gen 3, firmware actualizado, cámara funcionando.

- **Modelo convertido a `.hef`** y versionado en
  `model/yolov8npareysemaforo.hef`. Compilado con DFC 3.33.1 + Model Zoo v2.18
  para target `hailo8`. Verificado contra el `.pt` original en el emulador del
  DFC sobre 42 imágenes que no se usaron para calibrar: **recall 100 %,
  precisión 96.2 %**.
- Set de verificación versionado en `docs/muestras/` (42 imágenes) con
  `docs/referencia_pt.json` (las detecciones del `.pt`), para poder repetir la
  medición cuando se quiera.

### Pendiente

- Verificar el `.hef` sobre el acelerador real:
  `hailortcli parse-hef` y después `tools/verificar_hef.py`.
- Probar con la cámara en vivo.
- Pruebas en pista; medir FPS, distancia de frenado y tasa de detección.
- Completar las secciones de resultados y galería del README.
- Fotos, videos y póster 2026.

---

## El modelo

YOLOv8n, **2 clases**: `PARE` y `semaforoverde`. Entrada 640×640 RGB.
Entrenado con Ultralytics 8.2.103 sobre el dataset `pareysemaforo-3` de
Roboflow. Es **el mismo modelo entrenado que en 2025**; lo único que cambia es
el formato de ejecución.

### El pipeline de conversión

```
.pt  --ultralytics-->  .onnx  --DFC-->  .har  --cuantizacion INT8-->  .har  --compilacion-->  .hef
```

Se usa el **Hailo Model Zoo** (`hailomz`) y no el DFC crudo, porque ya trae
resueltos los dos puntos donde más se traba la gente con YOLOv8: los 6 *end
nodes* donde hay que cortar antes del decode, y la configuración del NMS.

El NMS se compila **dentro del `.hef`** para que corra en el chip. Por eso
`hailo_detector.py` recibe cajas ya decodificadas y no tiene postproceso.

---

## Trampas conocidas

Cosas que ya nos costaron tiempo. No repetirlas.

### 1. `RPi.GPIO` no funciona en la Raspberry Pi 5

Escribe sobre los registros del SoC vía `/dev/mem`, pero en la Pi 5 los GPIO
cuelgan del chip **RP1**. **No falla con error**: los pines simplemente nunca
cambian de estado. El proyecto usa `gpiozero`. (Está instalado `RPi.GPIO` en
la Pi, pero no se usa.)

### 2. El compilador de Hailo no corre en esta máquina

El Dataflow Compiler necesita **Linux x86_64 con AVX**. No funciona en macOS,
ni en Apple Silicon, ni en la propia Raspberry (el acelerador *ejecuta* `.hef`
pero no los *produce*). Por eso la conversión va en **Google Colab**.

### 3. La versión del DFC tiene que coincidir con la de HailoRT

| HailoRT en la Pi | DFC |
|---|---|
| **4.23.x** (el nuestro) | **3.33.x** |
| 4.22.x | 3.32.x |

**La línea DFC 5.x no sirve**: es para Hailo-10H y Hailo-15, y aparece primero
en la Developer Zone por ser la más nueva. Un `.hef` compilado con la versión
equivocada **compila bien y después no carga**.

Chequeo rápido apenas el `.hef` esté en la Pi:

```bash
hailortcli parse-hef model/yolov8npareysemaforo.hef
```

### 4. La cuantización INT8 degrada en silencio

El `.hef` puede compilar bien, cargar bien, correr rápido y **detectar la
mitad**. Es la falla típica de los YOLOv8 custom sobre Hailo. Por eso hay
verificación obligatoria en dos etapas: en Colab contra el emulador del DFC
(paso 5 del notebook), y en la Pi con `tools/verificar_hef.py`.

Criterio: recall ≥ 90 % respecto del `.pt` → OK. Entre 75 y 90 % → probar con
cuidado. Menos de 75 % → recompilar con más imágenes de calibración o un set
más representativo de la pista.

### 5. El Model Zoo también tiene dos líneas, y la default es la equivocada

`pip install git+.../hailo_model_zoo.git` trae la **5.x**, que es para
Hailo-10H y Hailo-15 y **ya no soporta Hailo-8**: `--hw-arch hailo8` ni
figura entre las opciones válidas. Hay que fijar **v2.18**, que es la que
corresponde a DFC 3.33 + HailoRT 4.23. Además hay que instalarla clonando el
tag y con `--no-build-isolation`, porque desde la URL `git+` falla al
construir.

Un detalle más: el Model Zoo importa todos sus backends de inferencia al
arrancar, y el de torch espera una clase que DFC 3.33 no tiene. Hay que sacar
`core/infer/torch_infer.py` del escaneo. No se pierde nada: la calibración
usa `SimulationInferenceModel`, que sí está.

### 6. La salida NMS puede venir transpuesta

Un array por clase, pero la disposición varía: `(N, 5)` —una detección por
fila— o `(5, max_det)` —un campo por fila, con columnas de ceros de relleno—.
El emulador del DFC devuelve la segunda.

Leer una como si fuera la otra **no da error: da cero detecciones**, que es
indistinguible de "el modelo no detecta nada". Nos costó un susto: parecía
que la cuantización había destruido el modelo con 0 % de recall, cuando en
realidad daba 100 %. `parsear_salida_nms` ahora detecta la forma en vez de
asumirla, y hay tests para las dos.

### 7. `hailo8` y `hailo8l` no son intercambiables

Este proyecto es **`hailo8`** (26 TOPS). Un `.hef` de uno no carga en el otro.

### 8. El wheel del DFC se baja a mano

Está detrás del login de la Hailo Developer Zone y no se puede automatizar.
Las versiones viejas están ocultas; hay que buscarlas con el filtro de archivo
o escribiendo en el buscador (el desplegable por categoría a veces no las
muestra).

---

## Estructura del repo

```
source/                        Código de la Raspberry Pi 5
  config.py                    Pines, umbrales, tiempos — TOCAR ACÁ al calibrar
  senales.py                   Máquina de estados PARE/GO (lógica pura, testeable)
  hailo_detector.py            Inferencia sobre el Hailo-8 + parseo del NMS
  gpio_control.py              Salidas hacia el Arduino (gpiozero)
  deteccion_hailo.py           Programa principal, headless, para la pista
  deteccion_hailo_preview.py   Con ventana pygame, para el banco de pruebas
arduino/lineaydeteccion/       Sketch del PID. NO SE TOCÓ desde 2025.
model/                         .pt, labels.txt, y el .hef cuando exista
tools/
  conversion_pt_a_hef.ipynb    Notebook de Colab (.pt -> .hef)
  verificar_hef.py             Mide pérdida por cuantización (corre en la Pi)
  diagnostico_pi.sh            Qué hay instalado en la Pi (solo lectura)
tests/                         Tests de lógica pura
hardware/                      Esquemático y diseños 3D
docs/                          instalacion-pi5, conversion-modelo, migracion-2025
```

### Diseño del código

`config.py` centraliza todo lo que se toca al calibrar. Los módulos que
necesitan hardware (`hailo_detector`, `gpio_control`) hacen **import diferido**
de `hailo_platform` y `gpiozero`, así se pueden importar y testear fuera de la
Raspberry. La lógica pura (`senales.py`, el parser del NMS) no toca hardware y
tiene tests.

```bash
python3 -m pytest tests/ -v     # 19 tests, corren en cualquier máquina
```

---

## Convenciones

- **Todo en español**: código, comentarios, documentación y commits. Sin
  tildes ni ñ dentro del código fuente y los mensajes de commit (sí en los
  `.md`), para evitar problemas de encoding.
- Los comentarios explican **por qué**, no qué. El código ya dice qué hace.
- El repo no tiene licencia, por decisión del autor.
- Commits en español, con cuerpo explicando el razonamiento.
