# Muñeco en pista y modo felicidad — diseño

Fecha: 1 de noviembre de 2026. Estado: **borrador para revisión**.

## Alcance por etapas (decidido el 1 de noviembre de 2026)

- **Etapa 1 (ahora): modo felicidad.** Se puede probar en el banco, sin la
  estructura del auto: personas, caras y carita por cara.
- **Etapa 2 (después): muñeco en pista.** Se posterga porque todavía no hay
  fotos del muñeco en la pista ni la estructura del auto. Cuando se haga, el
  muñeco se trata **como un PARE más** (opción 1 de "Decisión abierta": frena
  4 s por el pulso de GPIO26, sin tocar el Arduino). Queda el riesgo conocido
  de que pase por encima si sigue enfrente después de los 4 s.

Las secciones de "Modo pista" de abajo describen la etapa 2 y no se
implementan en la etapa 1.

## Intención

Se agregan dos capacidades nuevas al robot sin tocar el Arduino ni los dos
cables que lo unen con la Raspberry:

1. **Modo pista**: además de PARE y semáforo verde, el robot reconoce un
   **muñeco** (figura de persona) y frena si está **enfrente**, no si lo ve en
   otro tramo de la pista (el zigzag de la línea lo muestra de costado).
2. **Modo felicidad** (nuevo, aparte): con la cámara **inclinada hacia
   arriba**, detecta **personas** y sus **caras**, estima qué tan feliz está
   cada persona y dibuja una **carita** (de muy feliz a muy triste) pegada a la
   caja de cada cara, en el video por red que ya existe (`:8000`, para OBS).

## Metas

- Reutilizar modelos ya entrenados para personas, caras y emoción. Etiquetar a
  mano sólo si no queda otra, y sólo el muñeco.
- Varias personas y caras a la vez, cada una con su propia caja y su propia
  carita.
- La frontera de dos pines con el Arduino queda intacta.

## No-metas y anti-metas

- No es una escala de emociones por categoría (enojo, miedo…): sólo un eje
  triste ↔ feliz.
- No reconocer *quién* es la persona. Ningún dato de cara se guarda en disco.
- Anti-meta: que PARE y semáforo pierdan detección por agregar el muñeco. Si la
  verificación del `.hef` nuevo muestra que sí, el cambio no se acepta.
- Anti-meta: que el robot frene por un muñeco que no está en su camino.

## Lo decidido

### Modo pista

- El YOLOv8n propio pasa de 2 a 3 clases: `PARE`, `semaforoverde`, `muneco`
  (el orden de `config.ETIQUETAS` y `model/labels.txt` tiene que coincidir con
  el `.hef`, como hasta ahora).
- Se **reentrena con `pareysemaforo-3` junto con fotos del muñeco** (si se
  entrenara sólo con el muñeco, el modelo olvida PARE y semáforo).
