"""Las trampas declaradas, reproducidas: la tesis del paquete como guarda.

Cada fuente de este paquete se documenta con al menos una trampa que **no da error** y produce una
serie creíble pero falsa. La tabla del README las declara; acá se reproducen sobre un archivo armado
con `tmp_path`, y se exige que el lector haga lo que el docstring dice.

Las dos mitades importan:

- **`TRAMPAS`**: el archivo roto tiene que ser rechazado, o la fila salteada y contada.
- **`VALIDOS`**: el archivo bueno **tiene que pasar**. Medido el 09/10/26, un `inumet` que rechazaba
  los archivos reales enteros pasaba sus 23 tests de unidad: ese es el rojo que este archivo existe
  para atrapar, y no lo atrapa ningún test escrito desde el lector.

No sale a la red: los archivos se arman acá.

    pytest -q tests/test_trampas.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from uydatos import hojas
from uydatos.ancap import AncapInvalido, leer_publicaciones
from uydatos.bcu import BcuInvalido, leer_crudo
from uydatos.inumet import InumetInvalido, filas_sin_dato, leer_archivo


@dataclass(frozen=True)
class Trampa:
    """Una trampa declarada: cómo se arma el archivo roto, y qué tiene que hacer el lector."""

    nombre: str
    escribir: Callable[[Path], Path]
    afirmar: Callable[[Path], None]


@dataclass(frozen=True)
class Valido:
    """La mitad inversa: el archivo bueno de un lector, y la función que lo lee."""

    nombre: str
    escribir: Callable[[Path], Path]
    leer: Callable[[Path], object]


# --- ANCAP: el encabezado dice Unidad y Valor, y están invertidas (medido el 04/10/26) ---


def _ancap(p: Path, filas: list[str]) -> Path:
    """El archivo real trae **dos** BOM, así que `utf-8-sig` no alcanza (medido el 04/10/26)."""
    p.write_text("\ufeff\ufeffAño;Mes;Producto;Unidad;Valor\n" + "\n".join(filas) + "\n", encoding="utf-8-sig")
    return p


def _ancap_bueno(p: Path) -> Path:
    return _ancap(p / "a.csv", ["2026;7;GASOIL 50-S *;58,68;$/lt", "2026;6;GASOIL 50-S *;57,10;$/lt"])


# --- INUMET: la columna de la estación puede traer el texto de un error (medido el 09/10/26) ---


def _inumet(p: Path, filas: list[str], nombre: str = "t.csv") -> Path:
    p = p / nombre
    p.write_text("\n".join(["fecha;estacion_id;temp_aire", *filas]) + "\n", encoding="utf-8")
    return p


def _inumet_bueno(p: Path) -> Path:
    return _inumet(p, ["2026-10-01 00:00;Salto G3;20.0", "2026-10-01 01:00;Salto G3;19.5"])


# --- BCU: una respuesta de error se guarda igual y parece un mes sin cotización ---


def _bcu_xml(datos: list[tuple[str, int, float]], status: int = 1, codigo: int = 0) -> str:
    filas = "".join(
        f'<datoscotizaciones.dato xmlns="Cotiza"><Fecha>{f}</Fecha><Moneda>{m}</Moneda>'
        f"<Nombre>X</Nombre><CodigoISO>X</CodigoISO><Emisor>X</Emisor>"
        f"<TCC>{v:.6f}</TCC><TCV>{v:.6f}</TCV><ArbAct>1</ArbAct><FormaArbitrar>0</FormaArbitrar>"
        f"</datoscotizaciones.dato>"
        for f, m, v in datos
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
        '<wsbcucotizaciones.ExecuteResponse xmlns="Cotiza"><Salida xmlns="Cotiza">'
        f"<respuestastatus><status>{status}</status><codigoerror>{codigo}</codigoerror><mensaje/></respuestastatus>"
        f"<datoscotizaciones>{filas}</datoscotizaciones>"
        "</Salida></wsbcucotizaciones.ExecuteResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )


def _bcu_bueno(p: Path) -> Path:
    p = p / "9800_2026-10.xml"
    p.write_text(_bcu_xml([("2026-10-01", 9800, 6.5432)]), encoding="utf-8")
    return p


# --- Las trampas: la aserción va adentro de `escribir`, así cada caso se lee como una frase ---


def _ancap_doble_bom(p: Path) -> Path:
    ruta = _ancap(p / "a.csv", ["2026;7;GASOIL 50-S *;58,68;$/lt"])
    assert leer_publicaciones(ruta)[0]["precio"] == pytest.approx(58.68)
    return ruta


def _ancap_invertidas(p: Path) -> Path:
    ruta = _ancap(p / "a.csv", ["2026;7;GASOIL 50-S *;$/lt;58,68"])
    with pytest.raises(AncapInvalido, match="invirtió las columnas"):
        leer_publicaciones(ruta)
    return ruta


def _inumet_error_sin_fecha(p: Path) -> Path:
    ruta = _inumet(p, ["; please try again later.;", "2026-10-01 00:00;Salto G3;20.0"])
    assert filas_sin_dato(ruta) == 1
    assert len(leer_archivo(ruta, ("temp_aire",))) == 1
    return ruta


def _inumet_estacion_fantasma(p: Path) -> Path:
    ruta = _inumet(p, ["2026-10-01 00:00;Estacion Fantasma;20.0"])
    with pytest.raises(InumetInvalido, match="estación desconocida"):
        leer_archivo(ruta, ("temp_aire",))
    return ruta


def _bcu_respuesta_mala(p: Path) -> Path:
    ruta = p / "9800_2026-10.xml"
    ruta.write_text(_bcu_xml([], status=2, codigo=1), encoding="utf-8")
    with pytest.raises(BcuInvalido, match="respuesta mala"):
        leer_crudo(ruta, 9800)
    return ruta


def _hojas_xlsx_con_extension_xls(p: Path) -> Path:
    """El `formato` del catálogo miente 23 de 24 veces: el motor sale de la firma, no de la
    extensión. openpyxl, en cambio, se fía de la extensión: hay que pasarle el archivo abierto."""
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    assert hoja is not None
    hoja.append(["a", "b"])
    hoja.append([1, 2])
    ruta = p / "mentira.xls"
    libro.save(ruta)
    assert hojas.leer(ruta)[0] == ["a", "b"]
    return ruta


TRAMPAS = [
    Trampa("ancap: el archivo trae dos BOM y se lee igual", _ancap_doble_bom, lambda p: None),
    Trampa("ancap: si Valor trae un número se rechaza", _ancap_invertidas, lambda p: None),
    Trampa(
        "inumet: una fila con el error del servidor se saltea y se cuenta",
        _inumet_error_sin_fecha,
        lambda p: None,
    ),
    Trampa("inumet: una estación que no está declarada se rechaza", _inumet_estacion_fantasma, lambda p: None),
    Trampa("bcu: una respuesta de error no se lee como mes sin cotización", _bcu_respuesta_mala, lambda p: None),
    Trampa("hojas: un XLSX con extensión .xls se lee igual", _hojas_xlsx_con_extension_xls, lambda p: None),
]

VALIDOS = [
    Valido("ancap: el archivo bueno se lee", _ancap_bueno, leer_publicaciones),
    Valido("inumet: el archivo bueno se lee", _inumet_bueno, lambda p: leer_archivo(p, ("temp_aire",))),
    Valido("bcu: el archivo bueno se lee", _bcu_bueno, lambda p: leer_crudo(p, 9800)),
]


@pytest.mark.parametrize("caso", TRAMPAS, ids=[c.nombre for c in TRAMPAS])
def test_la_trampa_declarada(caso: Trampa, tmp_path: Path):
    caso.afirmar(caso.escribir(tmp_path))


@pytest.mark.parametrize("caso", VALIDOS, ids=[c.nombre for c in VALIDOS])
def test_el_archivo_valido_pasa(caso: Valido, tmp_path: Path):
    """Sin esto, un lector que rechaza todo pasa las doscientas guardas de rechazo."""
    resultado = caso.leer(caso.escribir(tmp_path))
    assert resultado, f"{caso.nombre}: leyó cero filas"
