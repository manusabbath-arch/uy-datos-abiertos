"""Comparar dos copias de la misma fuente: qué cambió, y si el cambio es de dominio.

`procedencia.sello()` dice de dónde salió un número; esto contesta la otra mitad. Medido el
2026-10-17: el archivo de sanciones del DSS declara `metadata_modified` del 2026-03-22 y su sha256
es el mismo del 2026-10-09 — la fecha se movió sin que el archivo cambiara. Al revés también pasa:
ANCAP republicó el 2026-10-12 y cambió el id del recurso. Un sello sin comparación dice «algo».

La regla es la de `docs/plantilla-lector.md`: **un cambio de columnas no es una revisión, es otra
fuente**, y se rechaza. Una fila con una clave repetida tampoco se compara: no se puede decir cuál
de las dos cambió.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Optional, Sequence

from uydatos.errores import DatosInvalidos


class RevisionInvalida(DatosInvalidos):
    """Las dos copias no se pueden comparar con la clave pedida."""


def _leer(ruta: Path, delimitador: str, codificacion: str) -> tuple[list[str], list[list[str]]]:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise RevisionInvalida(f"{ruta}: no está en el disco")
    try:
        with ruta.open(encoding=codificacion, newline="") as f:
            lector = csv.reader(f, delimiter=delimitador)
            try:
                encabezado = [c.replace("\ufeff", "").strip() for c in next(lector)]
            except StopIteration:
                raise RevisionInvalida(f"{ruta}: archivo vacío") from None
            filas = [campos for campos in lector if any(c.strip() for c in campos)]
    except UnicodeDecodeError as e:
        # La codificación se pide explícita porque no se adivina el dialecto: si no coincide, el
        # rechazo dice qué archivo es y con qué se intentó, en vez de dejar escapar el codec.
        raise RevisionInvalida(f"{ruta}: no se puede leer como {codificacion} ({e})") from None
    return encabezado, filas


def comparar(
    antes: Path,
    despues: Path,
    *,
    clave: Sequence[str],
    delimitador: str = ";",
    codificacion: str = "utf-8",
    muestra: int = 20,
) -> dict:
    """Compara dos copias por `clave` y declara qué cambió.

    `delimitador` y `codificacion` se piden explícitos: la mayoría de los archivos del catálogo
    viene con `;`, y el de sanciones con cp1252 (medido). Adivinar el dialecto es exactamente lo
    que este paquete no hace, y si la codificación no coincide el rechazo nombra el archivo que no
    se pudo leer.
    """
    enc_a, filas_a = _leer(antes, delimitador, codificacion)
    enc_d, filas_d = _leer(despues, delimitador, codificacion)
    if enc_a != enc_d:
        agregadas = [c for c in enc_d if c not in enc_a]
        quitadas = [c for c in enc_a if c not in enc_d]
        if not agregadas and not quitadas:
            # Mismo juego de columnas en otro orden: el motivo lo dice, porque la comparación es
            # por posición y el mismo dato en otra columna es otro dato.
            raise RevisionInvalida(
                f"columnas distintas: las mismas en otro orden ({enc_a} → {enc_d}). "
                "Un cambio de columnas es otra fuente."
            )
        raise RevisionInvalida(
            f"columnas distintas: agregadas {agregadas}, quitadas {quitadas}. Un cambio de columnas es otra fuente."
        )
    for nombre, enc, filas, ruta in (("antes", enc_a, filas_a, antes), ("después", enc_d, filas_d, despues)):
        for n, campos in enumerate(filas, start=2):
            if len(campos) != len(enc):
                raise RevisionInvalida(f"{ruta} ({nombre}) fila {n}: {len(campos)} columnas, se esperaban {len(enc)}")
    indices = [enc_a.index(c) for c in clave] if all(c in enc_a for c in clave) else None
    if indices is None:
        raise RevisionInvalida(f"la clave {list(clave)} no está en las columnas {enc_a}")

    def tabla(filas: list[list[str]], ruta: Path) -> dict[tuple, list[str]]:
        salida: dict[tuple, list[str]] = {}
        for n, campos in enumerate(filas, start=2):
            k = tuple(campos[i].strip() for i in indices)
            if any(not v for v in k):
                continue  # una fila sin clave no es una fila de dato: se saltea y se cuenta aparte
            if k in salida:
                raise RevisionInvalida(f"{ruta} fila {n}: clave repetida {k}")
            salida[k] = campos
        return salida

    ta, td = tabla(filas_a, antes), tabla(filas_d, despues)
    cambiadas = sorted(k for k in ta.keys() & td.keys() if ta[k] != td[k])
    agregadas = sorted(td.keys() - ta.keys())
    quitadas = sorted(ta.keys() - td.keys())
    sin_clave = (len(filas_a) - len(ta)) + (len(filas_d) - len(td))
    return {
        "columnas": enc_a,
        "cambio": bool(cambiadas or agregadas or quitadas),
        "filas_agregadas": len(agregadas),
        "filas_quitadas": len(quitadas),
        "filas_cambiadas": len(cambiadas),
        "claves_cambiadas": [list(k) for k in cambiadas[:muestra]],
        "claves_agregadas": [list(k) for k in agregadas[:muestra]],
        "claves_quitadas": [list(k) for k in quitadas[:muestra]],
        "sin_clave": sin_clave,
    }


def _numero(texto: str) -> Optional[float]:
    """El valor como número, o `None`. No adivina separadores de miles: si no es un número limpio,
    la fila se cuenta en `no_numericas` y no se compara."""
    limpio = texto.strip().replace(" ", "")
    if not limpio:
        return None
    try:
        return float(limpio)
    except ValueError:
        return None


def _por_clave(encabezado: list[str], filas: list[list[str]], clave: Sequence[str]) -> dict[tuple[str, ...], list[str]]:
    faltan = [c for c in clave if c not in encabezado]
    if faltan:
        raise RevisionInvalida(f"no están las columnas de la clave: {faltan}")
    posiciones = [encabezado.index(c) for c in clave]
    indice: dict[tuple[str, ...], list[str]] = {}
    for fila in filas:
        k = tuple(fila[i] for i in posiciones)
        if k in indice:
            raise RevisionInvalida(f"la clave {k} se repite: no se puede decir cuál de las dos cambió")
        indice[k] = fila
    return indice


def revisadas(
    antes: Path,
    despues: Path,
    *,
    clave: Sequence[str],
    valor: str,
    delimitador: str = ";",
    codificacion: str = "utf-8",
    tolerancia: float = 0.0,
    muestra: int = 20,
) -> dict:
    """Qué filas que YA estaban cambiaron de `valor`: la revisión del pasado, no las altas y bajas.

    Un archivo que crece agrega filas al final y se nota; uno que se reprocesa **reescribe el
    pasado** y el total no cambia, así que nadie se entera. Medido el 2026-10-17: el archivo de
    sanciones declara `metadata_modified` 2026-03-22 y su sha256 es el del 09/10 — la fecha se movió
    sin que el archivo cambiara; al revés, una fuente puede cambiar el archivo sin mover la fecha.

    `tolerancia` está para la fuente que publica con redondeo: por debajo de eso, no es revisión.
    Las filas con un valor que no es número se cuentan en `no_numericas`, no se saltean en silencio.
    """
    enc_a, filas_a = _leer(antes, delimitador, codificacion)
    enc_d, filas_d = _leer(despues, delimitador, codificacion)
    if enc_a != enc_d:
        raise RevisionInvalida(f"los encabezados no coinciden: {antes.name} contra {despues.name}")
    if valor not in enc_d:
        raise RevisionInvalida(f"no hay columna `{valor}`: están {enc_d}")
    i_valor = enc_d.index(valor)
    a = _por_clave(enc_d, filas_a, clave)
    d = _por_clave(enc_d, filas_d, clave)
    revisadas_, no_numericas = [], 0
    for k in sorted(a.keys() & d.keys()):
        va, vd = _numero(a[k][i_valor]), _numero(d[k][i_valor])
        if va is None or vd is None:
            no_numericas += 1
            continue
        delta = vd - va
        if abs(delta) > tolerancia:
            revisadas_.append({"clave": list(k), "antes": va, "despues": vd, "delta": round(delta, 6)})
    mayores = sorted(revisadas_, key=lambda r: abs(r["delta"]), reverse=True)[:muestra]
    return {
        "revisadas": len(revisadas_),
        "nuevas": len(d.keys() - a.keys()),
        "borradas": len(a.keys() - d.keys()),
        "no_numericas": no_numericas,
        "mayores": mayores,
    }


def desde_json(antes: Path, despues: Path, *, variacion: float = 0.2, minimo: int = 10) -> dict:
    """Qué cambió entre dos informes de `python -m uydatos.verificar --json`.

    El umbral de filas es `max(minimo, variación × las de antes)`: una fuente que agrega cien filas
    por semana no es noticia; una que pierde el 20% sí. Un cambio de columnas se informa antes que
    el de filas, porque explica el otro.
    """

    def cargar(p: Path) -> dict[str, dict]:
        datos = json.loads(p.read_text(encoding="utf-8"))
        return {f["lector"]: f for f in datos["fuentes"]}

    a, d = cargar(antes), cargar(despues)
    rompieron, columnas, filas = [], [], []
    for lector in sorted(a.keys() & d.keys()):
        fa, fd = a[lector], d[lector]
        if fa["ok"] and not fd["ok"]:
            rompieron.append({"lector": lector, "motivo": fd["motivo"]})
            continue
        if not fd["ok"]:
            continue
        nuevas = sorted(set(fd["columnas"]) - set(fa["columnas"]))
        idas = sorted(set(fa["columnas"]) - set(fd["columnas"]))
        if nuevas or idas:
            columnas.append({"lector": lector, "nuevas": nuevas, "idas": idas})
            continue
        if fa["ok"]:
            umbral = max(minimo, int(fa["filas"] * variacion))
            if abs(fd["filas"] - fa["filas"]) > umbral:
                filas.append({"lector": lector, "antes": fa["filas"], "despues": fd["filas"]})
    tocados = {r["lector"] for r in rompieron} | {c["lector"] for c in columnas} | {f["lector"] for f in filas}
    return {
        "aparecen": sorted(set(d) - set(a)),
        "desaparecen": sorted(set(a) - set(d)),
        "rompieron": rompieron,
        "columnas": columnas,
        "filas": filas,
        # Sanas son las que se midieron y no cambiaron. Una fuente que pide un parámetro no está sana:
        # está sin medir, y contarla infla el verde (medido el 19/10: «sanas 19» con 8 sin medir).
        "sanos": sorted(lector for lector in a.keys() & d.keys() if d[lector]["ok"] and lector not in tocados),
    }


def markdown(comparacion: dict, titulo: str = "") -> str:
    """La comparación como tabla, para el resumen del CI o para un documento.

    Las fuentes sanas se cuentan, no se listan: trece filas verdes esconden la que importa. Y un
    informe sin cambios lo dice con una frase, porque un texto vacío no se distingue de uno que no
    se pudo hacer.
    """
    lineas = [f"## {titulo}", ""] if titulo else []
    filas = []
    for r in comparacion["rompieron"]:
        filas.append((r["lector"], "rompió", r["motivo"]))
    for c in comparacion["columnas"]:
        # Las que se fueron primero: se lee como un diff.
        partes = [f"-{x}" for x in c["idas"]] + [f"+{x}" for x in c["nuevas"]]
        filas.append((c["lector"], "columnas", " ".join(partes)))
    for f in comparacion["filas"]:
        filas.append((f["lector"], "filas", f"{f['antes']} → {f['despues']}"))
    for lector in comparacion["aparecen"]:
        filas.append((lector, "aparece", ""))
    for lector in comparacion["desaparecen"]:
        filas.append((lector, "desaparece", ""))
    if filas:
        lineas += ["| fuente | qué pasó | detalle |", "|---|---|---|"]
        lineas += [f"| `{a}` | {b} | {c} |" for a, b, c in filas]
        lineas.append("")
    else:
        lineas += ["Sin cambios de forma.", ""]
    # Ordenadas acá y no confiando en el llamador: la tabla no cambia porque cambie el orden del dict.
    lineas.append(f"sanas {len(comparacion['sanos'])}: {', '.join(sorted(comparacion['sanos'])) or 'ninguna'}")
    return "\n".join(lineas) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.revisiones", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    j = sub.add_parser("desde-json", help="compara los dos últimos informes de verificar de un directorio")
    j.add_argument("directorio", type=Path)
    args = ap.parse_args(argv)
    informes = sorted(args.directorio.glob("fuentes-*.json"))
    if len(informes) < 2:
        print(f"hacen falta dos informes en {args.directorio}: hay {len(informes)}")
        return 2
    r = desde_json(informes[-2], informes[-1])
    print(f"# {informes[-2].name} → {informes[-1].name}")
    for clave in ("rompieron", "columnas", "filas", "aparecen", "desaparecen"):
        for fila in r[clave]:
            print(f"{clave:<12} {fila}")
    print(f"sanos {len(r['sanos'])}: {', '.join(r['sanos']) or 'ninguno'}")
    return 0 if not r["rompieron"] and not r["columnas"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
