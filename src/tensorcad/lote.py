"""Processamento em lote: casos (CSV ou xlsx) → resultados.csv e resultados.xlsx.

Camada de I/O sobre `processamento` (núcleo puro).
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook

from tensorcad import processamento as proc
from tensorcad.loader import BaseDados, carregar
from tensorcad.models import COLUNAS_RESULTADO, Resultado
from tensorcad.planilha import (
    VARREDURA_PADRAO,
    _aba_varredura,
    _coluna,
    _cor_status,
    _escrever_tabela,
    _linhas_resultado,
)


@dataclass(frozen=True)
class SaidaLote:
    resultados: list[Resultado]
    csv: Path
    xlsx: Path


def escrever_resultados_csv(resultados: Iterable[Resultado], caminho: Path) -> Path:
    """resultados.csv (UTF-8, ';', decimal '.'); floats com precisão total (repr)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(COLUNAS_RESULTADO)
        for r in resultados:
            w.writerow(
                [
                    "" if v is None else repr(v) if isinstance(v, float) else v
                    for v in (getattr(r, c) for c in COLUNAS_RESULTADO)
                ]
            )
    return caminho


def escrever_resultados_xlsx(
    resultados: Sequence[Resultado],
    base: BaseDados,
    caminho: Path,
    caso_varredura: str | None,
    varredura: tuple[float, float, float],
) -> Path:
    """resultados.xlsx: aba 'resultados' + aba 'varredura_dy' (gráfico s×Δy)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "resultados"
    n = _escrever_tabela(ws, "resultados", COLUNAS_RESULTADO, _linhas_resultado(resultados), {})
    letra = _coluna(COLUNAS_RESULTADO, "status")
    _cor_status(ws, f"{letra}2:{letra}{n + 1}")
    if caso_varredura is not None:
        caso = base.casos[caso_varredura]
        pontos = list(
            zip(proc.faixa(*varredura), proc.varredura_dy(caso, base, *varredura), strict=True)
        )
        _aba_varredura(
            wb.create_sheet("varredura_dy"),
            pontos,
            caso_varredura,
            proc.limites_s(caso, base),
            proc.faixa_dy_caso(caso, base),
        )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)
    return caminho


def executar_lote(
    fonte: Path | str,
    saida: Path | str,
    *,
    casos: Path | str | None = None,
    caso_varredura: str | None = None,
    varredura: tuple[float, float, float] = VARREDURA_PADRAO,
) -> SaidaLote:
    """Carrega a base, calcula todos os casos e grava resultados.csv/.xlsx em `saida`.
    caso_varredura: padrão VAR-BASE se existir, senão o primeiro caso."""
    base = carregar(fonte, casos)
    if not base.casos:
        raise ValueError("nenhum caso para processar")
    if caso_varredura is None:
        caso_varredura = "VAR-BASE" if "VAR-BASE" in base.casos else next(iter(base.casos))
    elif caso_varredura not in base.casos:
        raise ValueError(f"caso de varredura '{caso_varredura}' não existe")
    proc.faixa(*varredura)  # valida antes de calcular
    resultados = proc.calcular_todos(base)
    saida = Path(saida)
    return SaidaLote(
        resultados,
        escrever_resultados_csv(resultados, saida / "resultados.csv"),
        escrever_resultados_xlsx(
            resultados, base, saida / "resultados.xlsx", caso_varredura, varredura
        ),
    )


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Processa casos em lote.")
    ap.add_argument("--dados", default="data", help="diretório de CSVs ou arquivo .xlsx")
    ap.add_argument("--casos", default=None, help="CSV/xlsx de casos (opcional)")
    ap.add_argument("--saida", default="output")
    ap.add_argument("--caso-varredura", default=None)
    ap.add_argument("--dy-ini", type=float, default=VARREDURA_PADRAO[0])
    ap.add_argument("--dy-fim", type=float, default=VARREDURA_PADRAO[1])
    ap.add_argument("--passo", type=float, default=VARREDURA_PADRAO[2])
    a = ap.parse_args(argv)
    out = executar_lote(
        a.dados,
        a.saida,
        casos=a.casos,
        caso_varredura=a.caso_varredura,
        varredura=(a.dy_ini, a.dy_fim, a.passo),
    )
    print(f"{len(out.resultados)} caso(s) → {out.csv} e {out.xlsx}")


if __name__ == "__main__":
    main()
