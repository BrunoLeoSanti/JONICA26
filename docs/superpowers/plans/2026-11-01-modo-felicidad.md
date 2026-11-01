# Modo felicidad — plan de implementación (etapa 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un programa de banco que, con la cámara inclinada hacia arriba, detecta personas y caras, estima la felicidad de cada cara y dibuja una carita (5 niveles) pegada a cada cara en el stream MJPEG de `:8000`.

**Architecture:** Dos `.hef` del Model Zoo (YOLOv8 COCO para personas, SCRFD para caras) comparten un `VDevice` con el scheduler de HailoRT. Las cajas de cara se recortan del cuadro grande y HSEmotion (ONNX, CPU) devuelve la valencia. Un seguidor por IoU asigna ids y suaviza la valencia. Toda la lógica que no toca hardware vive en módulos puros con tests.

**Tech Stack:** Python 3.13, HailoRT 4.23.x (`hailo_platform`), picamera2, onnxruntime, Pillow, numpy, pytest.

**Spec:** [docs/superpowers/specs/2026-11-01-muneco-y-modo-felicidad-design.md](../specs/2026-11-01-muneco-y-modo-felicidad-design.md) (sólo el "Modo felicidad"; el muñeco es la etapa 2 y NO entra acá).

## Global Constraints

- Hardware: Raspberry Pi 5 + AI HAT+ **Hailo-8** (no 8L), HailoRT **4.23.x**. Un `.hef` de otra versión de DFC o de `hailo8l` no carga.
- Todo en español: código, comentarios, docs y commits. **Sin tildes ni ñ** en código fuente y mensajes de commit (sí en los `.md`).
- Los comentarios explican el porqué, no el qué.
- Los módulos que necesitan hardware hacen **import diferido** de `hailo_platform`, `picamera2`, `onnxruntime`; la lógica pura se testea en cualquier máquina (`python3 -m pytest tests/ -v`).
- Los parámetros de calibración viven en `source/config.py`.
- El modo felicidad **no usa GPIO** y no toca `arduino/`, ni `deteccion_hailo*.py`, ni `senales.py`.
- Formato de cámara `BGR888` entrega RGB en el array (ver `config.FORMATO_CAMARA`); los modelos esperan 640x640 RGB; el stream usa `config.RESOLUCION_STREAM` (1640x1232) en el puerto `config.PUERTO_STREAM` (8000), MJPEG.
- Escala de caritas: **5 niveles**, de muy feliz a muy triste. Emoción en la CPU con HSEmotion `enet_b0_8_va_mtl`, usando la **valencia**.
- Commits con cuerpo que explica el razonamiento y terminan con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Trabajar en una rama nueva `modo-felicidad` a partir de `energia-y-streaming`.

## Review Focus

Entradas que el spec no menciona y que pueden romper el programa; cada una tiene su test en la tarea indicada.

1. Cuadro sin ninguna persona ni cara: no debe fallar ni dibujar nada (Tarea 2, 7).
2. Cara pegada al borde: el recorte se sale del cuadro; debe recortarse al límite, nunca lanzar excepción ni dar un recorte vacío (Tarea 4).
3. Muchas caras a la vez (10+): el costo de la emoción no puede frenar el stream; hay tope de caras evaluadas por cuadro (Tarea 4, 7).
4. Dos caras que se cruzan: los ids no deben intercambiarse en un cruce corto, ni crearse ids nuevos por un cuadro perdido (Tarea 2).
5. Valencia fuera de rango o NaN: el nivel debe quedar acotado a 0–4 y NaN no puede propagarse (Tarea 2).
6. Persona sin cara y cara sin persona: se dibuja lo que hay, sin carita en el primer caso (Tarea 2, 7).
7. Falta alguno de los archivos de modelo: error claro con la ruta, no un traceback de HailoRT (Tarea 6).

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `source/config.py` (modificar) | Rutas de modelos y parámetros de calibración del modo felicidad |
| `source/felicidad.py` (crear) | Lógica pura: valencia→nivel, IoU, seguidor de caras con suavizado, asociación cara→persona |
| `source/caras_scrfd.py` (crear) | Lógica pura: decodificación de las salidas crudas de SCRFD + NMS |
| `source/dibujo_felicidad.py` (crear) | Dibujo de cajas y caritas sobre el cuadro (Pillow) |
| `source/emocion.py` (crear) | Envoltorio ONNX de HSEmotion: recorte → valencia |
| `source/hailo_multi.py` (crear) | `VDevice` compartido con scheduler y dos detectores |
| `source/deteccion_felicidad_stream.py` (crear) | Programa principal, reutiliza el servidor MJPEG del stream actual |
| `tools/medir_valencia.py` (crear) | Mide la valencia del modelo sobre fotos para fijar los cortes |
| `tests/test_felicidad.py`, `tests/test_caras_scrfd.py`, `tests/test_dibujo_felicidad.py` (crear) | Tests puros |
| `model/` (agregar) | `personas_yolov8.hef`, `caras_scrfd.hef`, `emocion_hsemotion.onnx` |

