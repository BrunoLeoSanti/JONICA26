"""Dos modelos a la vez sobre el mismo Hailo-8: personas (YOLOv8 COCO) y caras (SCRFD).

`DetectorHailo` activa un solo grupo de red y lo deja activo, lo que alcanza
para el modelo de pista. Para el modo felicidad hacen falta dos .hef, y un
mismo chip no puede tener dos grupos activados a mano: se le delega el cambio
al scheduler de HailoRT (round-robin), que carga y descarga cada modelo segun
llegan los cuadros.

Este modulo se importa en cualquier maquina: `hailo_platform` se importa recien
al abrir la sesion.
"""
from contextlib import ExitStack
from pathlib import Path
from typing import List, Sequence

import numpy as np

import config
from caras_scrfd import CaraDetectada, decodificar_scrfd
from felicidad import Caja
from hailo_detector import parsear_salida_nms


def personas_de_salida_nms(
    salida: Sequence[np.ndarray],
    indice: int = config.INDICE_PERSONA_COCO,
    umbral: float = config.UMBRAL_PERSONA,
) -> List[Caja]:
    """De la salida NMS del YOLO COCO (un array por clase) deja solo `person`."""
    detecciones = parsear_salida_nms([salida[indice]], ["person"], umbral)
    return [d.bbox for d in detecciones if d.confianza >= umbral]


def _exigir(ruta) -> str:
    if not Path(ruta).is_file():
        raise FileNotFoundError(f"Falta el modelo: {ruta}")
    return str(ruta)


class SesionHailo:
    """Context manager que abre los dos modelos sobre un VDevice compartido."""

    def __init__(
        self,
        ruta_personas=config.RUTA_HEF_PERSONAS,
        ruta_caras=config.RUTA_HEF_CARAS,
    ) -> None:
        self._ruta_personas = _exigir(ruta_personas)
        self._ruta_caras = _exigir(ruta_caras)
        self._pila = ExitStack()

    def __enter__(self) -> "SesionHailo":
        # Import diferido: hailo_platform solo existe en la Raspberry.
        from hailo_platform import (
            HEF,
            ConfigureParams,
            FormatType,
            HailoSchedulingAlgorithm,
            HailoStreamInterface,
            InferVStreams,
            InputVStreamParams,
            OutputVStreamParams,
            VDevice,
        )

        params = VDevice.create_params()
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        vdevice = self._pila.enter_context(VDevice(params=params))

        def abrir(ruta):
            hef = HEF(ruta)
            grupo = vdevice.configure(
                hef,
                ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe),
            )[0]
            entrada = InputVStreamParams.make(grupo, format_type=FormatType.UINT8)
            salida = OutputVStreamParams.make(grupo, format_type=FormatType.FLOAT32)
            info = hef.get_input_vstream_infos()[0]
            tuberia = self._pila.enter_context(InferVStreams(grupo, entrada, salida))
            return tuberia, info.name, info.shape

        self._personas, self._nombre_personas, self._forma_personas = abrir(self._ruta_personas)
        self._caras, self._nombre_caras, self._forma_caras = abrir(self._ruta_caras)
        return self

    def __exit__(self, *exc) -> None:
        self._pila.__exit__(*exc)

    def detectar_personas(self, frame: np.ndarray) -> List[Caja]:
        """Frame RGB uint8 del tamano de entrada del modelo -> cajas de personas."""
        lote = np.expand_dims(frame, axis=0).astype(np.uint8)
        resultados = self._personas.infer({self._nombre_personas: lote})
        salida_lote = next(iter(resultados.values()))
        return personas_de_salida_nms(salida_lote[0])

    def detectar_caras(self, frame: np.ndarray) -> List[CaraDetectada]:
        """Frame RGB uint8 del tamano de entrada del modelo -> caras detectadas."""
        lote = np.expand_dims(frame, axis=0).astype(np.uint8)
        resultados = self._caras.infer({self._nombre_caras: lote})
        alto, ancho = self._forma_caras[0], self._forma_caras[1]
        return decodificar_scrfd(resultados, (alto, ancho))
