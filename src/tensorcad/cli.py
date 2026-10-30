"""Interface de linha de comando do tensorcad (base do executável)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from tensorcad import __version__, recursos
from tensorcad.loader import (
    BaseDados,
    ErroCarga,
    Padroes,
    analisar,
    carregar,
    carregar_padroes,
    relatorio,
)
from tensorcad.planilha_projeto import (
    EntradaPlanilha,
    adicionar_caso,
    ler_entradas,
    status_do_caso,
)
from tensorcad.projeto import X_TUBO_PADRAO, Y_PISO_PADRAO, ConfigProjeto

app = typer.Typer(
    help=(
        "Posição do motor sobre a chapa inclinada (base tensora) e planilha do projeto. "
        "Sem comando, abre a interface no navegador."
    ),
    add_completion=False,
)

Dados = Annotated[
    Path | None,
    typer.Option(help="Diretório de CSVs (ou .xlsx) com os cadastros. Padrão: dados embutidos."),
]
PadroesOpt = Annotated[
    Path | None,
    typer.Option(help="Diretório com chapas_carcaca.csv. Padrão: <dados>/padrao."),
]


def _resolver(dados: Path | None, padroes: Path | None) -> tuple[Path, Path]:
    try:
        d = dados or recursos.dir_dados()
    except FileNotFoundError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(1) from None
    return d, padroes or recursos.dir_padroes(d)


def _carregar(dados: Path, padroes: Path) -> tuple[BaseDados, Padroes]:
    try:
        return carregar(dados), carregar_padroes(padroes)
    except ErroCarga as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


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


@app.callback(invoke_without_command=True)
def principal(
    ctx: typer.Context,
    versao: Annotated[bool, typer.Option("--versao", help="Mostra a versão.")] = False,
) -> None:
    """Sem comando: interface no navegador (uso com duplo clique no executável)."""
    if versao:
        typer.echo(f"tensorcad {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        web(None, None, None, False, 160, 250)


@app.command()
def web(
    dados: Dados = None,
    padroes: PadroesOpt = None,
    porta: Annotated[
        int | None, typer.Option(help="Porta local (padrão: 8765 ou a próxima livre).")
    ] = None,
    sem_navegador: Annotated[
        bool, typer.Option("--sem-navegador", help="Não abre o navegador automaticamente.")
    ] = False,
    carcaca_min: Annotated[int, typer.Option(help="Menor carcaça oferecida.")] = 160,
    carcaca_max: Annotated[int, typer.Option(help="Maior carcaça oferecida.")] = 250,
) -> None:
    """Abre a interface visual no navegador (servidor local em 127.0.0.1)."""
    from tensorcad.web import servidor
    from tensorcad.web.api import Contexto

    d, p = _resolver(dados, padroes)
    try:
        base = carregar(d)
        pad = carregar_padroes(p, estrito=False)  # linha com erro marca só a carcaça
    except ErroCarga as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    ctx = Contexto(base, pad, d, p, faixa=(carcaca_min, carcaca_max))
    servidor.executar(ctx, porta=porta, abrir=not sem_navegador)


@app.command()
def validar(dados: Dados = None, padroes: PadroesOpt = None) -> None:
    """Valida os cadastros e as chapas padrão e mostra erros/avisos."""
    dados, padroes = _resolver(dados, padroes)
    typer.echo(f"Dados: {dados}")
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
    dados: Dados = None,
    padroes: PadroesOpt = None,
) -> None:
    """Calcula um caso e o adiciona (uma aba) à planilha do projeto."""
    if (motor is None) == (carcaca is None):
        raise typer.BadParameter("informe exatamente um entre --motor e --carcaca")
    base, pad = _carregar(*_resolver(dados, padroes))
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
    dados: Dados = None,
    saida: Annotated[Path, typer.Option(help="Diretório de saída.")] = Path("output"),
    casos: Annotated[Path | None, typer.Option(help="CSV/xlsx de casos.")] = None,
    caso_varredura: Annotated[str | None, typer.Option(help="Caso da varredura Δy.")] = None,
    dy_ini: float = -100.0,
    dy_fim: float = 100.0,
    passo: float = 10.0,
) -> None:
    """Processa os casos da base (F4): resultados.csv e resultados.xlsx."""
    from tensorcad.lote import executar_lote

    dados = dados or _resolver(None, None)[0]
    out = executar_lote(
        dados, saida, casos=casos, caso_varredura=caso_varredura, varredura=(dy_ini, dy_fim, passo)
    )
    typer.echo(f"{len(out.resultados)} caso(s) → {out.csv} e {out.xlsx}")


SIM = {"s", "sim", "y", "yes"}
NAO = {"n", "nao", "não", "no"}


def _sim_nao(pergunta: str, padrao: bool) -> bool:
    dica = "[S/n]" if padrao else "[s/N]"
    while True:
        resp = typer.prompt(f"{pergunta} {dica}", default="", show_default=False).strip().lower()
        if not resp:
            return padrao
        if resp in SIM:
            return True
        if resp in NAO:
            return False
        typer.echo("  responda s ou n")


def _num(texto: str) -> float:
    return float(texto.strip().replace(",", "."))


def _perguntar_num(
    rotulo: str, padrao: float | None = None, opcional: bool = False
) -> float | None:
    while True:
        dica = "" if padrao is None else f" [{padrao:g}]"
        resp = typer.prompt(f"{rotulo}{dica}", default="", show_default=False).strip()
        if not resp:
            if padrao is not None:
                return padrao
            if opcional:
                return None
            typer.echo("  valor obrigatório")
            continue
        try:
            return _num(resp)
        except ValueError:
            typer.echo("  número inválido (use ponto ou vírgula decimal)")


@app.command()
def interativo(dados: Dados = None, padroes: PadroesOpt = None) -> None:
    """Pergunta os dados de cada caso e monta a planilha do projeto (uma aba por caso)."""
    typer.echo(f"tensorcad {__version__} — planilha do projeto (uma aba por caso)\n")
    base, pad = _carregar(*_resolver(dados, padroes))
    carcacas = sorted(
        {m.carcaca for m in base.motores.values() if pad.chapa_para(m.carcaca) is not None}
    )
    typer.echo(f"Carcaças com chapa padrão: {', '.join(carcacas) or 'nenhuma'}")
    arq = Path(typer.prompt("Arquivo da planilha do projeto", default="projeto_tensorcad.xlsx"))
    if arq.suffix.lower() != ".xlsx":
        arq = arq.with_suffix(".xlsx")
    cfg = ConfigProjeto()
    if arq.exists():
        cfg, ents = ler_entradas(arq)
        typer.echo(f"Projeto existente '{cfg.nome}' com {len(ents)} caso(s).")
    else:
        cfg = ConfigProjeto(nome=typer.prompt("Nome do projeto", default="PROJETO"))
    while True:
        caso_id = typer.prompt("Nome do caso (aba)")
        carc = typer.prompt("Carcaça", default=carcacas[0] if carcacas else "")
        r_min = _perguntar_num("R_min (0 %) mm")
        r_max = _perguntar_num("R_max (3 %) mm")
        cota = _perguntar_num("Cota 1646 a verificar (Enter = só calcular)", opcional=True)
        try:
            motor_id = _motor_por_carcaca(base, carc)
            adicionar_caso(
                arq, EntradaPlanilha(caso_id, motor_id, r_min, r_max, cota), base, pad, cfg=cfg
            )
            typer.echo(f"Caso {caso_id}: {status_do_caso(arq, caso_id)} → {arq.resolve()}")
        except (ValueError, typer.BadParameter) as exc:
            typer.echo(f"Erro: {exc}")
        if not _sim_nao("Adicionar outro caso?", False):
            break
    if arq.exists() and _sim_nao("Abrir a planilha?", True):
        _abrir(arq)


if __name__ == "__main__":  # pragma: no cover
    app()
