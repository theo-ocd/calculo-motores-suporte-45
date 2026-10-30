"""Respostas JSON da interface web (funções sobre a base carregada, sem I/O de rede)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tensorcad
from tensorcad import ajustes as ajustes_mod
from tensorcad import desenho
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

CAMPOS_CHAPA = ajustes_mod.CAMPOS_CHAPA
CAMPOS_MOTOR = ajustes_mod.CAMPOS_MOTOR


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
    aj_chapa, aj_motor = ajustes_mod.ler(corpo.get("ajustes"), erros)
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
    linha, motor = ajustes_mod.aplicar(linha, motor, aj_chapa, aj_motor, erros)
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


# --------------------------------------------------------------------------- projeto (W4)

FORMATO_PROJETO = "tensorcad-projeto"
VERSAO_PROJETO = 1
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def validar_projeto(corpo: Any) -> dict[str, Any]:
    """Confere o envelope do projeto (.json): formato, versão e lista de casos."""
    if not isinstance(corpo, dict):
        raise ErroEntrada({"(projeto)": "esperado um objeto JSON"})
    erros: dict[str, str] = {}
    if corpo.get("formato") != FORMATO_PROJETO:
        erros["formato"] = f"esperado '{FORMATO_PROJETO}'"
    if corpo.get("versao") != VERSAO_PROJETO:
        erros["versao"] = f"versão suportada: {VERSAO_PROJETO}"
    casos = corpo.get("casos")
    if not isinstance(casos, list) or not casos:
        erros["casos"] = "o projeto precisa de ao menos um caso"
    else:
        nomes = [str((c or {}).get("caso_id") or "").strip() for c in casos]
        if any(not n for n in nomes):
            erros["casos"] = "todo caso precisa de um nome"
        elif len({n.lower() for n in nomes}) != len(nomes):
            erros["casos"] = "nomes de caso repetidos"
    if erros:
        raise ErroEntrada(erros)
    return corpo


def exportar(ctx: Contexto, corpo: Any) -> tuple[bytes, str]:
    """Planilha do projeto (.xlsx, uma aba por caso) a partir do projeto da interface."""
    import io

    from tensorcad.planilha_projeto import EntradaPlanilha, gerar_projeto

    projeto = validar_projeto(corpo)
    erros: dict[str, str] = {}
    entradas = []
    for i, caso in enumerate(projeto["casos"]):
        dados = {**caso, "cota": projeto.get("cota")}
        try:
            r = calcular(ctx, dados)
        except ErroEntrada as exc:
            erros.update({f"casos[{i}].{k}": v for k, v in exc.erros.items()})
            continue
        aj = r["ajustes_aplicados"]
        entradas.append(
            EntradaPlanilha(
                caso_id=str(caso["caso_id"]).strip(),
                motor_id=r["motor"]["motor_id"],
                R_min=r["R_min"],
                R_max=r["R_max"],
                cota_informada=r["cota_informada"],
                ajustes={k: v for k, v in aj.items() if v} or None,
            )
        )
    if erros:
        raise ErroEntrada(erros)
    nome = str(projeto.get("nome") or "PROJETO").strip() or "PROJETO"
    cfg = ConfigProjeto(nome=nome, y_piso=ctx.y_piso, x_tubo=ctx.x_tubo)
    buf = io.BytesIO()
    gerar_projeto(buf, cfg, entradas, ctx.base, ctx.padroes)
    arquivo = re.sub(r"[^\w\-. ]", "_", nome).strip() or "projeto"
    return buf.getvalue(), f"{arquivo}.xlsx"
