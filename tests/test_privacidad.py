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

from uydatos import rut

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
        for numero, que_es in _hallazgos_en(texto, compiladas):
            hallazgos.append(f"  {ruta.relative_to(RAIZ)}:{numero}: {que_es}")
    # El hallazgo dice el archivo, la línea y qué clase de interno es, pero no la línea: mostrarla en
    # la salida de un CI público sería publicar lo que se encontró.
    assert not hallazgos, "este paquete es público y hay internos en archivos versionados:\n" + "\n".join(hallazgos)


DOCE_DIGITOS = re.compile(r"(?<!\d)(\d{12})(?!\d)")

# RUT con dígito verificador válido que están permitidos porque son inventados. Si hay que agregar
# uno, el comentario tiene que decir de dónde salió y por qué no es de nadie.
PERMITIDOS = {
    "012345678919",  # el ejemplo de siempre (README, docstring de `rut`, test de `rut`)
    "210000000019",  # RUT sintético de las fixtures de compras
    "219000000004",  # RUT sintético de las fixtures de sanciones (21 + ceros, DV 4)
}

# Cédulas con DV válido que están permitidas porque son inventadas.
CIS_PERMITIDAS = {
    "12345672",  # el ejemplo del README y de `rut.validar_ci` (1.234.567-2)
}

# Ni pegado a otros dígitos ni metido dentro de un hash hexadecimal: una corrida de 8 dígitos
# adentro de `ae3d1ba4...` no es una cédula.
OCHO_DIGITOS = re.compile(r"(?<![0-9a-fA-F])(\d{8})(?![0-9a-fA-F])")
CI_PUNTEADA = re.compile(r"(?<![0-9a-fA-F])(\d{1}[.\-]\d{3}[.\-]\d{3}[.\-/]?\d)(?![0-9a-fA-F])")


def _rut_validos(texto: str) -> list[str]:
    return [m.group(1) for m in DOCE_DIGITOS.finditer(texto) if rut.es_rut_valido(m.group(1))]


def _parece_fecha(valor: str) -> bool:
    """`YYYYMMDD` pasa el DV de cédula por casualidad, una de cada diez fechas.

    Medido el 2026-11-17: sin esta guarda, `20261018` entraba como cédula válida y el guardián
    se volvía ruido. Un documento real que coincida con una fecha se pierde: es el precio de que
    el chequeo sirva en un repositorio lleno de fechas.
    """
    anio, mes, dia = int(valor[:4]), int(valor[4:6]), int(valor[6:])
    return 1900 <= anio <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31


def _ci_validas(texto: str) -> list[str]:
    """Cédulas con DV válido en la línea, cada una una sola vez.

    El algoritmo no se reimplementa acá: `rut.es_ci_valida` ya lo tiene, con vector publicado
    (`1.234.567-2` válida, `1.234.567-3` no).
    """
    vistas: dict[str, None] = {}
    for patron in (OCHO_DIGITOS, CI_PUNTEADA):
        for match in patron.finditer(texto):
            valor = re.sub(r"\D", "", match.group(1))
            if valor in CIS_PERMITIDAS or valor in vistas:
                continue
            if patron is OCHO_DIGITOS and _parece_fecha(valor):
                continue
            if rut.es_ci_valida(valor):
                vistas[valor] = None
    return list(vistas)


def _hallazgos_en(texto: str, compiladas: list[tuple[re.Pattern[str], str]]) -> list[tuple[int, str]]:
    """`(línea, qué es)` por cada forma que aparece. Separado para poder probarlo plantado."""
    return [
        (numero, que_es)
        for numero, linea in enumerate(texto.splitlines(), 1)
        for patron, que_es in compiladas
        if patron.search(linea)
    ]


def test_el_guardian_ve_un_rut_plantado():
    """El guardián no puede estar verde porque no mira."""
    assert _rut_validos("razón social;219000000004    ;MONTEVIDEO") == ["219000000004"]
    assert _rut_validos("no hay ninguno acá: 2026-10-18") == []


def test_ningun_archivo_versionado_tiene_un_rut_valido():
    """El README dice que el repositorio publica código y no datos. Medido el 2026-10-18 había un
    RUT real —de una empresa sancionada, copiado del archivo del DSS— en un doc y en una fixture.
    Este test es la razón por la que no puede volver a pasar.

    **La guarda no publica lo que protege**: el hallazgo dice archivo y línea, nunca el número.
    """
    hallazgos = []
    for ruta in archivos_versionados():
        if ruta == ESTE or not ruta.is_file() or ruta.suffix.lower() in {".lock"}:
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            for valor in _rut_validos(linea):
                if valor not in PERMITIDOS:
                    hallazgos.append(f"  {ruta.relative_to(RAIZ)}:{numero}: un RUT con dígito válido")
    assert not hallazgos, "hay un RUT con dígito válido en un archivo versionado:\n" + "\n".join(hallazgos)


def test_el_guardian_ve_un_termino_local_plantado():
    """La lista privada vive fuera del repo; igual tiene que morder si aparece."""
    compiladas = [(re.compile(r"proyecto-interno"), "un nombre de un proyecto privado")]

    assert _hallazgos_en("primera línea\nacá dice proyecto-interno\n", compiladas) == [
        (2, "un nombre de un proyecto privado")
    ]
    assert _hallazgos_en("nada que ver", compiladas) == []


def test_el_guardian_ve_una_ci_plantada():
    assert _ci_validas("titular;1.111.111-1;MONTEVIDEO") == ["11111111"]
    assert _ci_validas("titular;11111111;MONTEVIDEO") == ["11111111"]


def test_una_ci_con_dv_invalido_no_es_un_hallazgo():
    assert _ci_validas("titular;1.234.567-3;MONTEVIDEO") == []


def test_el_ejemplo_documentado_no_es_un_hallazgo():
    assert _ci_validas('validar_ci("1.234.567-2")') == []


def test_una_fecha_no_se_confunde_con_una_ci():
    """`20261018` tiene DV válido por casualidad; sin esto el guardián era ruido."""
    assert _ci_validas("medido el 2026-10-18") == []
    assert _ci_validas("fecha 20261018") == []


def test_una_corrida_de_digitos_en_un_hash_no_es_una_ci():
    assert _ci_validas('sha = "ae3d1ba4111111111f8c"') == []


def test_ningun_archivo_versionado_tiene_una_ci_valida():
    """La guarda no publica lo que protege: dice archivo y línea, nunca el número."""
    hallazgos = []
    for ruta in archivos_versionados():
        if ruta == ESTE or not ruta.is_file() or ruta.suffix.lower() in {".lock"}:
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            if _ci_validas(linea):
                hallazgos.append(f"  {ruta.relative_to(RAIZ)}:{numero}: una cédula con DV válido")
    assert not hallazgos, "hay una cédula con DV válido en un archivo versionado:\n" + "\n".join(hallazgos)
