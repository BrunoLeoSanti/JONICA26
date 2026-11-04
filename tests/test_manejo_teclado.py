"""Tests del manejo con WASD del modo felicidad (sin Raspberry ni Arduino)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from manejo_teclado import QUIETO, ControlTeclado, Motores, motores_de_teclas  # noqa: E402


# --- Teclas -> (motor izquierdo, motor derecho, reversa) ----------------------

def test_w_prende_los_dos_hacia_adelante():
    assert motores_de_teclas("w") == Motores(True, True, False)


def test_s_prende_los_dos_en_reversa():
    assert motores_de_teclas("s") == Motores(True, True, True)


def test_a_gira_a_la_izquierda_con_el_motor_derecho():
    assert motores_de_teclas("a") == Motores(False, True, False)


def test_d_gira_a_la_derecha_con_el_motor_izquierdo():
    assert motores_de_teclas("d") == Motores(True, False, False)


def test_w_con_a_gira_igual_que_a():
    assert motores_de_teclas("wa") == Motores(False, True, False)


def test_s_con_d_gira_marcha_atras():
    assert motores_de_teclas("sd") == Motores(True, False, True)


def test_opuestas_se_anulan():
    assert motores_de_teclas("ws") == QUIETO
    assert motores_de_teclas("ad") == QUIETO


def test_w_con_a_y_d_va_recto():
    assert motores_de_teclas("wad") == Motores(True, True, False)


def test_sin_teclas_quieto():
    assert motores_de_teclas("") == QUIETO


def test_mayusculas_valen_igual():
    assert motores_de_teclas("W") == Motores(True, True, False)


# --- Vencimiento por seguridad ------------------------------------------------

def test_antes_de_recibir_nada_esta_quieto():
    assert ControlTeclado().motores(ahora=0.0) == QUIETO


def test_sigue_la_ultima_orden_mientras_no_venza():
    c = ControlTeclado(tiempo_sin_teclas=0.4)
    c.recibir("w", ahora=10.0)
    assert c.motores(ahora=10.3) == Motores(True, True, False)


def test_apaga_si_dejan_de_llegar_teclas():
    """Se corto la red o se cerro la pestana con la W apretada."""
    c = ControlTeclado(tiempo_sin_teclas=0.4)
    c.recibir("w", ahora=10.0)
    assert c.motores(ahora=10.5) == QUIETO


def test_soltar_todo_apaga_al_instante():
    c = ControlTeclado()
    c.recibir("w", ahora=10.0)
    c.recibir("", ahora=10.1)
    assert c.motores(ahora=10.1) == QUIETO


def test_ignora_caracteres_que_no_son_wasd():
    c = ControlTeclado()
    c.recibir("sx\n", ahora=0.0)
    assert c.motores(ahora=0.0) == Motores(True, True, True)
