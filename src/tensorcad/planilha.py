"""Geração da planilha consolidada (output/tensorcad_base.xlsx).

Camada de I/O: lê os CSVs de /data, calcula resultados com o núcleo e grava o xlsx.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

import tensorcad
from tensorcad import processamento as proc
from tensorcad.loader import BaseDados, carregar_diretorio
from tensorcad.models import COLUNAS_RESULTADO, Resultado

ABAS = (
    "LEIAME",
    "dicionario",
    "motores",
    "chapas",
    "ranhuras",
    "transmissoes",
    "montagens",
    "casos",
    "resultados",
    "varredura_dy",
    "calculadora",
    "testes_referencia",
    "pendencias",
)
ABAS_CSV = ("dicionario", "motores", "chapas", "ranhuras", "transmissoes", "montagens", "casos")

FMT_MM, FMT_GRAUS, FMT_SENS = "0.00", "0.0", "0.000"
FMT_POR_UNIDADE = {"mm": FMT_MM, "graus": FMT_GRAUS, "mm/mm": FMT_SENS}
FMT_POR_CAMPO = {  # campos fora do dicionário
    "R": FMT_MM,
    "theta_deg": FMT_GRAUS,
    "delta_y": FMT_MM,
    "s_min": FMT_MM,
    "s_max": FMT_MM,
}
COLUNAS_TEXTO = {"carcaca", "carcacas_compat", "modelo", "descricao", "item", "R_alvo"}

VERDE = PatternFill("solid", fgColor="C6EFCE")
AMARELO = PatternFill("solid", fgColor="FFEB9C")
VERMELHO = PatternFill("solid", fgColor="FFC7CE")
LARANJA = PatternFill("solid", fgColor="F8CBAD")
CORES_STATUS = {
    "OK": VERDE,
    "FORA_RANHURA": AMARELO,
    "SEM_SOLUCAO": VERMELHO,
    "INCOMPATIVEL": VERMELHO,
}

CASO_VARREDURA = "VAR-BASE"
VARREDURA_PADRAO = (-100.0, 100.0, 10.0)


# --------------------------------------------------------------------------- util


def ler_csv(caminho: Path) -> tuple[list[str], list[dict[str, str]]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        linhas = list(leitor)
        return list(leitor.fieldnames or []), linhas


def _valor(coluna: str, texto: str | None) -> Any:
    """Converte texto do CSV para número quando aplicável (vazio → None)."""
    if texto is None or texto.strip() == "":
        return None
    t = texto.strip()
    if coluna.endswith("_id") or coluna in COLUNAS_TEXTO:
        try:  # R_alvo numérico continua número
            return float(t) if coluna == "R_alvo" else t
        except ValueError:
            return t
    try:
        return float(t)
    except ValueError:
        return t


def _formatos(dicionario: Iterable[dict[str, str]]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for d in dicionario:
        fmt = FMT_POR_UNIDADE.get(d["unidade"])
        if fmt:
            out[(d["tabela"], d["campo"])] = fmt
    return out


def _escrever_tabela(
    ws: Worksheet,
    nome: str,
    colunas: Sequence[str],
    linhas: Iterable[Sequence[Any]],
    formatos: dict[tuple[str, str], str],
) -> int:
    """Escreve cabeçalho + linhas como Tabela do Excel. Retorna nº de linhas de dados."""
    ws.append(list(colunas))
    n = 0
    for linha in linhas:
        ws.append([None if isinstance(v, float) and math.isnan(v) else v for v in linha])
        n += 1
    ultima = max(n, 1) + 1
    ref = f"A1:{get_column_letter(len(colunas))}{ultima}"
    tabela = Table(displayName=nome, ref=ref)
    tabela.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tabela)
    ws.freeze_panes = "A2"
    for j, col in enumerate(colunas, start=1):
        fmt = formatos.get((nome, col)) or FMT_POR_CAMPO.get(col)
        if fmt:
            for i in range(2, ultima + 1):
                ws.cell(i, j).number_format = fmt
    _largura_auto(ws)
    return n


def _largura_auto(ws: Worksheet, minimo: int = 8, maximo: int = 60) -> None:
    larguras: dict[int, int] = {}
    for linha in ws.iter_rows():
        for c in linha:
            if c.value is None:
                continue
            v = c.value
            txt = f"{v:.3f}" if isinstance(v, float) else str(v)
            larguras[c.column] = max(larguras.get(c.column, 0), len(txt))
    for col, w in larguras.items():
        ws.column_dimensions[get_column_letter(col)].width = min(max(w + 2, minimo), maximo)


def _coluna(colunas: Sequence[str], nome: str) -> str:
    return get_column_letter(list(colunas).index(nome) + 1)


def _cor_status(ws: Worksheet, faixa: str) -> None:
    for status, cor in CORES_STATUS.items():
        ws.conditional_formatting.add(
            faixa, CellIsRule(operator="equal", formula=[f'"{status}"'], fill=cor)
        )


def _cor_origem(ws: Worksheet, colunas: Sequence[str], n: int) -> None:
    if "origem" not in colunas:
        return
    letra = _coluna(colunas, "origem")
    faixa = f"{letra}2:{letra}{max(n, 1) + 1}"
    for valor in ("HIPOTESE", "TODO"):
        ws.conditional_formatting.add(
            faixa, CellIsRule(operator="equal", formula=[f'"{valor}"'], fill=LARANJA)
        )


def _linhas_resultado(resultados: Iterable[Resultado]) -> list[list[Any]]:
    return [[getattr(r, c) for c in COLUNAS_RESULTADO] for r in resultados]


# --------------------------------------------------------------------------- abas


def _aba_leiame(ws: Worksheet, versao_dados: str) -> None:
    linhas = [
        ("tensorcad — base de dados e resultados", True),
        ("", False),
        ("Objetivo", True),
        (
            "Calcular a posição do motor sobre a chapa-guia inclinada (base tensora de "
            "correia) para que o entre-centros seja R, validar as ranhuras e exportar ao CAD.",
            False,
        ),
        ("", False),
        ("Convenções", True),
        ("Origem O = centro do arco (eixo acionado). x+ para a ESQUERDA, y+ para BAIXO.", False),
        ("P = (a, b): ponto de referência da chapa sobre a reta da guia, com Δy = 0.", False),
        ("u = (cosθ, sinθ): direção da guia; s+ afasta o motor de O (tensiona).", False),
        ("n = (sinθ, −cosθ): normal da guia, lado do motor. h = H + e_apoio.", False),
        ("Δy+ = conjunto desce. Unidades: mm; ângulos em graus.", False),
        ("CAD (y para cima): X_cad = X_O_cad − x ; Y_cad = Y_O_cad − y.", False),
        ("", False),
        ("Fórmulas do núcleo", True),
        ("l_proj = a·cosθ + (b+Δy)·sinθ", False),
        ("d_perp = a·sinθ − (b+Δy)·cosθ + h", False),
        ("se R² < d_perp² → SEM_SOLUCAO", False),
        ("s = −l_proj + √(R² − d_perp²)", False),
        ("Cx = a + s·cosθ + h·sinθ ;  Cy = b + Δy + s·sinθ − h·cosθ", False),
        ("∂s/∂Δy = −sinθ + d_perp·cosθ / √(R² − d_perp²) ;  ∂s/∂h = −d_perp / √(…)", False),
        ("folga_neg = (s − A/2 − K/2) − u_ini(ranhura 1)", False),
        ("folga_pos = u_fim(ranhura 2) − (s + A/2 + K/2)", False),
        ("", False),
        ("Geração", True),
        (f"Data: {datetime.now():%Y-%m-%d %H:%M}", False),
        (f"Versão do pacote tensorcad: {tensorcad.__version__}", False),
        (f"Dados: {versao_dados}", False),
        ("", False),
        ("Abas", True),
        (", ".join(ABAS), False),
        ("resultados e varredura_dy são calculadas pelo núcleo (não digitar).", False),
        ("Cores: OK verde, FORA_RANHURA amarelo, SEM_SOLUCAO/INCOMPATIVEL vermelho;", False),
        ("origem HIPOTESE/TODO em laranja.", False),
    ]
    for texto, negrito in linhas:
        ws.append([texto])
        if negrito:
            ws.cell(ws.max_row, 1).font = Font(bold=True, size=12)
    ws.column_dimensions["A"].width = 110


def _validacoes_casos(ws: Worksheet, colunas: Sequence[str], n: int, base: BaseDados) -> None:
    fim = max(n, 1) + 1
    fontes = {
        "motor_id": ("motores", len(base.motores)),
        "montagem_id": ("montagens", len(base.montagens)),
        "transmissao_id": ("transmissoes", len(base.transmissoes)),
    }
    for campo, (aba, qtd) in fontes.items():
        dv = DataValidation(
            type="list",
            formula1=f"={aba}!$A$2:$A${max(qtd, 1) + 1}",
            allow_blank=False,
            showErrorMessage=True,
            errorTitle="Valor inválido",
            error=f"Escolha um {campo} cadastrado na aba {aba}.",
        )
        letra = _coluna(colunas, campo)
        dv.add(f"{letra}2:{letra}{fim}")
        ws.add_data_validation(dv)
    letra = _coluna(colunas, "R_alvo")
    c = f"{letra}2"
    dv = DataValidation(
        type="custom",
        formula1=f'=OR({c}="min",{c}="nom",{c}="max",AND(ISNUMBER({c}),{c}>0))',
        showErrorMessage=True,
        errorTitle="R_alvo inválido",
        error="Use min, nom, max ou um número positivo (mm).",
    )
    dv.add(f"{letra}2:{letra}{fim}")
    ws.add_data_validation(dv)


def _aba_varredura(
    ws: Worksheet,
    pontos: Sequence[tuple[float, Resultado]],
    caso_id: str,
    limites_s: tuple[float, float] | None,
) -> None:
    colunas = ["delta_y", "s", "folga_neg", "folga_pos", "status"]
    if limites_s:
        colunas += ["s_min", "s_max"]
    linhas = []
    for dy, r in pontos:
        linha: list[Any] = [dy, r.s, r.folga_neg, r.folga_pos, r.status]
        if limites_s:
            linha += list(limites_s)
        linhas.append(linha)
    n = _escrever_tabela(ws, "varredura_dy", colunas, linhas, {})
    for col in ("s", "folga_neg", "folga_pos"):
        letra = _coluna(colunas, col)
        for i in range(2, n + 2):
            ws[f"{letra}{i}"].number_format = FMT_MM
    letra = _coluna(colunas, "status")
    _cor_status(ws, f"{letra}2:{letra}{n + 1}")

    graf = ScatterChart()
    graf.title = f"s × Δy — caso {caso_id}"
    graf.style = 13
    graf.x_axis.title = "Δy (mm)"
    graf.y_axis.title = "s (mm)"
    graf.x_axis.delete = False
    graf.y_axis.delete = False
    xs = Reference(ws, min_col=1, min_row=2, max_row=n + 1)
    for col in colunas:
        if col not in ("s", "s_min", "s_max"):
            continue
        j = colunas.index(col) + 1
        serie = Series(Reference(ws, min_col=j, min_row=1, max_row=n + 1), xs, title_from_data=True)
        serie.marker.symbol = "circle" if col == "s" else "none"
        if col != "s":
            serie.graphicalProperties.line.dashStyle = "dash"
        graf.series.append(serie)
    graf.height, graf.width = 10, 18
    ws.add_chart(graf, f"{get_column_letter(len(colunas) + 2)}2")


def _aba_calculadora(ws: Worksheet, linhas: Iterable[dict[str, str]]) -> None:
    for d in linhas:
        cel = d["celula"]
        texto = d["rotulo"] if d["rotulo"] else d["conteudo"]
        if texto.startswith("="):
            ws[cel] = texto
        else:
            try:
                ws[cel] = float(texto)
            except ValueError:
                ws[cel] = texto
        if cel.startswith("B"):
            ws[cel].number_format = FMT_SENS if cel in ("B17", "B18") else FMT_MM
            if texto.startswith("="):
                ws[cel].font = Font(bold=True)
    ws["D1"] = "Entradas: B1..B8 (editáveis). Resultados: B10..B18 (fórmulas)."
    ws["D2"] = "Valores iniciais reproduzem o caso REF-1 (s ≈ 7.81 mm)."
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14
    for cel in ("D1", "D2"):
        ws[cel].alignment = Alignment(wrap_text=False)


def _verificar_referencia(
    linhas: Iterable[dict[str, str]], resultados: dict[str, Resultado]
) -> list[list[Any]]:
    out = []
    for d in linhas:
        r = resultados.get(d["caso_id"])
        calc: Any = getattr(r, d["campo"], None) if r else None
        esperado = _valor("esperado", d["esperado"])
        tol = _valor("tolerancia", d["tolerancia"])
        if calc is None:
            aprovado = "N/D"
        elif isinstance(esperado, float):
            aprovado = "SIM" if abs(float(calc) - esperado) <= (tol or 0) else "NAO"
        else:
            aprovado = "SIM" if str(calc) == str(esperado) else "NAO"
        out.append([d["caso_id"], d["campo"], esperado, tol, d["depende_hipotese"], calc, aprovado])
    return out


# --------------------------------------------------------------------------- API


def gerar_planilha(
    dir_dados: Path | str,
    destino: Path | str,
    *,
    caso_varredura: str = CASO_VARREDURA,
    varredura: tuple[float, float, float] = VARREDURA_PADRAO,
) -> Path:
    """Gera o xlsx completo e retorna o caminho gravado."""
    dir_dados, destino = Path(dir_dados), Path(destino)
    base = carregar_diretorio(dir_dados)
    _, dicionario = ler_csv(dir_dados / "dicionario.csv")
    formatos = _formatos(dicionario)

    resultados = proc.calcular_todos(base)
    por_caso = {r.caso_id: r for r in resultados}

    wb = Workbook()
    wb.remove(wb.active)
    abas = {nome: wb.create_sheet(nome) for nome in ABAS}

    _aba_leiame(abas["LEIAME"], str(dir_dados.resolve().name))

    for nome in ABAS_CSV:
        colunas, linhas = ler_csv(dir_dados / f"{nome}.csv")
        dados = [[_valor(c, d.get(c)) for c in colunas] for d in linhas]
        n = _escrever_tabela(abas[nome], nome, colunas, dados, formatos)
        _cor_origem(abas[nome], colunas, n)
        if nome == "casos":
            _validacoes_casos(abas[nome], colunas, n, base)

    ws = abas["resultados"]
    cols = ["caso_id", *COLUNAS_RESULTADO[1:]]
    n = _escrever_tabela(ws, "resultados", cols, _linhas_resultado(resultados), formatos)
    letra = _coluna(cols, "status")
    _cor_status(ws, f"{letra}2:{letra}{n + 1}")

    caso = base.casos[caso_varredura]
    pontos = list(
        zip(proc.faixa(*varredura), proc.varredura_dy(caso, base, *varredura), strict=True)
    )
    _aba_varredura(abas["varredura_dy"], pontos, caso_varredura, None)

    _, calc = ler_csv(dir_dados / "calculadora.csv")
    _aba_calculadora(abas["calculadora"], calc)

    _, refs = ler_csv(dir_dados / "testes_referencia.csv")
    cols_ref = [
        "caso_id",
        "campo",
        "esperado",
        "tolerancia",
        "depende_hipotese",
        "calculado",
        "aprovado",
    ]
    n = _escrever_tabela(
        abas["testes_referencia"],
        "testes_referencia",
        cols_ref,
        _verificar_referencia(refs, por_caso),
        {},
    )
    ws = abas["testes_referencia"]
    letra = _coluna(cols_ref, "aprovado")
    faixa = f"{letra}2:{letra}{n + 1}"
    for valor, cor in (("SIM", VERDE), ("NAO", VERMELHO), ("N/D", AMARELO)):
        ws.conditional_formatting.add(
            faixa, CellIsRule(operator="equal", formula=[f'"{valor}"'], fill=cor)
        )

    colunas, linhas = ler_csv(dir_dados / "pendencias.csv")
    _escrever_tabela(
        abas["pendencias"],
        "pendencias",
        colunas,
        [[d[c] for c in colunas] for d in linhas],
        {},
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Gera a planilha consolidada do tensorcad.")
    ap.add_argument("--dados", default="data")
    ap.add_argument("--saida", default="output/tensorcad_base.xlsx")
    args = ap.parse_args(argv)
    print(gerar_planilha(args.dados, args.saida))


if __name__ == "__main__":
    main()
