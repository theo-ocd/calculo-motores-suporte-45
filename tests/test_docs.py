import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_pendencias_md_sincronizado_com_csv() -> None:
    md = (RAIZ / "docs" / "pendencias.md").read_text(encoding="utf-8")
    with (RAIZ / "data" / "pendencias.csv").open(encoding="utf-8") as f:
        for p in csv.DictReader(f, delimiter=";"):
            linha = f"| {p['id']} | {p['item']} | {p['impacto']} | {p['status']} |"
            assert linha in md, p["id"]
