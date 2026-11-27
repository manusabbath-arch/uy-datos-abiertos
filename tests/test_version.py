"""`uydatos.__version__` (que va en el User-Agent) es la de `pyproject.toml`.

Es una constante a mano: en `mcp-uruguay` la misma constante quedó en 0.7.0 durante cuatro versiones
y nadie lo vio hasta instalar el paquete desde PyPI. Acá no pasó, y este test es para que no pase.
"""

from __future__ import annotations

import re
from pathlib import Path

import uydatos


def test_la_version_del_paquete_es_la_de_pyproject():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert uydatos.__version__ == re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert uydatos.__version__ in uydatos.USER_AGENT


def test_el_user_agent_tiene_la_forma_que_acepta_el_parlamento():
    """Medido el 2026-11-27: parlamento.gub.uy (CloudFront) responde 403 a `uydatos/X (…)`, a curl, a
    `python-requests` y a los bots conocidos, y 200 a `Mozilla/5.0 (compatible; nombre/versión; +url)`,
    la convención con que se identifica un cliente que no es un navegador. Es la misma identidad: el
    nombre, la versión y el repositorio siguen a la vista."""
    assert re.fullmatch(r"Mozilla/5\.0 \(compatible; uydatos/[0-9.]+; \+https://github\.com/\S+\)", uydatos.USER_AGENT)
