#!/usr/bin/env bash
# Diagnostico del entorno de la Raspberry Pi para JONICA26.
#
# Solo lee informacion: no instala, no modifica y no necesita sudo.
# Correlo en la Raspberry y pega la salida completa.
#
#   bash tools/diagnostico_pi.sh
#
# Si lo guardaste suelto, tambien sirve:
#   curl -sL https://raw.githubusercontent.com/BrunoLeoSanti/JONICA26/main/tools/diagnostico_pi.sh | bash

# pygame imprime un banner al importarse y ensucia la salida.
export PYGAME_HIDE_SUPPORT_PROMPT=1

titulo() { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }
ok()     { printf '  [OK]    %s\n' "$1"; }
falta()  { printf '  [FALTA] %s\n' "$1"; }
info()   { printf '  %-22s %s\n' "$1" "$2"; }

echo "================================================================"
echo " JONICA26 - diagnostico de la Raspberry Pi"
echo " $(date)"
echo "================================================================"

# ---------------------------------------------------------------- hardware
titulo "Hardware"
if [ -r /proc/device-tree/model ]; then
  info "Modelo:" "$(tr -d '\0' < /proc/device-tree/model)"
else
  info "Modelo:" "no detectado (no parece una Raspberry Pi)"
fi
info "Arquitectura:" "$(uname -m)"
info "RAM total:" "$(free -h 2>/dev/null | awk '/^Mem:/{print $2}')"
info "Disco libre:" "$(df -h / 2>/dev/null | awk 'NR==2{print $4" de "$2}')"

# ---------------------------------------------------------------- sistema
titulo "Sistema operativo"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  info "Distribucion:" "$PRETTY_NAME"
  info "Nombre clave:" "${VERSION_CODENAME:-?}"
fi
info "Kernel:" "$(uname -r)"

case "$(uname -m)" in
  aarch64|arm64)
    ok "Sistema de 64 bits (necesario para Hailo)" ;;
  armv7l|armv6l)
    falta "Sistema de 32 bits -- el runtime de Hailo no existe para 32 bits"
    echo "          Hay que reinstalar Raspberry Pi OS de 64 bits." ;;
  *)
    info "Arquitectura inesperada:" "$(uname -m)" ;;
esac

# ---------------------------------------------------------------- firmware
titulo "Firmware / EEPROM"
if command -v rpi-eeprom-update >/dev/null 2>&1; then
  rpi-eeprom-update 2>/dev/null | sed 's/^/  /' | head -5
else
  info "rpi-eeprom-update:" "no disponible"
fi

titulo "Configuracion PCIe"
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
if [ -f "$CFG" ]; then
  info "Archivo:" "$CFG"
  if grep -qE '^\s*dtparam=pciex1' "$CFG"; then
    grep -E '^\s*dtparam=pciex1' "$CFG" | sed 's/^/  /'
  else
    info "" "sin dtparam=pciex1 -> el enlace PCIe corre en Gen2"
    echo "          El AI HAT+ aprovecha Gen3. Para habilitarlo:"
    echo "            echo 'dtparam=pciex1_gen=3' | sudo tee -a $CFG"
  fi
else
  info "config.txt:" "no encontrado"
fi

# ---------------------------------------------------------------- PCIe / Hailo
titulo "Deteccion del acelerador Hailo"
if command -v lspci >/dev/null 2>&1; then
  SALIDA=$(lspci 2>/dev/null | grep -i hailo)
  if [ -n "$SALIDA" ]; then
    ok "Dispositivo visible en el bus PCIe:"
    echo "$SALIDA" | sed 's/^/          /'
  else
    falta "No aparece ningun Hailo en lspci"
    echo "          (revisar el cable PCIe, o que falte reiniciar)"
  fi
else
  info "lspci:" "no instalado (sudo apt install pciutils)"
fi

if [ -e /dev/hailo0 ]; then
  ok "/dev/hailo0 presente (el driver cargo)"
else
  falta "/dev/hailo0 no existe (driver no cargado o no instalado)"
fi

# ---------------------------------------------------------------- paquetes apt
titulo "Paquetes del sistema (apt)"
for p in hailo-all hailort hailo-tappas-core python3-hailort \
         python3-picamera2 python3-libcamera pciutils; do
  if dpkg -s "$p" >/dev/null 2>&1; then
    ok "$p  ($(dpkg-query -W -f='${Version}' "$p" 2>/dev/null))"
  else
    falta "$p"
  fi
done

# ---------------------------------------------------------------- hailortcli
titulo "Herramientas de Hailo"
if command -v hailortcli >/dev/null 2>&1; then
  ok "hailortcli: $(command -v hailortcli)"
  echo
  echo "  --- hailortcli fw-control identify ---"
  hailortcli fw-control identify 2>&1 | sed 's/^/  /'
  echo
  echo "  >>> Fijate en 'Device Architecture':"
  echo "      HAILO8   = AI HAT+ de 26 TOPS  -> compilar con --hw-arch hailo8"
  echo "      HAILO8L  = AI HAT+ de 13 TOPS  -> compilar con --hw-arch hailo8l"
else
  falta "hailortcli no esta instalado"
  echo "          Se instala con: sudo apt install hailo-all && sudo reboot"
fi

# ---------------------------------------------------------------- python
titulo "Python"
info "Version:" "$(python3 --version 2>&1)"
info "Ejecutable:" "$(command -v python3)"
[ -n "$VIRTUAL_ENV" ] && info "venv activo:" "$VIRTUAL_ENV"

titulo "Modulos de Python"
for m in hailo_platform picamera2 gpiozero lgpio numpy PIL pygame; do
  if python3 -c "import $m" 2>/dev/null; then
    V=$(python3 -c "import $m;print(getattr($m,'__version__',''))" 2>/dev/null | head -1)
    ok "$m ${V:+($V)}"
  else
    falta "$m"
  fi
done

# RPi.GPIO: avisar si esta, porque en Pi 5 no sirve.
if python3 -c "import RPi.GPIO" 2>/dev/null; then
  printf '  [AVISO] RPi.GPIO instalado: NO funciona en Pi 5 (chip RP1).\n'
  printf '          JONICA26 usa gpiozero, asi que no molesta.\n'
fi

# ---------------------------------------------------------------- camara
titulo "Camara"
if command -v rpicam-hello >/dev/null 2>&1; then
  rpicam-hello --list-cameras 2>&1 | head -8 | sed 's/^/  /'
elif command -v libcamera-hello >/dev/null 2>&1; then
  libcamera-hello --list-cameras 2>&1 | head -8 | sed 's/^/  /'
else
  falta "rpicam-hello / libcamera-hello no encontrados"
fi

# ---------------------------------------------------------------- resumen
titulo "Resumen"
FALTANTES=0
command -v hailortcli >/dev/null 2>&1 || { echo "  - Falta el software de Hailo  -> sudo apt install hailo-all && sudo reboot"; FALTANTES=1; }
python3 -c "import picamera2" 2>/dev/null || { echo "  - Falta picamera2             -> sudo apt install python3-picamera2"; FALTANTES=1; }
python3 -c "import gpiozero"  2>/dev/null || { echo "  - Falta gpiozero              -> pip install -r requirements.txt --break-system-packages"; FALTANTES=1; }
python3 -c "import numpy"     2>/dev/null || { echo "  - Falta numpy                 -> pip install -r requirements.txt --break-system-packages"; FALTANTES=1; }
[ "$FALTANTES" -eq 0 ] && echo "  Todo lo necesario esta instalado."

echo
echo "================================================================"
echo " Fin. Pega esta salida completa para revisarla."
echo "================================================================"
