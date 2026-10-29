import math
from pathlib import Path

import pytest

from tensorcad import geometry as g
from tensorcad.geometry import Status
from tensorcad.loader import ErroCarga, carregar_diretorio, carregar_padroes
from tensorcad.models import ChapaPadrao, RanhuraPadrao
from tensorcad.projeto import (
    ConfigProjeto,
    EntradaCaso,
    cota_max_margem,
    ponto_base,
    posicao,
    resolver_caso,
)

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = carregar_diretorio(DATA)
PAD = carregar_padroes(DATA / "padrao")
M180 = BASE.motores["IEC-180M-4P"]
CH = PAD.chapa_para("180M")
CFG = ConfigProjeto()


def entrada(R_max: float = 2161, cota: float | None = 1646, motor=M180, R_min: float = 2086):
    return EntradaCaso(
        "C", motor, CH, PAD.ranhuras_de(CH.chapa_id, motor.carcaca), R_min, R_max, cota
    )


def test_padroes_carregados() -> None:
    assert CH.chapa_id == "CH-180" and CH.comprimento == 635
    assert PAD.chapa_para("180L") is CH and PAD.chapa_para("160M") is None
    rs = PAD.ranhuras_de("CH-180", "180M")
    assert rs[1].u_ini == -544.51 and rs[2].u_fim == -192.51  # u = −d


def test_desenho_de_referencia_reproduzido() -> None:
    a0, b0 = ponto_base(CFG, CH)
    assert (a0, b0) == pytest.approx((823.44, 722.0))
    p = posicao(entrada(), CFG, 2086, 1646)
    assert (p.Cx, p.Cy) == pytest.approx((681.53, 1971.53), abs=0.01)
    assert p.d_motor == pytest.approx(380.70, abs=0.01)
    assert (p.folga_neg, p.folga_pos) == pytest.approx((16.81, 41.19), abs=0.01)
    assert p.status is Status.OK
    assert math.hypot(p.Cx, p.Cy) == pytest.approx(2086)
    # no desenho (s = 0 relativo ao P antigo) as folgas medidas são 9 e 49
    t_L = (722.0 + 1646 - 2093.2792) / math.sin(math.radians(45))
    fn = (-t_L - M180.A / 2 - M180.K / 2) - (-544.51)
    assert fn == pytest.approx(9.0, abs=0.01)


def test_referencia_inviavel_com_deficit() -> None:
    r = resolver_caso(entrada(), CFG)
    assert r.status is Status.FORA_RANHURA and r.faixas_cota == ()
    assert r.margem_recomendada == pytest.approx(-12.74, abs=0.01)
    assert r.cota_recomendada == pytest.approx(1673.99, abs=0.01)
    pmin, pmax = r.em_recomendada
    # na cota de compromisso o déficit é igual nos dois extremos
    assert pmin.folga_neg == pytest.approx(pmax.folga_pos, abs=1e-4)
    assert "12.74" in r.mensagem
    assert r.em_informada[1].status is Status.FORA_RANHURA


def test_caso_viavel_faixa_e_recomendada() -> None:
    r = resolver_caso(entrada(R_max=2110), CFG)
    assert r.status is Status.OK
    ((lo, hi),) = r.faixas_cota
    assert (lo, hi) == pytest.approx((1632.07, 1661.96), abs=0.01)
    assert lo < r.cota_recomendada < hi
    assert r.margem_recomendada == pytest.approx(15.67, abs=0.01)
    # nas bordas da faixa uma das folgas zera
    for c in (lo, hi):
        ms = [posicao(entrada(R_max=2110), CFG, R, c).margem for R in (2086, 2110)]
        assert min(ms) == pytest.approx(0, abs=1e-5)
    assert all(p.status is Status.OK for p in r.em_recomendada)


def test_cota_otima_e_maximo_local() -> None:
    e = entrada(R_max=2110)
    c, m = cota_max_margem(e, CFG)
    for dc in (-0.5, 0.5):
        vizinho = min(posicao(e, CFG, R, c + dc).margem for R in (2086, 2110))
        assert vizinho <= m + 1e-9


def test_motor_incompativel() -> None:
    r = resolver_caso(entrada(motor=BASE.motores["IEC-160L-4P"]), CFG)
    assert r.status is Status.INCOMPATIVEL and r.cota_recomendada is None
    assert "carcacas_compat" in r.mensagem


def test_sem_ranhuras_e_sem_solucao() -> None:
    e = EntradaCaso("C", M180, CH, {}, 2086, 2161)
    r = resolver_caso(e, CFG)
    assert r.status is Status.OK and "AVISO" in r.mensagem and r.faixas_cota == ()
    # com a cota livre sempre há solução geométrica; R pequeno cai fora das ranhuras
    r = resolver_caso(entrada(R_min=50, R_max=60), CFG)
    assert r.status is Status.FORA_RANHURA
    assert posicao(entrada(), CFG, 50, 1646).status is Status.SEM_SOLUCAO


def test_modelos_padrao_validacao(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ranhura 1"):
        RanhuraPadrao(chapa_id="X", ranhura_n=1, d_ini=1, largura=17, origem="TODO")
    with pytest.raises(ValueError, match="ranhura 2"):
        RanhuraPadrao(chapa_id="X", ranhura_n=2, d_fim=1, largura=17, origem="TODO")
    with pytest.raises(ValueError, match="menor"):
        RanhuraPadrao(chapa_id="X", ranhura_n=1, d_ini=5, d_fim=1, largura=17, origem="TODO")
    ch = ChapaPadrao(
        chapa_id="X",
        carcacas_compat="200",
        theta_deg=45,
        e_apoio=0,
        comprimento=700,
        dx_L=1,
        cota_L_tubo=45,
        origem="TODO",
    )
    assert ch.como_chapa().aceita_carcaca("200L")
    (tmp_path / "chapas_padrao.csv").write_text(
        (DATA / "padrao" / "chapas_padrao.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "ranhuras_padrao.csv").write_text(
        "chapa_id;ranhura_n;d_ini;d_fim;largura;origem\nCH-NADA;1;;10;17;TODO\n",
        encoding="utf-8",
    )
    with pytest.raises(ErroCarga, match="não existe em chapas_padrao"):
        carregar_padroes(tmp_path)
    (tmp_path / "ranhuras_padrao.csv").unlink()
    with pytest.raises(ErroCarga, match="arquivo ausente"):
        carregar_padroes(tmp_path)


def test_h_da_chapa_padrao() -> None:
    assert g.calcular_h(M180.H, CH.e_apoio) == 180