---

### Task 1: Reconocimiento en la Pi y modelos

**Files:**
- Create: `model/personas_yolov8.hef`, `model/caras_scrfd.hef`, `model/emocion_hsemotion.onnx`
- Create: `docs/modo-felicidad-modelos.md` (qué es cada archivo, de dónde se bajó, formas de entrada y salida)

**Interfaces:**
- Produces: las formas y nombres de entrada/salida reales de los dos `.hef` y del ONNX, escritos en `docs/modo-felicidad-modelos.md`. Las Tareas 3, 5 y 6 dependen de ese archivo.

Requiere la Pi encendida (`ssh jonica`).

- [ ] **Step 1: Crear la rama.** `git switch -c modo-felicidad` desde `energia-y-streaming`.
- [ ] **Step 2: En la Pi, instalar dependencias.** `pip install onnxruntime pillow` (en el mismo entorno que usa `deteccion_hailo.py`). Verificar con `python3 -c "import onnxruntime, PIL"`.
- [ ] **Step 3: Conseguir los `.hef` precompilados para `hailo8`.** Del Hailo Model Zoo: un YOLOv8 COCO (n o s) y un SCRFD (empezar por `scrfd_2.5g`; probar `500m` si el FPS no alcanza). Guardarlos con los nombres de la tabla. Si el Model Zoo sólo ofrece `.hef` para otra versión de HailoRT, anotarlo y parar: hay que recompilar con el pipeline del repo.
- [ ] **Step 4: Validar que cargan.** `hailortcli parse-hef model/personas_yolov8.hef` y lo mismo con `caras_scrfd.hef`. Esperado: ambos reportan `HAILO8` y entrada 640x640 (o la que sea; anotarla). Si alguno falla, resolverlo antes de seguir.
- [ ] **Step 5: Conseguir el ONNX de HSEmotion** `enet_b0_8_va_mtl` (exportar desde el paquete oficial `hsemotion` si el export de la comunidad no sirve). Verificar con onnxruntime que tiene entrada 1x3x224x224 y salidas de expresión (1,8), valencia y activación; anotar nombres, orden y normalización de entrada (media/desvío).
- [ ] **Step 6: Escribir `docs/modo-felicidad-modelos.md`** con la tabla de entradas, salidas (nombre, forma, dtype) de los tres modelos, el orden de clases del YOLO COCO (índice de `person`) y de dónde salió cada archivo.
- [ ] **Step 7: Commit.** `git add model docs/modo-felicidad-modelos.md` y commit "Agregar modelos del modo felicidad y documentar sus formas".

---

### Task 2: Lógica pura de felicidad

**Files:**
- Modify: `source/config.py` (agregar bloque `# --- Modo felicidad ---`)
- Create: `source/felicidad.py`
- Test: `tests/test_felicidad.py`

