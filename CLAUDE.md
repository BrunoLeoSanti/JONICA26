# JONICA26 — contexto del proyecto

Documento de contexto para retomar el trabajo sin historia previa.
Última actualización: **1 de noviembre de 2026**.

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
| GPIO | `RPi.GPIO` | `lgpio` directo |
| Arduino | — | **sin cambios** |

---

## Arquitectura

Dos cerebros, y entre ellos **cuatro cables** (eran dos hasta el modo
felicidad):

```
RASPBERRY PI 5 + AI HAT+ (Hailo-8)        ARDUINO UNO
  camara -> YOLOv8n en el Hailo             5 sensores IR -> PID -> motores
       +-- GPIO26 (fisico 37) -> D12   PARE: frena 5 s   | felicidad: motor izq
       +-- GPIO16 (fisico 36) -> D13   GO: arranca       | felicidad: motor der
       +-- GPIO20 (fisico 38) -> D7    MUNECO: frena 10 s  | felicidad: reversa
       +-- GPIO21 (fisico 40) -> D8    MODO: bajo = pista, alto = felicidad
                (GND comun: fisico 39)
```

`source/robot.py` coordina todo: corre el programa de pista o el de felicidad
(no pueden correr a la vez, comparten cámara y Hailo) y los alterna con la
tecla **2**. Se maneja desde el navegador de la compu en
`http://bumblebee.local:8080`; el video para OBS sigue en `:8000/stream`.

En modo felicidad el Arduino deja de seguir la linea: PARE/GO prenden un motor
cada uno y MUNECO los pone en reversa (WASD). La velocidad la pone el Arduino:
arranca en 110 y, yendo recto, sube de a poco hasta 150. Si la página deja de
mandar teclas 0.4 s, la Pi apaga los motores.

**La Raspberry ve. El Arduino maneja.** La Pi no sabe nada de motores; el
Arduino no sabe nada de redes neuronales.

> **Esta frontera de pocos pines es la decisión de diseño más importante del
> proyecto.** Es la razón por la que se pudo cambiar computadora, acelerador,
> formato de modelo y librería de GPIO sin tocar una línea del Arduino ni
> recalibrar el PID. Cualquier cambio futuro debería respetarla: si algo
> necesita cruzar más información entre los dos, pensarlo dos veces.

Los pines del Arduino son `INPUT` sin pullup, a propósito: con pullup, si el
programa de la Pi se corta los pines se leen HIGH, y en modo felicidad eso es
"los dos motores prendidos".

### Las dos señales se comportan distinto, a propósito

- **Semáforo verde**: instantáneo. El pin sigue a la detección.
- **PARE**: se engancha 5 segundos. Si siguiera a la detección, el robot
  dejaría de ver el cartel al acercarse y saldría disparando antes de frenar.
  El Arduino frena 5 s y después ignora el PARE hasta 15 s, para pasar el cartel.
- **Muñeco**: se engancha 10 segundos. El Arduino frena 10 s y después lo
  ignora 15 s contados desde que vuelve a arrancar.

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
| Microcontrolador | Arduino UNO, 4 sensores IR centrados (A3–A0; el A4 se sacó porque no andaba), 2 motores DC |

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
- 62 tests pasando (lógica pura, corren en cualquier máquina).
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

- **`.hef` verificado sobre el Hailo-8 real**: `hailortcli parse-hef` lo
  acepta, y `tools/verificar_hef.py` da **recall 100 %, precisión 100 %**
  sobre las 42 imágenes de prueba. La conversión del modelo está cerrada.

- **Modo felicidad (etapa 1)**, rama `modo-felicidad`: programa aparte que, con
  la cámara inclinada hacia arriba, detecta personas (YOLOv8n COCO) y caras
  (SCRFD 500m) en el Hailo-8 con el scheduler de HailoRT, estima la valencia de
  cada cara con HSEmotion en la CPU y dibuja una carita de 5 niveles pegada a
  cada cara en el stream de `:8000`. Verificado en la Pi sobre una foto real
  (4 personas, 3 caras, niveles coherentes); sin caras en vivo da 18 FPS.
  Diseño: `docs/superpowers/specs/2026-11-01-muneco-y-modo-felicidad-design.md`.

