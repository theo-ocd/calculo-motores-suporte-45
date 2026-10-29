"""Planilha "calculadora" independente, com fórmulas nativas do Excel (em inglês).

As fórmulas vêm de data/calculadora.csv (B10..B18 equivalentes ao núcleo). As entradas
B1..B8 podem ser preenchidas a partir de um caso: o ponto P (a, b) da montagem é
convertido no centro de desenho (Cx0, Cy0) equivalente para h0/θ0 de referência.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook

from tensorcad import processamento as proc
from tensorcad.loader import carregar
from tensorcad.planilha import _aba_calculadora, ler_csv

H0_REF, THETA0_REF = 180.0, 45.0


def entradas(
    p: proc.Parametros, h0: float = H0_REF, theta0: float = THETA0_REF
) -> dict[str, float]:
    """Células B1..B8 que reproduzem os parâmetros `p` (inversa de calibrar_P)."""
    t0 = math.radians(theta0)
    return {
        "B1": p.R,
        "B2": p.a + h0 * math.sin(t0),
        "B3": p.b - h0 * math.cos(t0),
        "B4": h0,
        "B5": theta0,
        "B6": p.h,
        "B7": p.theta_deg,
        "B8": p.delta_y,
    }


def gerar_calculadora(
    destino: Path | str,
    modelo: Path | str = Path("data") / "calculadora.csv",
    parametros: proc.Parametros | None = None,
) -> Path:
    """Grava calculadora.xlsx (aba única 'calculadora')."""
    _, linhas = ler_csv(Path(modelo))
    wb = Workbook()
    ws = wb.active
    ws.title = "calculadora"
    _aba_calculadora(ws, linhas)
    if parametros is not None:
        for cel, v in entradas(parametros).items():
            ws[cel] = v
        ws["D2"] = f"Entradas preenchidas a partir do caso {parametros.caso_id}."
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Gera a planilha calculadora (fórmulas Excel).")
    ap.add_argument("--dados", default="data")
    ap.add_argument("--caso", default=None, help="preenche as entradas com este caso")
    ap.add_argument("--saida", default="output/calculadora.xlsx")
    a = ap.parse_args(argv)
    p = None
    if a.caso:
        base = carregar(a.dados)
        p = proc.parametros(base.casos[a.caso], base)
    modelo = Path(a.dados) / "calculadora.csv" if Path(a.dados).is_dir() else "data/calculadora.csv"
    print(gerar_calculadora(a.saida, modelo, p))


if __name__ == "__main__":
    main()
