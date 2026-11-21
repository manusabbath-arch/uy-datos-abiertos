"""Una sola forma de salir a la red: `User-Agent`, timeout y reintentos, en un lugar.

Los lectores no llaman a `urllib` directamente. Motivo medido el 2026-10-09: `bcu.descargar()`
mandaba `Content-Type` y `SOAPAction` pero **ningun `User-Agent`**, y los timeouts iban de 60 a 90
segundos segun el archivo. Un servidor que bloquee `Python-urllib` bloqueaba una fuente y no las
 otras, sin que nada lo dijera.

    python -m uydatos.red https://catalogodatos.gub.uy/api/3/action/package_list
"""

from __future__ import annotations

import argparse
import http.client
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Sequence

from uydatos import USER_AGENT

TIMEOUT = 60
TIMEOUT_DESCARGA = 180
INTENTOS = 3
ESPERA = 2.0
CHUNK = 64 * 1024  # el pico de una bajada: un trozo mas el buffer, nunca el archivo entero


def _abrir(pedido: urllib.request.Request, timeout: int):
    """La unica llamada de red del paquete. Los tests la reemplazan con `monkeypatch`."""
    return urllib.request.urlopen(pedido, timeout=timeout)  # noqa: S310 - la URL la fija el lector


def pedido(
    url: str,
    *,
    datos: Optional[bytes] = None,
    cabeceras: Optional[dict[str, str]] = None,
) -> urllib.request.Request:
    """El `Request` con el `User-Agent` del paquete, sin salir a la red.

    Lo usan los lectores que necesitan el objeto armado (los tests miran su `User-Agent`); quien
    sale de verdad es `pedir()`.
    """
    return urllib.request.Request(url, data=datos, headers={"User-Agent": USER_AGENT, **(cabeceras or {})})


def codificar(params: dict[str, str]) -> str:
    """El query string de `params`, como lo espera una URL. No sale a la red.

    Vive acá para que ningun lector le hable a `urllib` ni para armar la dirección.
    """
    return urllib.parse.urlencode(params)


def _con_reintentos(lo_que_intenta, url: str):
    """El bucle comun de reintentos: `lo_que_intenta()` consume la respuesta.

    Un 4xx **no** se reintenta: la URL o el recurso estan mal y esperar no los arregla. Todo lo
    demas (5xx, DNS, corte de conexion, lectura truncada) se reintenta con una espera creciente.
    `http.client.HTTPException` (la lectura truncada, `IncompleteRead`) **no** hereda de `OSError`
    y se atrapa aparte: el 2026-11-16 tumbo el cron de `mcp-uruguay` con el archivo de compras de
    27 MB. El mensaje final incluye `ultimo`, asi que nombra la causa.
    """
    ultimo: Optional[Exception] = None
    for intento in range(INTENTOS):
        if intento:
            time.sleep(ESPERA * intento)
        try:
            return lo_que_intenta()
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise OSError(f"{url}: el servidor respondio {e.code} {e.reason}") from e
            ultimo = e
        except OSError as e:
            ultimo = e
        except http.client.HTTPException as e:
            ultimo = e
    raise OSError(f"{url}: {ultimo} (tras {INTENTOS} intentos)")


def pedir(
    url: str,
    *,
    datos: Optional[bytes] = None,
    cabeceras: Optional[dict[str, str]] = None,
    timeout: int = TIMEOUT,
) -> bytes:
    """Devuelve el cuerpo de la respuesta. Reintenta lo que puede mejorar solo (ver `_con_reintentos`)."""
    req = pedido(url, datos=datos, cabeceras=cabeceras)

    def lo_pide() -> bytes:
        with _abrir(req, timeout) as r:
            return r.read()

    return _con_reintentos(lo_pide, url)


def bajar(url: str, destino: Path, *, timeout: int = TIMEOUT_DESCARGA) -> Path:
    """Baja a `destino`, creando las carpetas que falten. **Una respuesta vacia no se escribe.**

    El cuerpo se escribe en trozos a un temporal en la misma carpeta, y el temporal se publica
    con `os.replace` solo si la bajada salio entera: nunca queda un `destino` parcial (el corte
    del 2026-11-16 no debe dejar un archivo que parezca bueno) y el pico de memoria es un trozo,
    no el archivo. Medido el 2026-11-21 con un cuerpo de 27 MB: `pedir` pica 27.1 MiB y `bajar`
    134 KB (207x menos). `pedir` mantiene su pico: su contrato devuelve el cuerpo entero.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # El temporal lleva sufijo propio: con un nombre fijo (`.<archivo>.parcial`), dos bajadas del
    # mismo destino a la vez escriben el mismo archivo y una publica la copia mezclada de las dos.
    parcial = destino.parent / f".{destino.name}.{secrets.token_hex(4)}.parcial"

    def lo_baja() -> int:
        total = 0
        with _abrir(pedido(url), timeout=timeout) as r, open(parcial, "wb") as f:
            while trozo := r.read(CHUNK):
                f.write(trozo)
                total += len(trozo)
        return total

    try:
        total = _con_reintentos(lo_baja, url)
    except OSError:
        parcial.unlink(missing_ok=True)
        raise
    if not total:
        parcial.unlink(missing_ok=True)
        raise OSError(f"{url}: la respuesta vino vacia; no se escribio nada")
    try:
        os.replace(parcial, destino)
    except OSError:
        parcial.unlink(missing_ok=True)
        raise
    return destino


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uydatos.red", description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("-o", "--salida", type=Path)
    args = ap.parse_args(argv)
    if args.salida:
        print(bajar(args.url, args.salida))
    else:
        sys.stdout.buffer.write(pedir(args.url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
