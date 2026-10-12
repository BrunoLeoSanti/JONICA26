"""Verifica el .hef contra el modelo original. CORRE EN LA RASPBERRY PI.

POR QUE EXISTE ESTE SCRIPT
--------------------------
Al compilar para Hailo el modelo se cuantiza a INT8. Esa cuantizacion puede
degradar la precision sin que nada falle: el .hef compila bien, carga bien,
corre rapido... y detecta de menos. Es un problema reportado seguido con
modelos YOLOv8 custom, y si no se mide, uno se entera en plena pista.

Este script corre el .hef sobre un set de imagenes y compara contra las
detecciones de referencia del .pt original (generadas en Colab, paso 5 del
notebook). Si no se pasa referencia, igual sirve como chequeo rapido de que
el modelo detecta algo razonable.

Uso:
    python3 tools/verificar_hef.py --imagenes docs/muestras/
    python3 tools/verificar_hef.py --imagenes docs/muestras/ --referencia referencia_pt.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

import config  # noqa: E402
from hailo_detector import DetectorHailo  # noqa: E402

EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp"}


def iou(a, b) -> float:
    """Interseccion sobre union de dos cajas (x1, y1, x2, y2)."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def cargar_imagen(ruta: Path) -> np.ndarray:
    from PIL import Image

    img = Image.open(ruta).convert("RGB").resize(config.RESOLUCION)
    return np.asarray(img, dtype=np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imagenes", required=True, type=Path,
                        help="carpeta con imagenes de prueba")
    parser.add_argument("--referencia", type=Path,
                        help="JSON con las detecciones del .pt (opcional)")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="confianza minima a reportar")
    parser.add_argument("--iou-min", type=float, default=0.5,
                        help="IoU minimo para considerar que dos cajas coinciden")
    args = parser.parse_args()

    rutas = sorted(
        p for p in args.imagenes.iterdir() if p.suffix.lower() in EXTENSIONES
    )
    if not rutas:
        print(f"No hay imagenes en {args.imagenes}")
        return 1

    referencia = {}
    if args.referencia:
        referencia = json.loads(args.referencia.read_text())

    total_hef = total_ref = coincidencias = 0
    faltantes, sobrantes = [], []

    with DetectorHailo() as detector:
        print(f"Modelo: {detector.ruta_hef}")
        print(f"Imagenes: {len(rutas)}\n")

        for ruta in rutas:
            dets = detector.detectar(cargar_imagen(ruta), conf_minima=args.conf)
            total_hef += len(dets)

            resumen = ", ".join(
                f"{d.nombre} {d.confianza:.2f}" for d in dets
            ) or "(nada)"
            print(f"{ruta.name:<40} {resumen}")

            if not referencia:
                continue

            esperadas = [
                r for r in referencia.get(ruta.name, [])
                if r["confianza"] >= args.conf
            ]
            total_ref += len(esperadas)

            usadas = set()
            for esp in esperadas:
                mejor, mejor_iou = None, 0.0
                for i, det in enumerate(dets):
                    if i in usadas or det.nombre != esp["nombre"]:
                        continue
                    valor = iou(det.bbox, tuple(esp["bbox"]))
                    if valor > mejor_iou:
                        mejor, mejor_iou = i, valor
                if mejor is not None and mejor_iou >= args.iou_min:
                    usadas.add(mejor)
                    coincidencias += 1
                else:
                    faltantes.append((ruta.name, esp["nombre"]))
            sobrantes.extend(
                (ruta.name, d.nombre)
                for i, d in enumerate(dets) if i not in usadas
            )

    print("\n" + "=" * 60)
    print(f"Detecciones del .hef: {total_hef}")

    if not referencia:
        print("\nSin archivo de referencia: solo se listaron las detecciones.")
        print("Para comparar contra el .pt, generar referencia_pt.json en el")
        print("paso 5 del notebook tools/conversion_pt_a_hef.ipynb")
        return 0

    print(f"Detecciones del .pt (referencia): {total_ref}")
    print(f"Coincidencias (IoU >= {args.iou_min}): {coincidencias}")

    recall = coincidencias / total_ref if total_ref else 0.0
    precision = coincidencias / total_hef if total_hef else 0.0
    print(f"\nRecall vs .pt:    {recall:.1%}  (cuanto del original conserva)")
    print(f"Precision vs .pt: {precision:.1%}  (cuanto inventa de mas)")

    if faltantes:
        print(f"\nPerdidas ({len(faltantes)}):")
        for nombre, clase in faltantes[:10]:
            print(f"  - {nombre}: {clase}")
        if len(faltantes) > 10:
            print(f"  ... y {len(faltantes) - 10} mas")
    if sobrantes:
        print(f"\nFalsos positivos nuevos ({len(sobrantes)}):")
        for nombre, clase in sobrantes[:10]:
            print(f"  + {nombre}: {clase}")

    print("\n" + "=" * 60)
    if recall >= 0.90:
        print("OK: la cuantizacion conservo el modelo. Listo para la pista.")
        return 0
    if recall >= 0.75:
        print("ATENCION: se perdio algo de precision. Probar en la pista con")
        print("cuidado, y considerar recalibrar con mas imagenes.")
        return 0
    print("MAL: se perdio demasiada precision con la cuantizacion.")
    print("Recompilar con mas imagenes de calibracion, o revisar que el set de")
    print("calibracion sea representativo de la pista real.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
