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
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
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
    assert c180["status"] == api.OK and c180["calculavel"] and c180["chapa"] == "CH-180"
    assert c180["detalhe"] == "medidas completas (largura da ranhura não informada)"
    assert [m["carcaca"] for m in c180["motores"]] == ["180L", "180M"]
    for n in ("160", "200", "225", "250"):
        assert lista[n]["status"] == api.ERRO and not lista[n]["calculavel"]
        assert "a preencher" in lista[n]["detalhe"]


def test_status_completa_e_sem_chapa(tmp_path: Path) -> None:
    (tmp_path / "chapas_carcaca.csv").write_text(
        "carcaca;theta_deg;e_apoio;comprimento_chapa;dx_L_tubo;dy_L_tubo;dist_L_ranhura;"
        "comprimento_ranhura;dist_entre_ranhuras;dist_ranhura_topo;largura_ranhura;origem;"
        "observacao\n200;45;0;700;380;45;150;150;150;100;20;MEDIDO;\n",
        encoding="utf-8",
    )
    ctx = api.Contexto(carregar_diretorio(DADOS), carregar_padroes(tmp_path), DADOS, tmp_path)
    lista = {c["carcaca"]: c for c in api.carcacas(ctx)}
    assert lista["200"]["status"] == api.OK
    assert lista["180"]["status"] == api.ERRO and "ausente" in lista["180"]["detalhe"]


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
            assert chip.get_attribute("data-status") == "ok"
            assert (
                pg.locator("#lista-carcacas li[data-carcaca='200'] .chip").get_attribute(
                    "data-status"
                )
                == "erro"
            )
            assert pg.locator("#carcaca").input_value() == "180"
            assert pg.locator("#carcaca option[value='200']").is_disabled()
            fundo = pg.evaluate("getComputedStyle(document.body).backgroundColor")
            assert fundo == "rgb(17, 25, 29)"  # --bg (tema escuro)
            assert erros == []
        finally:
            nav.close()


