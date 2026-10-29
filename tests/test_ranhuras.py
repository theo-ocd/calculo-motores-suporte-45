import pytest

from tensorcad import geometry as g
from tensorcad import ranhuras as rn
from tensorcad.geometry import Status
from tensorcad.models import Chapa, Montagem, Motor, Ranhura

A_REF, B_REF = 548.72, 2093.28
MOTOR = Motor(motor_id="M160", carcaca="160M", H=160, A=254, K=15)
CHAPA = Chapa(chapa_id="CH", theta_deg=45, e_apoio=20, carcacas_compat="160M|160L", origem="MEDIDO")
S_REF1 = g.resolver_s(A_REF, B_REF, 0, 180, 45, 2086)  # ≈ 7.81


def sinteticas(largura: float = 20, folga_neg: float = 9, folga_pos: float = 49, chapa="CH"):
    r1, r2 = rn.ranhuras_calibradas(
        chapa, "160M", S_REF1, MOTOR.A, MOTOR.K, folga_neg, folga_pos, largura, comprimento=60
    )
    return {1: r1, 2: r2}


def test_folgas_formula() -> None:
    fn, fp = rn.folgas(10, 254, 15, -130, 200)
    assert fn == pytest.approx(10 - 127 - 7.5 + 130)
    assert fp == pytest.approx(200 - (10 + 127 + 7.5))


def test_calibracao_reproduz_folgas_medidas() -> None:
    rs = sinteticas()
    av = rn.avaliar(S_REF1, MOTOR, CHAPA, rs)
    assert av.status is Status.OK
    assert av.folga_neg == pytest.approx(9)
    assert av.folga_pos == pytest.approx(49)
    assert av.margem == pytest.approx(9)
    # lado invertido (pendência 2): também calibrável
    av2 = rn.avaliar(S_REF1, MOTOR, CHAPA, sinteticas(folga_neg=49, folga_pos=9))
    assert (av2.folga_neg, av2.folga_pos) == pytest.approx((49, 9))


def test_fora_ranhura() -> None:
    rs = sinteticas()
    av = rn.avaliar(S_REF1 - 20, MOTOR, CHAPA, rs)  # folga_neg = 9 - 20 < 0
    assert av.status is Status.FORA_RANHURA
    assert av.folga_neg == pytest.approx(-11)
    assert "ranhura 1" in av.mensagens[0]
    av = rn.avaliar(S_REF1 + 60, MOTOR, CHAPA, rs)
    assert av.status is Status.FORA_RANHURA and "ranhura 2" in av.mensagens[0]


def test_incompativel_largura_menor_que_K() -> None:
    av = rn.avaliar(S_REF1, MOTOR, CHAPA, sinteticas(largura=14))
    assert av.status is Status.INCOMPATIVEL
    assert "< K" in av.mensagens[0]


def test_incompativel_carcaca() -> None:
    m = Motor(motor_id="M132", carcaca="132S", H=132, A=216, K=12)
    av = rn.avaliar(0, m, CHAPA, sinteticas())
    assert av.status is Status.INCOMPATIVEL
    assert "carcacas_compat" in av.mensagens[0]


def test_sem_ranhuras_ok_com_aviso() -> None:
    av = rn.avaliar(S_REF1, MOTOR, CHAPA, {})
    assert av.status is Status.OK and av.margem is None
    assert "AVISO" in av.mensagens[0]


def test_sem_solucao_com_ranhuras() -> None:
    assert rn.avaliar(None, MOTOR, CHAPA, sinteticas()).status is Status.SEM_SOLUCAO


def test_s_admissivel() -> None:
    rs = sinteticas()
    s_min, s_max = rn.s_admissivel(rs, MOTOR)
    assert s_min == pytest.approx(S_REF1 - 9)
    assert s_max == pytest.approx(S_REF1 + 49)
    assert rn.s_admissivel({}, MOTOR) is None
    estreita = {
        1: Ranhura(
            chapa_id="CH",
            carcaca="160M",
            ranhura_n=1,
            u_ini=0,
            u_fim=10,
            largura=20,
            origem="MEDIDO",
        ),
        2: Ranhura(
            chapa_id="CH",
            carcaca="160M",
            ranhura_n=2,
            u_ini=0,
            u_fim=10,
            largura=20,
            origem="MEDIDO",
        ),
    }
    assert rn.s_admissivel(estreita, MOTOR) is None


