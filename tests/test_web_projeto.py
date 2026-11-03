import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.planilha_projeto import EntradaPlanilha, adicionar_caso, ler_entradas
from tensorcad.projeto import ConfigProjeto
from tensorcad.web import api, servidor

DADOS = Path(__file__).resolve().parents[1] / "data"
AJ = {"chapa": {"dist_L_ranhura": 130, "dist_entre_ranhuras": 104}, "motor": {}}
PROJ = {
    "formato": "tensorcad-projeto",
    "versao": 1,
    "nome": "Obra X/1",
    "cota": 1646,
    "casos": [
        {"caso_id": "REF", "carcaca": "180", "R_min": 2086, "R_max": 2161},
        {
            "caso_id": "AJ",
            "carcaca": "180",
            "motor_id": "IEC-180M-4P",
            "R_min": "2086",
            "R_max": "2161",
            "ajustes": AJ,
        },
    ],
}


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def _indice(wb) -> dict[str, tuple]:
    return {r[0]: r for r in wb["PROJETO"].iter_rows(min_row=10, values_only=True) if r[0]}


def test_exportar_igual_a_cli(ctx, tmp_path: Path) -> None:
    conteudo, nome = api.exportar(ctx, PROJ)
    assert nome == "Obra X_1.xlsx"
    wb = load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ["PROJETO", "REF", "AJ", "_entradas"]
    assert wb["PROJETO"]["A1"].value == "Projeto Obra X/1"
    web = _indice(wb)

    cli = tmp_path / "cli.xlsx"
    cfg = ConfigProjeto(nome="Obra X/1")
    adicionar_caso(
        cli, EntradaPlanilha("REF", "IEC-180L-4P", 2086, 2161, 1646), ctx.base, ctx.padroes, cfg=cfg
    )
    adicionar_caso(
        cli,
        EntradaPlanilha("AJ", "IEC-180M-4P", 2086, 2161, 1646, ajustes=AJ),
        ctx.base,
        ctx.padroes,
    )
    ref = _indice(load_workbook(cli))
    for caso in ("REF", "AJ"):
        assert web[caso][6:9] == ref[caso][6:9], caso  # status, H recomendada, folga
    assert web["REF"][7] == pytest.approx(1634.32, abs=0.01)
    assert web["AJ"][7] == pytest.approx(1643.92, abs=0.01)


def test_ajustes_ficam_no_arquivo(ctx, tmp_path: Path) -> None:
    conteudo, _ = api.exportar(ctx, PROJ)
    arq = tmp_path / "p.xlsx"
    arq.write_bytes(conteudo)
    cfg, ents = ler_entradas(arq)
    assert cfg.nome == "Obra X/1"
    assert ents[0].ajustes is None
    assert ents[1].ajustes == {"chapa": {"dist_L_ranhura": 130.0, "dist_entre_ranhuras": 104.0}}
    ws = load_workbook(arq)["AJ"]
    rotulos = [ws.cell(i, 1).value for i in range(1, 60)]
    assert "Ajustes de dimensões (diferentes do padrão)" in rotulos
    assert "Ponta baixa → ranhura" in rotulos
    # a CLI pode acrescentar casos sem perder os ajustes já gravados
    adicionar_caso(arq, EntradaPlanilha("NOVO", "IEC-180M-4P", 2086, 2110), ctx.base, ctx.padroes)
    _, ents = ler_entradas(arq)
    assert [e.caso_id for e in ents] == ["REF", "AJ", "NOVO"] and ents[1].ajustes


@pytest.mark.parametrize(
    ("mudanca", "chave", "trecho"),
    [
        ({"formato": "outro"}, "formato", "tensorcad-projeto"),
        ({"versao": 2}, "versao", "1"),
        ({"casos": []}, "casos", "ao menos um"),
        ({"casos": [{"caso_id": "a"}, {"caso_id": "A"}]}, "casos", "repetidos"),
        ({"casos": [{"caso_id": ""}]}, "casos", "nome"),
        ({"layout": "vertical"}, "layout", "desconhecida"),
        ({"horizontal": []}, "horizontal", "objeto"),
        (
            {
                "casos": [
                    PROJ["casos"][0],
                    {"caso_id": "X", "carcaca": "200", "R_min": 1, "R_max": 2},
                ]
            },
            "casos[1].carcaca",
            "a preencher",
        ),
        (
            {"casos": [{**PROJ["casos"][0], "ajustes": {"chapa": {"dist_L_ranhura": 999}}}]},
            "casos[0].ajustes.chapa",
            "≥ comprimento_chapa",
        ),
    ],
)
def test_projeto_invalido(ctx, mudanca, chave, trecho) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.exportar(ctx, {**PROJ, **mudanca})
    assert trecho in exc.value.erros[chave]
    with pytest.raises(api.ErroEntrada):
        api.validar_projeto([])


def test_ajuste_invalido_na_planilha(ctx, tmp_path: Path) -> None:
    ruim = EntradaPlanilha("X", "IEC-180M-4P", 2086, 2161, ajustes={"chapa": {"x": 1}})
    with pytest.raises(ValueError, match="ajustes inválidos em X"):
        adicionar_caso(tmp_path / "p.xlsx", ruim, ctx.base, ctx.padroes)


