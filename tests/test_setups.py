"""S2/S5 — API de setups, biblioteca e saídas no .xlsx."""

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad.loader import carregar_diretorio, carregar_padroes, carregar_transmissao
from tensorcad.web import api

DADOS = Path(__file__).resolve().parents[1] / "data"
SETUP = {
    "nome": "MDDL",
    "polia_maquina": 355,
    "polia_motor": 170,
    "correia": 5000,
    "rpm_motor": 1200,
}


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def test_listas_da_tabela(ctx) -> None:
    t = api.transmissao(ctx)
    assert t == carregar_transmissao(DADOS / "padrao")
    assert t["polia_maquina"] == [355] and len(t["polia_motor"]) == 14
    assert t["rpm_motor"] == [900, 1200, 1800, 3600]  # WEG 60 Hz síncrono


def test_setup_calcula(ctx) -> None:
    r = api.setup(ctx, {**SETUP, "id": "a1"})
    assert r["id"] == "a1" and r["sufixo"] == "-170-5000"
    assert (r["R_min"], r["R_info"], r["R_max"]) == pytest.approx(
        (2085.61, 2135.61, 2160.61), abs=0.01
    )
    assert r["rpm_maquina"] == pytest.approx(574.65, abs=0.01) and r["banco2"] is None
    b = api.setup(
        ctx, {**SETUP, "banco2": {"polia_maquina": 355, "polia_motor": 200, "correia": 5500}}
    )
    assert b["banco2"]["R2_min"] == pytest.approx(2312.81, abs=0.01)
    assert b["banco2"]["R2_max"] == pytest.approx(2395.31, abs=0.01)


@pytest.mark.parametrize(
    ("mudanca", "campo", "trecho"),
    [
        ({"nome": ""}, "nome", "nome"),
        ({"polia_maquina": 400}, "polia_maquina", "fora da lista"),
        ({"polia_motor": 175}, "polia_motor", "fora da lista"),
        ({"rpm_motor": 1750}, "rpm_motor", "WEG"),
        ({"correia": 900}, "correia", "curta demais"),
        ({"correia": "x"}, "correia", "inválido"),
        ({"banco2": {"polia_maquina": 355, "polia_motor": 170}}, "banco2.correia", "obrigatório"),
        ({"banco2": "sim"}, "banco2", "objeto"),
    ],
)
def test_setup_valida(ctx, mudanca, campo, trecho) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.setup(ctx, {**SETUP, **mudanca})
    assert trecho in exc.value.erros[campo]


def test_biblioteca(ctx) -> None:
    bib = {
        "formato": "tensorcad-setups",
        "versao": 1,
        "setups": [SETUP, {**SETUP, "nome": "B", "correia": 5500}],
    }
    d = api.biblioteca(ctx, bib)
    assert [s["sufixo"] for s in d["setups"]] == ["-170-5000", "-170-5500"]
    with pytest.raises(api.ErroEntrada) as exc:
        api.biblioteca(ctx, {**bib, "setups": [SETUP, {**SETUP, "nome": "mddl"}]})
    assert "repetidos" in exc.value.erros["setups"]
    with pytest.raises(api.ErroEntrada) as exc:
        api.biblioteca(ctx, {**bib, "setups": [{**SETUP, "polia_motor": 1}]})
    assert "setups[0].polia_motor" in exc.value.erros
    with pytest.raises(api.ErroEntrada):
        api.biblioteca(ctx, {"formato": "outro"})


def test_exportar_casos_de_setup(ctx, tmp_path: Path) -> None:
    from tensorcad.planilha_projeto import ler_entradas, ler_entradas_horizontais

    st = api.setup(ctx, {**SETUP, "id": "a1"})
    caso = {
        "caso_id": "MDDL-170-5000",
        "carcaca": "180",
        "R_min": round(st["R_min"], 2),
        "R_max": round(st["R_max"], 2),
        "setup": st,
    }
    proj = {
        "formato": "tensorcad-projeto",
        "versao": 1,
        "nome": "ST",
        "cota": 1646,
        "casos": [caso],
        "horizontal": {
            "comprimento_tubo": 2000,
            "casos": [{**caso, "caso_id": "H-170-5000", "carcaca": "250"}],
        },
    }
    dados, _ = api.exportar(ctx, proj)
    wb = load_workbook(io.BytesIO(dados))
    for aba in ("MDDL-170-5000", "H-170-5000"):
        ws = wb[aba]
        pares = {ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(1, ws.max_row + 1)}
        assert pares["setup"] == "MDDL-170-5000"
        assert pares["R 0 % / 2 % / 3 %"] == "2085.61 / 2135.61 / 2160.61"
    idx = [c.value for c in wb["PROJETO"]["A"]]
    assert "Setups de transmissão" in idx
    linha = idx.index("Setups de transmissão") + 3  # título, cabeçalho, 1ª linha (1-based)
    assert wb["PROJETO"].cell(linha, 12).value == "MDDL-170-5000, H-170-5000"
    arq = tmp_path / "p.xlsx"
    arq.write_bytes(dados)
    assert ler_entradas(arq)[1][0].setup["sufixo"] == "-170-5000"
    assert ler_entradas_horizontais(arq)[0].setup["id"] == "a1"
    # setup gravado inválido é apontado no caso
    caso_ruim = {**caso, "setup": {**st, "polia_motor": 1}}
    with pytest.raises(api.ErroEntrada) as exc:
        api.exportar(ctx, {**proj, "casos": [caso_ruim]})
    assert "casos[0].setup.polia_motor" in exc.value.erros
