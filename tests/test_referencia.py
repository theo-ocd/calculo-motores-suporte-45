"""Compara o núcleo com data/testes_referencia.csv (tolerâncias da própria tabela)."""

import csv
from pathlib import Path

import pytest

from tensorcad import processamento as proc
from tensorcad import ranhuras as rn
from tensorcad.loader import carregar_diretorio

DATA = Path(__file__).resolve().parents[1] / "data"
with (DATA / "testes_referencia.csv").open(encoding="utf-8") as f:
    LINHAS = list(csv.DictReader(f, delimiter=";"))


@pytest.fixture(scope="module")
def calculados() -> dict[str, dict[str, object]]:
    base = carregar_diretorio(DATA)
    out = {r.caso_id: r.model_dump() for r in proc.calcular_todos(base)}
    # FUNC-FOLGA-S0: função de folgas com s=0, motor 160L e ranhuras de CH-REF
    m = base.motores["IEC-160L-4P"]
    rs = base.ranhuras_de("CH-REF", m.carcaca)
    fn, fp = rn.folgas(0.0, m.A, m.K, rs[1].u_ini, rs[2].u_fim)
    out["FUNC-FOLGA-S0"] = {"folga_neg": fn, "folga_pos": fp}
    return out


@pytest.mark.parametrize("linha", LINHAS, ids=[f"{d['caso_id']}-{d['campo']}" for d in LINHAS])
def test_referencia(linha: dict[str, str], calculados) -> None:
    valor = calculados[linha["caso_id"]][linha["campo"]]
    if linha["tolerancia"]:
        assert valor == pytest.approx(float(linha["esperado"]), abs=float(linha["tolerancia"]))
    else:
        assert valor == linha["esperado"]
