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


def test_la_version_tiene_su_entrada_en_el_changelog():
    """Una versión sin su sección en el CHANGELOG sale sin notas: `scripts/publicar.sh` las toma de ahí.

    Lo medido el 2026-11-04: la 0.17.0 llevaba una semana en `main` sin publicarse, con el CHANGELOG
    en orden. El CHANGELOG es lo que la Release copia; este test asegura que esté antes de publicar."""
    raiz = Path(__file__).resolve().parents[1]
    changelog = (raiz / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## {re.escape(uydatos.__version__)} — \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M), (
        f"CHANGELOG.md no tiene «## {uydatos.__version__} — AAAA-MM-DD»"
    )
