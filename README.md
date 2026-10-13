# JONICA26 — Robot seguidor de línea con visión por computadora

Robot autónomo que sigue una línea con un controlador PID y, al mismo tiempo,
detecta señales de tránsito con una red neuronal: frena ante un cartel de
**PARE** y arranca ante un **semáforo en verde**.

Continuación de [JONICA25](https://github.com/BrunoLeoSanti/JONICA25). El
proyecto es el mismo; lo que cambió este año es el cerebro.

> **El cambio de 2026:** se pasó de una **Raspberry Pi 4** haciendo inferencia
> por CPU con NCNN, a una **Raspberry Pi 5 con AI HAT+ de 26 TOPS**, que corre
> el modelo en un chip Hailo-8 dedicado. El control de motores no se tocó.
> El detalle completo está en [`docs/migracion-2025.md`](docs/migracion-2025.md).

---

## Cómo funciona

El robot son dos cerebros con tareas separadas, y entre ellos **sólo dos
cables**:

```
┌──────────────────────────────────────┐
│  RASPBERRY PI 5  +  AI HAT+ 26 TOPS  │
│                                      │
│   Cámara ──► YOLOv8n en el Hailo-8   │
│                     │                │
│              ¿qué señal veo?         │
│                     │                │
│          ┌──────────┴──────────┐     │
│       GPIO26                GPIO16   │
│       (PARE)                 (GO)    │
└──────────┬──────────────────┬────────┘
           │                  │
           ▼                  ▼
┌──────────────────────────────────────┐
│             ARDUINO UNO              │
│                                      │
│   5 sensores IR ──► PID ──► motores  │
│                                      │
│   PARE  → frena 4 s                  │
│   GO    → habilita el arranque       │
└──────────────────────────────────────┘
```

**La Raspberry ve. El Arduino maneja.** La Pi no sabe nada de motores y el
Arduino no sabe nada de redes neuronales. Se hablan por dos pines digitales:
uno dice "hay un PARE", el otro dice "el semáforo está en verde".

Esa frontera es la razón por la que este año se pudo cambiar la computadora,
el acelerador, el formato del modelo y la librería de GPIO **sin tocar una
línea del Arduino** ni volver a calibrar el PID.

### Del lado de la visión

La cámara captura a 640×640 y el modelo corre en el acelerador Hailo. El
`.hef` lleva el NMS compilado adentro, así que el chip devuelve las cajas ya
filtradas y la CPU de la Pi no hace postproceso.

Las dos señales se tratan distinto, a propósito:

- El **semáforo verde** es instantáneo: mientras se lo ve, el pin está activo.
- El **PARE** se engancha 5 segundos. Si siguiera a la detección, el robot
  dejaría de ver el cartel al acercarse y saldría disparando antes de terminar
  de frenar.

### Del lado del control

El Arduino lee 5 sensores infrarrojos, calcula la posición de la línea y
corrige con un PID. Ajusta la velocidad según el tramo: acelera en las rectas
y baja en las curvas. Si pierde la línea por completo, usa la última posición
conocida para saber hacia qué lado buscarla.

---

## Hardware

| Componente | Detalle |
|---|---|
| Computadora | Raspberry Pi 5 — 8 GB |
| Acelerador de IA | Raspberry Pi AI HAT+ 26 TOPS (Hailo-8) |
| Cámara | Raspberry Pi Camera vía Picamera2 |
| Microcontrolador | Arduino UNO |
| Sensores de línea | 5 × infrarrojo reflectivo (A0–A4) |
| Motores | 2 × DC con driver puente H |
| Chasis | Diseño propio impreso en 3D — [`hardware/disenos-3d.zip`](hardware/disenos-3d.zip) |

Esquemático de conexiones: [`hardware/esquematico-arduino.png`](hardware/esquematico-arduino.png)

### Conexión Pi ↔ Arduino

| Raspberry Pi 5 | | Arduino |
|---|---|---|
| GPIO26 (pin 37) | → | pin 12 (`PinPare`) |
| GPIO16 (pin 36) | → | pin 13 (`PinSemaforo`) |
| GND | → | GND |

La masa común es obligatoria: sin ella las señales flotan y el Arduino lee
basura.

---

## El modelo

YOLOv8n entrenado sobre un dataset propio de **2 clases**: `PARE` y
`semaforoverde`.

| | |
|---|---|
| Arquitectura | YOLOv8n |
| Entrada | 640 × 640 RGB |
| Clases | 2 |
| Dataset | `pareysemaforo-3` (Roboflow) |
| Entrenamiento | Ultralytics 8.2.103 |
| Formato en el robot | HEF, cuantizado a INT8 |

El modelo entrenado es el mismo de 2025. Lo que cambia es el formato en el que
se ejecuta: antes NCNN sobre CPU, ahora HEF sobre el Hailo-8.

Para regenerar el `.hef` desde el `.pt`:
**[`tools/conversion_pt_a_hef.ipynb`](tools/conversion_pt_a_hef.ipynb)**
(notebook de Colab), explicado en
[`docs/conversion-modelo.md`](docs/conversion-modelo.md).

> El compilador de Hailo corre sólo en **Linux x86_64 con AVX**: no funciona en
> macOS, ni en Apple Silicon, ni en la propia Raspberry. Por eso la conversión
> se hace en Colab.

---

## Puesta en marcha

Guía completa: [`docs/instalacion-pi5.md`](docs/instalacion-pi5.md). Resumido:

```bash
# En la Raspberry Pi 5, con Raspberry Pi OS Bookworm de 64 bits
sudo apt install -y hailo-all python3-picamera2
sudo reboot

hailortcli fw-control identify     # tiene que decir HAILO8

git clone https://github.com/BrunoLeoSanti/JONICA26.git
cd JONICA26
pip install -r requirements.txt --break-system-packages
```

Cargá `arduino/lineaydeteccion/lineaydeteccion.ino` en el Arduino y corré:

```bash
python3 source/deteccion_hailo_preview.py   # con ventana, para probar
python3 source/deteccion_hailo.py           # sin ventana, para la pista
```

---

## Estructura del repositorio

```
JONICA26/
├── source/                        Código de la Raspberry Pi 5
│   ├── config.py                  Pines, umbrales y tiempos (tocar acá al calibrar)
│   ├── senales.py                 Máquina de estados PARE / GO
│   ├── hailo_detector.py          Inferencia sobre el Hailo-8
│   ├── gpio_control.py            Salidas hacia el Arduino
│   ├── deteccion_hailo.py         Programa principal (pista)
│   └── deteccion_hailo_preview.py Programa con ventana (banco de pruebas)
├── arduino/
│   └── lineaydeteccion/           Sketch del PID seguidor de línea
├── model/
│   ├── yolov8npareysemaforo.pt    Modelo entrenado (origen)
│   ├── yolov8npareysemaforo.hef   Modelo compilado para Hailo-8
│   └── labels.txt
├── tools/
│   ├── conversion_pt_a_hef.ipynb  Notebook de conversión (Colab)
│   └── verificar_hef.py           Mide la pérdida por cuantización
├── tests/                         Tests de lógica pura
├── hardware/                      Esquemático y diseños 3D
└── docs/                          Instalación, conversión y migración
```

### Dónde tocar cada cosa

| Quiero... | Archivo |
|---|---|
| Cambiar umbrales, pines o tiempos | `source/config.py` |
| Ajustar el PID o las velocidades | `arduino/lineaydeteccion/lineaydeteccion.ino` |
| Cambiar cómo se interpretan las señales | `source/senales.py` |
| Reconvertir el modelo | `tools/conversion_pt_a_hef.ipynb` |

---

## Tests

La lógica que no depende de hardware está separada y se puede testear en
cualquier computadora, sin Raspberry, sin cámara y sin acelerador:

```bash
pip install pytest numpy
python3 -m pytest tests/ -v
```

Cubre la máquina de estados de las señales (incluido el enganche del PARE) y
el parseo de las salidas del Hailo — que es donde se originan los errores
silenciosos del tipo "compila pero no detecta".

Lo que sí necesita hardware se verifica en la Pi:

```bash
python3 tools/verificar_hef.py --imagenes docs/muestras/ --referencia docs/referencia_pt.json
```

---

## Estado

- [x] Migración del código a Raspberry Pi 5
- [x] Integración con el AI HAT+ (Hailo-8)
- [x] Pipeline de conversión `.pt` → `.hef`
- [x] Verificación de pérdida por cuantización
- [x] `.hef` compilado y medido — recall 100 %, precisión 96.2 %
- [ ] Verificar sobre el acelerador real en la Pi
- [ ] Pruebas con la cámara en vivo
- [ ] Pruebas en pista
- [ ] Fotos, videos y póster 2026

## Resultados

_Pendiente: completar con las mediciones en pista (FPS reales, distancia de
frenado, tasa de detección) y la galería del año._

---

## Año anterior

- [JONICA25](https://github.com/BrunoLeoSanti/JONICA25) — Raspberry Pi 4 + NCNN
- [JONICA24](https://github.com/BrunoLeoSanti/JONICA24) — detección básica de frames
- Fotos y videos 2025: [`docs/enlaces.md`](docs/enlaces.md)
