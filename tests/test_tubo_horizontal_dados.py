"""T0 do layout tubo horizontal: tabela de parâmetros e conferência da pilha."""

import csv
from pathlib import Path

import pytest

ARQ = Path(__file__).resolve().parents[1] / "data" / "padrao" / "tubo_horizontal.csv"


def _tabela() -> dict[str, dict[str, str]]:
    with ARQ.open(encoding="utf-8", newline="") as f:
        return {r["parametro"]: r for r in csv.DictReader(f, delimiter=";")}


def test_tabela_bem_formada() -> None:
    t = _tabela()
    for nome, r in t.items():
        assert r["origem"] in {"MEDIDO", "CALCULADO", "HIPOTESE", "TODO"}, nome
        assert (r["valor"] == "") == (r["origem"] == "TODO"), nome
    assert {"comprimento_tubo", "altura_tubo_invertido"} <= {
        n for n, r in t.items() if r["origem"] == "TODO"
    }


def test_valores_informados_pelo_usuario() -> None:
    v = {n: float(r["valor"]) for n, r in _tabela().items() if r["valor"]}
    assert v == {
        "altura_tubo": 1375,
        "espessura_tubo": 80,
        "espessura_porca": 27.5,
        "espessura_chapa": 15,
        "g_min": 30,
        "g_max": 150,
        "acrescimo_furacao": 75,
    }


@pytest.mark.parametrize(("H", "esperado"), [(250, 910.0), (225, 935.0)])
def test_pilha_do_desenho_de_referencia(H: float, esperado: float) -> None:
    # centro do motor abaixo do topo da laje com g = 65 (docs/tubo_horizontal.md, P16)
    v = {n: float(r["valor"]) for n, r in _tabela().items() if r["valor"]}
    y = v["altura_tubo"] - v["espessura_tubo"] - 2 * v["espessura_porca"] - 65
    assert y - v["espessura_chapa"] - H == esperado
