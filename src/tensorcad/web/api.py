"""Respostas JSON da interface web (funções puras sobre a base carregada)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tensorcad
from tensorcad.loader import BaseDados, Padroes
from tensorcad.models import Origem

FAIXA_CARCACAS = (160, 250)


@dataclass
class Contexto:
    """Dados carregados pelo servidor."""

    base: BaseDados
    padroes: Padroes
    dir_dados: Path
    dir_padroes: Path


def _numero(carcaca: str) -> int | None:
    m = re.match(r"\d+", carcaca)
    return int(m.group(0)) if m else None


def saude(ctx: Contexto) -> dict[str, Any]:
    return {
        "status": "ok",
        "versao": tensorcad.__version__,
        "dados": str(ctx.dir_dados),
        "padroes": str(ctx.dir_padroes),
        "avisos": len(ctx.base.avisos) + len(ctx.padroes.avisos),
    }


def _status_chapa(ctx: Contexto, numero: int) -> tuple[str, str | None, str]:
    """(status, chapa_id, detalhe). Status: completa | parcial | a_preencher | sem_chapa."""
    chapa = ctx.padroes.chapa_para(str(numero))
    if chapa is None:
        if str(numero) in ctx.padroes.a_preencher:
            return "a_preencher", None, "medidas da chapa a preencher"
        return "sem_chapa", None, "carcaça ausente da tabela de chapas"
    rs = [r for r in ctx.padroes.ranhuras if r.chapa_id == chapa.chapa_id]
    faltam = []
    if chapa.origem is not Origem.MEDIDO:
        faltam.append(f"origem {chapa.origem.value}")
    if any(r.largura is None for r in rs):
        faltam.append("largura das ranhuras")
    if any(r.d_ini is None or r.d_fim is None for r in rs):
        faltam.append("comprimento das ranhuras / vão")
    if faltam:
        return "parcial", chapa.chapa_id, "pendente: " + ", ".join(faltam)
    return "completa", chapa.chapa_id, "medidas completas"


def carcacas(ctx: Contexto) -> list[dict[str, Any]]:
    """Carcaças da faixa 160–250 com motores cadastrados e situação da chapa padrão."""
    motores: dict[int, list[dict[str, Any]]] = {}
    for m in ctx.base.motores.values():
        n = _numero(m.carcaca)
        if n is not None and FAIXA_CARCACAS[0] <= n <= FAIXA_CARCACAS[1]:
            motores.setdefault(n, []).append(
                {"motor_id": m.motor_id, "carcaca": m.carcaca, "H": m.H, "A": m.A, "K": m.K}
            )
    numeros = set(motores)
    for txt in ctx.padroes.a_preencher:
        n = _numero(txt)
        if n is not None and FAIXA_CARCACAS[0] <= n <= FAIXA_CARCACAS[1]:
            numeros.add(n)
    out = []
    for n in sorted(numeros):
        status, chapa_id, detalhe = _status_chapa(ctx, n)
        out.append(
            {
                "carcaca": str(n),
                "status": status,
                "chapa": chapa_id,
                "detalhe": detalhe,
                "motores": sorted(motores.get(n, []), key=lambda d: d["motor_id"]),
                "calculavel": status in ("completa", "parcial") and bool(motores.get(n)),
            }
        )
    return out
