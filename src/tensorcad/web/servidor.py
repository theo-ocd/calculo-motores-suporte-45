"""Servidor HTTP local da interface (somente 127.0.0.1)."""

from __future__ import annotations

import json
import mimetypes
import socket
import threading
import webbrowser
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from tensorcad.web import api

ESTATICOS = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORTA_PADRAO = 8765

Rota = Callable[[api.Contexto], Any]
ROTAS_GET: dict[str, Rota] = {
    "/api/saude": api.saude,
    "/api/carcacas": api.carcacas,
    "/api/campos": api.campos,
    "/api/transmissao": api.transmissao,
}
RotaPost = Callable[[api.Contexto, Any], Any]
ROTAS_POST: dict[str, RotaPost] = {
    "/api/calcular": api.calcular,
    "/api/calcular_horizontal": api.calcular_horizontal,
    "/api/setup": api.setup,
    "/api/biblioteca": api.biblioteca,
}
RotaArquivo = Callable[[api.Contexto, Any], tuple[bytes, str]]
ROTAS_POST_ARQUIVO: dict[str, RotaArquivo] = {
    "/api/exportar": api.exportar,
}
MIME_ARQUIVO = {".xlsx": api.MIME_XLSX}
LIMITE_CORPO = 256 * 1024


class Manipulador(BaseHTTPRequestHandler):
    contexto: api.Contexto  # definido em criar_servidor
    server_version = "tensorcad"

    def log_message(self, formato: str, *args: Any) -> None:  # silencioso no console
        pass

    def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dados: Any) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(status, corpo, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho.startswith("/api/"):
            rota = ROTAS_GET.get(caminho)
            if rota is None:
                self._json(HTTPStatus.NOT_FOUND, {"erro": f"rota inexistente: {caminho}"})
                return
            try:
                self._json(HTTPStatus.OK, rota(self.contexto))
            except Exception as exc:  # erro inesperado vira JSON legível na página
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"erro": str(exc)})
            return
        self._estatico(caminho)

    def do_POST(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        rota = ROTAS_POST.get(caminho) or ROTAS_POST_ARQUIVO.get(caminho)
        if rota is None:
            self._json(HTTPStatus.NOT_FOUND, {"erro": f"rota inexistente: {caminho}"})
            return
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if not 0 <= tamanho <= LIMITE_CORPO:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"erro": "corpo inválido ou grande"})
            return
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"erro": "JSON inválido"})
            return
        try:
            if caminho in ROTAS_POST_ARQUIVO:
                conteudo, nome = rota(self.contexto, corpo)
                self._arquivo(conteudo, nome)
            else:
                self._json(HTTPStatus.OK, rota(self.contexto, corpo))
        except api.ErroEntrada as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"erro": "entradas inválidas", "erros": exc.erros})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"erro": str(exc)})

    def _arquivo(self, conteudo: bytes, nome: str) -> None:
        tipo = MIME_ARQUIVO.get(Path(nome).suffix.lower(), "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(conteudo)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(nome)}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(conteudo)

    def _estatico(self, caminho: str) -> None:
        nome = "index.html" if caminho in ("", "/") else caminho.lstrip("/")
        alvo = (ESTATICOS / nome).resolve()
        if ESTATICOS not in alvo.parents or not alvo.is_file():
            self._enviar(HTTPStatus.NOT_FOUND, b"nao encontrado", "text/plain; charset=utf-8")
            return
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
            tipo += "; charset=utf-8"
        self._enviar(HTTPStatus.OK, alvo.read_bytes(), tipo)


def porta_livre(preferida: int = PORTA_PADRAO) -> int:
    """A porta preferida se estiver livre; senão uma porta qualquer do sistema."""
    for porta in (preferida, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, porta))
            except OSError:
                continue
            return s.getsockname()[1]
    raise OSError("nenhuma porta livre")  # pragma: no cover


def criar_servidor(contexto: api.Contexto, porta: int = 0) -> ThreadingHTTPServer:
    manip = type("ManipuladorTensorcad", (Manipulador,), {"contexto": contexto})
    srv = ThreadingHTTPServer((HOST, porta), manip)
    srv.daemon_threads = True
    return srv


def url_de(srv: ThreadingHTTPServer) -> str:
    return f"http://{HOST}:{srv.server_address[1]}/"


def iniciar_em_thread(contexto: api.Contexto, porta: int = 0) -> ThreadingHTTPServer:
    """Sobe o servidor numa thread (testes); encerre com srv.shutdown()."""
    srv = criar_servidor(contexto, porta)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def executar(contexto: api.Contexto, porta: int | None = None, abrir: bool = True) -> None:
    """Bloqueia servindo a interface até Ctrl+C / fechar a janela."""
    srv = criar_servidor(contexto, porta_livre() if porta is None else porta)
    url = url_de(srv)
    print(f"tensorcad: interface em {url}")
    print("Mantenha esta janela aberta; feche-a (ou Ctrl+C) para encerrar.")
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
