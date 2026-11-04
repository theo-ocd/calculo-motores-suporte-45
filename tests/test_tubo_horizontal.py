"""T2 — núcleo do layout tubo horizontal."""

import math
from pathlib import Path

import pytest

from tensorcad import tubo_horizontal as th
from tensorcad.geometry import Status
from tensorcad.loader import carregar_diretorio, carregar_parametros_th

DADOS = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def motores():
    return carregar_diretorio(DADOS).motores


@pytest.fixture(scope="module")
def par() -> th.ParametrosTH:
    return th.ParametrosTH(comprimento_tubo=2000, **carregar_parametros_th(DADOS / "padrao"))


def test_parametros_da_tabela(par) -> None:
    assert (par.espessura_tubo, par.espessura_porca, par.espessura_chapa) == (80, 27.5, 15)
    assert (par.g_min, par.g_max, par.acrescimo_furacao) == (30, 150, 75)


def test_parametros_invalidos(tmp_path: Path) -> None:
    (tmp_path / "tubo_horizontal.csv").write_text(
        "parametro;valor;unidade;origem;observacao\ng_min;abc;mm;MEDIDO;\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="g_min"):
        carregar_parametros_th(tmp_path)


def test_pilha_de_referencia(par, motores) -> None:
    m = motores["IEC-250M-4P"]
    assert th.pilha(par, m) == 55 + 15 + 250  # do topo do tubo (normal)
    assert th.y_motor(par, m, 1295, 65) == 910  # desenho: 1375 até o fundo − 80 (P16)
    assert th.x_max(par, m) == 1000 - (406 + 75) / 2
    # raio com x = 248 (cota do desenho) e y = 910
    assert th.raio(par, 248, 910) == pytest.approx(math.hypot(713, 1677))


def test_invertido_desce_a_partir_do_fundo_do_tubo(par, motores) -> None:
    m = motores["IEC-180L-4P"]
    inv = th.ParametrosTH(comprimento_tubo=2000, invertido=True)
    assert th.pilha(inv, m) == 55 + 15 + 180
    assert th.y_motor(inv, m, 1100, 65) == 1100 + 250 + 65
    assert th.y_motor(par, m, 1295, 65) == 1295 - 250 - 65


def test_posicao_sobre_o_arco(par, motores) -> None:
    m = motores["IEC-250M-4P"]
    p = th.posicao(par, m, 1839, 1295)
    assert p.status is Status.OK
    assert th.raio(par, p.x, p.y_motor) == pytest.approx(1839)
    xm = th.x_max(par, m)
    assert p.folga_g == pytest.approx(min(p.g - 30, 150 - p.g))
    assert p.folga_x == pytest.approx(min(p.x, xm - p.x))
    # folgas relativas equilibradas: g e x no mesmo ponto proporcional do curso
    assert p.folga_rel == pytest.approx(p.folga_g / 60, abs=1e-4)
    assert p.folga_rel == pytest.approx(p.folga_x / (xm / 2), abs=1e-4)


def test_resolver_referencia_250(par, motores) -> None:
    e = th.EntradaTH("REF", motores["IEC-250M-4P"], 1839, 1894, 1295)
    r = th.resolver(par, e)
    assert r.status is Status.OK
    ((lo, hi),) = r.faixas_altura
    assert lo == pytest.approx(1027.93, abs=0.01) and hi == pytest.approx(1482.24, abs=0.01)
    assert r.altura_recomendada == pytest.approx(1306.96, abs=0.05)
    assert r.margem_recomendada == pytest.approx(52.68, abs=0.01)
    # P19: de 0 % a 3 % o tensionamento usa g e x, simétricos nos seus cursos
    p0, p3 = r.em_recomendada
    xm = th.x_max(par, e.motor)
    assert p0.g - 90 == pytest.approx(90 - p3.g, abs=0.05) and p3.g < p0.g
    assert p0.x == pytest.approx(xm - p3.x, abs=0.05) and p3.x > p0.x
    assert p0.x > 0 and p3.x > 0  # motor sempre do mesmo lado
    i0, i3 = r.em_informada
    assert (i0.altura_tubo, i3.altura_tubo) == (1295, 1295)
    assert i0.status is Status.OK and i3.x > i0.x  # 3 % mais longe de O1


def test_fora_porcas_quando_o_tubo_e_curto(motores) -> None:
    par = th.ParametrosTH(comprimento_tubo=900)  # x_max = 209,5
    e = th.EntradaTH("C", motores["IEC-250M-4P"], 1839, 2200)
    r = th.resolver(par, e)
    assert r.status is Status.FORA_PORCAS and r.faixas_altura == ()
    assert r.margem_recomendada < 0
    assert "faltam" in r.mensagem
    assert any(p.status is Status.FORA_PORCAS for p in r.em_recomendada)


def test_chapa_maior_que_o_tubo(motores) -> None:
    par = th.ParametrosTH(comprimento_tubo=400)
    r = th.resolver(par, th.EntradaTH("X", motores["IEC-250M-4P"], 1839, 1894))
    assert r.status is Status.INCOMPATIVEL and "não cabe" in r.mensagem


def test_invertido_resolve(motores) -> None:
    par = th.ParametrosTH(comprimento_tubo=2000, invertido=True)
    r = th.resolver(par, th.EntradaTH("INV", motores["IEC-180L-4P"], 2300, 2369))
    assert r.status is Status.OK
    for p in r.em_recomendada:
        assert th.raio(par, p.x, p.y_motor) == pytest.approx(p.R)
        assert par.g_min <= p.g <= par.g_max and p.x >= 0
    # altura do tubo fica acima do motor: y_motor = altura + pilha + g
    p0 = r.em_recomendada[0]
    assert p0.y_motor == pytest.approx(r.altura_recomendada + 250 + p0.g)


def test_motor_nao_troca_de_lado(par, motores) -> None:
    # R 1650 com o topo do tubo em 1295: mesmo com g = 150 o ponto do arco fica com x < 0
    p = th.posicao(par, motores["IEC-250M-4P"], 1650, 1295)
    assert p.status is Status.FORA_PORCAS
    assert p.x < 0 and any("lado de O1" in m for m in p.mensagens)


# --------------------------------------------------------------------------- T3: invertido


def test_invertido_desenho_de_referencia(motores) -> None:
    """Desenho do invertido (carcaça 180): centro 2242 − 767 = 1475 abaixo da laje, x = 93."""
    inv = th.ParametrosTH(comprimento_tubo=2000, invertido=True)
    m = motores["IEC-180L-4P"]
    assert th.raio(inv, 93, 1475) == pytest.approx(math.hypot(558, 2242))
    # fundo da chapa 170 + 1120 = 1290 abaixo da laje: altura + 2 porcas + g + chapa = 1290
    altura, g = 1155.0, 65.0  # altura + g = 1220
    assert altura + 2 * inv.espessura_porca + g + inv.espessura_chapa == 1290
    assert th.y_motor(inv, m, altura, g) == 1290 + m.H == 1470  # desenho: 1475 (Δ 5)


def test_invertido_e_normal_mesmas_posicoes_alturas_diferentes(motores) -> None:
    m = motores["IEC-180L-4P"]
    e = th.EntradaTH("C", m, 2310.4, 2379.7)
    nor = th.resolver(th.ParametrosTH(comprimento_tubo=2000), e)
    inv = th.resolver(th.ParametrosTH(comprimento_tubo=2000, invertido=True), e)
    assert nor.status is inv.status is Status.OK
    # o centro do motor é o mesmo; muda onde fica o tubo
    for pn, pi in zip(nor.em_recomendada, inv.em_recomendada, strict=True):
        assert (pn.x, pn.y_motor) == pytest.approx((pi.x, pi.y_motor), abs=0.05)
        k_n = th.pilha(nor.parametros, m)
        k_i = th.pilha(inv.parametros, m)
        assert nor.altura_recomendada - inv.altura_recomendada == pytest.approx(
            k_n + pn.g + k_i + pi.g, abs=0.05
        )
    assert inv.altura_recomendada == pytest.approx(1067.28, abs=0.05)
    assert nor.altura_recomendada == pytest.approx(1747.28, abs=0.05)
    # tensionar (0 % → 3 %): no normal g diminui, no invertido g aumenta
    n0, n3 = nor.em_recomendada
    i0, i3 = inv.em_recomendada
    assert n3.g < n0.g and i3.g > i0.g


# --------------------------------------------------------------------------- T4: banco duplo


def _ref(motores, b2=None):
    from tensorcad.banco_duplo import ConfigBancoDuplo

    par = th.ParametrosTH(comprimento_tubo=2000)
    cfg = None if b2 is None else ConfigBancoDuplo(*b2)
    return par, th.resolver(par, th.EntradaTH("REF", motores["IEC-250M-4P"], 1839, 1894, 1295, cfg))


def test_banco_duplo_folgado_nao_muda_nada(motores) -> None:
    _, sem = _ref(motores)
    par, com = _ref(motores, (2400, 2470))  # R2 folgado
    assert com.status is Status.OK
    assert com.altura_recomendada == pytest.approx(sem.altura_recomendada, abs=1e-3)
    assert [v for f in com.faixas_altura for v in f] == pytest.approx(
        [v for f in sem.faixas_altura for v in f], abs=1e-3
    )
    for p in com.em_recomendada:
        assert p.folga_R2 == pytest.approx(
            p.R2 - th.raio_o2(par, com.entrada.banco2, p.x, p.y_motor)
        )
        assert p.folga_R2 > 0 and th.raio(par, p.x, p.y_motor) == pytest.approx(p.R)


def test_banco_duplo_corta_faixa_e_desloca_recomendada(motores) -> None:
    _, r = _ref(motores, (2349, 2420))  # R2349 do desenho: corta a faixa
    ((lo, hi),) = r.faixas_altura
    assert lo == pytest.approx(1027.93, abs=0.05) and hi == pytest.approx(1410.67, abs=0.1)
    assert r.altura_recomendada == pytest.approx(1306.96, abs=0.05)
    _, r = _ref(motores, (2300, 2380))
    assert r.status is Status.OK
    assert r.altura_recomendada == pytest.approx(1173.43, abs=0.1)
    assert min(p.folga_R2 for p in r.em_recomendada) == pytest.approx(0, abs=0.05)
    assert all(p.status is Status.OK for p in r.em_recomendada)


def test_banco_duplo_sem_altura_fica_fora_tensionamento(motores) -> None:
    _, r = _ref(motores, (2240, 2300))
    assert r.status is Status.FORA_TENSIONAMENTO and r.faixas_altura == ()
    assert "tensionamento para banco duplo" in r.mensagem
    assert all(p.folga_R2 < 0 for p in r.em_recomendada)
    i0, _ = r.em_informada
    assert any("O2" in m for m in i0.mensagens)


def test_o2_fica_540_acima_de_o1(motores) -> None:
    from tensorcad.banco_duplo import ConfigBancoDuplo

    par = th.ParametrosTH(comprimento_tubo=2000)
    # motor na vertical de O1 a 1000 abaixo dele: 1540 de O2 (540 acima de O1)
    assert th.raio_o2(par, ConfigBancoDuplo(1, 1), -465, 1000 - 767) == pytest.approx(1540)


# --------------------------------------------------------------------------- g manual


def test_posicao_em_g_anda_sobre_o_arco(par, motores) -> None:
    m = motores["IEC-250M-4P"]
    p = th.posicao_em_g(par, m, 1839, 1295, 65)
    assert p.status is Status.OK and p.g == 65
    assert p.y_motor == 910 and th.raio(par, p.x, p.y_motor) == pytest.approx(1839)
    assert p.x == pytest.approx(289.71, abs=0.01)
    # +1 mm em g sobe o motor 1 mm e o arco empurra x para fora
    q = th.posicao_em_g(par, m, 1839, 1295, 66)
    assert q.y_motor == 909 and q.x > p.x
    # g fora do curso: FORA_PORCAS
    f = th.posicao_em_g(par, m, 1839, 1295, 160)
    assert f.status is Status.FORA_PORCAS and "fora de 30–150" in f.mensagens[0]


def test_g_manual_vale_so_na_altura_informada(par, motores) -> None:
    m = motores["IEC-250M-4P"]
    r = th.resolver(par, th.EntradaTH("C", m, 1839, 1894, 1295, g_manual=(65, None)))
    auto = th.resolver(par, th.EntradaTH("C", m, 1839, 1894, 1295))
    i0, i3 = r.em_informada
    assert i0.g == 65 and i3.g == pytest.approx(auto.em_informada[1].g)
    # recomendada, faixa e status do caso não mudam
    assert r.altura_recomendada == pytest.approx(auto.altura_recomendada)
    assert r.em_recomendada[0].g == pytest.approx(auto.em_recomendada[0].g)
    assert r.status is auto.status
    # banco duplo também é conferido no ajuste manual
    from tensorcad.banco_duplo import ConfigBancoDuplo

    b = th.resolver(
        par, th.EntradaTH("C", m, 1839, 1894, 1295, ConfigBancoDuplo(2300, 2380), (65, None))
    )
    assert b.em_informada[0].folga_R2 == pytest.approx(
        2300 - th.raio_o2(par, b.entrada.banco2, b.em_informada[0].x, 910)
    )
