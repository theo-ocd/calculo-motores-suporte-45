"""Interface de linha de comando do tensorcad (base do executável)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from tensorcad.loader import ErroCarga, analisar, carregar, carregar_padroes, relatorio
from tensorcad.planilha_projeto import EntradaPlanilha, adicionar_caso, status_do_caso
from tensorcad.projeto import X_TUBO_PADRAO, Y_PISO_PADRAO, ConfigProjeto

app = typer.Typer(
    help="Posição do motor sobre a chapa inclinada (base tensora) e planilha do projeto.",
    no_args_is_help=True,
    add_completion=False,
)

Dados = Annotated[Path, typer.Option(help="Diretório de CSVs (ou .xlsx) com os cadastros.")]
PadroesOpt = Annotated[Path, typer.Option(help="Diretório com chapas_padrao/ranhuras_padrao.")]


def _abrir(caminho: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(caminho)  # type: ignore[attr-defined]
    else:
        cmd = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([cmd, str(caminho)])


def _motor_por_carcaca(base, carcaca: str) -> str:
    for m in base.motores.values():
        if m.carcaca.upper() == carcaca.upper():
            return m.motor_id
    raise typer.BadParameter(f"nenhum motor cadastrado com carcaça {carcaca}")


@app.command()
def validar(dados: Dados = Path("data"), padroes: PadroesOpt = Path("data/padrao")) -> None:
    """Valida os cadastros e as chapas padrão e mostra erros/avisos."""
    base, erros = analisar(dados)
    typer.echo(relatorio(erros))
    for a in base.avisos:
        typer.echo(f"  {a}")
    try:
        pad = carregar_padroes(padroes)
        typer.echo(f"Chapas padrão: {', '.join(pad.chapas) or 'nenhuma'}")
    except ErroCarga as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None
    if erros:
        raise typer.Exit(1)


@app.command()
def caso(
    projeto: Annotated[Path, typer.Option(help="Planilha do projeto (criada se não existir).")],
    caso_id: Annotated[str, typer.Option("--id", help="Nome do caso (vira o nome da aba).")],
    r_min: Annotated[float, typer.Option("--rmin", help="Entre-centros a 0 % (mm).")],
    r_max: Annotated[float, typer.Option("--rmax", help="Entre-centros a 3 % (mm).")],
    motor: Annotated[str | None, typer.Option(help="motor_id cadastrado.")] = None,
    carcaca: Annotated[str | None, typer.Option(help="Carcaça (alternativa a --motor).")] = None,
    cota: Annotated[
        float | None, typer.Option(help="Cota 1646 a verificar (opcional, mm).")
    ] = None,
    chapa: Annotated[str | None, typer.Option(help="Força uma chapa padrão.")] = None,
    nome_projeto: Annotated[str, typer.Option(help="Nome (só na criação).")] = "PROJETO",
    y_piso: Annotated[float, typer.Option(help="Centro dos raios → piso.")] = Y_PISO_PADRAO,
    x_tubo: Annotated[float, typer.Option(help="Centro dos raios → tubo (x).")] = X_TUBO_PADRAO,
    substituir: Annotated[bool, typer.Option(help="Substitui caso de mesmo nome.")] = False,
    abrir: Annotated[bool, typer.Option(help="Abre a planilha ao final.")] = False,
    dados: Dados = Path("data"),
    padroes: PadroesOpt = Path("data/padrao"),
) -> None:
    """Calcula um caso e o adiciona (uma aba) à planilha do projeto."""
    if (motor is None) == (carcaca is None):
        raise typer.BadParameter("informe exatamente um entre --motor e --carcaca")
    try:
        base = carregar(dados)
        pad = carregar_padroes(padroes)
    except ErroCarga as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    motor_id = motor or _motor_por_carcaca(base, carcaca or "")
    entrada = EntradaPlanilha(caso_id, motor_id, r_min, r_max, cota, chapa)
    try:
        arq = adicionar_caso(
            projeto,
            entrada,
            base,
            pad,
            cfg=ConfigProjeto(nome=nome_projeto, y_piso=y_piso, x_tubo=x_tubo),
            substituir=substituir,
        )
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Caso {caso_id}: {status_do_caso(arq, caso_id)} → {arq}")
    if abrir:
        _abrir(arq)


@app.command()
def lote(
    dados: Dados = Path("data"),
    saida: Annotated[Path, typer.Option(help="Diretório de saída.")] = Path("output"),
    casos: Annotated[Path | None, typer.Option(help="CSV/xlsx de casos.")] = None,
    caso_varredura: Annotated[str | None, typer.Option(help="Caso da varredura Δy.")] = None,
    dy_ini: float = -100.0,
    dy_fim: float = 100.0,
    passo: float = 10.0,
) -> None:
    """Processa os casos da base (F4): resultados.csv e resultados.xlsx."""
    from tensorcad.lote import executar_lote

    out = executar_lote(
        dados, saida, casos=casos, caso_varredura=caso_varredura, varredura=(dy_ini, dy_fim, passo)
    )
    typer.echo(f"{len(out.resultados)} caso(s) → {out.csv} e {out.xlsx}")


if __name__ == "__main__":  # pragma: no cover
    app()
