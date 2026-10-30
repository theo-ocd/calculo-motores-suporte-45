"""Esboço do banco duplo: núcleo, API e desenho."""

import math
from pathlib import Path

import pytest

from tensorcad import banco_duplo as bd
from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.projeto import ConfigProjeto, EntradaCaso
from tensorcad.web import api

DADOS = Path(__file__).resolve().parents[1] / "data"
REF = {"carcaca": "180", "R_min": 2086, "R_max": 2161, "cota": 1646}
DIST_O2 = (2563.77, 2636.32)  # |C − O2| sobre os arcos R1 (CH-180, H = 1646)


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def _calc(ctx, r2_min, r2_max, **extra):
    return api.calcular(
        ctx, {**REF, **extra, "banco_duplo": {"ativo": True, "R2_min": r2_min, "R2_max": r2_max}}
    )


def test_centro_o2_acima_de_o() -> None:
    assert bd.ConfigBancoDuplo(1, 2).centro == (0.0, -500.0)  # y+ para baixo


def test_trecho_entre_arcos_confere_com_distancias(ctx) -> None:
    r = _calc(ctx, 2600, 2680)
    b = r["banco_duplo"]
    assert b["ok"] and b["avisos"] == [] and b["H"] == 1646
    for q, p, dist in zip(b["posicoes"], r["em_informada"], DIST_O2, strict=True):
        assert q["dist_O2"] == pytest.approx(math.hypot(p["Cx"], p["Cy"] + 500))
        assert q["dist_O2"] == pytest.approx(dist, abs=0.01)
        assert q["d_R1"] == pytest.approx(p["d_motor"])
        assert q["curso"] == pytest.approx(q["d_R1"] - q["d_R2"]) and q["curso"] > 0
        assert q["folga_R2"] == pytest.approx(q["R2"] - q["dist_O2"])
    # na ponta baixa do trecho o centro está sobre o arco R2 de O2 (e além de R1 de O)
    linha = ctx.padroes.linhas["180"]
    chapa, ranhuras = linha.como_padrao()
    motor = ctx.base.motores[r["motor"]["motor_id"]]
    e = EntradaCaso(
        "x", motor, chapa, {x.ranhura_n: x.como_ranhura("180") for x in ranhuras}, 2086, 2161, 1646
    )
    cfg = ConfigProjeto()
    for q in b["posicoes"]:
        cx, cy = bd.centro_em(e, cfg, 1646, -q["d_R2"])
        assert math.hypot(cx, cy + 500) == pytest.approx(q["R2"])
        assert math.hypot(cx, cy) > q["R1"]


def test_sem_trecho_gera_aviso_e_nao_muda_status(ctx) -> None:
    r = _calc(ctx, 2560, 2640)
    b = r["banco_duplo"]
    assert not b["ok"] and len(b["avisos"]) == 1 and "a 0 %" in b["avisos"][0]
    q0, q3 = b["posicoes"]
    assert not q0["dentro"] and q0["folga_R2"] == pytest.approx(-3.77, abs=0.01)
    assert q0["curso"] < 0 and q3["dentro"]
    assert r["status"] == "OK"
    ids = {p["id"]: p for p in r["desenho"]["primitivas"] if p["camada"] == "banco2"}
    assert ids["raio2-0"]["status"] == "AVISO" and "trecho-0" not in ids
    assert ids["trecho-3"]["status"] == "OK"


def test_r2_independente_de_r1(ctx) -> None:
    # mesmos R2 com outros R1: R2 não é derivado de R1
    r = _calc(ctx, 2600, 2680, R_max=2110)
    assert (r["banco_duplo"]["R2_min"], r["banco_duplo"]["R2_max"]) == (2600, 2680)


def test_desligado_nao_muda_resultado(ctx) -> None:
    base = api.calcular(ctx, REF)
    desl = api.calcular(ctx, {**REF, "banco_duplo": {"ativo": False, "R2_min": 1}})
    assert base["banco_duplo"] is None and desl["banco_duplo"] is None
    assert desl["status"] == base["status"]
    assert not any(p["camada"] == "banco2" for p in base["desenho"]["primitivas"])


def test_desenho_banco2(ctx) -> None:
    r = _calc(ctx, 2600, 2680)
    ids = {p["id"]: p for p in r["desenho"]["primitivas"] if p["camada"] == "banco2"}
    assert {"O2", "cota-O2", "arco-R2_min", "arco-R2_max", "raio2-0", "raio2-3"} <= set(ids)
    assert {"trecho-0", "trecho-3"} <= set(ids)
    assert ids["O2"]["c"] == [0.0, 500.0]  # vista CAD: Y para cima
    assert ids["arco-R2_min"]["c"] == [0.0, 500.0] and ids["arco-R2_min"]["r"] == 2600


def test_sem_altura_e_r2_invertido_no_nucleo(ctx) -> None:
    av = bd.avaliar(bd.ConfigBancoDuplo(2700, 2600), None, ConfigProjeto(), None, None)  # type: ignore[arg-type]
    assert not av.ok and av.posicoes == ()
    assert "maior que R2_max" in av.avisos[0] and "sem altura H" in av.avisos[1]


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        (
            {"ativo": True, "R2_min": "x"},
            {"banco_duplo.R2_min": "número inválido", "banco_duplo.R2_max": "obrigatório"},
        ),
        (
            {"ativo": True, "R2_min": 2700, "R2_max": 2600},
            {"banco_duplo.R2_max": "R2_max deve ser maior ou igual a R2_min"},
        ),
        (
            {"ativo": True, "R2_min": 0, "R2_max": 2600},
            {"banco_duplo.R2_min": "deve ser maior que zero"},
        ),
        ("sim", {"banco_duplo": "esperado um objeto"}),
    ],
)
def test_api_valida_r2(ctx, bruto, esperado) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular(ctx, {**REF, "banco_duplo": bruto})
    assert exc.value.erros == esperado


def test_saude_informa_deslocamento(ctx) -> None:
    assert api.saude(ctx)["fixos"]["dy_banco2"] == 500