def test_faixa_dy_consistente_com_varredura() -> None:
    s_min, s_max = rn.s_admissivel(sinteticas(), MOTOR)
    faixas = rn.faixa_dy(A_REF, B_REF, 180, 45, 2086, s_min, s_max)
    assert len(faixas) == 1
    lo, hi = faixas[0]
    assert lo < 0 < hi
    assert g.resolver_s(A_REF, B_REF, lo, 180, 45, 2086) == pytest.approx(s_max, abs=1e-6)
    assert g.resolver_s(A_REF, B_REF, hi, 180, 45, 2086) == pytest.approx(s_min, abs=1e-6)
    # força bruta
    for i in range(-2000, 2001):
        dy = i * 0.1
        s = g.resolver_s(A_REF, B_REF, dy, 180, 45, 2086)
        dentro = s is not None and s_min <= s <= s_max
        if abs(dy - lo) > 1e-3 and abs(dy - hi) > 1e-3:
            assert dentro == (lo <= dy <= hi), dy


def test_faixa_dy_vazia_e_domínio() -> None:
    assert rn.faixa_dy(A_REF, B_REF, 180, 45, 2086, 5000, 6000) == []
    # limites de s muito largos → faixa = domínio de existência de solução
    faixas = rn.faixa_dy(A_REF, B_REF, 180, 45, 2086, -1e9, 1e9)
    lo, hi = faixas[0]
    assert g.resolver_s(A_REF, B_REF, lo - 1, 180, 45, 2086) is None
    assert g.resolver_s(A_REF, B_REF, hi + 1, 180, 45, 2086) is None


def test_selecao_chapas_ordenada_por_margem() -> None:
    mont = Montagem(montagem_id="M", chapa_id="CH", a_ref=A_REF, b_ref=B_REF, origem="CALCULADO")
    chapas = [
        Chapa(chapa_id="CH", theta_deg=45, e_apoio=20, carcacas_compat="160", origem="MEDIDO"),
        Chapa(
            chapa_id="CH-LARGA", theta_deg=45, e_apoio=20, carcacas_compat="160", origem="MEDIDO"
        ),
        Chapa(
            chapa_id="CH-ESTREITA", theta_deg=45, e_apoio=20, carcacas_compat="160", origem="MEDIDO"
        ),
        Chapa(
            chapa_id="CH-OUTRA", theta_deg=45, e_apoio=20, carcacas_compat="132", origem="MEDIDO"
        ),
        Chapa(
            chapa_id="CH-SEM-RANHURA",
            theta_deg=45,
            e_apoio=20,
            carcacas_compat="160",
            origem="MEDIDO",
        ),
    ]
    ranhuras = [
        *sinteticas().values(),
        *sinteticas(folga_neg=30, folga_pos=30, chapa="CH-LARGA").values(),
        *sinteticas(largura=10, chapa="CH-ESTREITA").values(),
    ]
    ops = rn.selecionar_chapas(MOTOR, mont, chapas, ranhuras, R=2086)
    ids = [o.chapa_id for o in ops]
    assert ids[:3] == ["CH-LARGA", "CH", "CH-SEM-RANHURA"]
    assert {o.chapa_id for o in rn.compativeis(ops)} == {"CH-LARGA", "CH", "CH-SEM-RANHURA"}
    assert ops[0].margem == pytest.approx(30)
    status = {o.chapa_id: o.status for o in ops}
    assert status["CH-ESTREITA"] is Status.INCOMPATIVEL
    assert status["CH-OUTRA"] is Status.INCOMPATIVEL


def test_selecao_sem_solucao() -> None:
    mont = Montagem(montagem_id="M", chapa_id="CH", a_ref=A_REF, b_ref=B_REF, origem="CALCULADO")
    ops = rn.selecionar_chapas(MOTOR, mont, [CHAPA], [], R=10)
    assert ops[0].status is Status.SEM_SOLUCAO


def test_calibracao_sem_comprimento_deixa_pontas_internas_vazias() -> None:
    r1, r2 = rn.ranhuras_calibradas("CH-REF", "160L", 0, 254, 15, 9, 49, 17)
    assert (r1.u_ini, r1.u_fim) == (-143.5, None)
    assert (r2.u_ini, r2.u_fim) == (None, 183.5)
