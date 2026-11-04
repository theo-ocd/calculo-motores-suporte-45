"""T5 — desenho do tubo horizontal e rota da API."""

from pathlib import Path

import pytest

from tensorcad import desenho_th
from tensorcad import tubo_horizontal as th
from tensorcad.banco_duplo import ConfigBancoDuplo
from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.web import api

DADOS = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def _resolver(ctx, invertido=False, altura=1295.0, b2=None, motor="IEC-250M-4P", R=(1839, 1894)):
    par = th.ParametrosTH(comprimento_tubo=2000, invertido=invertido)
    m = ctx.base.motores[motor]
    return th.resolver(par, th.EntradaTH("C", m, *R, altura, b2))


def test_pilha_no_desenho_normal(ctx) -> None:
    r = _resolver(ctx)
    d = desenho_th.gerar(r)
    assert d["altura"] == 1295
    ids = {p["id"]: p for p in d["primitivas"]}
    assert set(d["camadas"]) == {p["camada"] for p in d["primitivas"]} | {"banco2"}
    # tubo: topo 1295 (altura, motor normal) e fundo 1375 abaixo da laje (Y = −(767 + y))
    ys = sorted({q[1] for q in ids["tubo"]["pts"]})
    assert ys == [-(767 + 1375), -(767 + 1295)]
    p0 = r.em_informada[0]
    # porca do tubo encosta no topo do tubo; g entre as porcas; chapa sobre a 2ª porca
    porca = sorted({q[1] for q in ids["porca-tubo-0-e"]["pts"]})
    assert porca == pytest.approx([-(767 + 1295), -(767 + 1295 - 27.5)])
    g = ids["cota-g"]
    assert g["p1"][1] - g["p0"][1] == pytest.approx(p0.g)
    chapa = sorted({q[1] for q in ids["chapa-0"]["pts"]})
    assert chapa[1] - chapa[0] == pytest.approx(15)
    # centro do motor = topo da chapa + H
    assert ids["centro-0"]["p"] == pytest.approx([465 + p0.x, -(767 + p0.y_motor)])
    assert ids["centro-0"]["p"][1] - chapa[1] == pytest.approx(250)
    # barras roscadas a ±(A + 75)/2 do motor
    assert ids["barra-0-d"]["p0"][0] - ids["barra-0-e"]["p0"][0] == pytest.approx(406 + 75)
    assert ids["eixo-centro"]["p0"][0] == 465


def test_desenho_invertido_motor_abaixo_do_tubo(ctx) -> None:
    r = _resolver(ctx, invertido=True, altura=1100.0, motor="IEC-180L-4P", R=(2310, 2380))
    assert r.em_informada[0].x is not None
    ids = {p["id"]: p for p in desenho_th.gerar(r)["primitivas"]}
    fundo_tubo = -(767 + 1100)
    porca = sorted({q[1] for q in ids["porca-tubo-0-e"]["pts"]})
    assert porca == pytest.approx([fundo_tubo - 27.5, fundo_tubo])  # abaixo do fundo do tubo
    assert ids["centro-0"]["p"][1] < fundo_tubo  # motor abaixo do tubo


def test_desenho_recomendada_e_banco_duplo(ctx) -> None:
    r = _resolver(ctx, altura=None, b2=ConfigBancoDuplo(2349, 2420))
    d = desenho_th.gerar(r)
    assert d["altura"] == pytest.approx(r.altura_recomendada)
    ids = {p["id"]: p for p in d["primitivas"]}
    assert ids["O2"]["c"] == [0.0, 540.0]
    assert ids["raio2-0"]["status"] == "OK" and ids["arco-R2_min"]["r"] == 2349


def test_api_calcular_horizontal(ctx) -> None:
    corpo = {"carcaca": "250", "R_min": 1839, "R_max": 1894, "comprimento_tubo": 2000}
    r = api.calcular_horizontal(ctx, corpo)
    assert r["status"] == "OK" and r["layout"] == "horizontal"
    assert r["altura_recomendada"] == pytest.approx(1306.96, abs=0.05)
    assert r["desenho"]["altura"] == pytest.approx(r["altura_recomendada"])
    assert len(r["em_recomendada"]) == 2 and r["em_informada"] is None
    inv = api.calcular_horizontal(ctx, {**corpo, "carcaca": "180", "invertido": True})
    assert inv["invertido"] is True


@pytest.mark.parametrize(
    ("mudanca", "campo", "trecho"),
    [
        ({"comprimento_tubo": None}, "comprimento_tubo", "obrigatório"),
        ({"comprimento_tubo": -5}, "comprimento_tubo", "maior que zero"),
        ({"carcaca": "999"}, "carcaca", "sem motor"),
        ({"R_max": 1000}, "R_max", "maior ou igual"),
        ({"altura_tubo": "x"}, "altura_tubo", "inválido"),
        ({"motor_id": "IEC-180L-4P"}, "motor_id", "não pertence"),
    ],
)
def test_api_calcular_horizontal_valida(ctx, mudanca, campo, trecho) -> None:
    corpo = {"carcaca": "250", "R_min": 1839, "R_max": 1894, "comprimento_tubo": 2000}
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular_horizontal(ctx, {**corpo, **mudanca})
    assert trecho in exc.value.erros[campo]


def test_carcacas_status_horizontal(ctx) -> None:
    lista = {c["carcaca"]: c for c in api.carcacas(ctx)}
    assert lista["250"]["calculavel"] is False and lista["250"]["calculavel_horizontal"] is True
    assert lista["250"]["status_horizontal"] == "ok"


def test_api_g_manual(ctx) -> None:
    corpo = {
        "carcaca": "250",
        "R_min": 1839,
        "R_max": 1894,
        "comprimento_tubo": 2000,
        "altura_tubo": 1295,
        "g_manual": [65, None],
    }
    r = api.calcular_horizontal(ctx, corpo)
    assert r["g_manual"] == [65, None] and r["em_informada"][0]["g"] == 65
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular_horizontal(ctx, {**corpo, "altura_tubo": None})
    assert "altura do tubo" in exc.value.erros["g_manual"]
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular_horizontal(ctx, {**corpo, "g_manual": ["x", None]})
    assert "número" in exc.value.erros["g_manual"]
    # lista vazia/nulos = sem ajuste
    assert api.calcular_horizontal(ctx, {**corpo, "g_manual": [None, None]})["g_manual"] is None
