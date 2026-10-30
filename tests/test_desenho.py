import math
from pathlib import Path

import pytest

from tensorcad import desenho
from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.projeto import ConfigProjeto, EntradaCaso, resolver_caso

DADOS = Path(__file__).resolve().parents[1] / "data"
BASE = carregar_diretorio(DADOS)
PAD = carregar_padroes(DADOS / "padrao")
M = BASE.motores["IEC-180M-4P"]
CH = PAD.chapa_para("180M")
CFG = ConfigProjeto()


def _resultado(R_max: float = 2161, cota: float | None = 1646):
    e = EntradaCaso("C", M, CH, PAD.ranhuras_de(CH.chapa_id, M.carcaca), 2086, R_max, cota)
    return resolver_caso(e, CFG)


def _por_id(d):
    return {p["id"]: p for p in d["primitivas"]}


def test_elementos_e_camadas() -> None:
    d = desenho.gerar(_resultado(), CFG)
    ids = _por_id(d)
    esperados = {
        "O",
        "arco-R_min",
        "arco-R_max",
        "raio-0",
        "raio-3",
        "piso",
        "tubo",
        "tubo-L",
        "chapa",
        "L",
        "ranhura-1",
        "ranhura-2",
        "motor-0",
        "motor-3",
        "centro-0",
        "centro-3",
        "furo-0-inferior",
        "furo-0-superior",
        "cota-H",
        "cota-x-tubo",
        "cota-y-piso",
        "cota-dy",
        "cota-h",
    }
    assert esperados <= set(ids)
    assert {p["camada"] for p in d["primitivas"]} == set(desenho.CAMADAS)
    assert d["H"] == 1646


def test_posicoes_na_vista_do_cad() -> None:
    r = _resultado()
    ids = _por_id(desenho.gerar(r, CFG))
    p0 = r.em_informada[0]
    assert ids["centro-0"]["p"] == pytest.approx([-p0.Cx, -p0.Cy])
    assert ids["centro-0"]["p"] == pytest.approx([-681.53, -1971.53], abs=0.01)
    assert ids["tubo"]["c"] == pytest.approx([-465, -(767 + 1646)])
    # centro do apoio: quadrado a 45° (losango); O: octógono; linha de centro do apoio
    assert len(ids["tubo"]["pts"]) == 4 and ids["tubo"]["pts"][0][1] == ids["tubo"]["c"][1]
    assert len(ids["O"]["pts"]) == 8 and ids["O"]["c"] == [0.0, 0.0]
    eixo = ids["eixo-apoio"]
    assert eixo["p0"] == ids["tubo"]["c"] and eixo["p1"][0] == -465 and eixo["p1"][1] > 0
    assert ids["L"]["p"] == pytest.approx([-(465 + 358.44), -(767 + 1646 - 45)])
    assert ids["piso"]["p0"][1] == -767
    assert ids["arco-R_max"]["r"] == 2161
    assert math.hypot(*ids["raio-3"]["p1"]) == pytest.approx(2161)
    # h: do pé na chapa até o centro do motor, perpendicular à chapa
    h = ids["cota-h"]
    assert math.dist(h["p0"], h["p1"]) == pytest.approx(180)
    # furos do pé distam A da linha entre eles
    a = math.dist(ids["furo-0-inferior"]["c"], ids["furo-0-superior"]["c"])
    assert a == pytest.approx(M.A)
    # a chapa tem o comprimento cadastrado
    pts = ids["chapa"]["pts"]
    assert math.dist(pts[0], pts[1]) == pytest.approx(635)
    assert ids["motor-3"]["status"] == "OK"
    assert ids["ranhura-2"]["rotulo"] == "ranhura 2"  # pontas conhecidas: trecho completo


def test_sem_cota_usa_recomendada_e_limites() -> None:
    r = _resultado(R_max=2110, cota=None)
    d = desenho.gerar(r, CFG)
    assert d["H"] == r.cota_recomendada
    xmin, ymin, xmax, ymax = d["limites"]
    assert xmin < -1000 < xmax and ymin < -2400 and ymax >= 0
    assert desenho.altura_desenho(r) == r.cota_recomendada


def test_ranhura_completa_e_sem_altura() -> None:
    from tensorcad.models import Ranhura

    rs = {
        1: Ranhura(
            chapa_id="CH-180",
            carcaca="180M",
            ranhura_n=1,
            u_ini=-544.51,
            u_fim=-400,
            largura=17,
            origem="MEDIDO",
        ),
        2: Ranhura(
            chapa_id="CH-180",
            carcaca="180M",
            ranhura_n=2,
            u_ini=-330,
            u_fim=-192.51,
            largura=17,
            origem="MEDIDO",
        ),
    }
    e = EntradaCaso("C", M, CH, rs, 2086, 2161, 1646)
    ids = _por_id(desenho.gerar(resolver_caso(e, CFG), CFG))
    assert ids["ranhura-1"]["rotulo"] == "ranhura 1"
    assert math.dist(ids["ranhura-1"]["p0"], ids["ranhura-1"]["p1"]) == pytest.approx(144.51)
    sem = EntradaCaso("C", M, CH, {}, 2086, 2161)
    assert desenho.gerar(resolver_caso(sem, CFG), CFG) is None  # sem ranhuras: sem H