- Dataset del muñeco: **manual** (no existe uno público). Para ahorrar
  trabajo se pre-etiqueta con un modelo grande (Grounding DINO vía
  [autodistill](https://github.com/autodistill/autodistill)) a partir de
  video grabado con la cámara del robot en la pista, y se corrigen las cajas.
- Se convierte a `.hef` por el pipeline existente (Colab, DFC 3.33.1, Model
  Zoo v2.18, `hailo8`) y se verifica con `tools/verificar_hef.py`.
- **"Enfrente"** es una regla sobre la caja del muñeco, evaluada en una
  función pura nueva, testeable sin hardware:
  - el centro horizontal de la caja cae dentro de una franja central de la
    imagen, y
  - la caja es suficientemente grande o su borde inferior está suficientemente
    abajo (está cerca);
  - y se cumple durante varios cuadros seguidos, para que un cruce de un
    instante en el zigzag no frene al robot.
  Los números viven en `config.py` y se calibran en la pista.
- Salida: **PENDIENTE DE DECISIÓN.** Se leyó el sketch del Arduino
  (`arduino/lineaydeteccion/`) y el pin de PARE (D12) **no** significa "frená
  mientras esté en alto": al verlo en alto una vez, el Arduino frena con
  `delay(4000)` y después ignora el pin durante 15 s (`stopflag`). El pin de
  semáforo (D13) sólo sirve para el arranque inicial. Por eso reutilizar
  GPIO26 haría que el muñeco frene 4 s y que el robot siga de largo aunque el
  muñeco siga enfrente. Opciones en la sección "Decisión abierta".

### Modo felicidad

- Programa **aparte** (`source/deteccion_felicidad_stream.py`), sin GPIO. No
  carga el YOLO propio.
- **Personas**: detector COCO preentrenado del Hailo Model Zoo (YOLOv8, `.hef`
  precompilado para `hailo8`), quedándose sólo con la clase `person`.
- **Caras**: SCRFD del Hailo Model Zoo (500m / 2.5g / 10g; se elige el más
  chico que alcance en precisión).
- Los dos `.hef` conviven en el chip con el **scheduler de HailoRT**.
- **Emoción**: [HSEmotion](https://github.com/HSE-asavchenko/hsemotion)
  `enet_b0_8_va_mtl` en la **CPU de la Pi**, sobre el recorte de cada cara. Se
  usa la **valencia** (continua, de -1 a 1 según el modelo), que cubre todo el
  eje triste ↔ feliz. Las licencias de HSEmotion y de OpenCV Zoo son
  Apache-2.0.
- **Seguimiento simple entre cuadros**: a cada cara se le asigna un id por
  cercanía de cajas, y su valencia se suaviza con un promedio de los últimos
  cuadros, para que la carita no parpadee.
- **Escala**: 5 niveles de caritas, de muy feliz a muy triste. Los cortes entre
  niveles viven en `config.py`.
- **Dibujo**: caja de la persona, caja de la cara, y la carita pegada a la caja
  de la cara. Las 5 caritas son imágenes propias (no emojis de fuente, que la
  Pi puede no tener). Salen en el MJPEG existente, con los FPS encima como en
  `deteccion_hailo_stream.py`.
- Una persona sin cara visible (de espaldas) muestra sólo la caja de persona,
  sin carita.
- La valencia de HSEmotion mide expresión, no sonrisa pura: **no existe** un
  modelo ya hecho de intensidad de sonrisa (se buscó), y el eje triste ↔ feliz
  es lo que pide la escala.

## Restricciones

- Hailo-8, HailoRT 4.23.x. Un `.hef` precompilado con otra versión de DFC puede
  no cargar (ver "Trampas conocidas" en `CLAUDE.md`).
- Los `.hef` de SCRFD **no traen el NMS adentro**: el decodificado de las
  salidas se hace en Python. El del detector de personas sí lo trae y se parsea
  con `parsear_salida_nms` (80 clases).
- El ONNX de HSEmotion que existe es un export de la comunidad; el oficial es
  PyTorch. El rango real de la valencia **no está confirmado** para ese export.
- Convenciones del repo: todo en español, sin tildes ni ñ en código y commits,
  comentarios que explican el porqué, import diferido de hardware, lógica pura
  con tests.

## Qué queda para el que construye

- Elegir el tamaño de SCRFD y del YOLO COCO (n o s) midiendo FPS y precisión.
- Valores de franja central, tamaño mínimo y cantidad de cuadros del "enfrente".
- Cortes entre los 5 niveles de carita, **midiendo la valencia real** del
  modelo sobre fotos de caras antes de fijarlos.
- Dibujo de las 5 caritas.
- Si el ONNX de la comunidad no sirve, exportar el oficial a ONNX.
- La regla "enfrente" y la máquina de estados del muñeco viven en **una sola
  función pura** que usan los tres programas de pista (`deteccion_hailo.py`,
  `_preview.py`, `_stream.py`); preview y stream además dibujan la caja.
  *(Mi llamada.)*
- Si el muñeco, PARE y verde coinciden: **frenar gana**. El muñeco enfrente
  mantiene el freno aunque haya un verde visible. *(Mi llamada.)*
- El modo felicidad y el modo pista son **excluyentes** (misma cámara, mismo
  chip, procesos distintos): no hay que compartir la cámara. *(Mi llamada.)*
- Metas de velocidad *(mi llamada, a ajustar tras medir)*: modo pista, que la
  tasa de inferencia no sea peor que la actual de 3 clases vs 2; modo
  felicidad, al menos ~10 cuadros por segundo de video con 3 caras. Si la
  emoción en la CPU no alcanza, se evalúa en un hilo aparte y se muestra el
  último valor.

## Decisión: cómo frena el robot por el muñeco (etapa 2)

**Elegida: opción 1.** Las otras dos quedan como alternativas si en la pista el
muñeco no alcanza con 4 s de freno.

El Arduino hoy sólo sabe frenar por un pulso de PARE (4 s, y 15 s de
bloqueo). Tres caminos:

1. **Tratar al muñeco como un PARE más** (sin tocar el Arduino): frena 4 s y
   sigue. Simple, pero puede pasar por encima del muñeco si sigue enfrente.
2. **Tocar el sketch** para que haya un freno que dure mientras el pin esté en
   alto. Es la única forma de "frenar mientras esté enfrente", pero rompe el
   lema de que el Arduino no se toca desde 2025 y obliga a recalibrar/probar.
3. **Un tercer cable** dedicado al muñeco. Rompe la frontera de dos pines.

## Verificación

- Tests de lógica pura: regla de "enfrente", asignación de ids, suavizado,
  mapeo valencia → nivel de carita, parseo de la salida del detector COCO.
- `tools/verificar_hef.py` sobre el `.hef` de 3 clases: PARE y semáforo no
  pueden bajar del 90 % de recall (criterio existente).
- Prueba en pista con el muñeco enfrente, de costado y lejos.
- Prueba del modo felicidad con una y varias personas, midiendo FPS con los dos
  `.hef` cargados.
