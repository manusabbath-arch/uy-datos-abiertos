"""El punto de entrada unico: `python -m uydatos`."""

from __future__ import annotations

import subprocess
import sys

import pytest

from uydatos.__main__ import LECTORES, main


def test_sin_argumentos_lista_los_lectores(capsys):
    assert main([]) == 0
    salida = capsys.readouterr().out
    assert "inumet" in salida and "catalogo" in salida and "Lectores" in salida


def test_un_lector_que_no_existe_lo_dice_y_devuelve_dos(capsys):
    assert main(["no-existe"]) == 2
    err = capsys.readouterr().err
    assert "no existe" in err and "inumet" in err


@pytest.mark.parametrize("lector", sorted(LECTORES))
def test_cada_lector_acepta_ayuda_sin_salir_a_la_red(lector, capsys):
    """`--help` es el humo mas barato que hay: prueba el despacho entero sin tocar internet."""
    with pytest.raises(SystemExit) as salida:
        main([lector, "--help"])
    assert salida.value.code == 0
    assert capsys.readouterr().out


def test_python_m_uydatos_funciona_de_verdad():
    """El subproceso es lo unico que prueba que el `__main__.py` esta en su lugar."""
    r = subprocess.run([sys.executable, "-m", "uydatos"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "inumet" in r.stdout
