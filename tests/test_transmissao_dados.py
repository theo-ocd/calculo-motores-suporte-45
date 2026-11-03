"""S0 dos setups: tabela de transmissão (polias, rpm) e conferência com a planilha."""

import csv
import math
from pathlib import Path

import pytest

ARQ = Path(__file__).resolve().parents[1] / "data" / "padrao" / "transmissao.csv"


def _grupos() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    with ARQ.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            assert r["origem"] in {"MEDIDO", "CALCULADO", "HIPOTESE", "TODO"}
            out.setdefault(r["grupo"], []).append(float(r["valor"]))
    return out


def test_listas_confirmadas() -> None:
    g = _grupos()
    assert g["polia_maquina"] == [355]
    assert g["polia_motor"] == [
        125,
        132,
        140,
        150,
        160,
        170,
        180,
        190,
        200,
        212,
        224,
        236,
        250,
        280,
    ]
    assert set(g["rpm_motor"]) >= {900, 1200}
    assert (g["tensionamento_min"], g["tensionamento_max"]) == ([0], [3])


def _a0(L: float, D: float, d: float) -> float:
    b = (L - math.pi / 2 * (D + d)) / 4
    return b + math.sqrt(b * b - (D - d) ** 2 / 8)


@pytest.mark.parametrize(
    ("L", "d", "planilha"),
    [
        (5000, 170, (2086, 2136, 2161)),
        (5500, 170, (2336, 2391, 2418)),
        (5000, 125, (2120, 2170, 2195)),
    ],
)
def test_formula_confere_com_a_planilha(L, d, planilha) -> None:
    a0 = _a0(L, 355, d)
    calc = (a0, a0 + L * 0.02 / 2, a0 + L * 0.03 / 2)
    assert [round(v) for v in calc] == list(planilha)