def test_calculo_ao_vivo_no_navegador(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page()
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            assert pg.inner_text("#fixo-x-tubo") == "465"
            assert pg.inner_text("#fixo-y-piso") == "767"
            assert pg.locator("#fixo-x-tubo").evaluate("e => e.tagName") == "DD"  # não editável
            assert pg.locator("#carcaca").get_attribute("data-status") == "ok"
            assert pg.locator("#motor_id option").count() == 2

            # REF-180: inviável, cota informada 1646
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.fill("#cota", "1646")
            pg.wait_for_selector("#status[data-status='OK']", timeout=10_000)
            resumo = pg.inner_text("#resumo")
            assert "1.606,55 a 1.661,47" in resumo and "1.634,32" in resumo and "28,56" in resumo
            linhas = pg.locator("#posicoes tbody tr")
            assert linhas.count() == 4
            inf0 = linhas.nth(2).inner_text()
            assert "380,70" in inf0 and "16,30" in inf0
            assert "40,64" in linhas.nth(3).inner_text()  # base a 3 % (41 no desenho)

            # ALT-2110 com o motor 180M, sem cota: viável
            pg.select_option("#motor_id", "IEC-180M-4P")
            pg.fill("#cota", "")
            pg.fill("#R_max", "2110,0")
            pg.wait_for_function(
                "document.getElementById('resumo').textContent.includes('1.551,88')",
                timeout=10_000,
            )
            resumo = pg.inner_text("#resumo")
            assert "1.551,88 a 1.661,47" in resumo and "1.607,26" in resumo
            assert pg.locator("#posicoes tbody tr").count() == 2
            assert "IEC-180M-4P" in pg.inner_text("#chapa-info")

            # erro por campo
            pg.fill("#R_min", "2200")
            pg.wait_for_selector(".campo[data-campo='R_max'].invalido", timeout=10_000)
            assert "maior ou igual" in pg.inner_text(".campo[data-campo='R_max'] .erro-campo")

            # carcaças com ERRO não podem ser escolhidas
            assert pg.locator("#carcaca option[value='200']").is_disabled()
            pg.click("#lista-carcacas li[data-carcaca='200']")
            assert pg.locator("#carcaca").input_value() == "180"
            assert erros == []
        finally:
            nav.close()


def test_desenho_interativo_no_navegador(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page(viewport={"width": 1500, "height": 900})
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            assert pg.locator("#aviso-desenho").is_visible()
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.fill("#cota", "1646")
            pg.wait_for_selector("#el-motor-0", timeout=10_000)
            assert not pg.locator("#aviso-desenho").is_visible()
            assert "H = 1.646,00 (informada)" in pg.inner_text("#info-desenho")

            # elementos e posição do centro do motor (SVG: x = X, y = −Y)
            for id_ in (
                "O",
                "arco-R_min",
                "arco-R_max",
                "piso",
                "tubo",
                "chapa",
                "L",
                "ranhura-1",
                "ranhura-2",
                "motor-3",
                "cota-H",
                "cota-h",
            ):
                assert pg.locator(f"#el-{id_}").count() == 1, id_
            cx = float(pg.get_attribute("#el-centro-0", "cx"))
            cy = float(pg.get_attribute("#el-centro-0", "cy"))
            assert (cx, cy) == pytest.approx((-681.53, 1971.53), abs=0.01)
            assert pg.get_attribute("#el-motor-3", "data-status") == "OK"
            assert "H = 1646.00" in pg.text_content("#mundo [data-camada='cotas']")

            # camadas
            pg.uncheck(".ferramentas input[data-camada='motor']")
            assert not pg.locator("#el-motor-0").is_visible()
            pg.check(".ferramentas input[data-camada='motor']")
            assert pg.locator("#el-motor-0").is_visible()

            # zoom e ajustar
            vb0 = pg.get_attribute("#desenho", "viewBox")
            w0 = float(vb0.split()[2])
            caixa = pg.locator("#desenho").bounding_box()
            pg.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
            pg.mouse.wheel(0, -400)
            pg.wait_for_function(f"document.getElementById('desenho').viewBox.baseVal.width < {w0}")
            pg.click("#btn-ajustar")
            assert float(pg.get_attribute("#desenho", "viewBox").split()[2]) == pytest.approx(w0)

            # coordenadas do cursor e dica ao passar o mouse
            m = pg.locator("#el-centro-0").bounding_box()
            pg.mouse.move(m["x"] + m["width"] / 2, m["y"] + m["height"] / 2)
            assert "X -681," in pg.inner_text("#cursor-xy")
            pg.wait_for_selector("#dica-desenho:not([hidden])")
            assert "centro do motor 0 %" in pg.inner_text("#dica-desenho")

            # sem H informada: desenha na recomendada
            pg.fill("#cota", "")
            pg.wait_for_function(
                "document.getElementById('info-desenho').textContent.includes('recomendada')"
            )
            assert "1.634,32" in pg.inner_text("#info-desenho")
            assert erros == []
        finally:
            nav.close()


def test_dimensoes_editaveis_no_navegador(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page(viewport={"width": 1500, "height": 1000})
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.fill("#cota", "1646")
            pg.wait_for_selector("#el-motor-0", timeout=10_000)

            # padrão da carcaça 180 carregado; x do tubo e piso não aparecem como editáveis
            assert pg.input_value("#dim-chapa-dist_L_ranhura") == "110"
            assert pg.input_value("#dim-motor-A") == "279"
            assert pg.locator("#dim-chapa-x_tubo").count() == 0
            assert "= 635,0 ✓" in pg.inner_text("#soma-cotas")
            assert pg.locator(".dim.alterado").count() == 0
            assert pg.locator("#btn-restaurar-tudo").is_disabled()

            # soma que não fecha: aviso na soma e erro do servidor no painel
            pg.fill("#dim-chapa-dist_L_ranhura", "130")
            pg.wait_for_selector("#soma-cotas.erro")
            pg.wait_for_function(
                "document.getElementById('erro-dimensoes').textContent.includes('não fecham')"
            )
            # fecha a soma reduzindo o vão: recalcula com o ajuste
            pg.fill("#dim-chapa-dist_entre_ranhuras", "104")
            pg.wait_for_selector("#soma-cotas.ok")
            pg.wait_for_function(
                "document.getElementById('resumo').textContent.includes('1.643,92')"
            )
            assert pg.locator(".dim.alterado").count() == 2
            assert "2 alteradas" in pg.inner_text("#contagem-ajustes")
            inf3 = pg.locator("#posicoes tbody tr").nth(3).inner_text()
            assert "20,64" in inf3  # base a 3 %: 40,64 − 20

            # restaurar um campo e depois tudo
            pg.click(".dim[data-nome='dist_entre_ranhuras'] .restaurar")
            assert pg.input_value("#dim-chapa-dist_entre_ranhuras") == "124"
            assert pg.locator(".dim.alterado").count() == 1
            pg.fill("#dim-motor-A", "289")
            pg.click("#btn-restaurar-tudo")
            assert pg.locator(".dim.alterado").count() == 0
            pg.wait_for_function(
                "document.getElementById('resumo').textContent.includes('1.634,32')"
            )
            assert pg.input_value("#dim-motor-A") == "279"
            assert erros == []
        finally:
            nav.close()
