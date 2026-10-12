"""Tests de la maquina de estados de senales.

Corren en cualquier maquina: no necesitan Raspberry Pi, camara ni Hailo.
    python3 -m pytest tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from senales import ControlSenales, Deteccion  # noqa: E402


def det(nombre, conf):
    return Deteccion(nombre=nombre, confianza=conf, bbox=(0.0, 0.0, 1.0, 1.0))


# --- Semaforo verde: sigue al instante, sin memoria ---------------------------

def test_verde_enciende_go():
    c = ControlSenales()
    s = c.actualizar([det("semaforoverde", 0.9)], ahora=0.0)
    assert s.go is True
    assert s.pare is False


def test_verde_por_debajo_del_umbral_no_enciende():
    c = ControlSenales(umbral_verde=0.4)
    assert c.actualizar([det("semaforoverde", 0.39)], ahora=0.0).go is False


def test_go_se_apaga_cuando_el_verde_desaparece():
    c = ControlSenales()
    assert c.actualizar([det("semaforoverde", 0.9)], ahora=0.0).go is True
    assert c.actualizar([], ahora=0.1).go is False


# --- PARE: se engancha por una duracion fija ---------------------------------

def test_pare_enciende_y_se_mantiene_durante_la_duracion():
    c = ControlSenales(duracion_pare=5.0)
    assert c.actualizar([det("PARE", 0.9)], ahora=100.0).pare is True
    # Sigue activo aunque la senal ya no se vea.
    assert c.actualizar([], ahora=102.0).pare is True
    assert c.actualizar([], ahora=104.9).pare is True


def test_pare_se_apaga_al_cumplirse_la_duracion():
    c = ControlSenales(duracion_pare=5.0)
    c.actualizar([det("PARE", 0.9)], ahora=100.0)
    assert c.actualizar([], ahora=105.0).pare is False


def test_pare_no_reinicia_el_timer_mientras_esta_activo():
    """Ver la senal de nuevo a mitad de camino no debe extender la parada."""
    c = ControlSenales(duracion_pare=5.0)
    c.actualizar([det("PARE", 0.9)], ahora=100.0)
    c.actualizar([det("PARE", 0.9)], ahora=103.0)   # la sigue viendo
    assert c.actualizar([], ahora=105.0).pare is False


def test_pare_puede_volver_a_dispararse_despues_de_terminar():
    c = ControlSenales(duracion_pare=5.0)
    c.actualizar([det("PARE", 0.9)], ahora=100.0)
    assert c.actualizar([], ahora=105.0).pare is False
    assert c.actualizar([det("PARE", 0.9)], ahora=110.0).pare is True


def test_pare_por_debajo_del_umbral_no_dispara():
    c = ControlSenales(umbral_pare=0.3)
    assert c.actualizar([det("PARE", 0.29)], ahora=0.0).pare is False


# --- Varios -------------------------------------------------------------------

def test_nombres_de_clase_sin_distinguir_mayusculas():
    """El modelo exporta 'PARE' en mayusculas y 'semaforoverde' en minusculas."""
    c = ControlSenales()
    assert c.actualizar([det("pare", 0.9)], ahora=0.0).pare is True


def test_pare_y_verde_a_la_vez():
    """Prioriza frenar: el Arduino lee PARE y para igual."""
    c = ControlSenales()
    s = c.actualizar([det("PARE", 0.9), det("semaforoverde", 0.9)], ahora=0.0)
    assert s.pare is True and s.go is True


def test_clase_desconocida_se_ignora():
    c = ControlSenales()
    s = c.actualizar([det("perro", 0.99)], ahora=0.0)
    assert s.pare is False and s.go is False


def test_sin_detecciones_todo_apagado():
    c = ControlSenales()
    s = c.actualizar([], ahora=0.0)
    assert s.pare is False and s.go is False
