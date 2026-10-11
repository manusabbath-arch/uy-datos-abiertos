"""Indicadores sociales del Observatorio Social del MIDES, leídos de su página viva en gub.uy.

Por qué no del catálogo de datos abiertos: **la copia del catálogo quedó congelada en 2019.**
Medido el 11/10/2026 sobre 60 indicadores al azar de `uydatos.mides`: los 57 que se pudieron leer
tienen `metadata_modified` de 2019, y su último dato es de 2011 (12), 2013 (19) o 2017 (15); el
único que llega a 2025 es una **proyección** hecha en 2019. Otros 3 no tienen ningún recurso. La
página del mismo indicador en gub.uy llega a 2023 o 2024. `uydatos.mides` sigue sirviendo para la
serie histórica; para el dato vigente, este módulo.

La fuente
---------
- La lista: el sitemap de `www.gub.uy/ministerio-desarrollo-social` (cinco páginas), que el
  11/10/2026 declaraba **1.264 indicadores** bajo `/indicador/`, 253 con «departamento» en el nombre.
  El buscador de la página de indicadores no sirve para esto: devuelve la portada sin resultados.
- Cada indicador: una página HTML con una ficha (`<h3>Fuente</h3>`, `Forma de cálculo`,
  `Unidad de observación`, `Período`...) y **una tabla** con los datos. Se baja con un GET, como
  cualquier navegador; no se completa ningún formulario.

Las trampas (medidas sobre 159 páginas al azar)
----------------------------------------------
1. **La tabla es lo que hay siempre; el gráfico no.** 159 de 159 páginas tienen una tabla de una
   sola fila de encabezado, sin celdas combinadas; el gráfico (un JSON de Chart.js) está en 19 de 40.
   Se lee la tabla.
2. **Dos formatos de número que no se pueden leer con una sola regla.** Las páginas actuales usan
   coma decimal y punto de miles (`8,6`, `1.201`); las de formato viejo usan punto decimal
   (`16.8`). Las viejas son las que no traen el formulario de filtros: 5 de 5 con punto decimal en la
   segunda muestra. Una de ellas tenía la tabla desordenada (Montevideo, mujeres: 1.202.757 en 1963
   y 29.218 en 1975) y otra una fila sin dimensión. **Una página sin filtros se rechaza**, con el
   motivo; un número que no tiene la forma de las páginas actuales también.
3. **`-` y `.` son «sin dato»** y se leen como nulo, nunca como cero. El punto suelto está en 7 de
   159 páginas, casi siempre en la columna 2020 (la ECH de la pandemia, telefónica).
3b. **El formulario de filtros no siempre declara todas las dimensiones** («Pobreza» está en la tabla
   y no en los filtros, en 3 de 159): las dimensiones son las columnas anteriores al primer período.
3c. **Hay basura en la fuente**: una celda `@` y otra `HOJA127b` en lugar de un número (2 de 159).
   Esas páginas se rechazan con la celda a la vista.
4. **Las filas «Total» van mezcladas con las demás** (81 de 120 tablas): sumar una columna cuenta
   todo dos veces. Se devuelven marcadas en `avisos`.
5. **Columnas sin encabezado, llenas de ceros** (2 de 120; en la de asistencia a la vejez, las dos
   últimas). No son un período: se descartan y se cuentan. Si una de ellas tuviera un valor distinto
   de cero, se rechaza.
6. **Las columnas no siempre son años**: hay meses (`ene-2014`, y desde 2024 `ene-24`), tramos
   (`2010-2011`) y categorías (`Antes de 1970`, `Ignorado`). Se devuelven como texto, tal cual.
7. **A veces la tabla muestra sólo el último año** (4 de 159, todas mapas por departamento): el
   resto de los años está detrás del formulario. Se marca `parcial` y se listan los
   `periodos_disponibles`; no se completa nada.
8. **La ficha no siempre dice lo mismo que los datos.** El año de fin de la ficha difiere del último
   dato en 5 de 40 (la ficha dice 2023 y la tabla llega a 2024). Una ficha dice «Número absoluto» y
   sus valores son porcentajes (bajo peso al nacer). Se devuelven las dos cosas, sin elegir.
9. La fecha que aparece al pie del gráfico (`Fecha: 11/10/2026`) es **la del día en que se mira la
   página**, no la del dato.

Uso:
    python -m uydatos.observatorio buscar pobreza departamento
    python -m uydatos.observatorio leer porcentaje-personas-situacion-pobreza-segun-ascendencia-afro-total-pais
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from typing import Optional, Sequence

from uydatos import red

BASE = "https://www.gub.uy/ministerio-desarrollo-social"
SITEMAP = f"{BASE}/sitemap.xml"
PREFIJO = f"{BASE}/indicador/"
SIN_DATO = ("-", ".")
CAMPOS_FICHA = {
    "Forma de cálculo": "calculo",
    "Comentarios": "comentarios",
    "Fuente": "fuente",
    "Frecuencia": "frecuencia",
    "Unidad de observación": "unidad",
}
_NUMERO = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")


class ObservatorioInvalido(ValueError):
    """La página no tiene la forma que se midió, o el indicador no existe."""


def _texto(fragmento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


# --- La lista ------------------------------------------------------------------------------------


def paginas_del_sitemap(xml: str) -> list[str]:
    """Las páginas de un índice de sitemap (`<sitemap><loc>`). No sale a la red."""
    return re.findall(r"<sitemap>\s*<loc>([^<]+)</loc>", xml)


def indicadores_del_sitemap(xml: str) -> list[str]:
    """Los nombres (`slug`) de los indicadores de una página de sitemap. No sale a la red."""
    return [u[len(PREFIJO) :] for u in re.findall(r"<loc>([^<]+)</loc>", xml) if u.startswith(PREFIJO)]


def indice() -> list[str]:
    """Todos los indicadores que declara el sitemap del MIDES, ordenados. **Sale a la red.**

    Medido el 11/10/2026: 5 páginas de sitemap, 1.264 indicadores. Si el índice no trae ninguna
    página o ningún indicador, el sitemap cambió de forma: se rechaza en vez de devolver una lista
    vacía, que se leería como «no hay indicadores».
    """
    paginas = paginas_del_sitemap(red.pedir(SITEMAP).decode("utf-8"))
    if not paginas:
        raise ObservatorioInvalido(f"{SITEMAP}: el índice no trae páginas de sitemap")
    slugs: set[str] = set()
    for p in paginas:
        slugs.update(indicadores_del_sitemap(red.pedir(p).decode("utf-8")))
    if not slugs:
        raise ObservatorioInvalido(f"{SITEMAP}: ninguna página del sitemap trae indicadores")
    return sorted(slugs)


def buscar(slugs: Sequence[str], texto: str, cantidad: int = 20) -> list[str]:
    """Los indicadores cuyo nombre contiene **todas** las palabras de `texto`. No sale a la red.

    El nombre es el de la URL (sin tildes, con guiones), que sale del título. Las palabras se comparan
    sin tildes y por prefijo de cuatro letras, para que «departamentos» encuentre «departamento». Los
    más cortos primero: suelen ser el indicador general, y los largos sus aperturas.
    """
    palabras = [_sin_tildes(p)[:4] for p in re.findall(r"\w+", texto) if len(p) > 2]
    if not palabras:
        raise ObservatorioInvalido(f"{texto!r}: hace falta al menos una palabra de tres letras o más")
    encontrados = [s for s in slugs if all(p in s for p in palabras)]
    return sorted(encontrados, key=lambda s: (len(s), s))[: max(1, cantidad)]


def url_de(entrada: str) -> str:
    """La URL de un indicador a partir de su nombre o de la URL misma."""
    texto = entrada.strip().rstrip("/")
    if texto.startswith(PREFIJO):
        texto = texto[len(PREFIJO) :]
    if not re.fullmatch(r"[a-z0-9-]+", texto):
        raise ObservatorioInvalido(f"{entrada!r}: no parece un indicador (se esperaba algo como 'tasa-empleo-...')")
    return PREFIJO + texto


# --- Una página ----------------------------------------------------------------------------------


def _numero(celda: str, donde: str) -> Optional[float]:
    if celda in SIN_DATO or not celda:
        return None
    if not _NUMERO.fullmatch(celda):
        raise ObservatorioInvalido(
            f"{donde}: {celda!r} no tiene la forma de los números de la página (coma decimal, punto de miles)"
        )
    return float(celda.replace(".", "").replace(",", "."))


def _ficha(texto: str) -> dict:
    ficha: dict = {}
    for titulo, cuerpo in re.findall(r"<h3>(.*?)</h3>(.*?)(?=<h3>|<footer|$)", texto, flags=re.S):
        clave = CAMPOS_FICHA.get(_texto(titulo))
        if clave:
            parrafo = re.search(r"<p[^>]*>(.*?)</p>", cuerpo, flags=re.S)
            ficha[clave] = _texto(parrafo.group(1) if parrafo else cuerpo)
        elif _texto(titulo) == "Período":
            inicio = re.search(r"Año de inicio:\s*(\d{4})", _texto(cuerpo))
            fin = re.search(r"Año de fin:\s*(\d{4})", _texto(cuerpo))
            ficha["periodo_ficha"] = {
                "inicio": int(inicio.group(1)) if inicio else None,
                "fin": int(fin.group(1)) if fin else None,
            }
    return ficha


def _filtros(texto: str) -> dict:
    m = re.search(r'name="current_filters" value="([^"]*)"', texto)
    if not m:
        raise ObservatorioInvalido(
            "la página no trae el formulario de filtros: es del formato viejo, que usa punto decimal y en "
            "la medición tuvo una tabla desordenada. No se lee."
        )
    filtros = json.loads(html.unescape(m.group(1)))
    filtros.pop("style", None)
    return {k: v for k, v in filtros.items() if isinstance(v, dict)}


def _normal(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre.replace("#", "")).strip().lower()


def leer_pagina(texto: str, url: str = "") -> dict:
    """La ficha y los datos de una página de indicador. No sale a la red.

    Devuelve `titulo`, `descripcion`, `url`, la ficha (`calculo`, `fuente`, `frecuencia`, `unidad`,
    `periodo_ficha`, `comentarios`), `dimensiones` (los nombres de las columnas que no son período),
    `periodos` (las columnas de dato, como texto), `filas` (cada una con `dimensiones` y `valores`,
    un valor por período, `None` si es «sin dato»), `parcial` y `periodos_disponibles` (si la
    tabla muestra menos períodos de los que el indicador tiene), `columnas_descartadas` y `avisos`.
    """
    donde = url or "la página"
    titulo = re.search(r"<title>(.*?)</title>", texto, flags=re.S)
    descripcion = re.search(r'<meta name="description" content="([^"]*)"', texto)
    tablas = re.findall(r"<table.*?</table>", texto, flags=re.S)
    if len(tablas) != 1:
        raise ObservatorioInvalido(f"{donde}: tiene {len(tablas)} tablas y la medición encontró siempre una")
    if re.search(r"(?:col|row)span", tablas[0]):
        raise ObservatorioInvalido(f"{donde}: la tabla combina celdas, y la medición no encontró ninguna así")
    filtros = _filtros(texto)
    filas_html = re.findall(r"<tr.*?</tr>", tablas[0], flags=re.S)
    celdas = [[_texto(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", f, flags=re.S)] for f in filas_html]
    if len(celdas) < 2:
        raise ObservatorioInvalido(f"{donde}: la tabla no tiene filas de dato")
    encabezado, cuerpo = celdas[0], celdas[1:]

    # El período es el filtro cuyas opciones más se repiten en el encabezado; las dimensiones, las
    # columnas que van antes de la primera de ellas que traiga algún número. No se toman de los
    # filtros: medido, en 3 de 159 páginas una dimensión de la tabla («Pobreza») no tiene filtro
    # propio y figura **entre las opciones del filtro de años**.
    periodo = max(filtros.values(), key=lambda opciones: len(set(opciones) & set(encabezado)))

    def con_numeros(i: int) -> bool:
        return any(i < len(f) and (_NUMERO.fullmatch(f[i]) or f[i] in SIN_DATO) for f in cuerpo)

    n = next((i for i, c in enumerate(encabezado) if c in periodo and con_numeros(i)), 0)
    if n == 0:
        raise ObservatorioInvalido(f"{donde}: el encabezado {encabezado[:4]} no tiene dimensión o no tiene período")
    dimensiones = encabezado[:n]

    usadas = [i for i in range(n, len(encabezado)) if encabezado[i]]
    descartadas = [i for i in range(n, len(encabezado)) if not encabezado[i]]
    filas = []
    for numero, fila in enumerate(cuerpo, start=2):
        if len(fila) != len(encabezado):
            raise ObservatorioInvalido(
                f"{donde} fila {numero}: {len(fila)} celdas y el encabezado tiene {len(encabezado)}"
            )
        if any(not c for c in fila[:n]):
            raise ObservatorioInvalido(f"{donde} fila {numero}: una dimensión vacía {fila[:n]}")
        for i in descartadas:
            if _numero(fila[i], f"{donde} fila {numero}") not in (None, 0.0):
                raise ObservatorioInvalido(f"{donde} fila {numero}: una columna sin encabezado trae {fila[i]!r}")
        filas.append(
            {
                "dimensiones": dict(zip(dimensiones, fila[:n])),
                "valores": {encabezado[i]: _numero(fila[i], f"{donde} fila {numero}") for i in usadas},
            }
        )

    periodos = [encabezado[i] for i in usadas]
    # El mapa por departamento muestra un año y ofrece los demás en un selector (`filter_options`).
    opciones = list(dict.fromkeys(re.findall(r'name="filter_options" value="([^"]+)"', texto)))
    disponibles = opciones if set(periodos) < set(opciones) else []
    avisos = []
    totales = sorted({v for f in filas for v in f["dimensiones"].values() if _sin_tildes(v).startswith("total")})
    if totales:
        avisos.append(f"hay filas de total ({', '.join(totales)}) mezcladas con las demás: no sumar la columna entera")
    if disponibles:
        avisos.append(
            f"la página muestra sólo {', '.join(periodos)}; el indicador tiene {len(disponibles)} períodos "
            "que esta lectura no trae"
        )
    ficha = _ficha(texto)
    fin = (ficha.get("periodo_ficha") or {}).get("fin")
    anios = [int(p) for p in periodos if re.fullmatch(r"\d{4}", p)]
    if fin and anios and max(anios) != fin:
        avisos.append(f"la ficha dice que la serie termina en {fin} y la tabla llega a {max(anios)}")
    if descartadas:
        avisos.append(f"{len(descartadas)} columnas sin encabezado, con ceros, descartadas")
    return {
        "titulo": _texto(titulo.group(1)).removesuffix(" | MIDES") if titulo else "",
        "descripcion": html.unescape(descripcion.group(1)) if descripcion else "",
        "url": url,
        "calculo": ficha.get("calculo", ""),
        "fuente": ficha.get("fuente", ""),
        "frecuencia": ficha.get("frecuencia", ""),
        "unidad": ficha.get("unidad", ""),
        "comentarios": ficha.get("comentarios", ""),
        "periodo_ficha": ficha.get("periodo_ficha", {"inicio": None, "fin": None}),
        "dimensiones": dimensiones,
        "periodos": periodos,
        "filas": filas,
        "parcial": bool(disponibles),
        "periodos_disponibles": disponibles,
        "columnas_descartadas": len(descartadas),
        "avisos": avisos,
    }


def leer(entrada: str) -> dict:
    """Baja y lee la página de un indicador. **Sale a la red.** Un nombre que no existe da 404."""
    url = url_de(entrada)
    try:
        cuerpo = red.pedir(url)
    except OSError as e:
        if " 404 " in str(e):
            raise ObservatorioInvalido(f"{entrada!r}: no existe ese indicador (buscarlo con `buscar`)") from e
        raise
    return leer_pagina(cuerpo.decode("utf-8"), url)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.observatorio", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("buscar")
    b.add_argument("palabras", nargs="+")
    lee = sub.add_parser("leer")
    lee.add_argument("indicador")
    args = ap.parse_args(argv)
    if args.orden == "buscar":
        for s in buscar(indice(), " ".join(args.palabras)):
            print(s)
        return 0
    r = leer(args.indicador)
    print(r["titulo"])
    print(f"  unidad: {r['unidad']} · fuente: {r['fuente']} · períodos: {r['periodos'][0]} a {r['periodos'][-1]}")
    for aviso in r["avisos"]:
        print(f"  aviso: {aviso}")
    for f in r["filas"][:20]:
        print(" ", " / ".join(f["dimensiones"].values()), "→", list(f["valores"].values())[-3:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
