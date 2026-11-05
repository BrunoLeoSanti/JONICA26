# Hardware y conexiones

Todo lo físico del robot: qué hay, cómo se conecta, cómo se alimenta y qué
significa cada cable. Para el uso diario (arrancar, transmitir, qué hacer si
algo falla) ver [`operacion.md`](operacion.md).

Última revisión: 5 de noviembre de 2026.

---

## Vista general

```
                  ┌──────────────────────────────────────────┐
                  │  UPS HAT (E)  4 × 18650 en serie          │
                  │   pogo pins ─────────────┐                │
                  │   USB-A 5 V ── cable ──┐ │                │
                  └────────────────────────┼─┼────────────────┘
                                           ▼ ▼
   cámara imx219 ──CSI──►  RASPBERRY PI 5 (8 GB)  ◄──PCIe──  AI HAT+ (Hailo-8)
   (montada al revés)        │      │
                             │      └── WiFi ──► compu (navegador / OBS / YouTube)
                             │
                 4 cables + GND (señales 3,3 V)
                             │
                             ▼
                        ARDUINO UNO ──► puente H ──► 2 motores DC
                             ▲
                  4 sensores IR (A3–A0)
```

**La Raspberry ve. El Arduino maneja.** Entre los dos solo viajan cuatro
señales de prendido/apagado. La Pi no sabe nada de motores ni del PID, y el
Arduino no sabe nada de redes neuronales.

---

## Componentes

| | Detalle |
|---|---|
| Computadora | Raspberry Pi 5 Model B Rev 1.1, 8 GB — hostname `Bumblebee` |
| Acelerador | Raspberry Pi AI HAT+ 26 TOPS — **Hailo-8** (no 8L), PCIe Gen 3 |
| Cámara | Camera Module v2 (**imx219**), por CSI, **montada al revés** |
| Sistema | Debian 13 trixie 64 bits, kernel 6.18, Python 3.13.5, HailoRT 4.23.0 |
| Alimentación | Waveshare **UPS HAT (E)** con 4 × 18650 en serie (con adaptador) |
| Microcontrolador | Arduino UNO |
| Sensores de línea | 4 × infrarrojo reflectivo, centrados (A3–A0). El A4 se sacó porque no andaba |
| Motores | 2 × DC con driver puente H |
| Chasis | Impreso en 3D — [`hardware/disenos-3d.zip`](../hardware/disenos-3d.zip) |

Esquemático del Arduino: [`hardware/esquematico-arduino.png`](../hardware/esquematico-arduino.png).

---

## Raspberry Pi ↔ Arduino

Cuatro cables de señal y la masa común. La masa es obligatoria: sin ella las
señales flotan y el Arduino lee cualquier cosa.

| Raspberry Pi 5 | Pin físico | → | Arduino | Variable en el sketch | Modo pista | Modo felicidad |
|---|---|---|---|---|---|---|
| GPIO26 | 37 | → | D12 | `PinPare` | **PARE**: frena | **motor izquierdo** |
| GPIO16 | 36 | → | D13 | `PinSemaforo` | **semáforo verde**: arranca | **motor derecho** |
| GPIO20 | 38 | → | D7 | `PinMuneco` | **muñeco**: frena | **reversa** |
| GPIO21 | 40 | → | D8 | `PinModo` | **bajo** | **alto** |
| GND | 39 | → | GND | | | |

Los números de GPIO están en `source/config.py` (`STOP_PIN`, `GO_PIN`,
`MUNECO_PIN`, `MODO_PIN`) y los del Arduino, al principio del sketch.

### Por qué así

- **Del lado del Arduino los pines son `INPUT` sin pullup, a propósito.** Con
  pullup, si el programa de la Pi se corta, los pines se leen en alto; y en
  modo felicidad eso es "los dos motores prendidos".
- **Del lado de la Pi, al soltar un pin queda como entrada con pull-down**, así
  el Arduino lee bajo aunque no corra ningún programa
  (`gpio_control.PinSalida`). Se usa `lgpio` directo: `RPi.GPIO` no anda en la
  Pi 5 y `gpiozero` deja el pin flotando al soltarlo.
- **Si el programa de pista corre solo** (sin `robot.py`), nadie toma el pin
  MODO y queda en bajo por el pull-down, que es justamente el modo pista.

