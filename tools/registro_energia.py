"""Registra la energia de la placa cada pocos segundos. CORRE EN LA RASPBERRY PI.

POR QUE EXISTE ESTE SCRIPT
--------------------------
La placa se reiniciaba sola por bajo voltaje y no quedaba rastro: el journal
no es persistente y el UPS no guarda historial. Este script deja un CSV por
dia con lo que mide la Pi y lo que reporta el UPS, para poder ver despues
que paso justo antes de un corte.

Cada linea se fuerza a disco (fsync) apenas se escribe. Si no, el ultimo
minuto antes de un apagon queda en el buffer y se pierde, que es justo el
minuto que interesa.

Que se mide:
  - Pi: voltaje de entrada (EXT5V), consumo del lado del SoC sumando los
    rieles del PMIC, temperatura y el estado de throttling.
  - UPS HAT (E), I2C 0x2D: estado, entrada USB, bateria y las 4 celdas.
    Hoy el UPS devuelve ceros en todo eso; se registra igual, crudo, para
    ver si en algun momento empieza a reportar.

El consumo del PMIC NO incluye el AI HAT+ ni los USB: se alimentan de 5 V
antes del PMIC. Sirve para ver picos y tendencias, no el total exacto.

Uso:
    python3 tools/registro_energia.py                # cada 5 s, en ~/registros_energia
    python3 tools/registro_energia.py --intervalo 2
Arranque automatico: crontab -e y agregar
    @reboot /usr/bin/python3 /home/jonica/JONICA26/tools/registro_energia.py
"""
import argparse
import csv
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

UPS_DIRECCION = 0x2D
CARPETA_DEFAULT = Path.home() / "registros_energia"

COLUMNAS = [
    "fecha_hora", "uptime_s", "ext5v_v", "consumo_soc_w", "temp_c",
    "throttled", "bajo_voltaje_ahora",
    "ups_estado", "ups_vbus_mv", "ups_vbus_ma", "ups_vbus_mw",
    "ups_bat_mv", "ups_bat_ma", "ups_bat_pct", "ups_bat_mah",
    "ups_celda1_mv", "ups_celda2_mv", "ups_celda3_mv", "ups_celda4_mv",
]


def vcgencmd(*args) -> str:
    try:
        return subprocess.run(["vcgencmd", *args], capture_output=True,
                              text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def leer_pmic():
    """Devuelve (EXT5V en volts, consumo del SoC en watts)."""
    corrientes, voltajes = {}, {}
    for linea in vcgencmd("pmic_read_adc").splitlines():
        m = re.match(r"\s*(\S+)_([AV]) \w+\(\d+\)=([\d.]+)", linea)
        if m:
            destino = corrientes if m.group(2) == "A" else voltajes
            destino[m.group(1)] = float(m.group(3))
    watts = sum(i * voltajes[riel] for riel, i in corrientes.items() if riel in voltajes)
    return voltajes.get("EXT5V"), round(watts, 3)


def leer_throttled():
    m = re.search(r"0x[0-9a-fA-F]+", vcgencmd("get_throttled"))
    if not m:
        return "", ""
    valor = int(m.group(0), 16)
    # El bit 0 es "bajo voltaje en este momento"; los altos son "ocurrio desde el arranque"
    return m.group(0), int(bool(valor & 0x1))


def leer_temp():
    m = re.search(r"[\d.]+", vcgencmd("measure_temp"))
    return float(m.group(0)) if m else ""


def leer_ups(bus):
    """Mismos registros que ups.py de Waveshare. Vacio si el UPS no responde."""
    if bus is None:
        return [""] * 12
    try:
        estado = bus.read_byte_data(UPS_DIRECCION, 0x02)
        vbus = bus.read_i2c_block_data(UPS_DIRECCION, 0x10, 6)
        bat = bus.read_i2c_block_data(UPS_DIRECCION, 0x20, 8)
        celdas = bus.read_i2c_block_data(UPS_DIRECCION, 0x30, 8)
    except OSError:
        return [""] * 12

    def palabra(d, i):
        return d[i] | d[i + 1] << 8

    corriente = palabra(bat, 2)
    if corriente > 0x7FFF:
        corriente -= 0x10000
    return [
        hex(estado),
        palabra(vbus, 0), palabra(vbus, 2), palabra(vbus, 4),
        palabra(bat, 0), corriente, palabra(bat, 4), palabra(bat, 6),
        *(palabra(celdas, i) for i in (0, 2, 4, 6)),
    ]


def abrir_bus():
    try:
        import smbus
        return smbus.SMBus(1)
    except (ImportError, OSError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas")
    parser.add_argument("--carpeta", type=Path, default=CARPETA_DEFAULT)
    args = parser.parse_args()
    args.carpeta.mkdir(parents=True, exist_ok=True)

    bus = abrir_bus()
    while True:
        ahora = datetime.now()
        archivo = args.carpeta / f"energia_{ahora:%Y-%m-%d}.csv"
        nuevo = not archivo.exists()
        with open(archivo, "a", newline="") as f:
            escritor = csv.writer(f)
            if nuevo:
                escritor.writerow(COLUMNAS)
            ext5v, watts = leer_pmic()
            throttled, bajo_ahora = leer_throttled()
            uptime = Path("/proc/uptime").read_text().split()[0]
            escritor.writerow([ahora.isoformat(timespec="seconds"), uptime, ext5v, watts,
                               leer_temp(), throttled, bajo_ahora, *leer_ups(bus)])
            f.flush()
            os.fsync(f.fileno())
        time.sleep(args.intervalo)


if __name__ == "__main__":
    main()