**Interfaces:**
- Produces, en `config.py`: `RUTA_HEF_PERSONAS`, `RUTA_HEF_CARAS`, `RUTA_ONNX_EMOCION` (Path), `INDICE_PERSONA_COCO = 0`, `UMBRAL_PERSONA = 0.4`, `UMBRAL_CARA = 0.5`, `CORTES_VALENCIA` (4 cortes crecientes entre -1 y 1; valores iniciales `(-0.5, -0.1, 0.2, 0.5)`, se ajustan en la Tarea 5), `VENTANA_SUAVIZADO = 5`, `IOU_SEGUIMIENTO = 0.3`, `CUADROS_PERDIDOS_MAX = 10`, `MAX_CARAS_EVALUADAS = 6`.
- Produces, en `felicidad.py`:
  - `Caja = Tuple[float, float, float, float]` (x1, y1, x2, y2 normalizado 0–1)
  - `iou(a: Caja, b: Caja) -> float`
  - `nivel_de_valencia(valencia: float, cortes: Sequence[float] = config.CORTES_VALENCIA) -> int` (0 = muy triste … 4 = muy feliz; NaN → 2, fuera de rango se acota)
  - `class SeguidorCaras` con `asignar(cajas: Sequence[Caja]) -> List[int]` (un id por caja, estable entre cuadros) y `suavizar(id_cara: int, valencia: float) -> float` (promedio de las últimas `VENTANA_SUAVIZADO` valencias de ese id; descarta ids no vistos en `CUADROS_PERDIDOS_MAX` cuadros)
  - `persona_de_cara(cara: Caja, personas: Sequence[Caja]) -> Optional[int]` (índice de la persona más chica que contiene el centro de la cara, o `None`)

- [ ] **Step 1: Tests que fallan en `tests/test_felicidad.py`**, con estos nombres y aserciones:
  - `test_iou_cajas_iguales_es_uno`, `test_iou_cajas_disjuntas_es_cero`, `test_iou_media_superposicion` (cajas `(0,0,1,1)` y `(0.5,0,1.5,1)` → 1/3).
  - `test_nivel_extremos`: `nivel_de_valencia(-1.0) == 0`, `nivel_de_valencia(1.0) == 4`.
  - `test_nivel_en_cada_corte`: con los cortes por defecto, un valor apenas debajo y apenas encima de cada corte cambia el nivel en 1.
  - `test_nivel_nan_y_fuera_de_rango`: `nivel_de_valencia(float("nan")) == 2`, `nivel_de_valencia(5.0) == 4`, `nivel_de_valencia(-5.0) == 0`.
  - `test_seguidor_mantiene_id_con_cara_que_se_mueve_poco`.
  - `test_seguidor_ids_distintos_para_caras_distintas`.
  - `test_seguidor_no_intercambia_ids_en_cruce_corto`: dos caras que se acercan sin superponerse más que `IOU_SEGUIMIENTO` mantienen sus ids.
  - `test_seguidor_tolera_cuadro_sin_caras`: `asignar([])` devuelve `[]` y la cara que vuelve en el cuadro siguiente conserva su id.
  - `test_seguidor_descarta_id_tras_cuadros_perdidos_max`: pasados `CUADROS_PERDIDOS_MAX + 1` cuadros vacíos, la misma cara recibe un id nuevo.
  - `test_suavizado_promedia_ultimas_valencias`: con ventana 5 y valencias 0,0,0,0,1 → 0.2; la sexta empuja la primera fuera.
  - `test_persona_de_cara_elige_la_mas_chica_que_la_contiene`, `test_persona_de_cara_sin_persona_devuelve_none`.
- [ ] **Step 2: Correr y ver fallar.** `python3 -m pytest tests/test_felicidad.py -v` → FAIL (`ModuleNotFoundError: felicidad`).
- [ ] **Step 3: Agregar las constantes a `config.py` y implementar `felicidad.py`** con las firmas de arriba. Seguimiento: asignación voraz por mayor IoU ≥ `IOU_SEGUIMIENTO`, cada id usado una vez por cuadro. Sin imports de hardware.
- [ ] **Step 4: Correr y ver pasar.** `python3 -m pytest tests/ -v` → todo en verde (los 19 existentes más los nuevos).
- [ ] **Step 5: Commit** "Agregar logica pura del modo felicidad: niveles, seguidor y asociacion".

---

### Task 3: Decodificación de SCRFD