def test_post_exportar_devolve_xlsx(ctx) -> None:
    srv = servidor.iniciar_em_thread(ctx)
    url = servidor.url_de(srv) + "api/exportar"
    try:
        req = urllib.request.Request(url, data=json.dumps(PROJ).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            assert r.headers["Content-Type"] == api.MIME_XLSX
            assert "Obra%20X_1.xlsx" in r.headers["Content-Disposition"]
            assert load_workbook(io.BytesIO(r.read())).sheetnames[0] == "PROJETO"
        req = urllib.request.Request(url, data=b'{"formato": "x"}', method="POST")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 400
        assert "formato" in json.loads(exc.value.read())["erros"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_layout_horizontal_nao_muda_exportacao_45(ctx) -> None:
    """T1: o bloco do tubo horizontal fica no .json; a planilha segue com os casos 45°."""
    base, _ = api.exportar(ctx, PROJ)
    com_h, _ = api.exportar(
        ctx,
        {
            **PROJ,
            "layout": "horizontal",
            "horizontal": {
                "altura_tubo": 1375,
                "comprimento_tubo": 2000,
                "invertido": True,
                "casos": [{"caso_id": "th-1", "carcaca": "250"}],
            },
        },
    )
    import io

    from openpyxl import load_workbook

    def abas(b: bytes) -> list[str]:
        return load_workbook(io.BytesIO(b)).sheetnames

    assert abas(com_h) == abas(base)


def _proj_com_horizontal(**h):
    return {
        **PROJ,
        "casos": [{**c, "R2_min": 2600, "R2_max": 2680} for c in PROJ["casos"]],
        "banco_duplo": True,
        "horizontal": {
            "altura_tubo": None,
            "comprimento_tubo": 2000,
            "invertido": False,
            "casos": [
                {
                    "caso_id": "TH",
                    "carcaca": "250",
                    "R_min": 1839,
                    "R_max": 1894,
                    "R2_min": 2349,
                    "R2_max": 2420,
                },
                {"caso_id": "th-vazio", "carcaca": "250"},
            ],
            **h,
        },
    }


def test_exportar_dois_layouts(ctx, tmp_path: Path) -> None:
    import io

    from openpyxl import load_workbook

    from tensorcad.planilha_projeto import ler_entradas_horizontais

    proj = _proj_com_horizontal()
    proj["casos"] = [*proj["casos"], {"caso_id": "vazio45", "carcaca": "180"}]
    dados, _ = api.exportar(ctx, proj)
    wb = load_workbook(io.BytesIO(dados))
    # casos sem R ficam de fora, nos dois layouts
    assert wb.sheetnames == ["PROJETO", "REF", "AJ", "TH", "_entradas", "_entradas_horizontal"]
    ws = wb["TH"]
    pares = {ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(1, ws.max_row + 1)}
    assert pares["layout"] == "tubo horizontal" and pares["status"] == "OK"
    assert pares["altura do tubo recomendada"] == pytest.approx(1386.96, abs=0.05)
    assert pares["R2_min (0 %) a partir de O2"] == 2349
    # índice: tabela do tubo horizontal abaixo da do 45°
    idx = [c.value for c in wb["PROJETO"]["A"]]
    assert "Layout tubo horizontal" in idx and "TH" in idx
    arq = tmp_path / "p.xlsx"
    arq.write_bytes(dados)
    (e,) = ler_entradas_horizontais(arq)
    assert (e.caso_id, e.motor_id, e.comprimento_tubo) == ("TH", "IEC-250M-4P", 2000)
    assert e.banco_duplo["R2_min"] == 2349


def test_exportar_horizontal_valida(ctx) -> None:
    proj = _proj_com_horizontal(comprimento_tubo=None)
    with pytest.raises(api.ErroEntrada) as exc:
        api.exportar(ctx, proj)
    assert exc.value.erros == {"horizontal.casos[0].comprimento_tubo": "obrigatório"}
    proj = _proj_com_horizontal()
    proj["horizontal"]["casos"][0]["caso_id"] = "ref"
    with pytest.raises(api.ErroEntrada) as exc:
        api.exportar(ctx, proj)
    assert "dois layouts" in exc.value.erros["casos"]
    vazio = {**PROJ, "casos": [{"caso_id": "a", "carcaca": "180"}]}
    with pytest.raises(api.ErroEntrada) as exc:
        api.exportar(ctx, vazio)
    assert "nenhum caso" in exc.value.erros["casos"]


def test_adicionar_caso_preserva_horizontais(ctx, tmp_path: Path) -> None:
    from tensorcad.planilha_projeto import (
        EntradaPlanilha,
        adicionar_caso,
        ler_entradas_horizontais,
    )

    arq = tmp_path / "p.xlsx"
    arq.write_bytes(api.exportar(ctx, _proj_com_horizontal())[0])
    adicionar_caso(arq, EntradaPlanilha("NOVO", "IEC-180L-4P", 2086, 2161), ctx.base, ctx.padroes)
    assert [e.caso_id for e in ler_entradas_horizontais(arq)] == ["TH"]
