# Instalación en la Raspberry Pi 5

Procedimiento completo desde una Pi recién formateada hasta el robot andando.

## 1. Sistema operativo

**Raspberry Pi OS Bookworm de 64 bits.** La versión de 32 bits no sirve: el
runtime de Hailo sólo existe para arm64.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo rpi-eeprom-update -a     # el AI HAT+ necesita firmware reciente
sudo reboot
```

## 2. Conectar el AI HAT+

Con la Pi **apagada y desenchufada**: montás el HAT sobre el header de 40
pines y conectás el cable plano al puerto PCIe. Los separadores van puestos,
no es opcional — si el HAT queda flojo el enlace PCIe falla de forma
intermitente, que es mucho peor que fallar del todo.

Habilitar PCIe Gen 3 (el AI HAT+ lo aprovecha):

```bash
sudo raspi-config
# Advanced Options -> PCIe Speed -> Gen 3 -> Yes
sudo reboot
```

## 3. Software de Hailo

```bash
sudo apt install -y hailo-all
sudo reboot
```

Verificar que el acelerador aparece:

```bash
hailortcli fw-control identify
```

Tiene que decir **`Device Architecture: HAILO8`**. Si dice `HAILO8L` tenés la
placa de 13 TOPS, no la de 26, y hay que recompilar el modelo con
`--hw-arch hailo8l` (ver `conversion-modelo.md`).

Si no detecta nada: revisá el cable PCIe y que hayas reiniciado después del
`apt install`.

## 4. Cámara y dependencias de Python

```bash
sudo apt install -y python3-picamera2
pip install -r requirements.txt --break-system-packages
```

El `--break-system-packages` hace falta porque Bookworm protege el Python del
sistema. Es el camino habitual en la Pi. Si preferís un entorno virtual,
creálo con `--system-site-packages`, porque `picamera2` y `hailo_platform`
vienen por apt y un venv limpio no los ve:

```bash
python3 -m venv --system-site-packages .venv
```

Probar la cámara:

```bash
rpicam-hello --timeout 2000
```

## 5. Conexiones con el Arduino

| Raspberry Pi 5 | | Arduino |
|---|---|---|
| GPIO26 (pin físico 37) | → | pin 12 (`PinPare`) |
| GPIO16 (pin físico 36) | → | pin 13 (`PinSemaforo`) |
| GND | → | GND |

**La masa común no es opcional.** Sin GND compartido las señales flotan y el
Arduino lee basura.

Son los mismos pines que en 2025, así que si reutilizás el cableado del año
pasado no hay que cambiar nada.

## 6. Cargar el sketch del Arduino

Abrí `arduino/lineaydeteccion/lineaydeteccion.ino` en el Arduino IDE y
subilo. No cambió respecto de 2025.

## 7. Probar

Primero con ventana, para ver que detecta:

```bash
python3 source/deteccion_hailo_preview.py
```

Mostrale un cartel de PARE y fijate que aparezca el recuadro. Después, la
versión de pista:

```bash
python3 source/deteccion_hailo.py
```

## 8. Arranque automático (opcional)

Para que el robot arranque solo al encender, sin teclado ni monitor:

```bash
sudo tee /etc/systemd/system/jonica.service > /dev/null <<'UNIT'
[Unit]
Description=JONICA26 deteccion de senales
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/JONICA26
ExecStart=/usr/bin/python3 /home/pi/JONICA26/source/deteccion_hailo.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl enable --now jonica.service
journalctl -u jonica.service -f      # ver los logs en vivo
```

Ajustá `User` y `WorkingDirectory` si tu usuario o la ruta del repo son otros.

## Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| `hailortcli` no encuentra el dispositivo | Falta reiniciar tras `apt install hailo-all`, o el cable PCIe está flojo |
| `ModuleNotFoundError: hailo_platform` | Estás en un venv sin `--system-site-packages` |
| `ModuleNotFoundError: picamera2` | Ídem, o falta `sudo apt install python3-picamera2` |
| Los pines nunca cambian de estado | Quedó código viejo con `RPi.GPIO`, que no funciona en Pi 5 (ver `migracion-2025.md`) |
| Detecta en el preview pero el Arduino no reacciona | Falta la masa común, o el sketch no está cargado |
| El `.hef` no carga | Se compiló para `hailo8l` y tenés un `hailo8`, o al revés |
