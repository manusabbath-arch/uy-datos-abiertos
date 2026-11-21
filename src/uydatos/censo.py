"""Población del Censo 2023: los tabulados oficiales del INE, por departamento y por localidad.

La fuente
---------
El INE publica los tabulados de población del Censo 2023 como XLSX en
`https://www.gub.uy/instituto-nacional-estadistica/politicas-y-gestion/tabulados-hogares-poblacion-censo-2023`.
Este lector usa dos:

- **Cuadro 12** (`departamentos`): población, área (km²) y densidad por departamento, 19 filas.
- **Cuadro 13** (`localidades`): población por departamento y localidad, con el código INE de 5
  dígitos (2 del departamento y 3 de la localidad) y una fila `Total` arriba.

No están en el catálogo de datos abiertos: ahí solo hay indicadores del Censo 2011 (MIDES, medido el
2026-11-21 con `package_search`). La URL es de `www5.ine.gub.uy` y se mide a mano.

La medición (2026-11-21, hora de Montevideo)
--------------------------------------------
- Cuadro 13: 40.005 bytes, sha256 `220933b3720117e02942a1ea2ba9652f3024f8cc9d6303f6a841d515666b52cb`,
  674 filas en la hoja `Cuadro13_CAR`; `Total` 3.499.451.
- Cuadro 12: 13.704 bytes, sha256 `e1d366b9c36fd54d3554156f9b5530fdb730a6f773a9f6d25e21da5ce9c2aa16`,
  hoja `Cuadro12_CAR`, 19 departamentos.

Las trampas
-----------
1. **Son datos ponderados, y la capa cartográfica no.** El pie del cuadro 13 dice «Datos
   ponderados». La capa de localidades del INE (campo `pob_tot_23`, que lee `uydatos.limites`) trae
   otra cifra para la misma localidad: Salto, código 15120, 112.527 acá y 114.043 en la capa;
   Paysandú, 11120, 79.457 y 81.489. La cifra que el INE publica en sus infografías es la de estos
   cuadros.
2. **Las localidades no suman el departamento.** Sumar las filas del cuadro 13 de un departamento da
   un número que difiere en una o dos personas del cuadro 12 (Salto 136.197 contra 136.195; Paysandú
   121.837 contra 121.838): el redondeo de la ponderación. Para la población de un departamento se
   usa el cuadro 12, no la suma.
3. **El INE corrigió las cifras en mayo de 2026.** El comunicado de resultados finales decía
   Paysandú 121.843; el cuadro 12 vigente dice 121.838. Una cifra citada antes de esa fecha puede
   no coincidir: el sello de la copia (sha256 y fecha) dice cuál se leyó.
4. **Las filas que no son datos**: título, renglones vacíos, la fila `Total` y las notas al pie. Fila
   sin código = no es dato (se saltea); fila con código y fuera de contrato = se rechaza el archivo.
5. **`RURAL/PARAJE RURAL`** es una fila por departamento con código terminado en 900: población
   fuera de localidades, no una localidad. Se devuelve tal cual; quien la muestre debe decirlo.
6. **236 personas sin localidad van en filas con código `-`.** El pie dice «234 en situación de
   calle y 2 en hogares particulares»; están en dos filas `CANELONES - Sin dato localidad` (234) y
   `SAN JOSÉ - Sin dato localidad` (2), con `-` donde va el código. No son localidades: se
   excluyen de la salida, pero la fila `Total` (3.499.451) se compara con la suma de las
   localidades **más** esas filas, y el archivo se rechaza si no cierra.

El contrato
-----------
- `codigo`: texto de dígitos, 2 en el cuadro 12 y 5 en el 13; nunca repetido.
- `poblacion`: entero mayor o igual a cero. `area_km2`: número mayor que cero.
- Un encabezado distinto del medido es otro cuadro: se rechaza con `CensoInvalido`.

Uso:
    python -m uydatos censo bajar localidades c13.xlsx
    python -m uydatos censo ver localidades c13.xlsx SALTO
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from uydatos import hojas, red
from uydatos.errores import DatosInvalidos

BASE = "https://www5.ine.gub.uy/documents/CENSO%202023/Tabulados/Personas/"
URLS = {
    "departamentos": BASE + "Cuadro_12_CAR_2023.xlsx",
    "localidades": BASE + "Cuadro_13_CAR_2023.xlsx",
}
FUENTE = "INE, Censo 2023, tabulados de población (datos ponderados)"

ENCABEZADOS = {
    "departamentos": ("código localidad ine 2023", "departamento", "población total", "área (km2)"),
    "localidades": ("código localidad ine", "nombre departamento", "nombre localidad", "población total"),
}


class CensoInvalido(DatosInvalidos):
    """Un tabulado del censo que no tiene la forma medida."""


def _texto(valor) -> str:
    return " ".join(str(valor).split()).strip() if valor is not None else ""


def _filas_de_dato(ruta: Path, cuadro: str, digitos: int) -> list[list]:
    filas = hojas.leer(ruta)
    esperado = ENCABEZADOS[cuadro]
    inicio = next(
        (i for i, f in enumerate(filas) if tuple(_texto(c).lower() for c in f[: len(esperado)]) == esperado),
        None,
    )
    if inicio is None:
        raise CensoInvalido(f"{ruta.name}: no aparece el encabezado del cuadro de {cuadro} ({esperado})")
    datos, codigos = [], set()
    for f in filas[inicio + 1 :]:
        codigo = _texto(f[0]) if f else ""
        if not codigo.isdigit():
            continue  # renglón vacío, fila Total, nota al pie o «Sin dato localidad» (código «-»)
        if len(codigo) != digitos:
            raise CensoInvalido(f"{ruta.name}: código {codigo!r} no tiene {digitos} dígitos")
        if codigo in codigos:
            raise CensoInvalido(f"{ruta.name}: código {codigo} repetido")
        codigos.add(codigo)
        datos.append(f)
    if not datos:
        raise CensoInvalido(f"{ruta.name}: ninguna fila de dato debajo del encabezado")
    return datos


def _poblacion(valor, codigo: str, ruta: Path) -> int:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0 or valor != int(valor):
        raise CensoInvalido(f"{ruta.name}: código {codigo}: población {valor!r} no es un entero no negativo")
    return int(valor)


def leer_departamentos(ruta: Path) -> list[dict]:
    """Cuadro 12: `codigo` (2 dígitos), `departamento`, `poblacion`, `area_km2`."""
    salida = []
    for f in _filas_de_dato(Path(ruta), "departamentos", 2):
        codigo = _texto(f[0])
        area = f[3]
        if isinstance(area, bool) or not isinstance(area, (int, float)) or area <= 0:
            raise CensoInvalido(f"{Path(ruta).name}: código {codigo}: área {area!r} no es positiva")
        salida.append(
            {
                "codigo": codigo,
                "departamento": _texto(f[1]),
                "poblacion": _poblacion(f[2], codigo, Path(ruta)),
                "area_km2": area,
            }
        )
    return salida


def leer_localidades(ruta: Path) -> list[dict]:
    """Cuadro 13: `codigo` (5 dígitos), `departamento`, `localidad`, `poblacion`.

    Las filas «Sin dato localidad» (código `-`) no se devuelven. Rechaza el archivo si la fila `Total`
    no es la suma de las localidades más esas filas."""
    ruta = Path(ruta)
    salida = [
        {
            "codigo": _texto(f[0]),
            "departamento": _texto(f[1]),
            "localidad": _texto(f[2]),
            "poblacion": _poblacion(f[3], _texto(f[0]), ruta),
        }
        for f in _filas_de_dato(ruta, "localidades", 5)
    ]
    filas = hojas.leer(ruta)
    total = next((f[3] for f in filas if f and _texto(f[0]).lower() == "total"), None)
    sin_localidad = sum(
        _poblacion(f[3], "-", ruta) for f in filas if f and _texto(f[0]) == "-" and "sin dato" in _texto(f[2]).lower()
    )
    suma = sum(f["poblacion"] for f in salida)
    if total is not None and total != suma + sin_localidad:
        raise CensoInvalido(
            f"{ruta.name}: la fila total dice {total} y las localidades suman {suma} "
            f"(más {sin_localidad} sin dato de localidad)"
        )
    return salida


def descargar(cuadro: str, destino: Path) -> Path:
    if cuadro not in URLS:
        raise ValueError(f"cuadro {cuadro!r}: hay {', '.join(URLS)}")
    return red.bajar(URLS[cuadro], Path(destino))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos censo", description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="accion", required=True)
    b = sub.add_parser("bajar", help="baja un cuadro")
    b.add_argument("cuadro", choices=sorted(URLS))
    b.add_argument("destino", type=Path)
    v = sub.add_parser("ver", help="lee un cuadro bajado")
    v.add_argument("cuadro", choices=sorted(URLS))
    v.add_argument("ruta", type=Path)
    v.add_argument("filtro", nargs="?", default="", help="parte del nombre del departamento o la localidad")
    args = ap.parse_args(argv)
    if args.accion == "bajar":
        print(descargar(args.cuadro, args.destino))
        return 0
    leer = leer_departamentos if args.cuadro == "departamentos" else leer_localidades
    try:
        filas = leer(args.ruta)
    except DatosInvalidos as e:
        print(e, file=sys.stderr)
        return 1
    filtro = args.filtro.upper()
    for f in filas:
        if filtro in " ".join(str(v) for v in f.values()).upper():
            print("\t".join(str(v) for v in f.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