**Files:**
- Create: `source/caras_scrfd.py`
- Test: `tests/test_caras_scrfd.py`

**Interfaces:**
- Consumes: `felicidad.Caja`, `felicidad.iou`; las formas de salida de `docs/modo-felicidad-modelos.md` (Tarea 1).
- Produces: `@dataclass(frozen=True) class CaraDetectada: bbox: Caja; confianza: float` y `decodificar_scrfd(salidas: Mapping[str, np.ndarray], tam_entrada: Tuple[int, int], umbral: float = config.UMBRAL_CARA, iou_nms: float = 0.4) -> List[CaraDetectada]` — devuelve cajas normalizadas 0–1 con `x1 <= x2`, `y1 <= y2`, ordenadas por confianza.

- [ ] **Step 1: Tests que fallan**, usando tensores sintéticos con las formas reales anotadas en la Tarea 1:
  - `test_decodifica_una_cara_conocida`: un anchor con score alto y offsets conocidos produce la caja esperada (tolerancia 1e-3).
  - `test_descarta_bajo_umbral`.
  - `test_nms_une_cajas_superpuestas`: dos anchors vecinos sobre la misma cara dan una sola detección.
  - `test_sin_caras_devuelve_lista_vacia`.
  - `test_cajas_se_acotan_al_cuadro`: una cara que se sale del borde queda con coordenadas en [0, 1].
- [ ] **Step 2: Correr y ver fallar.** `python3 -m pytest tests/test_caras_scrfd.py -v` → FAIL.
- [ ] **Step 3: Implementar `decodificar_scrfd`.** SCRFD usa strides 8/16/32 con anchors fijos y salidas de score/bbox (distancias al centro del anchor × stride) por escala; el `.hef` del Model Zoo no trae el NMS, así que se hace acá. Seguir las formas reales documentadas en la Tarea 1; si el `.hef` agrupa las salidas distinto, adaptar el mapeo por nombre y dejarlo comentado.
- [ ] **Step 4: Correr y ver pasar.**
- [ ] **Step 5: Commit** "Agregar decodificacion de SCRFD con NMS".

---

### Task 4: Recorte y dibujo

**Files:**
- Create: `source/dibujo_felicidad.py`
- Test: `tests/test_dibujo_felicidad.py`

**Interfaces:**
- Consumes: `felicidad.Caja`.
- Produces:
  - `recortar_cara(frame: np.ndarray, caja: Caja, margen: float = 0.15) -> Optional[np.ndarray]` — recorte RGB uint8 con margen proporcional, acotado al cuadro; `None` si el recorte queda de menos de 2 px de lado.
  - `crear_caritas(tamano: int) -> List[Image.Image]` — 5 imágenes RGBA generadas con `ImageDraw` (óvalo, ojos, boca de sonrisa grande a mueca grande); índice = nivel de `nivel_de_valencia`.
  - `dibujar(frame: np.ndarray, personas: Sequence[Caja], caras: Sequence[Tuple[Caja, Optional[int]]], caritas: Sequence[Image.Image]) -> np.ndarray` — dibuja en copia del cuadro: caja de cada persona, caja de cada cara y, si el nivel no es `None`, la carita pegada junto a la caja (arriba; si no entra, abajo), sin salirse del cuadro.

- [ ] **Step 1: Tests que fallan:**
  - `test_recorte_normal_tiene_el_tamano_esperado`.
  - `test_recorte_en_el_borde_se_acota`: caja con `x1 = -0.1` o `x2 = 1.1` no lanza y devuelve un recorte válido.
  - `test_recorte_degenerado_devuelve_none`: caja de ancho 0.
  - `test_crear_caritas_devuelve_cinco_distintas`: 5 imágenes, tamaño `(t, t)`, no todas iguales.
  - `test_dibujar_sin_detecciones_no_cambia_el_cuadro`.
  - `test_dibujar_carita_en_el_borde_no_lanza`: cara en la esquina superior izquierda.
  - `test_dibujar_persona_sin_cara_no_dibuja_carita` (compara píxeles de la zona de la carita).
