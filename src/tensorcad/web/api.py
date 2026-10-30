"""Respostas JSON da interface web (funções sobre a base carregada, sem I/O de rede)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tensorcad
from tensorcad.loader import BaseDados, Padroes
from tensorcad.models import Origem
from tensorcad.projeto import (
    X_TUBO_PADRAO,
    Y_PISO_PADRAO,
    ConfigProjeto,
    EntradaCaso,
    Posicao,
    ResultadoProjeto,
    resolver_caso,
)

FAIXA_CARCACAS = (160, 250)

# Status exibidos na interface
OK, PARCIAL, ERRO = "ok", "parcial", "erro"


class ErroEntrada(ValueError):
    """Entradas inválidas: {campo: mensagem}."""

    def __init__(self, erros: dict[str, str]) -> None:
        self.erros = erros
        super().__init__("; ".join(f"{k}: {v}" for k, v in erros.items()))


@dataclass
class Contexto:
    """Dados carregados pelo servidor. Distâncias ao centro dos raios são fixas."""

    base: BaseDados
    padroes: Padroes
    dir_dados: Path
    dir_padroes: Path
    faixa: tuple[int, int] = FAIXA_CARCACAS
    y_piso: float = Y_PISO_PADRAO
    x_tubo: float = X_TUBO_PADRAO


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
        "erros_chapas": len(ctx.padroes.erros),
        "faixa": list(ctx.faixa),
        "fixos": {"y_piso": ctx.y_piso, "x_tubo": ctx.x_tubo},
    }


def _status_chapa(ctx: Contexto, numero: int) -> tuple[str, str | None, str]:
    """(status, chapa_id, detalhe) com status ok | parcial | erro."""
    chave = str(numero)
    if chave in ctx.padroes.com_erro:
        return ERRO, None, "erro na tabela de chapas: " + "; ".join(ctx.padroes.com_erro[chave])
    chapa = ctx.padroes.chapa_para(chave)
    if chapa is None:
        if chave in ctx.padroes.a_preencher:
            return ERRO, None, "medidas da chapa a preencher"
        return ERRO, None, "carcaça ausente da tabela de chapas"
    rs = [r for r in ctx.padroes.ranhuras if r.chapa_id == chapa.chapa_id]
    faltam = []
    if chapa.origem is not Origem.MEDIDO:
        faltam.append(f"origem {chapa.origem.value}")
    if any(r.largura is None for r in rs):
        faltam.append("largura das ranhuras")
    if any(r.d_ini is None or r.d_fim is None for r in rs):
        faltam.append("comprimento das ranhuras / vão")
    if faltam:
        return PARCIAL, chapa.chapa_id, "pendente: " + ", ".join(faltam)
    return OK, chapa.chapa_id, "medidas completas"


def carcacas(ctx: Contexto) -> list[dict[str, Any]]:
    """Carcaças da faixa do projeto presentes na planilha (motores e/ou chapas)."""
    lo, hi = ctx.faixa
    motores: dict[int, list[dict[str, Any]]] = {}
    for m in ctx.base.motores.values():
        n = _numero(m.carcaca)
        if n is not None and lo <= n <= hi:
            motores.setdefault(n, []).append(
                {"motor_id": m.motor_id, "carcaca": m.carcaca, "H": m.H, "A": m.A, "K": m.K}
            )
    numeros = set(motores)
    for txt in [*ctx.padroes.a_preencher, *ctx.padroes.com_erro]:
        n = _numero(txt)
        if n is not None and lo <= n <= hi:
            numeros.add(n)
    for ch in ctx.padroes.chapas.values():
        for txt in ch.carcacas_compat:
            n = _numero(txt)
            if n is not None and lo <= n <= hi:
                numeros.add(n)
    out = []
    for n in sorted(numeros):
        status, chapa_id, detalhe = _status_chapa(ctx, n)
        lista = sorted(motores.get(n, []), key=lambda d: d["motor_id"])
        if status != ERRO and not lista:
            status, detalhe = ERRO, "nenhum motor cadastrado para a carcaça"
        out.append(
            {
                "carcaca": str(n),
                "status": status,
                "chapa": chapa_id,
                "detalhe": detalhe,
                "motores": lista,
                "calculavel": status != ERRO,
            }
        )
    return out


# --------------------------------------------------------------------------- cálculo


def _num(
    corpo: dict[str, Any],
    campo: str,
    erros: dict[str, str],
    *,
    obrigatorio: bool,
    positivo: bool = False,
) -> float | None:
    v = corpo.get(campo)
    if v is None or (isinstance(v, str) and not v.strip()):
        if obrigatorio:
            erros[campo] = "obrigatório"
        return None
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        erros[campo] = "número inválido"
        return None
    if not math.isfinite(x):
        erros[campo] = "número inválido"
        return None
    if positivo and x <= 0:
        erros[campo] = "deve ser maior que zero"
        return None
    return x


def _posicao(p: Posicao) -> dict[str, Any]:
    return {
        "R": p.R,
        "cota": p.cota,
        "status": p.status.value,
        "s": p.s,
        "d_motor": p.d_motor,
        "Cx": p.Cx,
        "Cy": p.Cy,
        "folga_neg": p.folga_neg,
        "folga_pos": p.folga_pos,
        "margem": p.margem,
        "mensagens": list(p.mensagens),
    }


def _par(par: tuple[Posicao, Posicao] | None) -> list[dict[str, Any]] | None:
    return None if par is None else [_posicao(p) for p in par]


def serializar(r: ResultadoProjeto) -> dict[str, Any]:
    e = r.entrada
    rs = e.ranhuras
    return {
        "caso_id": e.caso_id,
        "status": r.status.value,
        "mensagem": r.mensagem,
        "motor": {
            "motor_id": e.motor.motor_id,
            "carcaca": e.motor.carcaca,
            "H": e.motor.H,
            "A": e.motor.A,
            "K": e.motor.K,
        },
        "chapa": {
            "chapa_id": e.chapa.chapa_id,
            "origem": e.chapa.origem.value,
            "theta_deg": e.chapa.theta_deg,
            "comprimento": e.chapa.comprimento,
            "dx_L_tubo": e.chapa.dx_L,
            "dy_L_tubo": e.chapa.cota_L_tubo,
            "ranhura1_d_fim": -rs[1].u_ini if 1 in rs and rs[1].u_ini is not None else None,
            "ranhura2_d_ini": -rs[2].u_fim if 2 in rs and rs[2].u_fim is not None else None,
        },
        "h": r.h,
        "R_min": e.R_min,
        "R_max": e.R_max,
        "cota_informada": e.cota_informada,
        "faixas_cota": [list(f) for f in r.faixas_cota],
        "cota_recomendada": r.cota_recomendada,
        "margem_recomendada": r.margem_recomendada,
        "em_recomendada": _par(r.em_recomendada),
        "em_informada": _par(r.em_informada),
    }


def calcular(ctx: Contexto, corpo: dict[str, Any]) -> dict[str, Any]:
    """Entradas: carcaca, motor_id (opcional), R_min, R_max, cota (opcional), caso_id."""
    if not isinstance(corpo, dict):
        raise ErroEntrada({"(corpo)": "esperado um objeto JSON"})
    erros: dict[str, str] = {}
    carc = str(corpo.get("carcaca") or "").strip()
    info = {c["carcaca"]: c for c in carcacas(ctx)}.get(carc)
    if not carc:
        erros["carcaca"] = "obrigatório"
    elif info is None:
        erros["carcaca"] = f"carcaça {carc} fora da faixa ou ausente da planilha"
    elif not info["calculavel"]:
        erros["carcaca"] = info["detalhe"]
    r_min = _num(corpo, "R_min", erros, obrigatorio=True, positivo=True)
    r_max = _num(corpo, "R_max", erros, obrigatorio=True, positivo=True)
    cota = _num(corpo, "cota", erros, obrigatorio=False)
    if r_min is not None and r_max is not None and r_min > r_max:
        erros["R_max"] = "R_max deve ser maior ou igual a R_min"
    motor = None
    if info is not None and info["calculavel"]:
        ids = [m["motor_id"] for m in info["motores"]]
        motor_id = str(corpo.get("motor_id") or ids[0])
        if motor_id not in ids:
            erros["motor_id"] = f"motor {motor_id} não pertence à carcaça {carc}"
        else:
            motor = ctx.base.motores[motor_id]
    if erros:
        raise ErroEntrada(erros)
    assert motor is not None and r_min is not None and r_max is not None
    chapa = ctx.padroes.chapa_para(motor.carcaca)
    assert chapa is not None
    entrada = EntradaCaso(
        str(corpo.get("caso_id") or "caso"),
        motor,
        chapa,
        ctx.padroes.ranhuras_de(chapa.chapa_id, motor.carcaca),
        r_min,
        r_max,
        cota,
    )
    cfg = ConfigProjeto(y_piso=ctx.y_piso, x_tubo=ctx.x_tubo)
    return serializar(resolver_caso(entrada, cfg))