### Pendiente

- **Modo felicidad, prueba en vivo**: apuntar la cámara a personas, calibrar
  `CORTES_VALENCIA` en `config.py` con `--valencia`, medir FPS con 1 y 3 caras
  y confirmar que se ve en OBS.
- **Muñeco en pista (etapa 2)**: modelo de 3 clases entrenado y compilado el
  5/11 con `tools/entrenar_y_convertir.ipynb` (recall 100 % en el emulador,
  ver `model/README.md`); `config.py` ya lo usa. Falta: `verificar_hef.py`
  en la Pi con `docs/muestras_muneco/` y probarlo en la pista.
- Probar con la cámara en vivo (`source/deteccion_hailo_preview.py`).
- Pruebas en pista; medir FPS, distancia de frenado y tasa de detección.
- Completar las secciones de resultados y galería del README.
- Fotos, videos y póster 2026.

---

## El modelo

YOLOv8n, **3 clases** en este orden: `PARE`, `semaforoverde`, `muneco`.
Entrada 640×640 RGB. Entrenado en Colab con Ultralytics 8.2.103 sobre la v5 de
`deteccion-3o8gk/pareysemaforo-fu6sg` en Roboflow (que suma las fotos del
muñeco a `pareysemaforo-3`). El de 2025, de 2 clases, queda de respaldo en
`model/yolov8npareysemaforo.hef`.

El modelo recibe la imagen de la cámara **al revés** (va montada así y en pista
sólo se endereza el video); por eso se entrena con `flipud`.

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
cambian de estado. El proyecto usa `lgpio` directo. (Está instalado `RPi.GPIO` en
la Pi, pero no se usa.)

**`gpiozero` tampoco sirve para esto:** al cerrar un pin lo deja como entrada
*sin pull* (flotando) y lo sigue reteniendo hasta que muere el proceso. Con el
Arduino leyendo sin pullup, flotando = lee cualquier cosa; y `robot.py` no podía
pasarle los pines al programa de pista ("GPIO busy"). `gpio_control.PinSalida`
los suelta como entrada con pull-down, verificado con `pinctrl get 16,20,21,26`
(`ip pd`).

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

### 9. El Arduino no frena "mientras el pin esté en alto"

Al ver `PinPare` (D12) en alto, el sketch frena con `delay(5000)` y después
**ignora el pin 15 s** (`stopflag`). El pin del semáforo (D13) sólo sirve para
el arranque inicial. Por eso el muñeco tiene su propio cable (D7) y otra regla.

### 10. SCRFD no trae el NMS y sus salidas vienen cuantizadas

Los `.hef` de caras del Model Zoo devuelven 9 tensores crudos (3 escalas x
cajas, scores y puntos), sin decodificar. `source/caras_scrfd.py` los decodifica;
la escala se deduce del tamaño del tensor y no de su nombre (`convNN` cambia
entre `scrfd_500m` y `scrfd_10g`). `scrfd_2_5g.hef` no se puede bajar (403).

### 11. En la Pi, el Python con HailoRT es el del sistema

`/usr/bin/python3` tiene `hailo_platform` y `picamera2`; el venv
`~/jonica26_env` no. `onnxruntime` y `pytest` se instalaron con
`pip install --user --break-system-packages`. La copia de trabajo en la Pi es
`~/jonica_dev` (sin git; se copia desde el Mac), no `~/JONICA26`. Y cuidado con `pkill -f` por ssh:
si el patrón aparece en el propio comando, mata la sesión (usar `[d]eteccion`).
Y un proceso lanzado con `&` desde un shell no interactivo hereda SIGINT
*ignorado*: `robot.py` lo reactiva al arrancar (y toma SIGTERM como Ctrl+C).

