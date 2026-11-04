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
                "O1",
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


def test_projeto_varios_casos_json_e_xlsx(url: str, tmp_path: Path) -> None:
    import io
    import json

    from openpyxl import load_workbook

    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            contexto = nav.new_context(
                accept_downloads=True, viewport={"width": 1500, "height": 1000}
            )
            pg = contexto.new_page()
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            dialogos: list[str] = []
            aceitar = {"sim": True}

            def responder(d) -> None:
                dialogos.append(d.message)
                d.accept() if aceitar["sim"] else d.dismiss()

            pg.on("dialog", responder)
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            assert pg.locator("#lista-casos li").count() == 1

            # caso 1
            pg.fill("#nome-projeto", "Obra Teste")
            pg.fill("#cota", "1646")
            pg.fill("#caso_id", "REF")
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.wait_for_selector("#lista-casos li.ativo .ponto[data-status='OK']", timeout=10_000)

            # caso 2 com motor 180M e ajuste do A
            pg.click("#btn-caso-novo")
            assert pg.locator("#lista-casos li").count() == 2
            assert pg.input_value("#R_min") == ""
            pg.fill("#caso_id", "ALT")
            pg.select_option("#motor_id", "IEC-180M-4P")
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2110")
            pg.fill("#dim-motor-A", "289")
            pg.wait_for_function(
                "document.querySelectorAll('#lista-casos .ponto[data-status=\"OK\"]').length === 2"
            )

            # nome repetido é apontado no campo
            pg.fill("#caso_id", "ref")
            pg.wait_for_selector(".campo[data-campo='caso_id'].invalido", timeout=10_000)
            pg.fill("#caso_id", "ALT")

            # voltar ao caso 1 carrega os valores dele; ao 2, o ajuste
            pg.click("#lista-casos li[data-indice='0']")
            assert pg.input_value("#caso_id") == "REF" and pg.input_value("#R_max") == "2161"
            assert pg.locator(".dim.alterado").count() == 0
            pg.click("#lista-casos li[data-indice='1']")
            assert pg.input_value("#motor_id") == "IEC-180M-4P"
            assert pg.input_value("#dim-motor-A") == "289"
            assert pg.locator(".dim.alterado").count() == 1

            # duplicar e excluir
            pg.click("#btn-caso-duplicar")
            assert pg.input_value("#caso_id") == "ALT-copia"
            assert pg.locator("#lista-casos li").count() == 3
            pg.click("#btn-caso-excluir")
            assert pg.locator("#lista-casos li").count() == 2

            # salvar .json
            pg.wait_for_timeout(400)
            with pg.expect_download() as dl:
                pg.click("#btn-salvar")
            arq_json = tmp_path / "proj.json"
            dl.value.save_as(arq_json)
            assert dl.value.suggested_filename == "Obra Teste.json"
            dados = json.loads(arq_json.read_text(encoding="utf-8"))
            assert dados["formato"] == "tensorcad-projeto" and dados["versao"] == 1
            assert dados["cota"] == 1646 and [c["caso_id"] for c in dados["casos"]] == [
                "REF",
                "ALT",
            ]
            assert dados["casos"][1]["ajustes"]["motor"] == {"A": 289}
            assert dados["casos"][1]["motor_id"] == "IEC-180M-4P"

            # recarregar restaura o rascunho
            pg.wait_for_timeout(600)
            pg.reload()
            pg.wait_for_selector("#aviso:not([hidden])", timeout=10_000)
            assert "rascunho restaurado" in pg.inner_text("#aviso")
            assert pg.locator("#lista-casos li").count() == 2
            assert pg.input_value("#nome-projeto") == "Obra Teste"

            # limpar memória pede confirmação: cancelar mantém os casos
            aceitar["sim"] = False
            pg.click("#btn-limpar")
            assert "2 caso(s)" in dialogos[-1]
            assert pg.locator("#lista-casos li").count() == 2
            aceitar["sim"] = True
            pg.click("#btn-limpar")
            assert pg.locator("#lista-casos li").count() == 1
            assert pg.input_value("#R_min") == ""
            pg.set_input_files("#arquivo-projeto", str(arq_json))
            pg.wait_for_function("document.querySelectorAll('#lista-casos li').length === 2")
            assert pg.input_value("#cota") == "1646"
            pg.wait_for_function(
                "document.querySelectorAll('#lista-casos .ponto[data-status=\"OK\"]').length === 2"
            )

            # arquivo inválido: aviso de erro, projeto mantido
            ruim = tmp_path / "ruim.json"
            ruim.write_text('{"formato": "outro"}', encoding="utf-8")
            pg.set_input_files("#arquivo-projeto", str(ruim))
            pg.wait_for_selector("#aviso[data-tipo='erro']")
            assert pg.locator("#lista-casos li").count() == 2

            # exportar .xlsx: uma aba por caso
            with pg.expect_download() as dl:
                pg.click("#btn-exportar")
            assert dl.value.suggested_filename == "Obra Teste.xlsx"
            wb = load_workbook(io.BytesIO(Path(dl.value.path()).read_bytes()))
            assert wb.sheetnames == ["PROJETO", "REF", "ALT", "_entradas"]
            indice = {
                r[0]: r for r in wb["PROJETO"].iter_rows(min_row=10, values_only=True) if r[0]
            }
            assert indice["REF"][7] == pytest.approx(1634.32, abs=0.01)
            assert indice["ALT"][6] == "OK"
            assert erros == []
        finally:
            nav.close()


