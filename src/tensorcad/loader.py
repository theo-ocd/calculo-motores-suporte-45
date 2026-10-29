"""Carga e validação das tabelas CSV (UTF-8, separador ';', decimal '.')."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from tensorcad.models import Caso, Chapa, Montagem, Motor, Origem, Ranhura, Transmissao

M = TypeVar("M", bound=BaseModel)

TABELAS: dict[str, type[BaseModel]] = {
    "motores": Motor,
    "chapas": Chapa,
    "ranhuras": Ranhura,
    "transmissoes": Transmissao,
    "montagens": Montagem,
    "casos": Caso,
}


ORIGENS_COM_AVISO = (Origem.TODO, Origem.HIPOTESE)


@dataclass(frozen=True)
class ErroValidacao:
    tabela: str
    linha: int  # linha no arquivo (cabeçalho = 1); 0 = arquivo inteiro
    campo: str
    mensagem: str
    nivel: str = "ERRO"  # ERRO | AVISO

    def __str__(self) -> str:
        prefixo = "AVISO: " if self.nivel == "AVISO" else ""
        return (
            f"{prefixo}{self.tabela}.csv linha {self.linha} campo '{self.campo}': {self.mensagem}"
        )


def aviso(tabela: str, linha: int, campo: str, mensagem: str) -> ErroValidacao:
    return ErroValidacao(tabela, linha, campo, mensagem, nivel="AVISO")


class ErroCarga(Exception):
    def __init__(self, erros: list[ErroValidacao]) -> None:
        self.erros = erros
        super().__init__(relatorio(erros))


def relatorio(erros: Iterable[ErroValidacao]) -> str:
    erros = list(erros)
    if not erros:
        return "Validação OK: nenhum erro encontrado."
    linhas = [f"{len(erros)} erro(s) de validação:"]
    linhas += [f"  - {e}" for e in erros]
    return "\n".join(linhas)


@dataclass
class BaseDados:
    motores: dict[str, Motor] = field(default_factory=dict)
    chapas: dict[str, Chapa] = field(default_factory=dict)
    ranhuras: list[Ranhura] = field(default_factory=list)
    transmissoes: dict[str, Transmissao] = field(default_factory=dict)
    montagens: dict[str, Montagem] = field(default_factory=dict)
    casos: dict[str, Caso] = field(default_factory=dict)
    avisos: list[ErroValidacao] = field(default_factory=list)

    def ranhuras_de(self, chapa_id: str, carcaca: str) -> dict[int, Ranhura]:
        return {
            r.ranhura_n: r for r in self.ranhuras if r.chapa_id == chapa_id and r.carcaca == carcaca
        }


def _limpar(registro: Mapping[str, Any]) -> dict[str, Any]:
    """Converte células vazias em ausência do campo (usa default do modelo)."""
    out: dict[str, Any] = {}
    for k, v in registro.items():
        if k is None:
            continue
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                continue
        elif v is None or (isinstance(v, float) and v != v):  # NaN
            continue
        out[k.strip()] = v
    return out


def validar_registros(
    tabela: str,
    registros: Iterable[Mapping[str, Any]],
    erros: list[ErroValidacao],
    avisos: list[ErroValidacao] | None = None,
) -> list[tuple[int, BaseModel]]:
    """Valida cada registro. Registros com origem TODO/HIPOTESE geram aviso listando
    as células vazias (válidas, mas a confirmar)."""
    modelo = TABELAS[tabela]
    ok: list[tuple[int, BaseModel]] = []
    for i, reg in enumerate(registros, start=2):
        limpo = _limpar(reg)
        try:
            obj = modelo.model_validate(limpo)
        except ValidationError as exc:
            for e in exc.errors():
                campo = ".".join(str(p) for p in e["loc"]) or "(registro)"
                erros.append(ErroValidacao(tabela, i, campo, e["msg"]))
            continue
        ok.append((i, obj))
        origem = getattr(obj, "origem", None)
        if avisos is not None and origem in ORIGENS_COM_AVISO:
            vazios = [k for k in reg if k and k.strip() not in limpo]
            msg = f"dado com origem={origem}"
            if vazios:
                msg += f"; células vazias: {', '.join(vazios)}"
            avisos.append(aviso(tabela, i, "origem", msg))
    return ok


def ler_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def montar_base(
    brutos: Mapping[str, Iterable[Mapping[str, Any]]], erros: list[ErroValidacao]
) -> BaseDados:
    """Valida registros de todas as tabelas, chaves duplicadas e FKs."""
    base = BaseDados()
    validados = {t: validar_registros(t, brutos.get(t, []), erros, base.avisos) for t in TABELAS}

    def indexar(tabela: str, chave: str) -> dict[str, Any]:
        idx: dict[str, Any] = {}
        for linha, obj in validados[tabela]:
            k = getattr(obj, chave)
            if k in idx:
                erros.append(ErroValidacao(tabela, linha, chave, f"id duplicado '{k}'"))
            idx[k] = obj
        return idx

    base.motores = indexar("motores", "motor_id")
    base.chapas = indexar("chapas", "chapa_id")
    base.transmissoes = indexar("transmissoes", "transmissao_id")
    base.montagens = indexar("montagens", "montagem_id")
    base.casos = indexar("casos", "caso_id")
    base.ranhuras = [r for _, r in validados["ranhuras"]]  # type: ignore[misc]

    def fk(tabela: str, campo: str, alvo: Mapping[str, Any], nome_alvo: str) -> None:
        for linha, obj in validados[tabela]:
            v = getattr(obj, campo)
            if v not in alvo:
                erros.append(
                    ErroValidacao(tabela, linha, campo, f"'{v}' não existe em {nome_alvo}.csv")
                )

    fk("ranhuras", "chapa_id", base.chapas, "chapas")
    fk("montagens", "chapa_id", base.chapas, "chapas")
    fk("casos", "montagem_id", base.montagens, "montagens")
    fk("casos", "motor_id", base.motores, "motores")
    fk("casos", "transmissao_id", base.transmissoes, "transmissoes")

    for linha, c in validados["casos"]:
        tr = base.transmissoes.get(c.transmissao_id)  # type: ignore[attr-defined]
        if tr is not None and c.R_efetivo(tr) is None:  # type: ignore[attr-defined]
            erros.append(
                ErroValidacao(
                    "casos", linha, "R_alvo", f"R_alvo='nom' mas {tr.transmissao_id}.R_nom vazio"
                )
            )

    a_validar = [m.motor_id for m in base.motores.values() if m.fonte == Origem.IEC_REF_VALIDAR]
    if a_validar:
        base.avisos.append(
            aviso(
                "motores",
                0,
                "fonte",
                f"{len(a_validar)} motor(es) com fonte={Origem.IEC_REF_VALIDAR}"
                " (dimensões a validar com catálogo)",
            )
        )

    vistos: dict[tuple[str, str, int], int] = {}
    for linha, r in validados["ranhuras"]:
        k = (r.chapa_id, r.carcaca, r.ranhura_n)  # type: ignore[attr-defined]
        if k in vistos:
            erros.append(ErroValidacao("ranhuras", linha, "ranhura_n", f"ranhura duplicada {k}"))
        vistos[k] = linha
    return base


def _texto_celula(v: Any) -> str | None:
    """Célula do Excel → texto equivalente ao do CSV (inteiros sem '.0')."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def ler_aba_xlsx(caminho: Path, aba: str) -> list[dict[str, str | None]] | None:
    """Linhas de uma aba (cabeçalho na linha 1) ou None se a aba não existir.
    Linhas totalmente vazias são ignoradas; numeração de linha preservada."""
    from openpyxl import load_workbook

    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba not in wb.sheetnames:
            return None
        linhas = wb[aba].iter_rows(values_only=True)
        cab = [str(c).strip() if c is not None else "" for c in next(linhas, ())]
        out: list[dict[str, str | None]] = []
        for valores in linhas:
            reg = {c: _texto_celula(v) for c, v in zip(cab, valores, strict=False) if c}
            out.append(reg)
        while out and all(v in (None, "") for v in out[-1].values()):
            out.pop()
        return out
    finally:
        wb.close()


