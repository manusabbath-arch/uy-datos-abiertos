"""El paquete es público: nada versionado cita internos de un proyecto privado.

La regla existe porque el incumplimiento pasó: la primera versión de un documento de `docs/` citaba
rutas, scripts y datos operativos del proyecto privado que motivó estos lectores. Una revisión humana
lo encontró y el documento se reescribió. Esto lo vuelve mecánico.

**La guarda no puede publicar lo que protege.** Por eso acá solo están las formas genéricas (rutas
absolutas de una máquina). Los nombres específicos de lo privado —carpetas, documentos, sistemas— van
en `.privacidad-local`, un archivo que git ignora: una línea por forma, `expresión<TAB>qué es`. Si el
archivo existe, se verifican también; en un clon sin él, solo las genéricas. Una versión anterior de
esta guarda listaba esos nombres en este mismo archivo, que se iba a publicar.

**Atrapa la forma, no el sentido.** Un dato del negocio contado con otras palabras no se detecta, y
los nombres de personas y empresas no se listan en ningún lado. La revisión humana no se reemplaza.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ESTE = Path(__file__).resolve()
LOCAL = RAIZ / ".privacidad-local"

# Las únicas formas que se pueden escribir acá: no dicen nada de nadie.
GENERICAS = {
    r"[A-Za-z]:[\\/]Users[\\/]": "una ruta de Windows de una máquina",
    r"/c/Users/": "una ruta de MSYS de una máquina",
}


def _hay_git() -> bool:
    try:
        subprocess.run(["git", "rev-parse", "--git-dir"], cwd=RAIZ, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


if not _hay_git():  # pragma: no cover - en un sdist no hay .git
    pytest.skip("sin git no se puede saber qué está versionado", allow_module_level=True)


def formas() -> dict[str, str]:
    """Las genéricas, más las de `.privacidad-local` si existe en esta máquina."""
    todas = dict(GENERICAS)
    if LOCAL.is_file():
        for linea in LOCAL.read_text(encoding="utf-8").splitlines():
            if linea.strip() and not linea.startswith("#"):
                expresion, _, que_es = linea.partition("\t")
                todas[expresion.strip()] = que_es.strip() or "una forma privada"
    return todas


def archivos_versionados() -> list[Path]:
    """Lo que git tiene versionado. Es la lista que importa: lo demás no se publica."""
    crudo = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, check=True).stdout
    return [RAIZ / nombre for nombre in crudo.decode().split("\0") if nombre]


def test_el_archivo_local_no_se_versiona():
    """Si `.privacidad-local` se versionara, se publicaría todo lo que protege."""
    ignorado = subprocess.run(["git", "check-ignore", "-q", ".privacidad-local"], cwd=RAIZ)
    assert ignorado.returncode == 0, ".privacidad-local tiene que estar en .gitignore"
    assert LOCAL not in archivos_versionados()


def test_ningun_archivo_versionado_cita_internos() -> None:
    hallazgos = []
    compiladas = [(re.compile(f), que_es) for f, que_es in sorted(formas().items())]
    for ruta in archivos_versionados():
        if ruta == ESTE or not ruta.is_file():
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binario, o algo que no es texto: acá no hay nada que citar
        for numero, linea in enumerate(texto.splitlines(), 1):
            for patron, que_es in compiladas:
                if patron.search(linea):
                    hallazgos.append(f"  {ruta.relative_to(RAIZ)}:{numero}: {que_es}")
    # El hallazgo dice el archivo, la línea y qué clase de interno es, pero no la línea: mostrarla en
    # la salida de un CI público sería publicar lo que se encontró.
    assert not hallazgos, "este paquete es público y hay internos en archivos versionados:\n" + "\n".join(hallazgos)