- [ ] **Step 2: Correr y ver fallar.**
- [ ] **Step 3: Implementar** las tres funciones; `dibujar` no modifica el arreglo recibido.
- [ ] **Step 4: Correr y ver pasar.**
- [ ] **Step 5: Commit** "Agregar recorte de caras y dibujo de cajas y caritas".

---

### Task 5: Emoción (HSEmotion) y calibración de cortes

**Files:**
- Create: `source/emocion.py`, `tools/medir_valencia.py`
- Modify: `source/config.py` (`CORTES_VALENCIA` con los valores medidos)
- Test: `tests/test_emocion.py` (sólo preprocesado puro)

**Interfaces:**
- Consumes: `recortar_cara` (Tarea 4), `config.RUTA_ONNX_EMOCION`, la normalización anotada en la Tarea 1.
- Produces:
  - `preprocesar(recorte: np.ndarray) -> np.ndarray` — pura: redimensiona a 224x224, normaliza como el modelo, devuelve `(1, 3, 224, 224)` float32.
  - `class EstimadorEmocion` con `__init__(ruta=config.RUTA_ONNX_EMOCION)` (import diferido de `onnxruntime`; `FileNotFoundError` con la ruta si falta) y `valencia(recorte: np.ndarray) -> float`.

- [ ] **Step 1: Test que falla** `test_preprocesar_forma_y_tipo` (recortes de 80x60 y 400x500 → `(1,3,224,224)`, `float32`) y `test_preprocesar_no_modifica_la_entrada`.
- [ ] **Step 2: Correr y ver fallar.**
- [ ] **Step 3: Implementar `preprocesar` y `EstimadorEmocion`.** `valencia` devuelve un `float` acotado a [-1, 1].
- [ ] **Step 4: Correr y ver pasar.**
- [ ] **Step 5: Escribir `tools/medir_valencia.py`.** Recibe una carpeta de fotos de caras, imprime la valencia de cada una y los percentiles 10/30/50/70/90. Uso: `python3 tools/medir_valencia.py carpeta/`.
- [ ] **Step 6: Medir con fotos reales en la Pi** (al menos una serie: cara seria, sonrisa suave, sonrisa grande, cara triste/enojada) y ajustar `CORTES_VALENCIA` para que cada serie caiga en un nivel distinto. Documentar el rango observado en `docs/modo-felicidad-modelos.md`.
- [ ] **Step 7: Commit** "Agregar estimador de emocion y calibrar cortes de valencia".

---

### Task 6: Dos modelos en el Hailo con scheduler

**Files:**
- Create: `source/hailo_multi.py`

**Interfaces:**
- Consumes: `senales.Deteccion`, `hailo_detector.parsear_salida_nms` (para el YOLO COCO, 80 clases), `caras_scrfd.decodificar_scrfd`, `config.RUTA_HEF_PERSONAS`, `config.RUTA_HEF_CARAS`.
- Produces: `class SesionHailo` (context manager; `FileNotFoundError` con la ruta si falta algún `.hef`) con `detectar_personas(frame: np.ndarray) -> List[Caja]` (sólo clase `INDICE_PERSONA_COCO`, confianza ≥ `UMBRAL_PERSONA`) y `detectar_caras(frame: np.ndarray) -> List[CaraDetectada]`. El frame es 640x640 RGB uint8. Las cajas salen normalizadas `(x1, y1, x2, y2)`.

Esta tarea sólo se puede verificar en la Pi, así que no tiene tests puros; la parte pura (filtrar `person`) se prueba con `parsear_salida_nms`, que ya tiene tests.

