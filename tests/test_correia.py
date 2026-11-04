"""S1 — cálculo da correia conferido com a planilha "Belt transmission – Riemenberechnung"."""

import pytest

from tensorcad import correia as cr

POLIAS = [125, 132, 140, 150, 160, 170, 180, 190, 200, 212, 224, 236, 250, 280]
# valores da planilha (inteiros, como ela mostra), polia da máquina 355
PLANILHA = {
    5000: {
        0.00: [2120, 2115, 2108, 2101, 2093, 2086, 2078, 2070, 2063, 2053, 2044, 2035, 2024, 2001],
        0.02: [2170, 2165, 2158, 2151, 2143, 2136, 2128, 2120, 2113, 2103, 2094, 2085, 2074, 2051],
        0.03: [2195, 2190, 2183, 2176, 2168, 2161, 2153, 2145, 2138, 2128, 2119, 2110, 2099, 2076],
    },
    5500: {
        0.00: [2370, 2365, 2359, 2351, 2343, 2336, 2328, 2320, 2313, 2304, 2294, 2285, 2274, 2251],
        0.02: [2425, 2420, 2414, 2406, 2398, 2391, 2383, 2375, 2368, 2359, 2349, 2340, 2329, 2306],
        0.03: [2453, 2447, 2441, 2434, 2426, 2418, 2411, 2403, 2395, 2386, 2377, 2368, 2357, 2333],
    },
}
RPM_1200 = [423, 446, 473, 507, 541, 575, 608, 642, 676, 717, 757, 798, 845, 946]


@pytest.mark.parametrize("L", sorted(PLANILHA))
@pytest.mark.parametrize("tensao", [0.0, 0.02, 0.03])
def test_distancia_entre_eixos_igual_a_planilha(L, tensao) -> None:
    calc = [round(cr.distancia_eixos(cr.Correia(355, d, L), tensao)) for d in POLIAS]
    assert calc == PLANILHA[L][tensao]


def test_raios_e_rpm() -> None:
    c = cr.Correia(355, 170, 5000)
    r = cr.raios(c)
    assert (r.R_min, r.R_info, r.R_max) == pytest.approx((2085.61, 2135.61, 2160.61), abs=0.01)
    assert r.R_max - r.R_min == pytest.approx(5000 * 0.03 / 2)
    assert [round(cr.rpm_maquina(1200, cr.Correia(355, d, 5000))) for d in POLIAS] == RPM_1200


def test_sufixo_sem_perfil() -> None:
    assert cr.sufixo(cr.Correia(355, 170, 5000)) == "-170-5000"
    assert cr.sufixo(cr.Correia(355, 212, 5300.5)) == "-212-5300.5"


@pytest.mark.parametrize(("L", "trecho"), [(1000, "curta demais"), (0, "maiores que zero")])
def test_correia_invalida(L, trecho) -> None:
    with pytest.raises(ValueError, match=trecho):
        cr.distancia_eixos(cr.Correia(355, 170, L))
