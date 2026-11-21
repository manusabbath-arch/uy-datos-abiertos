"""La unica salida a la red del paquete: `User-Agent`, timeout y reintentos en un lugar."""

from __future__ import annotations

import http.client
import urllib.error

import pytest

from uydatos import USER_AGENT, red


class _Respuesta:
    def __init__(self, datos: bytes):
        self._datos = datos

    def read(self) -> bytes:
        return self._datos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestUserAgentYTimeout:
    def test_toda_peticion_lleva_el_user_agent_del_paquete(self, monkeypatch):
        visto = {}

        def abrir(pedido, timeout):
            visto["ua"] = pedido.get_header("User-agent")
            visto["timeout"] = timeout
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert visto["ua"] == USER_AGENT
        assert visto["timeout"] == red.TIMEOUT

    def test_las_cabeceras_propias_ganan_sobre_la_del_paquete(self, monkeypatch):
        visto = {}

        def abrir(pedido, timeout):
            visto["ct"] = pedido.get_header("Content-type")
            return _Respuesta(b"")

        monkeypatch.setattr(red, "_abrir", abrir)
        red.pedir("https://ejemplo.uy/x", datos=b"<x/>", cabeceras={"Content-Type": "text/xml"})
        assert visto["ct"] == "text/xml"


class TestReintentos:
    def test_reintenta_un_error_de_red_y_termina_bien(self, monkeypatch):
        intentos = []

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) < 3:
                raise urllib.error.URLError("sin ruta al host")
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert len(intentos) == 3

    def test_un_404_no_se_reintenta(self, monkeypatch):
        intentos = []

        def abrir(pedido, timeout):
            intentos.append(1)
            raise urllib.error.HTTPError("https://ejemplo.uy/x", 404, "Not Found", {}, None)

        monkeypatch.setattr(red, "_abrir", abrir)
        with pytest.raises(OSError, match="404"):
            red.pedir("https://ejemplo.uy/x")
        assert len(intentos) == 1

    def test_si_se_agotan_los_intentos_el_error_dice_cuantos(self, monkeypatch):
        def abrir(pedido, timeout):
            raise urllib.error.URLError("sin ruta al host")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        with pytest.raises(OSError, match="3 intentos"):
            red.pedir("https://ejemplo.uy/x")

    def test_reintenta_una_lectura_truncada_y_termina_bien(self, monkeypatch):
        """Medido el 2026-11-16: el archivo de compras de 27 MB llego cortado a
        `mcp-uruguay` y el cron se cayo. `IncompleteRead` no es un `OSError`, asi
        que salia del bucle sin reintentar."""
        intentos = []

        class _Cortada(_Respuesta):
            def read(self) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) == 1:
                return _Cortada(b"")
            return _Respuesta(b"ok")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        assert red.pedir("https://ejemplo.uy/x") == b"ok"
        assert len(intentos) == 2

    def test_si_todas_las_lecturas_se_truncan_el_error_nombra_la_causa(self, monkeypatch):
        class _Cortada(_Respuesta):
            def read(self) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Cortada(b""))
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        with pytest.raises(OSError, match="IncompleteRead"):
            red.pedir("https://ejemplo.uy/x")


class TestBajar:
    def test_una_respuesta_vacia_no_se_escribe(self, monkeypatch, tmp_path):
        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Respuesta(b""))
        destino = tmp_path / "x.csv"
        with pytest.raises(OSError, match="vacia"):
            red.bajar("https://ejemplo.uy/x", destino)
        assert not destino.exists()

    def test_lo_bajado_se_escribe_tal_cual_vino(self, monkeypatch, tmp_path):
        monkeypatch.setattr(red, "_abrir", lambda pedido, timeout: _Respuesta(b"a;b\n1;2\n"))
        destino = red.bajar("https://ejemplo.uy/x", tmp_path / "sub" / "x.csv")
        assert destino.read_bytes() == b"a;b\n1;2\n"

    def test_un_archivo_cortado_se_rebaja_entero(self, monkeypatch, tmp_path):
        intentos = []

        class _Cortada(_Respuesta):
            def read(self) -> bytes:
                raise http.client.IncompleteRead(b"parcial", 10)

        def abrir(pedido, timeout):
            intentos.append(1)
            if len(intentos) == 1:
                return _Cortada(b"")
            return _Respuesta(b"a;b\n1;2\n")

        monkeypatch.setattr(red, "_abrir", abrir)
        monkeypatch.setattr(red.time, "sleep", lambda s: None)
        destino = red.bajar("https://ejemplo.uy/x", tmp_path / "compras.csv")
        assert destino.read_bytes() == b"a;b\n1;2\n"
