import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tensorcad import geometry as g
from tensorcad.geometry import Status

A, B = 548.72, 2093.28
TOL = 0.1

# caso: (R, Δy, h, θ) → s esperado
REFS = {
    "REF-1": ((2086, 0, 180, 45), 7.81),
    "REF-2": ((2161, 0, 180, 45), 90.86),
    "REF-3": ((2086, 100, 180, 45), -98.98),
    "REF-4": ((2086, 0, 150, 45), -7.08),
    "REF-5": ((2086, 0, 180, 40), 24.28),
}


def test_calibrar_P_referencia() -> None:
    a, b = g.calibrar_P(465 + 211, 1966, 180, 45)
    assert a == pytest.approx(548.72, abs=0.01)
    assert b == pytest.approx(2093.28, abs=0.01)


def test_calcular_h() -> None:
    assert g.calcular_h(160, 20) == 180
    assert g.calcular_h(132, 20, 18) == 150


@pytest.mark.parametrize("caso", sorted(REFS))
def test_s_referencia(caso: str) -> None:
    (R, dy, h, th), esperado = REFS[caso]
    assert g.resolver_s(A, B, dy, h, th, R) == pytest.approx(esperado, abs=TOL)
    sol = g.resolver(A, B, dy, h, th, R)
    assert sol.status is Status.OK
    assert sol.s == pytest.approx(esperado, abs=TOL)


@pytest.mark.parametrize("caso", sorted(REFS))
def test_modulo_C_igual_R(caso: str) -> None:
    (R, dy, h, th), _ = REFS[caso]
    sol = g.resolver(A, B, dy, h, th, R)
    assert math.hypot(sol.Cx, sol.Cy) == pytest.approx(R, abs=1e-6)


def test_centro_referencia_coincide_com_desenho() -> None:
    # Com Δy=0, h=180, θ=45 e s=0, o centro volta ao ponto medido (676, 1966).
    assert g.centro_motor(A, B, 0, 180, 45, 0) == pytest.approx((676, 1966), abs=0.01)


def test_sensibilidades_ref1() -> None:
    ds_ddy, ds_dh = g.sensibilidades(A, B, 0, 180, 45, 2086)
    assert ds_ddy == pytest.approx(-1.051, abs=1e-3)
    assert ds_dh == pytest.approx(0.486, abs=1e-3)
    sol = g.resolver(A, B, 0, 180, 45, 2086)
    assert (sol.ds_ddy, sol.ds_dh) == (ds_ddy, ds_dh)


def test_sem_solucao_R_pequeno() -> None:
    sol = g.resolver(A, B, 0, 180, 45, 100)
    assert sol.status is Status.SEM_SOLUCAO
    assert sol.s is None and sol.Cx is None and sol.ds_ddy is None
    assert g.resolver_s(A, B, 0, 180, 45, 100) is None
    assert g.sensibilidades(A, B, 0, 180, 45, 100) is None


def test_tangencia_sem_derivadas() -> None:
    _, d = g.projecoes(A, B, 0, 180, 45)
    R = abs(d)
    sol = g.resolver(A, B, 0, 180, 45, R)
    assert sol.status is Status.OK
    assert sol.ds_ddy is None and sol.ds_dh is None


def test_para_cad() -> None:
    assert g.para_cad(676, 1966, 10000, 5000) == (10000 - 676, 5000 - 1966)


@settings(max_examples=200, deadline=None)
@given(
    dy=st.floats(-300, 300),
    h=st.floats(80, 320),
    th=st.floats(20, 70),
    R=st.floats(1900, 2400),
)
def test_derivadas_vs_diferencas_finitas(dy: float, h: float, th: float, R: float) -> None:
    _, d = g.projecoes(A, B, dy, h, th)
    if R * R - d * d < (0.05 * R) ** 2:  # longe da tangência (derivada singular)
        return
    ds_ddy, ds_dh = g.sensibilidades(A, B, dy, h, th, R)
    eps = 1e-3

    def s(dy_: float, h_: float) -> float:
        return g.resolver_s(A, B, dy_, h_, th, R)

    fd_dy = (s(dy + eps, h) - s(dy - eps, h)) / (2 * eps)
    fd_h = (s(dy, h + eps) - s(dy, h - eps)) / (2 * eps)
    assert ds_ddy == pytest.approx(fd_dy, rel=1e-4, abs=1e-6)
    assert ds_dh == pytest.approx(fd_h, rel=1e-4, abs=1e-6)


def test_calcular_h_override_tem_prioridade() -> None:
    assert g.calcular_h(160, 20, h_override=150) == 150
    assert g.calcular_h(160, 20, 30, h_override=150) == 150