Para ver el estado real de los pines, en la Pi:

```bash
pinctrl get 16,20,21,26
```

o en la página de control (`:8080`), en el recuadro de arriba a la derecha.

---

## Qué hace cada señal

### Modo pista

| Señal | La Pi | El Arduino |
|---|---|---|
| Semáforo verde | El pin **sigue a la detección**: alto mientras se ve | Lo usa solo para el **arranque inicial** |
| PARE | Al verlo, **engancha** el pin 5 s (`DURACION_PARE`) | Frena 5 s y después lo ignora hasta **20 s desde que lo vio** (15 s ya andando) |
| Muñeco | Al verlo, **engancha** el pin 10 s (`DURACION_MUNECO`) | Frena 10 s y después lo ignora hasta **30 s desde que lo vio** (20 s ya andando) |

El enganche existe porque, al acercarse, el cartel sale de cuadro: si el pin
siguiera a la detección, el robot arrancaría antes de terminar de frenar.

Los tiempos del Arduino están arriba del sketch (`tiempo_pare`,
`tiempo_ignorar_pare`, `tiempo_muneco`, `tiempo_ignorar_muneco`). Los de
ignorar se cuentan **desde que se ve la señal, con el frenado incluido**.

### Cuándo la Pi da por buena una detección

Para prender un pin, la detección tiene que pasar **todos** estos filtros
(en `source/config.py`):

| | Confianza mínima | Alto mínimo de la caja | Proporción alto/ancho |
|---|---|---|---|
| PARE | > 0.3 (`UMBRAL_PARE`) | 0.12 de la imagen (~80 cm) | — |
| Semáforo verde | > 0.4 (`UMBRAL_VERDE`) | sin mínimo | — |
| Muñeco | > 0.83 (`UMBRAL_MUNECO`) | 0.22 de la imagen (~80 cm) | entre 2.5 y 5 |

- El **alto mínimo** hace que frene a la distancia del cartel y no apenas lo
  ve. Medido en la feria con el robot a ~80 cm: el PARE ocupa 0.13 del alto y
  el muñeco 0.24.
- La **proporción** del muñeco (~3.5 parado) evita que lo dispare una persona
  de cerca, que da una caja casi cuadrada.
- En el video se dibujan cajas desde confianza 0.4: **una caja en el video no
  quiere decir que el pin se prenda**. Para eso, mirar el recuadro de pines.

### Modo felicidad (manejo con WASD)

| Teclas | Motor izq (D12) | Motor der (D13) | Reversa (D7) | Resultado |
|---|---|---|---|---|
| W | 1 | 1 | 0 | adelante |
| S | 1 | 1 | 1 | atrás |
| A | 0 | 1 | 0 | gira a la izquierda |
| D | 1 | 0 | 0 | gira a la derecha |
| W+A / W+D | primero gira, a los 0.4 s los dos | | 0 | diagonal hacia adelante |
| S+A / S+D | primero gira, a los 0.4 s los dos | | 1 | diagonal hacia atrás |
| nada | 0 | 0 | 0 | quieto |

- **La velocidad la pone el Arduino**: arranca en 110 y, yendo recto, sube de
  a 5 cada 150 ms hasta 150. Al girar o cambiar de sentido vuelve a 110.
- **No hay "una rueda un poco más rápida"**: cada motor es un cable, prendido o
  apagado. La diagonal se arma en el tiempo (`TIEMPO_GIRO_DIAGONAL`).
- **Girar en el lugar** (una rueda para cada lado) no se puede sin cambiar el
  Arduino: el cable de reversa invierte los dos motores juntos.
- **Seguridad**: si la página deja de mandar teclas 0.4 s (`TIEMPO_SIN_TECLAS`),
  la Pi apaga los motores.

---

## Arduino

Sketch en uso: [`arduino/lineaydeteccion_26/lineaydeteccion_26.ino`](../arduino/lineaydeteccion_26/lineaydeteccion_26.ino).

