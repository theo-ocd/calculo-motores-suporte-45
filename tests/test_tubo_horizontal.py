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
    assert th.pilha(par, m) == 80 + 55 + 15 + 250
    assert th.y_motor(par, m, 1375, 65) == 910  # desenho de referência (P16)
    assert th.x_max(par, m) == 1000 - (406 + 75) / 2
    # raio com x = 248 (cota do desenho) e y = 910
    assert th.raio(par, 248, 910) == pytest.approx(math.hypot(713, 1677))


def test_invertido_desce_a_partir_do_fundo_do_tubo(par, motores) -> None:
    m = motores["IEC-180L-4P"]
    inv = th.ParametrosTH(comprimento_tubo=2000, invertido=True)
    assert th.pilha(inv, m) == 55 + 15 + 180
    assert th.y_motor(inv, m, 1100, 65) == 1100 + 250 + 65
    assert th.y_motor(par, m, 1375, 65) == 1375 - 330 - 65


def test_posicao_sobre_o_arco(par, motores) -> None:
    m = motores["IEC-250M-4P"]
    p = th.posicao(par, m, 1839, 1375)
    assert p.status is Status.OK
    assert p.g == pytest.approx(90, abs=1e-3)  # meio do curso das porcas
    assert th.raio(par, p.x, p.y_motor) == pytest.approx(1839)
    assert p.folga_g == pytest.approx(60, abs=1e-3)
    assert p.folga_x == pytest.approx(th.x_max(par, m) - abs(p.x))


def test_resolver_referencia_250(par, motores) -> None:
    e = th.EntradaTH("REF", motores["IEC-250M-4P"], 1839, 1894, 1375)
    r = th.resolver(par, e)
    assert r.status is Status.OK
    ((lo, hi),) = r.faixas_altura
    assert lo == pytest.approx(1107.93, abs=0.01) and hi == pytest.approx(1622.0, abs=0.01)
    assert r.margem_recomendada == pytest.approx(60, abs=1e-3)
    # desempate: curso em x centrado no tubo entre 0 % e 3 %
    p0, p3 = r.em_recomendada
    assert p0.x == pytest.approx(-p3.x, abs=0.05)
    assert r.altura_recomendada == pytest.approx(1527.49, abs=0.05)
    i0, i3 = r.em_informada
    assert (i0.altura_tubo, i3.altura_tubo) == (1375, 1375)
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
        assert par.g_min <= p.g <= par.g_max
    # altura do tubo fica acima do motor: y_motor = altura + pilha + g
    p0 = r.em_recomendada[0]
    assert p0.y_motor == pytest.approx(r.altura_recomendada + 250 + p0.g)
