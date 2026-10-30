import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tensorcad.cli import app
from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.web import api, servidor

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data"


@pytest.fixture(scope="module")
def contexto() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS), carregar_padroes(DADOS / "padrao"), DADOS, DADOS / "padrao"
    )


@pytest.fixture(scope="module")
def url(contexto):
    srv = servidor.iniciar_em_thread(contexto)
    yield servidor.url_de(srv)
    srv.shutdown()
    srv.server_close()


def _get(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def test_api_saude(contexto) -> None:
    s = api.saude(contexto)
    assert s["status"] == "ok" and s["dados"] == str(DADOS) and s["avisos"] > 0


def test_api_carcacas_status(contexto) -> None:
    lista = {c["carcaca"]: c for c in api.carcacas(contexto)}
    assert list(lista) == ["160", "180", "200", "225", "250"]
    c180 = lista["180"]
    assert c180["status"] == "parcial" and c180["calculavel"] and c180["chapa"] == "CH-180"
    assert "origem CALCULADO" in c180["detalhe"] and "comprimento das ranhuras" in c180["detalhe"]
    assert [m["carcaca"] for m in c180["motores"]] == ["180L", "180M"]
    for n in ("160", "200", "225", "250"):
        assert lista[n]["status"] == "a_preencher" and not lista[n]["calculavel"]


def test_status_completa_e_sem_chapa(tmp_path: Path) -> None:
    (tmp_path / "chapas_carcaca.csv").write_text(
        "carcaca;theta_deg;e_apoio;comprimento_chapa;dx_L_tubo;dy_L_tubo;dist_L_ranhura;"
        "comprimento_ranhura;dist_entre_ranhuras;dist_ranhura_topo;largura_ranhura;origem;"
        "observacao\n200;45;0;700;380;45;150;150;150;100;20;MEDIDO;\n",
        encoding="utf-8",
    )
    ctx = api.Contexto(carregar_diretorio(DADOS), carregar_padroes(tmp_path), DADOS, tmp_path)
    lista = {c["carcaca"]: c for c in api.carcacas(ctx)}
    assert lista["200"]["status"] == "completa"
    assert lista["180"]["status"] == "sem_chapa" and not lista["180"]["calculavel"]


def test_servidor_rotas(url: str) -> None:
    st, tipo, corpo = _get(url + "api/saude")
    assert st == 200 and tipo.startswith("application/json")
    assert json.loads(corpo)["status"] == "ok"
    st, _, corpo = _get(url + "api/carcacas")
    assert st == 200 and len(json.loads(corpo)) == 5
    st, _, corpo = _get(url + "api/nada")
    assert st == 404 and "rota inexistente" in json.loads(corpo)["erro"]


def test_servidor_estaticos(url: str) -> None:
    st, tipo, corpo = _get(url)
    assert st == 200 and tipo.startswith("text/html") and b"tensorcad" in corpo
    for arq, mime in (("estilo.css", "text/css"), ("app.js", "javascript")):
        st, tipo, _ = _get(url + arq)
        assert st == 200 and mime in tipo
    assert _get(url + "nao-existe.js")[0] == 404
    assert _get(url + "..%2f..%2fpyproject.toml")[0] == 404
    assert _get(url + "../../pyproject.toml")[0] == 404


def test_erro_interno_vira_json(contexto, monkeypatch) -> None:
    def falha(_ctx):
        raise RuntimeError("explodiu")

    monkeypatch.setitem(servidor.ROTAS_GET, "/api/falha", falha)
    srv = servidor.iniciar_em_thread(contexto)
    try:
        st, _, corpo = _get(servidor.url_de(srv) + "api/falha")
    finally:
        srv.shutdown()
        srv.server_close()
    assert st == 500 and json.loads(corpo)["erro"] == "explodiu"


def test_porta_livre_preferida_e_ocupada() -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        ocupada = s.getsockname()[1]
        assert servidor.porta_livre(ocupada) != ocupada
    livre = servidor.porta_livre(0)
    assert livre > 0


def test_cli_web_e_padrao_sem_argumentos(monkeypatch) -> None:
    chamadas = []
    monkeypatch.setattr(
        servidor, "executar", lambda ctx, porta=None, abrir=True: chamadas.append((porta, abrir))
    )
    runner = CliRunner()
    assert runner.invoke(app, ["web", "--porta", "9001", "--sem-navegador"]).exit_code == 0
    assert runner.invoke(app, []).exit_code == 0
    assert chamadas == [(9001, False), (None, True)]


def test_executar_abre_navegador_e_encerra(contexto, monkeypatch, capsys) -> None:
    abertos = []
    monkeypatch.setattr(servidor.webbrowser, "open", abertos.append)

    def parar(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(servidor.ThreadingHTTPServer, "serve_forever", parar)
    servidor.executar(contexto, porta=0)
    assert abertos and abertos[0].startswith("http://127.0.0.1:")
    assert "interface em" in capsys.readouterr().out


# ----------------------------------------------------------------- navegador (Playwright)


def _navegador(p):
    exe = os.environ.get("TENSORCAD_CHROMIUM") or (
        "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
    )
    try:
        return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    except Exception as exc:
        if os.environ.get("TENSORCAD_EXIGIR_NAVEGADOR"):
            pytest.fail(f"navegador exigido mas indisponível: {exc}")
        pytest.skip(f"navegador indisponível: {exc}")


def test_pagina_carrega_no_navegador(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page()
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            assert pg.title() == "tensorcad"
            assert pg.locator("#lista-carcacas li").count() == 5
            chip = pg.locator("#lista-carcacas li[data-carcaca='180'] .chip")
            assert chip.get_attribute("data-status") == "parcial"
            assert pg.locator("#carcaca").input_value() == "180"
            assert pg.locator("#carcaca option[value='200']").is_disabled()
            fundo = pg.evaluate("getComputedStyle(document.body).backgroundColor")
            assert fundo == "rgb(17, 25, 29)"  # --bg (tema escuro)
            assert erros == []
        finally:
            nav.close()
