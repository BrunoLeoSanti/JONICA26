# Operación del robot

Cómo se usa el robot día a día: entrar a la Pi, arrancar, manejar, transmitir
y qué hacer cuando algo falla. Lo físico (cables, alimentación, pines) está en
[`hardware-y-conexiones.md`](hardware-y-conexiones.md).

Última revisión: 5 de noviembre de 2026.

---

## Accesos

| | |
|---|---|
| Nombre en la red | `bumblebee.local` |
| Usuario | `jonica` (sudo pide contraseña) |
| Carpeta de trabajo en la Pi | `~/jonica_dev` (clon del repo, se actualiza con `git pull`) |
| VNC | puerto 5900 (TigerVNC) |
| Mac | `ssh jonica` (alias en `~/.ssh/config`, entra con clave, sin contraseña) |
| Windows | `ssh jonica@bumblebee.local` (pide la contraseña) |

### Redes WiFi guardadas en la Pi

| Red | IP de la Pi | Notas |
|---|---|---|
| "Jornadas Roboticas" (sin tilde) | 192.168.118.82 | Red de la feria. Ahorro de energía del WiFi desactivado |
| "Jornadas Robóticas" (con tilde) | — | También guardada |
| "Casa 5G" | 192.168.1.188 | |

Si `bumblebee.local` no responde, probar con la IP. Si tampoco, puede haberse
conectado a otra de las redes guardadas: pasar la compu a esa red.

Para agregar una red nueva (necesita la contraseña de sudo):

```bash
ssh -t jonica 'sudo nmcli connection add type wifi con-name "NOMBRE" ssid "NOMBRE" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "CLAVE"'
```

### Puertos

| Dirección | Qué es |
|---|---|
| `http://bumblebee.local:8080` | **Página de control**: video, modo, pines, tecla 2 y WASD |
| `http://bumblebee.local:8000/stream` | Solo el video (MJPEG), sin controles |
| `http://localhost:8080` | La página de control, cuando se transmite con el script de YouTube |

---

## Arrancar y detener

`robot.py` es el programa completo: corre el modo pista o el de felicidad y
los alterna con la tecla 2. **No arranca solo al prender la Pi.**

**Arrancar** (desde la Mac; en Windows, igual pero con `ssh jonica@bumblebee.local`):

```bash
ssh jonica 'cd ~/jonica_dev && git pull && (setsid nohup python3 source/robot.py > ~/robot.log 2>&1 < /dev/null &)'
```

Queda corriendo aunque se cierre la terminal. Tarda unos 15 s en cargar el
modelo. Para ver qué va haciendo:

```bash
ssh jonica 'tail -f ~/robot.log'     # Ctrl+C corta la vista, no el robot
```

**Detener**, como un Ctrl+C (suelta cámara, Hailo y pines):

```bash
ssh jonica 'pkill -TERM -f "python3 source/[r]obot.py"'
```

**Apagar la Pi** (siempre así, nunca desenchufándola):

```bash
ssh -t jonica 'sudo shutdown -h now'
```

Esperar a que la luz verde deje de parpadear y recién ahí apagar la UPS.

### Antes de arrancarlo, fijarse que no esté corriendo

```bash
ssh jonica 'ps -eo args | grep -E "python3 source/robot|deteccion_hailo" | grep -v grep'
```

Si ya corre y se lo arranca otra vez, el segundo falla con `GPIO busy`.

---

## Página de control (`:8080`)

- **Video** con las cajas de detección y los FPS arriba a la izquierda.
- **Recuadro de pines**, arriba a la derecha: 1 en verde = prendido. En pista
  dice `PARE`, `semaforoverde`, `muneco`, `MODO`; en felicidad, `motor izq`,
  `motor der`, `reversa`, `MODO`. Es lo que de verdad le llega al Arduino.
- **Abajo a la izquierda**: el modo actual y las teclas apretadas.

Hacer **clic en la página** antes de usar el teclado.

