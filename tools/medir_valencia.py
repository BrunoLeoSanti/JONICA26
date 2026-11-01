"""Mide la valencia que da el modelo de emocion sobre fotos de caras.

Sirve para fijar CORTES_VALENCIA en config.py: se corre sobre una carpeta con
caras serias, de sonrisa suave, de sonrisa grande y tristes, y se ve en que
rango cae cada serie. Cada foto se toma entera como una cara ya recortada.

Uso (en la Raspberry, con el Python del sistema):
    python3 tools/medir_valencia.py carpeta/ [carpeta2/ ...]

Una carpeta por expresion permite comparar series; se imprime el promedio y
el rango de cada una.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from emocion import EstimadorEmocion  # noqa: E402

EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp"}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    estimador = EstimadorEmocion()
    todas = []
    for carpeta in map(Path, sys.argv[1:]):
        valores = []
        for ruta in sorted(carpeta.iterdir()):
            if ruta.suffix.lower() not in EXTENSIONES:
                continue
            recorte = np.array(Image.open(ruta).convert("RGB"))
            valor = estimador.valencia(recorte)
            valores.append(valor)
            print(f"  {ruta.name:40s} {valor:+.3f}")
        if valores:
            print(
                f"{carpeta.name}: n={len(valores)} promedio={np.mean(valores):+.3f} "
                f"min={min(valores):+.3f} max={max(valores):+.3f}\n"
            )
            todas += valores
    if todas:
        pcts = np.percentile(todas, [10, 30, 50, 70, 90])
        print("Percentiles 10/30/50/70/90 de todo: " + " ".join(f"{p:+.3f}" for p in pcts))


if __name__ == "__main__":
    main()