---

## Estructura del repo

```
source/                        Código de la Raspberry Pi 5
  config.py                    Pines, umbrales, tiempos — TOCAR ACÁ al calibrar
  senales.py                   Máquina de estados PARE/GO (lógica pura, testeable)
  hailo_detector.py            Inferencia sobre el Hailo-8 + parseo del NMS
  gpio_control.py              Salidas hacia el Arduino (lgpio), 4 pines, modo pista o felicidad
  manejo_teclado.py            WASD -> motores y reversa, con vencimiento si dejan de llegar teclas
  robot.py                     Programa completo: alterna pista/felicidad con la tecla 2, pagina en :8080
  deteccion_hailo.py           Programa principal, headless, para la pista
  deteccion_hailo_preview.py   Con ventana pygame, para el banco de pruebas
  deteccion_hailo_stream.py    Video MJPEG 1640x1232 con las cajas, en :8000 (para OBS); --fotos arma dataset
  deteccion_felicidad_stream.py  Modo felicidad: personas, caras y carita por cara (--valencia calibra)
  felicidad.py                 Lógica pura: valencia->nivel, seguidor de caras, suavizado
  caras_scrfd.py               Decodifica las salidas crudas de SCRFD (+ NMS)
  hailo_multi.py               Dos modelos en el mismo Hailo con el scheduler
  emocion.py                   HSEmotion (ONNX, CPU): recorte de cara -> valencia
  dibujo_felicidad.py          Recorte de caras y dibujo de cajas y caritas
arduino/lineaydeteccion/       Sketch del PID, con muñeco y modo felicidad (4 pines)
model/                         .pt, labels.txt, y el .hef cuando exista
tools/
  conversion_pt_a_hef.ipynb    Notebook de Colab (.pt -> .hef)
                               Abrir: https://colab.research.google.com/github/BrunoLeoSanti/JONICA26/blob/main/tools/conversion_pt_a_hef.ipynb
  entrenar_y_convertir.ipynb   Colab (GPU): Roboflow -> entrenar 3 clases con muneco -> .hef verificado
                               Abrir: https://colab.research.google.com/github/BrunoLeoSanti/JONICA26/blob/main/tools/entrenar_y_convertir.ipynb
  medir_valencia.py            Valencia del modelo de emoción sobre fotos (calibra los cortes)
  verificar_hef.py             Mide pérdida por cuantización (corre en la Pi)
  registro_energia.py          CSV de voltaje, consumo, temperatura y UPS (corre en la Pi)
  diagnostico_pi.sh            Qué hay instalado en la Pi (solo lectura)
  fotos_muneco.sh              Modo pista + fotos 640x640 para el dataset del muñeco (corre en la Pi)
tests/                         Tests de lógica pura
hardware/                      Esquemático y diseños 3D
docs/                          instalacion-pi5, conversion-modelo, migracion-2025, modo-felicidad-modelos
```

### Diseño del código

`config.py` centraliza todo lo que se toca al calibrar. Los módulos que
necesitan hardware (`hailo_detector`, `gpio_control`) hacen **import diferido**
de `hailo_platform` y `lgpio`, así se pueden importar y testear fuera de la
Raspberry. La lógica pura (`senales.py`, el parser del NMS) no toca hardware y
tiene tests.

```bash
python3 -m pytest tests/ -v     # 62 tests, corren en cualquier máquina
```

---

## Convenciones

- **Todo en español**: código, comentarios, documentación y commits. Sin
  tildes ni ñ dentro del código fuente y los mensajes de commit (sí en los
  `.md`), para evitar problemas de encoding.
- Los comentarios explican **por qué**, no qué. El código ya dice qué hace.
- El repo no tiene licencia, por decisión del autor.
- Commits en español, con cuerpo explicando el razonamiento.
