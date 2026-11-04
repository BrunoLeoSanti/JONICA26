#!/bin/bash
# Modo normal (pista) sacando fotos para el dataset del muneco.
# Corre en la Pi: desde una terminal por VNC, o por ssh desde cualquier compu:
#   ssh -t jonica@bumblebee.local "bash ~/jonica_dev/tools/fotos_muneco.sh"
# Ctrl+C para terminar. Las fotos quedan en ~/dataset_muneco/<fecha_hora>/.
cd ~/jonica_dev && exec /usr/bin/python3 source/deteccion_hailo_stream.py --fotos "$@"