def test_banco_duplo_no_navegador(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page(viewport={"width": 1500, "height": 1000})
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            pg.evaluate("localStorage.clear()")
            pg.click("#btn-limpar")
            pg.fill("#cota", "1646")
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.wait_for_selector("#status[data-status='OK']", timeout=10_000)

            # desligado: nada do banco 2
            assert pg.locator("#resultado-banco2").is_hidden()
            assert pg.locator("#el-O2").count() == 0

            # ligado sem R2: banco 1 continua calculado e pede os raios do banco 2
            pg.click("label[for='banco-duplo']")
            assert pg.locator("#R2_min").is_visible()
            assert pg.inner_text("#fixo-dy-banco2") == "540"
            pg.wait_for_selector("#banco2-mensagem:has-text('preencha R2min e R2max')")
            assert pg.get_attribute("#status", "data-status") == "OK"

            # R2 que deixam trecho entre os arcos nas duas tensões
            pg.fill("#R2_min", "2640")
            pg.fill("#R2_max", "2720")
            pg.wait_for_selector("#el-O2", timeout=10_000)
            pg.wait_for_selector("#banco2-mensagem:has-text('entre os arcos R1 e R2')")
            assert pg.locator("#banco2 tbody tr").count() == 2
            assert pg.locator("#el-arco-R2_min").count() == 1
            assert pg.locator("#el-trecho-0").count() == 1

            # sem trecho a 0 %: obrigatório, o caso fica FORA_TENSIONAMENTO
            pg.fill("#R2_min", "2600")
            pg.wait_for_selector("#banco2 .ponto[data-status='AVISO']", timeout=10_000)
            assert "não há posição" in pg.inner_text("#banco2-mensagem")
            pg.wait_for_selector("#status[data-status='FORA_TENSIONAMENTO']")
            assert (
                pg.locator("#lista-casos li.ativo .ponto[data-status='FORA_TENSIONAMENTO']").count()
                == 1
            )
            assert pg.locator("#el-raio2-0[data-status='AVISO']").count() == 1

            # persiste no projeto (switch no projeto, adicionais por caso)
            dados = pg.evaluate("Projeto.serializar()")
            assert dados["banco_duplo"] is True
            assert dados["casos"][0]["R2_min"] == 2600

            # desligar esconde e remove o banco 2 do desenho
            pg.click("label[for='banco-duplo']")
            pg.wait_for_function("!document.querySelector('#el-O2')")
            assert pg.locator("#resultado-banco2").is_hidden()
            assert erros == []
        finally:
            nav.close()


def test_opcao_de_layout_no_navegador(url: str, tmp_path: Path) -> None:
    import json

    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            ctx = nav.new_context(accept_downloads=True, viewport={"width": 1500, "height": 1000})
            pg = ctx.new_page()
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            pg.click("#btn-limpar")

            # padrão: 45°, com os campos de sempre
            assert pg.is_checked("#layout-45")
            assert pg.locator("#cota").is_visible() and pg.locator("#altura-tubo").is_hidden()
            pg.fill("#caso_id", "REF")
            pg.fill("#R_min", "2086")
            pg.fill("#R_max", "2161")
            pg.wait_for_selector("#status[data-status='OK']", timeout=10_000)

            # tubo horizontal: campos próprios e lista própria; sem cálculo ainda (T2)
            pg.check("#layout-horizontal")
            assert pg.inner_text("#nome-layout") == "tubo horizontal"
            assert pg.locator("#altura-tubo").is_visible() and pg.locator("#cota").is_hidden()
            assert pg.locator("#painel-dimensoes").is_hidden()
            assert pg.locator("#lista-casos li").count() == 1
            assert pg.input_value("#caso_id") == "th-1"
            pg.wait_for_selector("#status:has-text('comprimento do tubo')", timeout=10_000)
            pg.wait_for_timeout(500)  # nenhum cálculo 45° atrasado sobrescreve a tela
            assert "comprimento do tubo" in pg.inner_text("#status")
            assert pg.get_attribute("#lista-casos li.ativo .ponto", "data-status") == ""
            pg.fill("#altura-tubo", "1375")
            pg.fill("#comprimento-tubo", "2000")
            pg.click("label[for='motor-invertido']")
            pg.click("#btn-caso-novo")
            assert pg.input_value("#caso_id") == "th-2"
            assert pg.locator("#lista-casos li").count() == 2

            # exportar no horizontal: casos vazios do horizontal ficam de fora (T6)
            with pg.expect_download() as dl:
                pg.click("#btn-exportar")
            assert dl.value.suggested_filename.endswith(".xlsx")

            # voltar ao 45°: o caso REF continua lá e calcula
            pg.check("#layout-45")
            assert pg.input_value("#caso_id") == "REF"
            assert pg.locator("#lista-casos li").count() == 1
            pg.wait_for_selector("#status[data-status='OK']", timeout=10_000)

            # .json guarda as duas opções e a escolhida
            pg.check("#layout-horizontal")
            pg.wait_for_timeout(450)
            with pg.expect_download() as dl:
                pg.click("#btn-salvar")
            arq = tmp_path / "p.json"
            dl.value.save_as(arq)
            d = json.loads(arq.read_text(encoding="utf-8"))
            assert d["layout"] == "horizontal"
            assert [c["caso_id"] for c in d["casos"]] == ["REF"]
            h = d["horizontal"]
            assert (h["altura_tubo"], h["comprimento_tubo"], h["invertido"]) == (1375, 2000, True)
            assert [c["caso_id"] for c in h["casos"]] == ["th-1", "th-2"]

            # recarregar restaura o layout escolhido e o caso ativo de cada um
            pg.reload()
            pg.wait_for_selector("#aviso:not([hidden])", timeout=10_000)
            assert pg.is_checked("#layout-horizontal") and pg.input_value("#caso_id") == "th-2"
            assert pg.is_checked("#motor-invertido")

            # arquivo antigo (sem layout): abre no 45°
            antigo = {k: v for k, v in d.items() if k not in ("layout", "horizontal")}
            arq_antigo = tmp_path / "antigo.json"
            arq_antigo.write_text(json.dumps(antigo), encoding="utf-8")
            pg.set_input_files("#arquivo-projeto", str(arq_antigo))
            pg.wait_for_function("document.querySelector('#layout-45').checked")
            assert pg.input_value("#caso_id") == "REF"
            assert erros == []
        finally:
            nav.close()


def test_tubo_horizontal_calcula_e_desenha(url: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            pg = nav.new_page(viewport={"width": 1500, "height": 1000})
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            pg.evaluate("localStorage.clear()")
            pg.click("#btn-limpar")
            pg.check("#layout-horizontal")
            # carcaça 250 não tem chapa 45°, mas no horizontal é calculável
            assert not pg.locator("#carcaca option[value='250']").is_disabled()
            pg.select_option("#carcaca", "250")
            pg.fill("#comprimento-tubo", "2000")
            pg.fill("#R_min", "1839")
            pg.fill("#R_max", "1894")
            pg.wait_for_selector("#status[data-status='OK']", timeout=20_000)
            pg.wait_for_selector("#el-tubo")
            for el in ("O1", "laje", "eixo-centro", "chapa-0", "motor-3", "cota-g", "cota-altura"):
                assert pg.locator(f"#el-{el}").count() == 1, el
            assert "1.306,96" in pg.inner_text("#resumo")
            assert "recomendada" in pg.inner_text("#info-desenho")
            # altura informada e banco duplo
            pg.fill("#altura-tubo", "1375")
            pg.wait_for_selector("#info-desenho:has-text('informada')", timeout=20_000)
            pg.click("label[for='banco-duplo']")
            pg.fill("#R2_min", "2349")
            pg.fill("#R2_max", "2420")
            pg.wait_for_selector("#el-O2", timeout=20_000)
            # painel de posições do horizontal (T6) e exportação com aba do caso
            pg.wait_for_function("document.querySelectorAll('#posicoes-th tbody tr').length === 4")
            assert pg.locator("#posicoes").is_hidden()
            with pg.expect_download() as dl:
                pg.click("#btn-exportar")
            import io

            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(Path(dl.value.path()).read_bytes()))
            assert "th-1" in wb.sheetnames and "_entradas_horizontal" in wb.sheetnames
            # ajuste manual de g com a altura fixa: ±1 mm, digitado e "auto"
            pg.fill("#altura-tubo", "1295")
            pg.wait_for_selector("#g-manual-0", timeout=20_000)
            pg.fill("#g-manual-0", "65")
            pg.press("#g-manual-0", "Enter")
            pg.wait_for_selector("#posicoes-th tr.manual", timeout=20_000)
            assert pg.input_value("#g-manual-0") == "65,0"
            pg.click("[data-g='0-mais']")
            pg.wait_for_function("document.querySelector('#g-manual-0').value === '66,0'")
            assert pg.evaluate("Projeto.gManual()") == [66, None]
            pg.click("[data-g='0-auto']")
            pg.wait_for_function("!document.querySelector('#posicoes-th tr.manual')")
            assert pg.evaluate("Projeto.gManual()") == [None, None]
            # clicar na cota g do desenho leva ao ajuste
            pg.click(".alvo[data-id='cota-g']", force=True)
            assert pg.evaluate("document.activeElement.id") == "g-manual-0"
            # voltar ao 45° mantém a 250 desabilitada lá
            pg.check("#layout-45")
            assert pg.locator("#carcaca option[value='250']").is_disabled()
            assert erros == []
        finally:
            nav.close()


def test_setups_no_navegador(url: str, tmp_path: Path) -> None:
    import json

    sync = pytest.importorskip("playwright.sync_api")
    with sync.sync_playwright() as p:
        nav = _navegador(p)
        try:
            ctx = nav.new_context(accept_downloads=True, viewport={"width": 1500, "height": 1000})
            pg = ctx.new_page()
            erros: list[str] = []
            pg.on("pageerror", lambda e: erros.append(str(e)))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(url)
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            pg.evaluate("localStorage.clear()")
            pg.reload()
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)

            # aba Setups troca a tela inteira
            assert pg.locator("#tela-setups").is_hidden()
            pg.click("#aba-setups")
            assert pg.locator("#tela-setups").is_visible() and pg.locator("main.layout").is_hidden()
            assert pg.locator("#setup-polia-motor option").count() == 14
            pg.fill("#setup-nome", "MDDL")
            pg.select_option("#setup-polia-motor", "170")
            pg.fill("#setup-correia", "5000")
            pg.select_option("#setup-rpm", "1200")
            pg.wait_for_selector("#setup-status:has-text('MDDL-170-5000')", timeout=10_000)
            assert "2.085,61" in pg.inner_text("#setup-resumo")
            assert "2.160,61" in pg.inner_text("#setup-resumo")
            pg.click("#btn-setup-salvar")
            pg.wait_for_function("document.querySelectorAll('#lista-setups li').length === 1")
            # salvar logo após digitar grava os valores novos (sem esperar o cálculo)
            pg.click("#btn-setup-novo")
            pg.fill("#setup-nome", "MDDL")
            pg.fill("#setup-correia", "5500")
            pg.click("#btn-setup-salvar")
            pg.wait_for_selector(".campo[data-campo='nome'].invalido")  # nome repetido
            pg.fill("#setup-nome", "B2")
            pg.click("#btn-setup-salvar")
            pg.wait_for_function("document.querySelectorAll('#lista-setups li').length === 2")
            assert "B2-170-5500" in pg.inner_text("#lista-setups")

            # biblioteca em arquivo próprio
            with pg.expect_download() as dl:
                pg.click("#btn-biblioteca-salvar")
            arq = tmp_path / "setups.json"
            dl.value.save_as(arq)
            bib = json.loads(arq.read_text(encoding="utf-8"))
            assert bib["formato"] == "tensorcad-setups" and len(bib["setups"]) == 2

            # layout: caso a partir do setup, R e sufixo travados
            pg.click("#aba-layout")
            pg.click("#btn-limpar")
            pg.click("#lista-setups-layout li[data-setup] button >> nth=0")
            assert pg.input_value("#caso_id") == "MDDL"
            assert pg.inner_text("#caso-sufixo") == "-170-5000"
            assert pg.input_value("#R_min") == "2085.61" and pg.input_value("#R_max") == "2160.61"
            assert not pg.is_editable("#R_min") and not pg.is_editable("#R_max")
            pg.fill("#caso_id", "LINHA1")
            pg.wait_for_selector("#status[data-status='OK']", timeout=10_000)
            assert "LINHA1-170-5000" in pg.inner_text("#lista-casos")
            # duplicar mantém o sufixo no fim
            pg.click("#btn-caso-duplicar")
            assert pg.input_value("#caso_id") == "LINHA1-copia"
            assert pg.inner_text("#caso-sufixo") == "-170-5000"
            pg.click("#lista-casos li[data-indice='1']")

            # setup alterado: aviso e botão para atualizar
            pg.click("#aba-setups")
            pg.click("#lista-setups li[data-indice='0']")
            pg.fill("#setup-correia", "5300")
            pg.click("#btn-setup-salvar")
            pg.wait_for_function(
                "document.querySelector('#lista-setups').innerText.includes('MDDL-170-5300')"
            )
            pg.click("#aba-layout")
            pg.wait_for_selector("#aviso-setup:not([hidden])")
            assert "mudou" in pg.inner_text("#aviso-setup")
            assert pg.input_value("#R_min") == "2085.61"  # fica como estava
            pg.click("#btn-atualizar-setup")
            assert pg.inner_text("#caso-sufixo") == "-170-5300"
            assert pg.input_value("#R_min") != "2085.61"
            assert pg.locator("#aviso-setup").is_hidden()

            # .json do projeto guarda a cópia do setup no caso
            dados = pg.evaluate("Projeto.serializar()")
            c = next(x for x in dados["casos"] if x["caso_id"] == "LINHA1-170-5300")
            assert c["setup"]["correia"] == 5300 and c["setup"]["sufixo"] == "-170-5300"

            # biblioteca reaberta (outro projeto/computador) é recalculada e mesclada
            pg.evaluate("localStorage.removeItem('tensorcad.setups.v1')")
            pg.reload()
            pg.wait_for_selector("#conexao[data-estado='ok']", timeout=10_000)
            assert pg.locator("#lista-setups-layout li[data-setup]").count() == 0
            pg.wait_for_selector("#aviso-setup:not([hidden])")  # setup fora da biblioteca
            pg.click("#aba-setups")
            pg.set_input_files("#arquivo-biblioteca", str(arq))
            pg.wait_for_function("document.querySelectorAll('#lista-setups li').length === 2")
            assert erros == []
        finally:
            nav.close()
