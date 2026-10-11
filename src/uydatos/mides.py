"""Indicadores de MIDES: una familia de 1.869 CSV con la misma forma.

**Esta copia quedó congelada en 2019** (medido el 11/10/2026: 57 de 57 indicadores con
`metadata_modified` de 2019, último dato entre 2011 y 2017). Para el dato vigente, que llega a 2024,
usar `uydatos.observatorio`, que lee la página viva de cada indicador.

La organizacion `mides` del catalogo publica 1.875 datasets, y **1.869 son indicadores**
(`mides-indicador-NNNNN`, numerados del 2718 al 14093). Los otros seis no son de esta familia:
cuatro encuestas ENDIS y dos paneles.

Medido el 09/10/26 sobre una muestra de 50 indicadores (uno cada cinco de las tres primeras paginas
de la busqueda) y sobre los 25 CSV bajados enteros:

- **La forma es una sola.** Cero o mas columnas de **dimension**, de nombre libre, y siempre las dos
  ultimas **`año`** y **`valor`**, en ese orden. Los 49 que tienen datastore terminan exactamente en
  `año, valor`, y los 10 que se bajaron tienen el encabezado identico al que declara el datastore.
  Cuantas dimensiones hay cambia (de cero a tres en la muestra) y como se llaman tambien -29 nombres
  distintos: `departamento`, `Sexo`, `Quintiles`, `Pobreza`, `Zona 2`, `Tipo de Cultivos`...-, asi
  que **no hay una declaracion de columnas por indicador**: las dimensiones son las de cada archivo.
- **El CSV viene en cp1252, no en UTF-8**, con `,` de delimitador y sin BOM. Decodificarlo como UTF-8
  no falla: convierte `año` en `aÃ±o`, que es peor. Por eso el lector decodifica en cp1252 y
  **rechaza el archivo si las dos ultimas columnas no son `año` y `valor`**, que es la senal de que
  la codificacion esta mal puesta.
- **El `_id` no esta en el CSV.** Es una columna que agrega el datastore de CKAN: el encabezado del
  archivo es el del datastore menos esa.
- **Un valor vacio es un nulo, no un cero.** En las 2.215 filas medidas no habia ninguno, asi que un
  vacio se rechaza en vez de rellenarse: si aparece, la fuente cambio y hay que mirarla.
- **Un indicador tiene un solo CSV** (49 de 49 en la muestra). Si aparece un segundo, algo cambio.
- El `total` del datastore coincide con las filas de dato del CSV en esta familia, al reves que en
  INUMET, donde venia una de mas con el encabezado adentro. **Se cuenta igual, uno mismo.**

Uso:
    python -m uydatos.mides listar
    python -m uydatos.mides bajar 10745 datos/mides-10745.csv
    python -m uydatos.mides ver datos/mides-10745.csv

La medicion que sostiene todo esto esta en `docs/2026-10-09-mides-medicion.md`.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Sequence

from uydatos import catalogo, procedencia, red

PREFIJO = "mides-indicador-"
ORGANIZACION = "mides"

# La invariante de la familia: estas dos columnas, en este orden, al final del encabezado.
COLUMNAS_FIJAS = ("año", "valor")

# El rango de años del que hablan los indicadores. Amplio a proposito: atrapa una fecha imposible,
# no una rara.
ANIO_MINIMO = 1900
ANIO_MAXIMO = 2100


class MidesInvalido(ValueError):
    """El archivo o el indicador no tienen la forma que declara la familia."""


def numero_de_indicador(entrada: str) -> str:
    """El nombre del dataset a partir de `10745`, de `mides-indicador-10745` o de la URL del dataset.

    Acepta las tres formas porque las tres aparecen en la vida real: el numero suelto en una
    planilla, el nombre del dataset en el catalogo, y la URL al copiar y pegar de la web.
    """
    texto = entrada.strip().rstrip("/")
    if "/" in texto:
        texto = texto.split("/dataset/")[-1].split("/")[0]
    nombre = texto if texto.startswith(PREFIJO) else f"{PREFIJO}{texto}"
    if not nombre[len(PREFIJO) :].isdigit():
        raise MidesInvalido(f"{entrada!r}: no parece un indicador de MIDES (se esperaba {PREFIJO}NNNNN)")
    return nombre


def indicadores(*, filas: int = 100, desde: int = 0) -> dict:
    """Los indicadores de MIDES que publica el catalogo. **Sale a la red.**

    Devuelve `{"total", "listados", "indicadores"}`. `total` es lo que declara la organizacion
    entera, que **incluye seis datasets que no son de esta familia** (las encuestas ENDIS y los
    paneles); los de `indicadores` si son todos de la familia.
    """
    r = catalogo.buscar("", organizacion=ORGANIZACION, filas=filas, desde=desde)
    return {
        "total": r["total"],
        "listados": len(r["datasets"]),
        "indicadores": [d for d in r["datasets"] if d["nombre"].startswith(PREFIJO)],
    }


def descargar(entrada: str, destino: Path) -> Path:
    """Baja el CSV de un indicador. **Sale a la red.**

    Un indicador tiene **un solo CSV** (medido: 49 de 49). Si aparece mas de uno, algo cambio: se
    levanta en vez de elegir por su cuenta cual es el bueno.
    """
    nombre = numero_de_indicador(entrada)
    csvs = [r for r in catalogo.recursos(nombre) if (r.get("formato") or "").upper() == "CSV"]
    if not csvs:
        raise MidesInvalido(f"{nombre}: no tiene ningun recurso CSV")
    if len(csvs) > 1:
        raise MidesInvalido(f"{nombre}: tiene {len(csvs)} CSV y la familia tiene uno. Hay que mirar cual es.")
    return red.bajar(csvs[0]["url"], destino)


def encabezado(ruta: Path) -> list[str]:
    """Las columnas del archivo, tal cual vienen. **No sale a la red.**"""
    with ruta.open(encoding="cp1252", newline="") as f:
        return next(csv.reader(f), [])


def dimensiones(columnas: Sequence[str]) -> list[str]:
    """Las columnas de dimension: todo el encabezado menos las dos fijas del final."""
    return list(columnas)[: -len(COLUMNAS_FIJAS)]


def filas_en_blanco(ruta: Path) -> int:
    """Cuantas lineas del archivo no son un dato (todas sus celdas vacias). **No sale a la red.**

    La familia no tiene ninguna (medido: 2.215 filas, cero vacias), pero una linea suelta al final
    de un archivo exportado no es raro. Se saltean y **se cuentan**, como en INUMET.
    """
    with ruta.open(encoding="cp1252", newline="") as f:
        lector = csv.reader(f)
        next(lector, None)  # el encabezado, que no es una fila de dato
        return sum(1 for fila in lector if not any(c.strip() for c in fila))


def leer_archivo(ruta: Path) -> list[dict]:
    """Las filas del indicador, una por año y combinacion de dimensiones. **No sale a la red.**

    Cada fila es `{"dimensiones": {...}, "año": 2000, "valor": 1048612.0}`. Las dimensiones van
    **anidadas en un diccionario porque sus nombres son libres**: no hay una columna fija por cada
    una, y aplanarlas contra `año` y `valor` seria inventar un contrato que la familia no tiene. Un
    archivo con solo `año, valor` devuelve `dimensiones` vacio, y eso es una fila valida.
    """
    with ruta.open(encoding="cp1252", newline="") as f:
        lector = csv.reader(f)
        columnas = next(lector, None)
        if not columnas:
            raise MidesInvalido(f"{ruta}: el archivo esta vacio")
        fijas = tuple(columnas[-len(COLUMNAS_FIJAS) :])
        if fijas != COLUMNAS_FIJAS:
            raise MidesInvalido(
                f"{ruta}: las dos ultimas columnas son {fijas} y la familia termina en "
                f"{COLUMNAS_FIJAS}. Si ademas la enie se ve rara, la codificacion no es cp1252."
            )
        nombres = dimensiones(columnas)
        if len(set(nombres)) != len(nombres):
            raise MidesInvalido(f"{ruta}: hay dimensiones con el mismo nombre ({nombres}): una se perderia.")
        filas = []
        for numero, fila in enumerate(lector, start=2):
            if not any(c.strip() for c in fila):
                continue  # una linea en blanco es un separador, no un dato
            if len(fila) != len(columnas):
                raise MidesInvalido(f"{ruta}:{numero}: tiene {len(fila)} campos y el encabezado {len(columnas)}")
            anio_texto, valor_texto = fila[-2].strip(), fila[-1].strip()
            if len(anio_texto) != 4 or not anio_texto.isdigit():
                raise MidesInvalido(f"{ruta}:{numero}: el año es {anio_texto!r} y la familia usa cuatro digitos")
            anio = int(anio_texto)
            if not ANIO_MINIMO <= anio <= ANIO_MAXIMO:
                raise MidesInvalido(f"{ruta}:{numero}: el año {anio} esta fuera de {ANIO_MINIMO}-{ANIO_MAXIMO}")
            if not valor_texto:
                raise MidesInvalido(
                    f"{ruta}:{numero}: el valor esta vacio. Un vacio es un nulo, no un cero, y en la "
                    "familia no hay ninguno: si aparece, la fuente cambio."
                )
            try:
                valor = float(valor_texto)
            except ValueError:
                raise MidesInvalido(f"{ruta}:{numero}: el valor {valor_texto!r} no es un numero") from None
            filas.append(
                {
                    "dimensiones": {n: v.strip() for n, v in zip(nombres, fila[:-2])},
                    "año": anio,
                    "valor": valor,
                }
            )
        return filas


def resumen(ruta: Path) -> dict:
    """El resumen de un indicador ya bajado, con su sello. **No sale a la red.**"""
    columnas = encabezado(ruta)
    filas = leer_archivo(ruta)
    valores = [f["valor"] for f in filas]
    anios = sorted({f["año"] for f in filas})
    return {
        "sello": procedencia.sello(f"MIDES {ruta.stem}", ruta=ruta, filas=len(filas)),
        "columnas": columnas,
        "dimensiones": dimensiones(columnas),
        "filas": len(filas),
        "filas_en_blanco": filas_en_blanco(ruta),
        "años": [anios[0], anios[-1]] if anios else [],
        "valor": {"min": min(valores), "max": max(valores)} if valores else None,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m uydatos.mides", description=__doc__.splitlines()[0])
    ordenes = p.add_subparsers(dest="orden", required=True)

    q = ordenes.add_parser("listar", help="los indicadores que publica el catalogo")
    q.add_argument("--desde", type=int, default=0, help="desde cual, para paginar")
    q.add_argument("--filas", type=int, default=20, help="cuantos listar (maximo 100)")

    q = ordenes.add_parser("bajar", help="el CSV de un indicador")
    q.add_argument("indicador", help="10745, mides-indicador-10745, o la URL del dataset")
    q.add_argument("destino", type=Path)

    q = ordenes.add_parser("ver", help="el resumen de un CSV ya bajado")
    q.add_argument("ruta", type=Path)

    args = p.parse_args(argv)
    try:
        if args.orden == "listar":
            r = indicadores(filas=args.filas, desde=args.desde)
            print(f"la organizacion {ORGANIZACION} declara {r['total']:,} datasets".replace(",", "."))
            print(f"de los {r['listados']} listados, {len(r['indicadores'])} son de la familia")
            for d in r["indicadores"]:
                print(f"  {d['nombre'][len(PREFIJO) :]:>6}  {d['titulo'][:70]}")
        elif args.orden == "bajar":
            nombre = numero_de_indicador(args.indicador)
            destino = descargar(nombre, args.destino)
            print(f"bajado {destino}")
            print(procedencia.como_linea(procedencia.sello(f"MIDES {nombre}", ruta=destino)))
        else:
            s = resumen(args.ruta)
            for clave, valor in s.items():
                if clave != "sello":  # el sello va al final, en su forma citable
                    print(f"{clave}: {valor}")
            print(procedencia.como_linea(s["sello"]))
    except MidesInvalido as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
