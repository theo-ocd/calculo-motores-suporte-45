"""Respostas JSON da interface web (funções sobre a base carregada, sem I/O de rede)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import tensorcad
from tensorcad import desenho
from tensorcad.loader import BaseDados, Padroes
from tensorcad.models import ChapaCarcaca, Motor, Origem
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

# Dimensões-chave editáveis (campo, rótulo, unidade); x do tubo e piso são fixos.
CAMPOS_CHAPA: tuple[tuple[str, str, str], ...] = (
    ("comprimento_chapa", "Comprimento da chapa", "mm"),
    ("dx_L_tubo", "Tubo → ponta baixa (x)", "mm"),
    ("dy_L_tubo", "Tubo → ponta baixa (y)", "mm"),
    ("dist_L_ranhura", "Ponta baixa → ranhura", "mm"),
    ("comprimento_ranhura", "Comprimento das ranhuras", "mm"),
    ("dist_entre_ranhuras", "Vão entre ranhuras", "mm"),
    ("dist_ranhura_topo", "Ranhura → ponta alta", "mm"),
    ("largura_ranhura", "Largura das ranhuras", "mm"),
    ("e_apoio", "Chapa → apoio dos pés", "mm"),
    ("theta_deg", "Inclinação", "°"),
)
CAMPOS_MOTOR: tuple[tuple[str, str, str], ...] = (
    ("H", "Altura de eixo", "mm"),
    ("A", "A — entre furos dos pés", "mm"),
    ("K", "K — diâmetro do furo", "mm"),
)


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
    if any(r.d_ini is None or r.d_fim is None for r in rs):
        faltam.append("comprimento das ranhuras / vão")
    if faltam:
        return PARCIAL, chapa.chapa_id, "pendente: " + ", ".join(faltam)
    # largura não entra na geometria 2D: só a verificação do furo K (aviso no cálculo)
    if any(r.largura is None for r in rs):
        return OK, chapa.chapa_id, "medidas completas (largura da ranhura não informada)"
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
        linha = ctx.padroes.linhas.get(str(n)) if chapa_id else None
        out.append(
            {
                "carcaca": str(n),
                "status": status,
                "chapa": chapa_id,
                "detalhe": detalhe,
                "motores": lista,
                "calculavel": status != ERRO,
                "dimensoes_chapa": (
                    {c: getattr(linha, c) for c, _, _ in CAMPOS_CHAPA} if linha else None
                ),
            }
        )
    return out


def campos(_ctx: Contexto) -> dict[str, Any]:
    """Metadados dos campos editáveis (rótulos e unidades)."""

    def lista(cs: tuple[tuple[str, str, str], ...]) -> list[dict[str, str]]:
        return [{"campo": c, "rotulo": r, "unidade": u} for c, r, u in cs]

    return {"chapa": lista(CAMPOS_CHAPA), "motor": lista(CAMPOS_MOTOR)}


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
    ajustes = corpo.get("ajustes") or {}
    if not isinstance(ajustes, dict):
        erros["ajustes"] = "esperado um objeto"
        ajustes = {}
    aj_chapa = _ler_ajustes(
        ajustes.get("chapa"),
        CAMPOS_CHAPA,
        "chapa",
        erros,
        opcionais={"comprimento_ranhura", "dist_entre_ranhuras", "largura_ranhura"},
    )
    aj_motor = _ler_ajustes(ajustes.get("motor"), CAMPOS_MOTOR, "motor", erros, opcionais=set())
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
    linha = ctx.padroes.linhas[carc]
    if aj_chapa:
        try:
            linha = ChapaCarcaca.model_validate({**linha.model_dump(), **aj_chapa})
        except ValidationError as exc:
            erros.update(_erros_pydantic(exc, "chapa"))
    if aj_motor:
        try:
            motor = Motor.model_validate({**motor.model_dump(), **aj_motor})
        except ValidationError as exc:
            erros.update(_erros_pydantic(exc, "motor"))
    if erros:
        raise ErroEntrada(erros)
    chapa, ranhuras = linha.como_padrao()
    entrada = EntradaCaso(
        str(corpo.get("caso_id") or "caso"),
        motor,
        chapa,
        {r.ranhura_n: r.como_ranhura(motor.carcaca) for r in ranhuras},
        r_min,
        r_max,
        cota,
    )
    cfg = ConfigProjeto(y_piso=ctx.y_piso, x_tubo=ctx.x_tubo)
    r = resolver_caso(entrada, cfg)
    return {
        **serializar(r),
        "desenho": desenho.gerar(r, cfg),
        "ajustes_aplicados": {"chapa": aj_chapa, "motor": aj_motor},
        "dimensoes_chapa": {c: getattr(linha, c) for c, _, _ in CAMPOS_CHAPA},
    }


def _ler_ajustes(
    bruto: Any,
    campos_validos: tuple[tuple[str, str, str], ...],
    grupo: str,
    erros: dict[str, str],
    opcionais: set[str],
) -> dict[str, float | None]:
    """Valores numéricos dos ajustes; chave inválida ou número ruim viram erro de campo.
    Campos opcionais aceitam vazio (= remover o valor)."""
    if bruto is None:
        return {}
    if not isinstance(bruto, dict):
        erros[f"ajustes.{grupo}"] = "esperado um objeto"
        return {}
    validos = {c for c, _, _ in campos_validos}
    out: dict[str, float | None] = {}
    for campo, valor in bruto.items():
        chave = f"ajustes.{grupo}.{campo}"
        if campo not in validos:
            erros[chave] = "campo não editável"
            continue
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            if campo in opcionais:
                out[campo] = None
            else:
                erros[chave] = "obrigatório"
            continue
        sub: dict[str, str] = {}
        x = _num({campo: valor}, campo, sub, obrigatorio=True)
        if sub:
            erros[chave] = sub[campo]
        else:
            out[campo] = x
    return out


def _erros_pydantic(exc: ValidationError, grupo: str) -> dict[str, str]:
    out = {}
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"])
        chave = f"ajustes.{grupo}.{loc}" if loc else f"ajustes.{grupo}"
        out[chave] = _traduzir(e)
    return out


_LIMITES = {
    "greater_than": "deve ser maior que {gt:g}",
    "greater_than_equal": "deve ser maior ou igual a {ge:g}",
    "less_than": "deve ser menor que {lt:g}",
    "less_than_equal": "deve ser menor ou igual a {le:g}",
}


def _traduzir(e: Any) -> str:
    """Mensagem de validação em português (limites numéricos e erros do modelo)."""
    modelo = _LIMITES.get(e.get("type", ""))
    if modelo:
        try:
            return modelo.format(**e.get("ctx", {}))
        except (KeyError, ValueError):
            pass
    return str(e["msg"]).removeprefix("Value error, ")
