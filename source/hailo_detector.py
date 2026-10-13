"""Inferencia YOLOv8 sobre el acelerador Hailo-8 del AI HAT+.

Reemplaza al `YOLO(..., task="detect")` de Ultralytics/NCNN que se usaba en
2025. La interfaz publica es deliberadamente chica -- `detectar(frame)` devuelve
una lista de `Deteccion` -- para que el bucle principal no sepa nada de HailoRT.

El .hef se compila con el NMS incluido (ver tools/conversion_pt_a_hef.ipynb),
asi que el acelerador devuelve cajas ya decodificadas y filtradas. Por eso aca
no hay decodificacion de anchors ni NMS en Python: todo eso corre en el chip.
"""
from typing import List, Optional, Sequence

import numpy as np

import config
from senales import Deteccion


def parsear_salida_nms(
    salida: Sequence[np.ndarray],
    etiquetas: Sequence[str],
    conf_minima: float = 0.0,
) -> List[Deteccion]:
    """Convierte la salida NMS de HailoRT en una lista de `Deteccion`.

    Para un .hef con NMS incluido se recibe un array por clase, con los campos

        [y_min, x_min, y_max, x_max, score]

    en coordenadas normalizadas 0-1. Dos cosas que hay que mirar con cuidado:

    1. El orden de las coordenadas es *yxyx*, no xyxy. Invertirlo no da error:
       da cajas dibujadas en el lugar equivocado. Se traduce aca, una sola vez.

    2. **La disposicion del array varia.** Segun de donde venga puede ser
       `(N, 5)` -- una deteccion por fila -- o `(5, max_det)` -- un campo por
       fila, con columnas de ceros como relleno. El emulador del Dataflow
       Compiler devuelve la segunda. Leer una como si fuera la otra no falla:
       devuelve cero detecciones, que es indistinguible de "el modelo no
       detecta nada". Por eso se detecta la forma en vez de asumirla.

    Esta funcion es pura y no toca el hardware, asi que se puede testear sin
    Raspberry ni acelerador (ver tests/test_hailo_detector.py).
    """
    if len(salida) != len(etiquetas):
        raise ValueError(
            f"El .hef devuelve {len(salida)} clases pero hay {len(etiquetas)} "
            f"etiquetas configuradas ({list(etiquetas)}). Se compilo el modelo "
            f"con otra cantidad de clases?"
        )

    detecciones: List[Deteccion] = []
    for indice_clase, cajas in enumerate(salida):
        if cajas is None or len(cajas) == 0:
            continue

        arr = np.asarray(cajas, dtype=np.float32)
        if arr.ndim != 2:
            continue

        # (5, max_det) -> (max_det, 5). El caso (5, 5) es ambiguo, pero se
        # interpreta como 5 detecciones de 5 campos, que es lo habitual.
        if arr.shape[1] != 5 and arr.shape[0] == 5:
            arr = arr.T
        if arr.shape[1] < 5:
            continue

        for fila in arr:
            y1, x1, y2, x2, score = (float(v) for v in fila[:5])
            if score < conf_minima:
                continue
            detecciones.append(
                Deteccion(
                    nombre=etiquetas[indice_clase],
                    confianza=score,
                    bbox=(x1, y1, x2, y2),
                )
            )
    return detecciones


class DetectorHailo:
    """Envoltorio de HailoRT para un .hef de deteccion con NMS incluido.

    Se usa como context manager para garantizar que el dispositivo se libere:

        with DetectorHailo() as detector:
            dets = detector.detectar(frame)
    """

    def __init__(
        self,
        ruta_hef=config.RUTA_HEF,
        etiquetas: Sequence[str] = config.ETIQUETAS,
    ) -> None:
        # Import diferido: hailo_platform solo existe en la Raspberry con el
        # paquete hailo-all instalado. Asi este modulo se puede importar (y
        # testear el parser) en cualquier maquina.
        from hailo_platform import (  # noqa: F401
            HEF,
            ConfigureParams,
            FormatType,
            HailoStreamInterface,
            InferVStreams,
            InputVStreamParams,
            OutputVStreamParams,
            VDevice,
        )

        self.etiquetas = list(etiquetas)
        self.ruta_hef = str(ruta_hef)

        self._hef = HEF(self.ruta_hef)
        self._vdevice = VDevice(params=VDevice.create_params())

        params_config = ConfigureParams.create_from_hef(
            self._hef, interface=HailoStreamInterface.PCIe
        )
        self._grupo = self._vdevice.configure(self._hef, params_config)[0]
        self._params_grupo = self._grupo.create_params()

        info_entrada = self._hef.get_input_vstream_infos()[0]
        self.nombre_entrada = info_entrada.name
        # (alto, ancho, canales) -- la resolucion que espera el modelo.
        self.forma_entrada = info_entrada.shape

        self._params_in = InputVStreamParams.make(
            self._grupo, format_type=FormatType.UINT8
        )
        self._params_out = OutputVStreamParams.make(
            self._grupo, format_type=FormatType.FLOAT32
        )

        self._InferVStreams = InferVStreams
        self._contexto_grupo = None
        self._pipeline = None

    # --- Ciclo de vida --------------------------------------------------------

    def __enter__(self) -> "DetectorHailo":
        self._contexto_grupo = self._grupo.activate(self._params_grupo)
        self._contexto_grupo.__enter__()
        self._pipeline = self._InferVStreams(
            self._grupo, self._params_in, self._params_out
        )
        self._pipeline.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._pipeline is not None:
            self._pipeline.__exit__(*exc)
            self._pipeline = None
        if self._contexto_grupo is not None:
            self._contexto_grupo.__exit__(*exc)
            self._contexto_grupo = None

    # --- Inferencia -----------------------------------------------------------

    def detectar(
        self, frame: np.ndarray, conf_minima: float = 0.0
    ) -> List[Deteccion]:
        """Corre inferencia sobre un frame RGB uint8 y devuelve detecciones.

        El frame tiene que venir ya en la resolucion del modelo (la camara se
        configura a 640x640 en config.py, justamente para evitar un resize por
        cada cuadro).
        """
        if self._pipeline is None:
            raise RuntimeError(
                "DetectorHailo se tiene que usar como context manager: "
                "with DetectorHailo() as detector: ..."
            )

        alto, ancho = self.forma_entrada[0], self.forma_entrada[1]
        if frame.shape[0] != alto or frame.shape[1] != ancho:
            raise ValueError(
                f"El frame es {frame.shape[1]}x{frame.shape[0]} pero el modelo "
                f"espera {ancho}x{alto}. Revisar RESOLUCION en config.py."
            )

        lote = np.expand_dims(frame, axis=0).astype(np.uint8)
        resultados = self._pipeline.infer({self.nombre_entrada: lote})

        # Un solo tensor de salida (el del NMS) y un solo elemento de lote.
        salida_lote = next(iter(resultados.values()))
        return parsear_salida_nms(salida_lote[0], self.etiquetas, conf_minima)