- [ ] **Step 1: Test que falla** `tests/test_felicidad.py::test_filtrar_personas_deja_solo_la_clase_person`: función pura `filtrar_personas(detecciones, etiquetas_coco, umbral) -> List[Caja]` en `hailo_multi.py` (con el import de `hailo_platform` diferido, el módulo se importa en cualquier máquina).
- [ ] **Step 2: Correr y ver fallar.**
- [ ] **Step 3: Implementar `filtrar_personas` y `SesionHailo`.** Un solo `VDevice` creado con `scheduling_algorithm=HailoSchedulingAlgorithm.ROUND_ROBIN` y `group_id` compartido; un `InferModel` por `.hef` configurado una vez; formato de entrada UINT8, salida FLOAT32 para el YOLO. Basarse en `hailo_detector.py` para la forma del código; si la API de `InferModel` no entrega el NMS en el mismo formato que `InferVStreams`, ajustar y dejar un comentario con el porqué.
- [ ] **Step 4: Correr tests y ver pasar** en la Mac.
- [ ] **Step 5: Verificar en la Pi.** Script corto que carga la sesión, corre `detectar_personas` y `detectar_caras` sobre una foto de `docs/muestras/` con una persona (si no hay, una foto propia) y mide el tiempo de 50 inferencias de cada una. Esperado: ambos modelos cargan a la vez sin error y devuelven al menos una caja.
- [ ] **Step 6: Commit** "Agregar sesion Hailo con dos modelos y scheduler".

---

### Task 7: Programa principal con stream

**Files:**
- Create: `source/deteccion_felicidad_stream.py`

**Interfaces:**
- Consumes: todo lo anterior; del stream actual (`deteccion_hailo_stream.py`) `UltimoJpeg` y `crear_servidor` (importarlos, no copiarlos; si no se pueden importar sin arrastrar `gpio_control` y el resto, extraerlos a `source/servidor_mjpeg.py` y que el stream actual los importe de ahí, con sus tests existentes en verde).
- Produces: `python3 source/deteccion_felicidad_stream.py` sirve en `http://bumblebee.local:8000` (`/` página, `/stream` video).

Flujo por cuadro: `capture_array` en dos tamaños (grande para video y recortes, 640x640 para el Hailo) como hace el stream actual → `detectar_personas` y `detectar_caras` → tomar hasta `MAX_CARAS_EVALUADAS` caras más grandes → `SeguidorCaras.asignar` → `recortar_cara` del cuadro grande → `valencia` → `suavizar` → `nivel_de_valencia` → `dibujar` → JPEG → `UltimoJpeg.publicar`. Los FPS del video y de la inferencia se muestran encima, como en el stream actual. Ctrl+C cierra cámara, sesión y servidor.

- [ ] **Step 1: Extraer `UltimoJpeg` y `crear_servidor` si hace falta** (ver Interfaces) y correr `python3 -m pytest tests/ -v` → verde.
- [ ] **Step 2: Escribir el programa.** Emoción en un hilo aparte con el último valor visible, para que una cola de caras no frene el video (hilos de captura e inferencia como en `deteccion_hailo.py`).
- [ ] **Step 3: Probar en la Pi con la cámara inclinada hacia arriba:** nadie en cuadro (no falla, sin dibujos), una persona (caja de persona, caja de cara, carita), varias personas (una carita por cara, ids estables), persona de espaldas (sólo caja de persona).
- [ ] **Step 4: Medir FPS** con 1 y con 3 caras. Meta de la spec: ≥ ~10 cuadros por segundo de video con 3 caras. Si no se llega, probar `scrfd_500m` y YOLO `n`, y anotar el resultado.
- [ ] **Step 5: Abrir el stream en la notebook y en OBS** (`/stream`) y confirmar que se ve.
- [ ] **Step 6: Commit** "Agregar modo felicidad con video por red".

---

### Task 8: Documentación

**Files:**
- Modify: `CLAUDE.md` (secciones "Estado actual", "Estructura del repo", "Pendiente"), `README.md` (sólo si menciona los modos)

- [ ] **Step 1: Actualizar `CLAUDE.md`:** estructura del repo con los archivos nuevos, el modo felicidad en "Estado actual", y el muñeco (etapa 2, tratado como PARE) en "Pendiente". Agregar a "Trampas conocidas" lo que se haya aprendido (SCRFD sin NMS, rango real de la valencia, el sketch del Arduino frena 4 s y bloquea 15 s).
- [ ] **Step 2: Correr `python3 -m pytest tests/ -v`** y anotar el número de tests resultante en `CLAUDE.md`.
- [ ] **Step 3: Commit** "Documentar el modo felicidad y dejar el muneco como etapa 2".
