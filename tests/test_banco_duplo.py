"""Esboço do banco duplo: núcleo, API e desenho."""

import math
from pathlib import Path

import pytest

from tensorcad import banco_duplo as bd
from tensorcad.geometry import Status
from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.projeto import Posicao
from tensorcad.web import api

DADOS = Path(__file__).resolve().parents[1] / "data"
REF = {"carcaca": "180", "R_min": 2086, "R_max": 2161, "cota": 1646}


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def _pos(R: float, Cx: float, Cy: float) -> Posicao:
    return Posicao(R, 0.0, Status.OK, Cx=Cx, Cy=Cy)


def test_centro_o2_acima_de_o() -> None:
    assert bd.ConfigBancoDuplo(0, 0).centro == (0.0, -500.0)  # y+ para baixo
    assert bd.faixa_R2(bd.ConfigBancoDuplo(10, 20), 100, 200) == (110, 220)


def test_dentro_e_fora_das_linhas() -> None:
    cfg = bd.ConfigBancoDuplo(adicional_R_min=0, adicional_R_max=0)
    # motor a 0 %: (0, 1500) → R2 = 2000; a 3 %: (0, 1600) → R2 = 2100
    av = bd.avaliar(cfg, 1900, 2100, (_pos(1900, 0, 1500), _pos(2100, 0, 1600)))
    assert [q.R2 for q in av.posicoes] == [2000, 2100]
    assert av.ok and all(q.dentro for q in av.posicoes)

    av = bd.avaliar(
        bd.ConfigBancoDuplo(150, 0), 1900, 2100, (_pos(1900, 0, 1500), _pos(2100, 0, 1600))
    )
    assert av.R2_min == 2050 and not av.ok
    assert av.posicoes[0].desvio == pytest.approx(-50)
    assert "abaixo de R2_min" in av.avisos[0]

    av = bd.avaliar(
        bd.ConfigBancoDuplo(0, -50), 1900, 2100, (_pos(1900, 0, 1500), _pos(2100, 0, 1600))
    )
    assert av.posicoes[1].desvio == pytest.approx(50) and "acima de R2_max" in av.avisos[0]


def test_sem_posicao_e_faixa_invertida() -> None:
    av = bd.avaliar(bd.ConfigBancoDuplo(0, 0), 2000, 2100, None)
    assert not av.ok and "sem altura H" in av.avisos[0]
    sem = Posicao(2000, 0.0, Status.SEM_SOLUCAO)
    av = bd.avaliar(bd.ConfigBancoDuplo(200, 0), 2000, 2100, (sem, sem))
    assert "R2_min (2200) maior que R2_max (2100)" in av.avisos[0]
    assert len(av.avisos) == 3 and av.posicoes == ()


def test_api_desligado_nao_muda_resultado(ctx) -> None:
    base = api.calcular(ctx, REF)
    desl = api.calcular(ctx, {**REF, "banco_duplo": {"ativo": False, "adicional_R_min": 1}})
    assert base["banco_duplo"] is None and desl["banco_duplo"] is None
    assert desl["status"] == base["status"]
    assert not any(p["camada"] == "banco2" for p in base["desenho"]["primitivas"])


def test_api_ligado_mede_distancia_a_o2(ctx) -> None:
    r = api.calcular(
        ctx, {**REF, "banco_duplo": {"ativo": True, "adicional_R_min": 470, "adicional_R_max": 480}}
    )
    b = r["banco_duplo"]
    assert b["deslocamento_y"] == 500 and (b["R2_min"], b["R2_max"]) == (2556, 2641)
    for q, p in zip(b["posicoes"], r["em_informada"], strict=True):
        assert q["R2"] == pytest.approx(math.hypot(p["Cx"], p["Cy"] + 500))
    assert b["ok"] and [round(q["R2"], 2) for q in b["posicoes"]] == [2563.77, 2636.32]
    assert r["status"] == "OK"  # banco 2 só gera aviso

    ids = {p["id"]: p for p in r["desenho"]["primitivas"] if p["camada"] == "banco2"}
    assert {"O2", "cota-O2", "arco-R2_min", "arco-R2_max", "raio2-0", "raio2-3"} <= set(ids)
    assert ids["O2"]["c"] == [0.0, 500.0]  # vista CAD: Y para cima
    assert ids["arco-R2_min"]["c"] == [0.0, 500.0] and ids["arco-R2_min"]["r"] == 2556


def test_api_aviso_quando_fora(ctx) -> None:
    r = api.calcular(
        ctx, {**REF, "banco_duplo": {"ativo": True, "adicional_R_min": 500, "adicional_R_max": 500}}
    )
    b = r["banco_duplo"]
    assert not b["ok"] and b["posicoes"][0]["desvio"] == pytest.approx(-22.23, abs=0.01)
    raio = next(p for p in r["desenho"]["primitivas"] if p["id"] == "raio2-0")
    assert raio["status"] == "AVISO"


def test_api_valida_adicionais(ctx) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular(ctx, {**REF, "banco_duplo": {"ativo": True, "adicional_R_min": "x"}})
    assert exc.value.erros == {
        "banco_duplo.adicional_R_min": "número inválido",
        "banco_duplo.adicional_R_max": "obrigatório",
    }
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular(ctx, {**REF, "banco_duplo": "sim"})
    assert "banco_duplo" in exc.value.erros


def test_saude_informa_deslocamento(ctx) -> None:
    assert api.saude(ctx)["fixos"]["dy_banco2"] == 500