| Tecla | Qué hace |
|---|---|
| **2** | Cambia entre pista y felicidad. **Una sola vez** y esperar unos 8–10 s: si se aprieta de nuevo durante el cambio, vuelve al modo anterior |
| **W A S D** | Manejo en modo felicidad (ver [la tabla](hardware-y-conexiones.md#modo-felicidad-manejo-con-wasd)) |
| **F11** | Pantalla completa, para el proyector |

---

## Transmitir a YouTube

La Pi manda el video por WiFi y la compu lo sube a YouTube. **La Pi tiene que
mandar una sola copia del video**: cada copia del video original pesa unos
48 Mbps y con dos el WiFi no da abasto y todo se traba.

Para eso está [`tools/transmitir_youtube.py`](../tools/transmitir_youtube.py):
pide el video a la Pi una sola vez y lo reparte a ffmpeg (que sube a YouTube)
y al navegador.

**Una vez por compu**: instalar ffmpeg y Python.

| Mac | Windows |
|---|---|
| `brew install ffmpeg` | `winget install Gyan.FFmpeg` y `winget install Python.Python.3.13` (después cerrar y abrir PowerShell) |

**Cada vez:**

1. Cerrar **toda** pestaña de `bumblebee.local` y cualquier OBS abierto.
2. En YouTube Studio: Crear → Emitir en directo → **Transmisión**, y copiar la
   **clave de emisión**.
3. Correr el script, en una sola terminal:
   ```bash
   cd JONICA26            # o ~/Repositorys/Jonica2026 en la Mac
   git pull
   python tools/transmitir_youtube.py      # en Mac: python3
   ```
   Pegar la clave. Si `bumblebee.local` no responde: `--pi 192.168.118.82`.
4. Ver y manejar desde **`http://localhost:8080`**. No usar `bumblebee.local`.
5. Cuando aparezca la vista previa en YouTube Studio, tocar **Emitir en directo**.

Para terminar: **Finalizar emisión** en YouTube y **Ctrl+C** en la terminal.

- La clave da acceso a transmitir en el canal: si queda a la vista (en el
  proyector, en un chat), regenerarla en YouTube Studio.
- Si se finaliza la emisión en YouTube, el script queda colgado: cortarlo y
  volver a correrlo con un directo nuevo.
- La cuenta tiene que tener el vivo habilitado. La primera vez YouTube tarda
  24 h en habilitarlo.

---

## Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| **El video se traba** | Dos copias del video: una pestaña de `bumblebee.local` además del script, dos pestañas, o un OBS abierto | Dejar una sola cosa pidiendo el video. Ver abajo cómo comprobarlo |
| | La Pi lleva rato prendida y su WiFi se degradó | Reiniciarla lo arregló varias veces |
| | Señal débil (robot lejos de la antena) | Acercarlo. Si no se puede, bajar `RESOLUCION_STREAM` a `(1280, 960)` y `CALIDAD_JPEG` a 60 en `config.py` |
| | Calor (> 80 °C) | Ventilación |
| **La Pi no aparece** en la red (ni por nombre ni por IP) | Se apagó (energía), está arrancando o se conectó a otra red guardada | Mirar las luces; probar la otra red; cable de red directo a la compu |
| **Se apaga sola** | Con voltaje bien hasta el final: contacto de los pogo pins. Con voltaje bajando: baterías | Cable USB-A → USB-C puesto; baterías cargadas; agarrar el robot por el chasis |
| `GPIO busy` | Ya hay un `robot.py` corriendo | No arrancarlo de nuevo, o detener el que corre |
| `Address already in use` (script de YouTube) | Ya hay otro script corriendo en la compu | Cerrar el otro (otra pestaña de la terminal) |
| ffmpeg: `Error opening output ... live2/?` | La clave se pegó mal | Volver a pegarla; el script la pide de nuevo si no parece válida |
| ffmpeg: `No se encontro ffmpeg` | No está instalado | Ver la tabla de instalación |
| **La tecla 2 no cambia el modo** | Se está mirando `:8000` (solo video) o se apretó dos veces | Usar `:8080`, apretar una vez y esperar |
| Frena ante algo que no es el cartel | Confianza o tamaño | Ajustar umbrales y filtros en `config.py` |

### Comprobar cuántas copias del video manda la Pi

```bash
ssh jonica 'ss -tn state established "( sport = :8000 )"'
```

Tiene que haber **una sola línea**. La columna `Send-Q` es lo que está
esperando salir: unos cientos de KB está bien; varios MB es que el WiFi no da
abasto.

### Registros en la Pi

| Archivo | Qué tiene |
|---|---|
| `~/robot.log` | Lo que imprime `robot.py`: FPS, PARE detectado, errores. Se pisa en cada arranque |
| `~/registros_energia/energia_AAAA-MM-DD.csv` | Cada 5 s: voltaje, consumo, temperatura, `throttled`. Arranca solo con la Pi. Sirve para saber por qué se apagó |
| `~/vigilar_wifi.log` | Cada 20 s: temperatura, enlace WiFi, señal, ping al router y video encolado. Se arranca a mano con `~/vigilar_wifi.sh` |

Los registros del sistema (`journalctl`) se borran en cada reinicio: si la Pi
se porta raro, revisar **antes** de reiniciarla.

---

## Dónde se ajusta cada cosa

| Qué | Dónde |
|---|---|
| Umbrales de confianza, alto mínimo, proporción del muñeco | `source/config.py` |
| Cuánto tiempo engancha la Pi cada señal | `DURACION_PARE`, `DURACION_MUNECO` en `config.py` |
| Cuánto frena y cuánto ignora el Arduino | `tiempo_*` arriba del sketch |
| Cuánto gira una diagonal en felicidad | `TIEMPO_GIRO_DIAGONAL` en `config.py` |
| Resolución y calidad del video | `RESOLUCION_STREAM`, `CALIDAD_JPEG` en `config.py` |
| Velocidades del PID y de felicidad | arriba del sketch |

Cualquier cambio en `config.py`: subirlo al repo, `git pull` en la Pi y
reiniciar `robot.py`. Cambios en el sketch: subirlo al Arduino desde el IDE.

---

## Antes de competir

- [ ] Baterías cargadas a fondo y cargador a mano.
- [ ] Cable USB-A → USB-C de la UPS a la Pi puesto.
- [ ] Ventilación para la Pi.
- [ ] Sketch actual compilado y subido al Arduino.
- [ ] `git pull` en la Pi y `robot.py` arrancado; la página muestra 30 FPS.
- [ ] Una sola cosa pidiendo el video.
- [ ] Probar en la pista: frena ante el PARE y el muñeco a ~80 cm, y arranca con el verde.