def _ler_tabela(fonte: Path, tabela: str) -> list[dict[str, Any]] | None:
    if fonte.is_dir():
        caminho = fonte / f"{tabela}.csv"
        return ler_csv(caminho) if caminho.exists() else None
    if fonte.suffix.lower() == ".csv":
        return ler_csv(fonte)
    return ler_aba_xlsx(fonte, tabela)


def analisar(
    fonte: Path | str, casos: Path | str | None = None
) -> tuple[BaseDados, list[ErroValidacao]]:
    """Carrega de um diretório de CSVs ou de um .xlsx (abas com os nomes das tabelas).
    `casos` (opcional): CSV ou .xlsx (aba 'casos') que substitui a tabela de casos."""
    fonte = Path(fonte)
    erros: list[ErroValidacao] = []
    if not fonte.exists():
        erros.append(ErroValidacao("(fonte)", 0, "(arquivo)", f"fonte ausente: {fonte}"))
        return BaseDados(), erros
    brutos: dict[str, list[dict[str, Any]]] = {}
    for tabela in TABELAS:
        origem = Path(casos) if (tabela == "casos" and casos is not None) else fonte
        linhas = _ler_tabela(origem, tabela)
        if linhas is None:
            erros.append(
                ErroValidacao(tabela, 0, "(arquivo)", f"tabela '{tabela}' ausente em {origem}")
            )
            continue
        brutos[tabela] = linhas
    return montar_base(brutos, erros), erros


def carregar(fonte: Path | str, casos: Path | str | None = None) -> BaseDados:
    """Como `analisar`, mas levanta ErroCarga se houver erros."""
    base, erros = analisar(fonte, casos)
    if erros:
        raise ErroCarga(erros)
    return base


def carregar_diretorio(diretorio: Path | str) -> BaseDados:
    """Carrega todas as tabelas de `diretorio`. Levanta ErroCarga se houver erros."""
    base, erros = analisar_diretorio(diretorio)
    if erros:
        raise ErroCarga(erros)
    return base


def analisar_diretorio(diretorio: Path | str) -> tuple[BaseDados, list[ErroValidacao]]:
    """Como carregar_diretorio, mas devolve (base parcial, erros) sem levantar exceção.
    Avisos ficam em base.avisos."""
    diretorio = Path(diretorio)
    erros: list[ErroValidacao] = []
    brutos: dict[str, list[dict[str, str]]] = {}
    for tabela in TABELAS:
        caminho = diretorio / f"{tabela}.csv"
        if not caminho.exists():
            erros.append(ErroValidacao(tabela, 0, "(arquivo)", f"arquivo ausente: {caminho}"))
            continue
        brutos[tabela] = ler_csv(caminho)
    return montar_base(brutos, erros), erros


def validar_diretorio(diretorio: Path | str) -> list[ErroValidacao]:
    return analisar_diretorio(diretorio)[1]
