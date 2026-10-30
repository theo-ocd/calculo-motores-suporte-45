from pathlib import Path

import pytest

from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.web import api

DADOS = Path(__file__).resolve().parents[1] / "data"
BASE = {"carcaca": "180", "R_min": 2086, "R_max": 2161, "cota": 1646}


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def test_dimensoes_padrao_e_campos(ctx) -> None:
    c180 = next(c for c in api.carcacas(ctx) if c["carcaca"] == "180")
    d = c180["dimensoes_chapa"]
    assert (d["comprimento_chapa"], d["dist_L_ranhura"], d["comprimento_ranhura"]) == (
        635,
        110,
        155,
    )
    assert (d["dist_entre_ranhuras"], d["dist_ranhura_topo"], d["largura_ranhura"]) == (
        124,
        91,
        None,
    )
    c200 = next(c for c in api.carcacas(ctx) if c["carcaca"] == "200")
    assert c200["dimensoes_chapa"] is None
    meta = api.campos(ctx)
    assert [m["campo"] for m in meta["motor"]] == ["H", "A", "K"]
    nomes = {m["campo"] for m in meta["chapa"]}
    assert "x_tubo" not in nomes and "y_piso" not in nomes  # fixos
    assert len(nomes) == 10


def test_sem_ajustes_igual_ao_padrao(ctx) -> None:
    r = api.calcular(ctx, BASE)
    assert r["cota_recomendada"] == pytest.approx(1634.32, abs=0.01)
    assert r["ajustes_aplicados"] == {"chapa": {}, "motor": {}}
    r2 = api.calcular(ctx, {**BASE, "ajustes": {}})
    assert r2["cota_recomendada"] == r["cota_recomendada"]


def test_ajuste_muda_resultado(ctx) -> None:
    # sobe a ranhura de baixo 20 mm (vão menor para fechar a soma): menos folga embaixo
    aj = {"chapa": {"dist_L_ranhura": 130, "dist_entre_ranhuras": 104}}
    r = api.calcular(ctx, {**BASE, "ajustes": aj})
    p3 = r["em_informada"][1]
    assert p3["folga_pos"] == pytest.approx(40.64 - 20, abs=0.01)
    assert r["dimensoes_chapa"]["dist_L_ranhura"] == 130
    assert r["ajustes_aplicados"]["chapa"] == {"dist_L_ranhura": 130, "dist_entre_ranhuras": 104}
    # motor com A maior: furos mais afastados, menos folga
    r = api.calcular(ctx, {**BASE, "ajustes": {"motor": {"A": "289"}}})
    assert r["em_informada"][0]["folga_neg"] == pytest.approx(16.30 - 5, abs=0.01)
    assert r["motor"]["A"] == 289
    # largura informada menor que K → INCOMPATIVEL
    r = api.calcular(ctx, {**BASE, "ajustes": {"chapa": {"largura_ranhura": 12}}})
    assert r["status"] == "INCOMPATIVEL"
    # h depende da altura de eixo e do apoio
    r = api.calcular(ctx, {**BASE, "ajustes": {"chapa": {"e_apoio": 10}, "motor": {"H": 170}}})
    assert r["h"] == 180


def test_opcionais_podem_ser_apagados(ctx) -> None:
    aj = {"chapa": {"comprimento_ranhura": None, "dist_entre_ranhuras": ""}}
    r = api.calcular(ctx, {**BASE, "ajustes": aj})
    assert r["chapa"]["ranhura1_d_fim"] == 544 and r["chapa"]["ranhura2_d_ini"] == 110
    assert r["dimensoes_chapa"]["comprimento_ranhura"] is None


@pytest.mark.parametrize(
    ("ajustes", "chave", "trecho"),
    [
        ({"chapa": {"dist_L_ranhura": 130}}, "ajustes.chapa", "cotas não fecham"),
        ({"chapa": {"x_tubo": 1}}, "ajustes.chapa.x_tubo", "não editável"),
        ({"motor": {"K": -1}}, "ajustes.motor.K", "maior que 0"),
        ({"chapa": {"theta_deg": 95}}, "ajustes.chapa.theta_deg", "menor que 90"),
        ({"chapa": {"comprimento_chapa": ""}}, "ajustes.chapa.comprimento_chapa", "obrigatório"),
        (
            {"chapa": {"comprimento_ranhura": "abc"}},
            "ajustes.chapa.comprimento_ranhura",
            "inválido",
        ),
        ({"chapa": [1]}, "ajustes.chapa", "objeto"),
        ([1], "ajustes", "objeto"),
    ],
)
def test_ajustes_invalidos(ctx, ajustes, chave, trecho) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular(ctx, {**BASE, "ajustes": ajustes})
    assert trecho in exc.value.erros[chave]
