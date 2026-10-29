"""Carga e validação das tabelas CSV (UTF-8, separador ';', decimal '.')."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from tensorcad.models import Caso, Chapa, Montagem, Motor, Ranhura, Transmissao

M = TypeVar("M", bound=BaseModel)

TABELAS: dict[str, type[BaseModel]] = {
    "motores": Motor,
    "chapas": Chapa,
    "ranhuras": Ranhura,
    "transmissoes": Transmissao,
    "montagens": Montagem,
    "casos": Caso,
}


@dataclass(frozen=True)
class ErroValidacao:
    tabela: str
    linha: int  # linha no arquivo (cabeçalho = 1); 0 = arquivo inteiro
    campo: str
    mensagem: str

    def __str__(self) -> str:
        return f"{self.tabela}.csv linha {self.linha} campo '{self.campo}': {self.mensagem}"


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
    tabela: str, registros: Iterable[Mapping[str, Any]], erros: list[ErroValidacao]
) -> list[tuple[int, BaseModel]]:
    modelo = TABELAS[tabela]
    ok: list[tuple[int, BaseModel]] = []
    for i, reg in enumerate(registros, start=2):
        try:
            ok.append((i, modelo.model_validate(_limpar(reg))))
        except ValidationError as exc:
            for e in exc.errors():
                campo = ".".join(str(p) for p in e["loc"]) or "(registro)"
                erros.append(ErroValidacao(tabela, i, campo, e["msg"]))
    return ok


def ler_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def montar_base(
    brutos: Mapping[str, Iterable[Mapping[str, Any]]], erros: list[ErroValidacao]
) -> BaseDados:
    """Valida registros de todas as tabelas, chaves duplicadas e FKs."""
    base = BaseDados()
    validados = {t: validar_registros(t, brutos.get(t, []), erros) for t in TABELAS}

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

    vistos: dict[tuple[str, str, int], int] = {}
    for linha, r in validados["ranhuras"]:
        k = (r.chapa_id, r.carcaca, r.ranhura_n)  # type: ignore[attr-defined]
        if k in vistos:
            erros.append(ErroValidacao("ranhuras", linha, "ranhura_n", f"ranhura duplicada {k}"))
        vistos[k] = linha
    return base


def carregar_diretorio(diretorio: Path | str) -> BaseDados:
    """Carrega todas as tabelas de `diretorio`. Levanta ErroCarga se houver erros."""
    diretorio = Path(diretorio)
    erros: list[ErroValidacao] = []
    brutos: dict[str, list[dict[str, str]]] = {}
    for tabela in TABELAS:
        caminho = diretorio / f"{tabela}.csv"
        if not caminho.exists():
            erros.append(ErroValidacao(tabela, 0, "(arquivo)", f"arquivo ausente: {caminho}"))
            continue
        brutos[tabela] = ler_csv(caminho)
    base = montar_base(brutos, erros)
    if erros:
        raise ErroCarga(erros)
    return base


def validar_diretorio(diretorio: Path | str) -> list[ErroValidacao]:
    erros: list[ErroValidacao] = []
    try:
        carregar_diretorio(diretorio)
    except ErroCarga as exc:
        erros = exc.erros
    return erros
