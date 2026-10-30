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
