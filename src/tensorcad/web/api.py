"""Respostas JSON da interface web (funções sobre a base carregada, sem I/O de rede)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tensorcad
from tensorcad import ajustes as ajustes_mod
from tensorcad import banco_duplo, correia, desenho, desenho_th
from tensorcad import tubo_horizontal as th
from tensorcad.loader import BaseDados, Padroes, carregar_parametros_th, carregar_transmissao
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
    dy_banco2: float = banco_duplo.DESLOCAMENTO_Y_PADRAO  # O2 acima de O (banco duplo)


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
        "fixos": {"y_piso": ctx.y_piso, "x_tubo": ctx.x_tubo, "dy_banco2": ctx.dy_banco2},
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
                # tubo horizontal: só depende de haver motor (não usa a chapa do 45°)
                "status_horizontal": OK if lista else ERRO,
                "detalhe_horizontal": (
                    f"{len(lista)} motor(es) no catálogo" if lista else "nenhum motor cadastrado"
                ),
                "calculavel_horizontal": bool(lista),
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


def _ler_banco_duplo(
    ctx: Contexto, bruto: Any, erros: dict[str, str]
) -> banco_duplo.ConfigBancoDuplo | None:
    """{"ativo": bool, "R2_min", "R2_max"} (raios do banco 2); None se desligado."""
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        erros["banco_duplo"] = "esperado um objeto"
        return None
    if not bruto.get("ativo"):
        return None
    sub: dict[str, str] = {}
    r2_min = _num(bruto, "R2_min", sub, obrigatorio=True, positivo=True)
    r2_max = _num(bruto, "R2_max", sub, obrigatorio=True, positivo=True)
    if r2_min is not None and r2_max is not None and r2_min > r2_max:
        sub["R2_max"] = "R2_max deve ser maior ou igual a R2_min"
    erros.update({f"banco_duplo.{k}": v for k, v in sub.items()})
    if sub or r2_min is None or r2_max is None:
        return None
    return banco_duplo.ConfigBancoDuplo(r2_min, r2_max, ctx.dy_banco2)


def _banco_duplo(av: banco_duplo.AvaliacaoBancoDuplo) -> dict[str, Any]:
    return {
        "deslocamento_y": av.config.deslocamento_y,
        "R2_min": av.config.R2_min,
        "R2_max": av.config.R2_max,
        "H": av.H,
        "ok": av.ok,
        "avisos": list(av.avisos),
        "posicoes": [
            {
                "rotulo": q.rotulo,
                "R1": q.R1,
                "R2": q.R2,
                "dist_O2": q.dist_O2,
                "folga_R2": q.folga_R2,
                "d_R1": -q.s_R1,
                "d_R2": None if q.s_R2 is None else -q.s_R2,
                "curso": q.curso,
                "dentro": q.dentro,
            }
            for q in av.posicoes
        ],
    }


def calcular(ctx: Contexto, corpo: dict[str, Any]) -> dict[str, Any]:
    """Entradas: carcaca, motor_id (opcional), R_min, R_max, cota (opcional), caso_id,
    banco_duplo (opcional: ativo, R2_min, R2_max)."""
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
    bd = _ler_banco_duplo(ctx, corpo.get("banco_duplo"), erros)
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
    if bd is None:
        r, av = resolver_caso(entrada, cfg), None
    else:
        r, av = banco_duplo.resolver(bd, entrada, cfg)
    return {
        **serializar(r),
        "banco_duplo": None if av is None else _banco_duplo(av),
        "desenho": desenho.gerar(r, cfg, av),
        "ajustes_aplicados": {"chapa": aj_chapa, "motor": aj_motor},
        "dimensoes_chapa": {c: getattr(linha, c) for c, _, _ in CAMPOS_CHAPA},
    }


# --------------------------------------------------------------------------- tubo horizontal


def _posicao_th(p: th.PosicaoTH) -> dict[str, Any]:
    return {
        "R": p.R,
        "altura_tubo": p.altura_tubo,
        "status": p.status.value,
        "g": p.g,
        "x": p.x,
        "y_motor": p.y_motor,
        "folga_g": p.folga_g,
        "folga_x": p.folga_x,
        "folga_rel": p.folga_rel,
        "margem": p.margem,
        "R2": p.R2,
        "dist_O2": p.dist_O2,
        "folga_R2": p.folga_R2,
        "mensagens": list(p.mensagens),
    }


def _par_th(par: tuple[th.PosicaoTH, th.PosicaoTH] | None) -> list[dict[str, Any]] | None:
    return None if par is None else [_posicao_th(p) for p in par]


def _ler_g_manual(
    bruto: Any, altura: float | None, erros: dict[str, str]
) -> tuple[float | None, float | None] | None:
    """[g 0 %, g 3 %] (cada um número ou null). Só vale com a altura do tubo informada."""
    if bruto is None or (isinstance(bruto, list) and all(v in (None, "") for v in bruto)):
        return None
    if not isinstance(bruto, list) or len(bruto) != 2:
        erros["g_manual"] = "esperado [g 0 %, g 3 %]"
        return None
    if altura is None:
        erros["g_manual"] = "o ajuste manual de g exige a altura do tubo informada"
        return None
    sub: dict[str, str] = {}
    vals = tuple(_num({"g": v}, "g", sub, obrigatorio=False) for v in bruto)
    if sub:
        erros["g_manual"] = "g deve ser número"
        return None
    return vals[0], vals[1]


def calcular_horizontal(ctx: Contexto, corpo: dict[str, Any]) -> dict[str, Any]:
    """Layout tubo horizontal. Entradas: carcaca, motor_id (opcional), R_min, R_max,
    comprimento_tubo, altura_tubo (opcional), invertido, banco_duplo (opcional), caso_id."""
    if not isinstance(corpo, dict):
        raise ErroEntrada({"(corpo)": "esperado um objeto JSON"})
    erros: dict[str, str] = {}
    carc = str(corpo.get("carcaca") or "").strip()
    info = {c["carcaca"]: c for c in carcacas(ctx)}.get(carc)
    if not carc:
        erros["carcaca"] = "obrigatório"
    elif info is None or not info["calculavel_horizontal"]:
        erros["carcaca"] = f"carcaça {carc} sem motor no catálogo"
    r_min = _num(corpo, "R_min", erros, obrigatorio=True, positivo=True)
    r_max = _num(corpo, "R_max", erros, obrigatorio=True, positivo=True)
    if r_min is not None and r_max is not None and r_min > r_max:
        erros["R_max"] = "R_max deve ser maior ou igual a R_min"
    comp = _num(corpo, "comprimento_tubo", erros, obrigatorio=True, positivo=True)
    altura = _num(corpo, "altura_tubo", erros, obrigatorio=False)
    g_manual = _ler_g_manual(corpo.get("g_manual"), altura, erros)
    bd = _ler_banco_duplo(ctx, corpo.get("banco_duplo"), erros)
    motor = None
    if info is not None and info["calculavel_horizontal"]:
        ids = [m["motor_id"] for m in info["motores"]]
        motor_id = str(corpo.get("motor_id") or ids[0])
        if motor_id not in ids:
            erros["motor_id"] = f"motor {motor_id} não pertence à carcaça {carc}"
        else:
            motor = ctx.base.motores[motor_id]
    if erros:
        raise ErroEntrada(erros)
    assert motor is not None and r_min is not None and r_max is not None and comp is not None
    try:
        fixos = carregar_parametros_th(ctx.dir_padroes)
    except FileNotFoundError:
        fixos = {}
    par = th.ParametrosTH(
        comprimento_tubo=comp,
        invertido=bool(corpo.get("invertido")),
        x_linha=ctx.x_tubo,
        y_laje=ctx.y_piso,
        **fixos,
    )
    e = th.EntradaTH(str(corpo.get("caso_id") or "caso"), motor, r_min, r_max, altura, bd, g_manual)
    r = th.resolver(par, e)
    return {
        "layout": "horizontal",
        "caso_id": e.caso_id,
        "status": r.status.value,
        "mensagem": r.mensagem,
        "motor": {"motor_id": motor.motor_id, "carcaca": motor.carcaca, "H": motor.H, "A": motor.A},
        "invertido": par.invertido,
        "comprimento_tubo": par.comprimento_tubo,
        "x_max": r.x_max,
        "R_min": r_min,
        "R_max": r_max,
        "altura_informada": altura,
        "g_manual": None if g_manual is None else list(g_manual),
        "faixas_altura": [list(f) for f in r.faixas_altura],
        "altura_recomendada": r.altura_recomendada,
        "margem_recomendada": r.margem_recomendada,
        "em_recomendada": _par_th(r.em_recomendada),
        "em_informada": _par_th(r.em_informada),
        "banco_duplo": None
        if bd is None
        else {"R2_min": bd.R2_min, "R2_max": bd.R2_max, "deslocamento_y": bd.deslocamento_y},
        "desenho": desenho_th.gerar(r),
    }


# --------------------------------------------------------------------------- setups (S2)

FORMATO_SETUPS = "tensorcad-setups"
VERSAO_SETUPS = 1
# padrão se a tabela não estiver disponível (data/padrao/transmissao.csv)
TRANSMISSAO_PADRAO = {
    "polia_maquina": [355.0],
    "polia_motor": [
        125.0,
        132.0,
        140.0,
        150.0,
        160.0,
        170.0,
        180.0,
        190.0,
        200.0,
        212.0,
        224.0,
        236.0,
        250.0,
        280.0,
    ],
    "rpm_motor": [900.0, 1200.0, 1800.0, 3600.0],
}


def transmissao(ctx: Contexto) -> dict[str, list[float]]:
    """Listas da tela de setups: polias da máquina e do motor e rpm do motor (WEG 60 Hz)."""
    try:
        return carregar_transmissao(ctx.dir_padroes)
    except FileNotFoundError:
        return TRANSMISSAO_PADRAO


def _correia(
    bruto: dict[str, Any], listas: dict[str, list[float]], erros: dict[str, str], pre: str = ""
) -> correia.Correia | None:
    sub: dict[str, str] = {}
    D = _num(bruto, "polia_maquina", sub, obrigatorio=True, positivo=True)
    d = _num(bruto, "polia_motor", sub, obrigatorio=True, positivo=True)
    L = _num(bruto, "correia", sub, obrigatorio=True, positivo=True)
    if D is not None and D not in listas["polia_maquina"]:
        sub["polia_maquina"] = "fora da lista de polias da máquina"
    if d is not None and d not in listas["polia_motor"]:
        sub["polia_motor"] = "fora da lista de polias do motor"
    c = None
    if not sub:
        assert D is not None and d is not None and L is not None
        c = correia.Correia(D, d, L)
        try:
            correia.distancia_eixos(c)
        except ValueError as exc:
            sub["correia"] = str(exc)
            c = None
    erros.update({f"{pre}{k}": v for k, v in sub.items()})
    return c


def setup(ctx: Contexto, corpo: dict[str, Any]) -> dict[str, Any]:
    """Valida e calcula um setup: R_min (0 %), R_info (2 %), R_max (3 %), rpm e sufixo.

    Entradas: id, nome, polia_maquina, polia_motor, correia, rpm_motor e, opcional,
    banco2 {polia_maquina, polia_motor, correia} (mesmo rpm do motor)."""
    if not isinstance(corpo, dict):
        raise ErroEntrada({"(corpo)": "esperado um objeto JSON"})
    listas = transmissao(ctx)
    erros: dict[str, str] = {}
    nome = str(corpo.get("nome") or "").strip()
    if not nome:
        erros["nome"] = "o setup precisa de um nome"
    rpm = _num(corpo, "rpm_motor", erros, obrigatorio=True, positivo=True)
    if rpm is not None and rpm not in listas["rpm_motor"]:
        erros["rpm_motor"] = "fora da lista de rpm (WEG 60 Hz)"
    c1 = _correia(corpo, listas, erros)
    b2 = corpo.get("banco2")
    c2 = None
    if b2 is not None:
        if not isinstance(b2, dict):
            erros["banco2"] = "esperado um objeto"
        else:
            c2 = _correia(b2, listas, erros, "banco2.")
    if erros:
        raise ErroEntrada(erros)
    assert c1 is not None and rpm is not None
    r1 = correia.raios(c1)
    out: dict[str, Any] = {
        "id": str(corpo.get("id") or "").strip() or None,
        "nome": nome,
        "polia_maquina": c1.polia_maquina,
        "polia_motor": c1.polia_motor,
        "correia": c1.comprimento,
        "rpm_motor": rpm,
        "rpm_maquina": correia.rpm_maquina(rpm, c1),
        "sufixo": correia.sufixo(c1),
        "R_min": r1.R_min,
        "R_info": r1.R_info,
        "R_max": r1.R_max,
        "banco2": None,
    }
    if c2 is not None:
        r2 = correia.raios(c2)
        out["banco2"] = {
            "polia_maquina": c2.polia_maquina,
            "polia_motor": c2.polia_motor,
            "correia": c2.comprimento,
            "rpm_maquina": correia.rpm_maquina(rpm, c2),
            "R2_min": r2.R_min,
            "R2_info": r2.R_info,
            "R2_max": r2.R_max,
        }
    return out


def biblioteca(ctx: Contexto, corpo: Any) -> dict[str, Any]:
    """Confere e recalcula uma biblioteca de setups (arquivo tensorcad-setups)."""
    if not isinstance(corpo, dict):
        raise ErroEntrada({"(biblioteca)": "esperado um objeto JSON"})
    erros: dict[str, str] = {}
    if corpo.get("formato") != FORMATO_SETUPS:
        erros["formato"] = f"esperado '{FORMATO_SETUPS}'"
    if corpo.get("versao") != VERSAO_SETUPS:
        erros["versao"] = f"versão suportada: {VERSAO_SETUPS}"
    lista = corpo.get("setups")
    if not isinstance(lista, list):
        erros["setups"] = "esperada uma lista de setups"
    if erros:
        raise ErroEntrada(erros)
    out = []
    for i, s in enumerate(lista):
        try:
            out.append(setup(ctx, s))
        except ErroEntrada as exc:
            erros.update({f"setups[{i}].{k}": v for k, v in exc.erros.items()})
    nomes = [s["nome"].lower() for s in out]
    if not erros and len(set(nomes)) != len(nomes):
        erros["setups"] = "nomes de setup repetidos"
    if erros:
        raise ErroEntrada(erros)
    return {"formato": FORMATO_SETUPS, "versao": VERSAO_SETUPS, "setups": out}


# --------------------------------------------------------------------------- projeto (W4)

FORMATO_PROJETO = "tensorcad-projeto"
VERSAO_PROJETO = 1
# opções de layout do projeto (T1); arquivos sem o campo são do tubo inclinado 45°
LAYOUTS = ("inclinado_45", "horizontal")
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
    if corpo.get("layout", LAYOUTS[0]) not in LAYOUTS:
        erros["layout"] = f"opção de layout desconhecida (use {' ou '.join(LAYOUTS)})"
    horizontal = corpo.get("horizontal")
    if horizontal is not None and not isinstance(horizontal, dict):
        erros["horizontal"] = "esperado um objeto"
    if erros:
        raise ErroEntrada(erros)
    return corpo


def _setup_do_caso(
    ctx: Contexto, caso: dict[str, Any], erros: dict[str, str], onde: str
) -> dict[str, Any] | None:
    """Setup de origem do caso, recalculado (confere os dados gravados no projeto)."""
    st = caso.get("setup")
    if not st:
        return None
    try:
        return setup(ctx, st)
    except ErroEntrada as exc:
        erros.update({f"{onde}.setup.{k}": v for k, v in exc.erros.items()})
        return None


def _vazio(caso: Any) -> bool:
    """Caso sem R_min nem R_max: fica fora da exportação (ex.: caso-modelo de um layout)."""
    c = caso if isinstance(caso, dict) else {}
    return all(c.get(k) in (None, "") for k in ("R_min", "R_max"))


def exportar(ctx: Contexto, corpo: Any) -> tuple[bytes, str]:
    """Planilha do projeto (.xlsx, uma aba por caso) a partir do projeto da interface.

    Exporta os casos dos dois layouts (tubo inclinado 45° e tubo horizontal); casos sem
    R_min e R_max são ignorados."""
    import io

    from tensorcad.planilha_projeto import EntradaHorizontal, EntradaPlanilha, gerar_projeto

    projeto = validar_projeto(corpo)
    erros: dict[str, str] = {}
    entradas = []
    bd_ativo = bool(projeto.get("banco_duplo"))
    for i, caso in enumerate(projeto["casos"]):
        if _vazio(caso):
            continue
        dados = {
            **caso,
            "cota": projeto.get("cota"),
            "banco_duplo": {
                "ativo": bd_ativo,
                "R2_min": caso.get("R2_min"),
                "R2_max": caso.get("R2_max"),
            },
        }
        try:
            r = calcular(ctx, dados)
        except ErroEntrada as exc:
            erros.update({f"casos[{i}].{k}": v for k, v in exc.erros.items()})
            continue
        aj = r["ajustes_aplicados"]
        st = _setup_do_caso(ctx, caso, erros, f"casos[{i}]")
        entradas.append(
            EntradaPlanilha(
                caso_id=str(caso["caso_id"]).strip(),
                motor_id=r["motor"]["motor_id"],
                R_min=r["R_min"],
                R_max=r["R_max"],
                cota_informada=r["cota_informada"],
                ajustes={k: v for k, v in aj.items() if v} or None,
                banco_duplo=None
                if r["banco_duplo"] is None
                else {
                    "R2_min": r["banco_duplo"]["R2_min"],
                    "R2_max": r["banco_duplo"]["R2_max"],
                    "deslocamento_y": r["banco_duplo"]["deslocamento_y"],
                },
                setup=st,
            )
        )
    horizontais = []
    h = projeto.get("horizontal") or {}
    for i, caso in enumerate(h.get("casos") or []):
        if _vazio(caso):
            continue
        dados = {
            **caso,
            "altura_tubo": h.get("altura_tubo"),
            "comprimento_tubo": h.get("comprimento_tubo"),
            "invertido": bool(h.get("invertido")),
            "banco_duplo": {
                "ativo": bd_ativo,
                "R2_min": caso.get("R2_min"),
                "R2_max": caso.get("R2_max"),
            },
        }
        try:
            r = calcular_horizontal(ctx, dados)
        except ErroEntrada as exc:
            erros.update({f"horizontal.casos[{i}].{k}": v for k, v in exc.erros.items()})
            continue
        horizontais.append(
            EntradaHorizontal(
                caso_id=str(caso["caso_id"]).strip(),
                motor_id=r["motor"]["motor_id"],
                R_min=r["R_min"],
                R_max=r["R_max"],
                comprimento_tubo=r["comprimento_tubo"],
                altura_informada=r["altura_informada"],
                invertido=r["invertido"],
                banco_duplo=r["banco_duplo"],
                g_manual=r["g_manual"],
                setup=_setup_do_caso(ctx, caso, erros, f"horizontal.casos[{i}]"),
            )
        )
    if not erros and not entradas and not horizontais:
        erros["casos"] = "nenhum caso preenchido (R_min e R_max) para exportar"
    nomes = [e.caso_id.lower() for e in [*entradas, *horizontais]]
    if not erros and len(set(nomes)) != len(nomes):
        erros["casos"] = "o mesmo nome de caso aparece nos dois layouts"
    if erros:
        raise ErroEntrada(erros)
    nome = str(projeto.get("nome") or "PROJETO").strip() or "PROJETO"
    cfg = ConfigProjeto(nome=nome, y_piso=ctx.y_piso, x_tubo=ctx.x_tubo)
    buf = io.BytesIO()
    try:
        fixos = carregar_parametros_th(ctx.dir_padroes)
    except FileNotFoundError:
        fixos = {}
    gerar_projeto(buf, cfg, entradas, ctx.base, ctx.padroes, horizontais, fixos)
    arquivo = re.sub(r"[^\w\-. ]", "_", nome).strip() or "projeto"
    return buf.getvalue(), f"{arquivo}.xlsx"
