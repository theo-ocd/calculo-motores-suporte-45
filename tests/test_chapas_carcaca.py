from pathlib import Path

import pytest

from tensorcad import ranhuras as rn
from tensorcad.geometry import Status
from tensorcad.loader import ErroCarga, carregar_padroes
from tensorcad.models import ChapaCarcaca, Motor

CAB = (
    "carcaca;theta_deg;e_apoio;comprimento_chapa;dx_L_tubo;dy_L_tubo;dist_L_ranhura;"
    "comprimento_ranhura;dist_entre_ranhuras;dist_ranhura_topo;largura_ranhura;origem;"
    "observacao\n"
)
BASE = dict(
    carcaca="200",
    theta_deg=45,
    e_apoio=0,
    comprimento_chapa=700,
    dx_L_tubo=380,
    dy_L_tubo=45,
    dist_L_ranhura=150,
    dist_ranhura_topo=100,
    origem="MEDIDO",
)


def _arquivo(tmp_path: Path, *linhas: str) -> Path:
    (tmp_path / "chapas_carcaca.csv").write_text(CAB + "\n".join(linhas) + "\n", "utf-8")
    return tmp_path


def test_cadeia_completa_gera_ranhuras() -> None:
    cc = ChapaCarcaca(**BASE, comprimento_ranhura=150, dist_entre_ranhuras=150)
    (i1, f1), (i2, f2) = cc.ranhuras_d()
    assert (i2, f2) == (150, 300)  # ranhura 2: perto de L
    assert (i1, f1) == (450, 600)  # ranhura 1: lado dos raios; 600 + 100 = 700
    chapa, rs = cc.como_padrao()
    assert chapa.chapa_id == "CH-200" and chapa.dx_L == 380 and chapa.cota_L_tubo == 45
    assert chapa.como_chapa().aceita_carcaca("200L")
    r1, r2 = (r.como_ranhura("200L") for r in rs)
    assert (r1.u_ini, r1.u_fim) == (-600, -450)  # u = −d
    assert (r2.u_ini, r2.u_fim) == (-300, -150)


def test_deduz_valor_faltante() -> None:
    so_tam = ChapaCarcaca(**BASE, comprimento_ranhura=150)
    assert so_tam.ranhuras_d() == ((450, 600), (150, 300))
    so_entre = ChapaCarcaca(**BASE, dist_entre_ranhuras=150)
    assert so_entre.ranhuras_d() == ((450, 600), (150, 300))
    nenhum = ChapaCarcaca(**BASE)
    assert nenhum.ranhuras_d() == ((None, 600), (150, None))


@pytest.mark.parametrize(
    ("extra", "msg"),
    [
        (dict(comprimento_ranhura=150, dist_entre_ranhuras=100), "cotas não fecham"),
        (dict(comprimento_ranhura=300), "2·comprimento_ranhura"),
        (dict(dist_entre_ranhuras=500), "dist_entre_ranhuras maior"),
        (dict(dist_ranhura_topo=600), "≥ comprimento_chapa"),
    ],
)
def test_cadeia_invalida(extra: dict, msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        ChapaCarcaca(**{**BASE, **extra})


def test_tolerancia_de_meio_milimetro() -> None:
    ChapaCarcaca(**BASE, comprimento_ranhura=150, dist_entre_ranhuras=150.4)


def test_tabela_do_repositorio() -> None:
    pad = carregar_padroes(Path(__file__).resolve().parents[1] / "data" / "padrao")
    assert list(pad.chapas) == ["CH-180"]
    a_preencher = [a for a in pad.avisos if "a preencher" in a.mensagem]
    assert [a.mensagem.split()[1] for a in a_preencher] == ["160", "200", "225", "250"]


def test_loader_erros_e_avisos(tmp_path: Path) -> None:
    ok = "200;45;0;700;380;45;150;150;150;100;;MEDIDO;"
    pad = carregar_padroes(_arquivo(tmp_path, ";;;;;;;;;;;TODO;", ok))
    assert "CH-200" in pad.chapas
    assert any(a.campo == "largura_ranhura" and a.linha == 3 for a in pad.avisos)
    with pytest.raises(ErroCarga) as exc:
        carregar_padroes(_arquivo(tmp_path, ok, ok, "225;45;0;700;380;45;150;150;100;100;;MEDIDO;"))
    txt = str(exc.value)
    assert "linha 3 campo 'carcaca': carcaça duplicada" in txt
    assert "linha 4" in txt and "cotas não fecham" in txt


def test_largura_vazia_nao_bloqueia_mas_avisa() -> None:
    cc = ChapaCarcaca(**BASE, comprimento_ranhura=150, dist_entre_ranhuras=150)
    chapa, rs = cc.como_padrao()
    ranhuras = {r.ranhura_n: r.como_ranhura("200L") for r in rs}
    m = Motor(motor_id="M", carcaca="200L", H=200, A=318, K=19)
    av = rn.avaliar(-375, m, chapa.como_chapa(), ranhuras)  # centro entre as ranhuras
    assert av.status is Status.OK
    assert any("largura da ranhura não informada" in x for x in av.mensagens)
