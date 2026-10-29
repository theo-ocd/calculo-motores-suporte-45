from pathlib import Path

import pytest

from tensorcad import geometry as g
from tensorcad import processamento as proc
from tensorcad.loader import carregar_diretorio


@pytest.fixture(scope="module")
def base(data_dir: Path):
    return carregar_diretorio(data_dir)


@pytest.fixture(scope="module")
def data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def test_parametros_com_overrides(base) -> None:
    p = proc.parametros(base.casos["REF-4"], base)
    assert (p.h, p.theta_deg, p.R) == (150, 45, 2086)
    p = proc.parametros(base.casos["REF-5"], base)
    assert (p.h, p.theta_deg) == (180, 40)
    assert proc.parametros(base.casos["REF-2"], base).R == 2161


def test_lote_identico_ao_nucleo(base) -> None:
    for r in proc.calcular_todos(base):
        p = proc.parametros(base.casos[r.caso_id], base)
        sol = g.resolver(p.a, p.b, p.delta_y, p.h, p.theta_deg, p.R)
        assert (r.s, r.Cx, r.Cy, r.ds_ddy, r.ds_dh) == (
            sol.s,
            sol.Cx,
            sol.Cy,
            sol.ds_ddy,
            sol.ds_dh,
        )
        assert r.X_cad is None and "X_O_cad" in r.mensagem


def test_X_cad_quando_origem_cad_informada(base) -> None:
    from dataclasses import replace

    p = replace(proc.parametros(base.casos["REF-1"], base), X_O_cad=10000.0, Y_O_cad=5000.0)
    r = proc.calcular(p)
    assert r.X_cad == pytest.approx(10000 - r.Cx)
    assert r.Y_cad == pytest.approx(5000 - r.Cy)
    assert r.mensagem == ""


def test_sem_solucao_e_tangencia(base) -> None:
    from dataclasses import replace

    p = proc.parametros(base.casos["REF-1"], base)
    r = proc.calcular(replace(p, R=100))
    assert r.status == "SEM_SOLUCAO" and r.s is None and "R²<d_perp²" in r.mensagem
    _, d = g.projecoes(p.a, p.b, p.delta_y, p.h, p.theta_deg)
    r = proc.calcular(replace(p, R=abs(d)))
    assert r.status == "OK" and "tangência" in r.mensagem


def test_faixa_e_varredura(base) -> None:
    assert proc.faixa(-100, 100, 10) == [float(v) for v in range(-100, 101, 10)]
    assert proc.faixa(0, 1, 0.3) == pytest.approx([0, 0.3, 0.6, 0.9])
    with pytest.raises(ValueError):
        proc.faixa(0, 10, 0)
    with pytest.raises(ValueError):
        proc.faixa(10, 0, 1)
    serie = proc.varredura_dy(base.casos["VAR-BASE"], base, -100, 100, 50)
    assert [round(r.s, 2) for r in serie] == [111.29, 59.95, 7.82, -45.15, -98.96]