| | |
|---|---|
| Motores (puente H) | IN1 = 9, IN2 = 11, IN3 = 6, IN4 = 3 |
| Sensores (izq → der) | A3 (extremo izq), A2 (medio izq), A1 (medio der), A0 (extremo der) |
| Umbral de los sensores | `UMBRAL = 400` |
| Velocidad del PID | de 120 (`vel_min`) a 180 (`vel_max`), sube de a 20 en recta |
| Velocidad en felicidad | de 110 a 150 (`vel_min_remoto`, `vel_max_remoto`) |
| Serie | 9600 baudios (imprime posición y lecturas de sensores) |

Hay dos sketches en el repo. `lineaydeteccion_26` es el que tiene el robot
(pines de motores intercambiados y umbrales propios). `lineaydeteccion` es la
versión anterior.

**Ojo con los `delay`**: mientras frena por un PARE (5 s) o por el muñeco
(10 s), el Arduino no lee nada, ni el cambio de modo.

---

## Alimentación

La Pi, el AI HAT y la cámara se alimentan de la **UPS HAT (E)**, por dos
caminos a la vez:

1. **Pogo pins**: los resortes de la UPS apoyan sobre las pistas de 5 V de abajo
   de la Pi.
2. **Cable USB-A → USB-C**: de la salida USB-A de la UPS a la entrada USB-C de
   la Pi. Es un respaldo para cuando los pogo pins pierden contacto con los
   saltos del robot. Las dos entradas vienen de la misma UPS, así que pueden
   estar conectadas juntas.

**No usar el USB-C de la UPS para alimentar la Pi**: es la entrada de carga.

| Dato | Valor |
|---|---|
| Duración con detección + video (18650 cargadas) | ~2 h 30 min |
| Duración en reposo | ~5 h 15 min |
| Consumo típico | 4–5 W, picos de 7–8 W |
| Voltaje normal (`EXT5V`) | 5,1–5,25 V |

**Cosas que ya pasaron:**

- **Baterías bajas**: el voltaje baja (5,17 → 4,8 V) y la Pi se apaga. Cargar a
  fondo antes de cada uso y tener el cargador a mano.
- **Apagones de golpe con el voltaje bien**: contacto de los pogo pins con los
  saltitos del robot. Por eso el cable USB.
- **Aviso de bajo voltaje en cada arranque** con la UPS: es el pico del
  arranque. Lo que importa es si aparece con el robot andando.
- **No correr `ups.py`** (el de Waveshare): apaga la Pi a los 60 s.

### Temperatura

Sin ventilación, el sándwich UPS / Pi / AI HAT llega a **80–85 °C** con video,
y ahí la Pi se frena sola. Necesita un ventilador de costado (no entra el
Active Cooler).

### Cómo leer `vcgencmd get_throttled`

| Bit | Valor | Significa |
|---|---|---|
| 0 | `0x1` | bajo voltaje **ahora** |
| 3 | `0x8` | frenada por temperatura **ahora** |
| 16 | `0x10000` | hubo bajo voltaje desde que arrancó |
| 17 | `0x20000` | se limitó la frecuencia desde que arrancó |
| 18 | `0x40000` | hubo frenado desde que arrancó |
| 19 | `0x80000` | se frenó por temperatura desde que arrancó |

Ejemplos: `0x50000` = hubo bajo voltaje y frenado (típico del arranque con la
UPS); `0xf0008` = todo eso y además **se está frenando por calor ahora**.

---

## Cámara

- **imx219**, modo del sensor 1640×1232 (campo completo, 4:3).
- De cada cuadro el ISP saca **dos imágenes** sin gastar CPU: 640×640 para el
  Hailo y 1640×1232 para el video (`RESOLUCION_STREAM`). Las cajas
  normalizadas del modelo caen justo sobre la imagen grande.
- Está **montada al revés**: en pista el modelo recibe la imagen al revés (por
  eso se entrena con `flipud`) y solo el video se endereza
  (`ROTAR_PREVIEW_180`). En felicidad se endereza en el ISP.

## Hailo-8

- Target **`hailo8`**: un `.hef` de `hailo8l` no carga, y al revés.
- Modelo de pista: `model/yolov8n_pare_semaforo_muneco.hef`, 3 clases (`PARE`,
  `semaforoverde`, `muneco`), con el NMS compilado adentro. Ver
  [`conversion-modelo.md`](conversion-modelo.md).
- Modelos de felicidad: ver [`modo-felicidad-modelos.md`](modo-felicidad-modelos.md).
