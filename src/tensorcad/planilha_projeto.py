"""Planilha do projeto (protótipo F6): uma aba por caso + aba PROJETO (índice).

Casos são adicionados individualmente com `adicionar_caso`. As entradas ficam numa aba
oculta (_entradas) e o arquivo é regenerado a cada inclusão (o openpyxl não preserva
gráficos ao reabrir um xlsx).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from openpyxl import Workbook, load_workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.worksheet import Worksheet

import tensorcad
from tensorcad import ajustes as ajustes_mod
from tensorcad import banco_duplo as bd
from tensorcad import desenho_th
from tensorcad import tubo_horizontal as th
from tensorcad.loader import BaseDados, Padroes
from tensorcad.planilha import CORES_STATUS, FMT_MM, _cor_status
from tensorcad.projeto import (
    ConfigProjeto,
    EntradaCaso,
    ResultadoProjeto,
    posicao,
    resolver_caso,
)

ABA_PROJETO = "PROJETO"
ABA_ENTRADAS = "_entradas"
ABA_ENTRADAS_TH = "_entradas_horizontal"  # casos do layout tubo horizontal (T6)
TITULO = Font(bold=True, size=14)
NEGRITO = Font(bold=True)
CINZA = PatternFill("solid", fgColor="D9D9D9")


@dataclass(frozen=True)
class EntradaPlanilha:
    """Entrada serializável de um caso."""

    caso_id: str
    motor_id: str
    R_min: float
    R_max: float
    cota_informada: float | None = None
    chapa_id: str | None = None
    # ajustes de dimensões {"chapa": {...}, "motor": {...}} sobre o padrão (opcional)
    ajustes: dict[str, Any] | None = None
    # tensionamento para banco duplo {"R2_min": ..., "R2_max": ...} (opcional)
    banco_duplo: dict[str, Any] | None = None


CAMPOS_ENTRADA = tuple(EntradaPlanilha.__dataclass_fields__)


@dataclass(frozen=True)
class EntradaHorizontal:
    """Caso do layout tubo horizontal (serializável)."""

    caso_id: str
    motor_id: str
    R_min: float
    R_max: float
    comprimento_tubo: float
    altura_informada: float | None = None
    invertido: bool = False
    # tensionamento para banco duplo {"R2_min", "R2_max", "deslocamento_y"} (opcional)
    banco_duplo: dict[str, Any] | None = None


def resolver_horizontal(
    ent: EntradaHorizontal,
    base: BaseDados,
    cfg: ConfigProjeto,
    fixos: dict[str, float] | None = None,
) -> th.ResultadoTH:
    if ent.motor_id not in base.motores:
        raise ValueError(f"motor '{ent.motor_id}' não cadastrado")
    par = th.ParametrosTH(
        comprimento_tubo=ent.comprimento_tubo,
        invertido=ent.invertido,
        x_linha=cfg.x_tubo,
        y_laje=cfg.y_piso,
        **(fixos or {}),
    )
    b2 = None
    if ent.banco_duplo:
        b2 = bd.ConfigBancoDuplo(
            float(ent.banco_duplo["R2_min"]),
            float(ent.banco_duplo["R2_max"]),
            float(ent.banco_duplo.get("deslocamento_y", bd.DESLOCAMENTO_Y_PADRAO)),
        )
    e = th.EntradaTH(
        ent.caso_id, base.motores[ent.motor_id], ent.R_min, ent.R_max, ent.altura_informada, b2
    )
    return th.resolver(par, e)


def nome_aba(caso_id: str) -> str:
    nome = re.sub(r"[\\/*?:\[\]]", "_", caso_id).strip() or "caso"
    return nome[:31]


def montar_entrada(ent: EntradaPlanilha, base: BaseDados, pad: Padroes) -> EntradaCaso:
    if ent.motor_id not in base.motores:
        raise ValueError(f"motor '{ent.motor_id}' não cadastrado")
    motor = base.motores[ent.motor_id]
    if ent.chapa_id is not None:
        if ent.chapa_id not in pad.chapas:
            raise ValueError(f"chapa padrão '{ent.chapa_id}' não cadastrada")
        chapa = pad.chapas[ent.chapa_id]
    else:
        chapa = pad.chapa_para(motor.carcaca)
        if chapa is None:
            raise ValueError(f"nenhuma chapa padrão cadastrada para a carcaça {motor.carcaca}")
    if ent.R_min > ent.R_max:
        raise ValueError(f"R_min ({ent.R_min}) > R_max ({ent.R_max})")
    ranhuras = pad.ranhuras_de(chapa.chapa_id, motor.carcaca)
    if ent.ajustes:
        linha = next((x for x in pad.linhas.values() if x.chapa_id == chapa.chapa_id), None)
        if linha is None:
            raise ValueError(f"chapa {chapa.chapa_id} sem dimensões cadastradas para ajustes")
        erros: dict[str, str] = {}
        aj_chapa, aj_motor = ajustes_mod.ler(ent.ajustes, erros)
        linha, motor = ajustes_mod.aplicar(linha, motor, aj_chapa, aj_motor, erros)
        if erros:
            raise ValueError(
                f"ajustes inválidos em {ent.caso_id}: "
                + "; ".join(f"{k}: {v}" for k, v in erros.items())
            )
        chapa, lista = linha.como_padrao()
        ranhuras = {r.ranhura_n: r.como_ranhura(motor.carcaca) for r in lista}
    return EntradaCaso(
        ent.caso_id,
        motor,
        chapa,
        ranhuras,
        ent.R_min,
        ent.R_max,
        ent.cota_informada,
    )


# --------------------------------------------------------------------------- aba do caso


def resolver_entrada(
    ent: EntradaPlanilha, base: BaseDados, pad: Padroes, cfg: ConfigProjeto
) -> tuple[ResultadoProjeto, bd.AvaliacaoBancoDuplo | None]:
    """Resolve o caso; com banco duplo, o tensionamento entra como restrição obrigatória."""
    e = montar_entrada(ent, base, pad)
    if not ent.banco_duplo:
        return resolver_caso(e, cfg), None
    cfg_bd = bd.ConfigBancoDuplo(
        float(ent.banco_duplo["R2_min"]),
        float(ent.banco_duplo["R2_max"]),
        float(ent.banco_duplo.get("deslocamento_y", bd.DESLOCAMENTO_Y_PADRAO)),
    )
    return bd.resolver(cfg_bd, e, cfg)


def _bloco(ws: Worksheet, linha: int, titulo: str, pares: Sequence[tuple[str, Any]]) -> int:
    ws.cell(linha, 1, titulo).font = NEGRITO
    ws.cell(linha, 1).fill = CINZA
    ws.cell(linha, 2).fill = CINZA
    for i, (rot, val) in enumerate(pares, start=1):
        ws.cell(linha + i, 1, rot)
        c = ws.cell(linha + i, 2, val)
        if isinstance(val, float):
            c.number_format = FMT_MM
    return linha + len(pares) + 2


def _faixas_txt(r: ResultadoProjeto) -> str:
    if not r.faixas_cota:
        return "nenhuma"
    return "; ".join(f"{a:.2f} a {b:.2f}" for a, b in r.faixas_cota)


def _linhas_posicoes(r: ResultadoProjeto) -> list[list[Any]]:
    out = []
    for rotulo, par in (("recomendada", r.em_recomendada), ("informada", r.em_informada)):
        if not par:
            continue
        for tens, p in zip(("0 % (R_min)", "3 % (R_max)"), par, strict=True):
            out.append(
                [
                    rotulo,
                    tens,
                    p.R,
                    p.cota,
                    p.d_motor,
                    p.Cx,
                    p.Cy,
                    p.folga_neg,
                    p.folga_pos,
                    p.status.value,
                    "; ".join(p.mensagens),
                ]
            )
    return out


def _cota_desenho(r: ResultadoProjeto) -> float | None:
    if r.entrada.cota_informada is not None:
        return r.entrada.cota_informada
    return r.cota_recomendada


def _pontos_geometria(
    r: ResultadoProjeto, cfg: ConfigProjeto, cota: float
) -> dict[str, list[tuple[float, float]]]:
    """Séries do esboço em coordenadas de desenho (X = −x, Y = −y; O na origem)."""
    e = r.entrada
    t = math.radians(e.chapa.theta_deg)
    u = (math.cos(t), math.sin(t))
    nrm = (math.sin(t), -math.cos(t))
    L = (r.a0, r.b0 + cota)

    def cad(p: tuple[float, float]) -> tuple[float, float]:
        return -p[0], -p[1]

    def ao_longo(d: float, alt: float = 0.0) -> tuple[float, float]:
        return (L[0] - d * u[0] + alt * nrm[0], L[1] - d * u[1] + alt * nrm[1])

    series: dict[str, list[tuple[float, float]]] = {}
    pos = [posicao(e, cfg, R, cota) for R in (e.R_min, e.R_max)]
    ang_ref = [math.atan2(p.Cy, p.Cx) for p in pos if p.Cx is not None] or [math.radians(70)]
    a_med = sum(ang_ref) / len(ang_ref)
    for nome, R in (("R_min", e.R_min), ("R_max", e.R_max)):
        series[f"arco {nome}"] = [
            cad(
                (
                    R * math.cos(a_med + k * math.radians(1)),
                    R * math.sin(a_med + k * math.radians(1)),
                )
            )
            for k in range(-15, 16)
        ]
    xs_piso = [-300.0, max(1300.0, r.a0 + e.chapa.comprimento)]
    series["piso"] = [cad((x, cfg.y_piso)) for x in xs_piso]
    series["chapa (topo)"] = [cad(ao_longo(0)), cad(ao_longo(e.chapa.comprimento))]
    tubo = (cfg.x_tubo, cfg.y_piso + cota)
    series["tubo → L"] = [cad(tubo), cad((tubo[0] + e.chapa.dx_L, tubo[1])), cad(L)]
    for n, rh in sorted(e.ranhuras.items()):
        d_lim = -(rh.u_ini if n == 1 else rh.u_fim)  # ponta conhecida
        series[f"limite ranhura {n}"] = [cad(ao_longo(d_lim, -5)), cad(ao_longo(d_lim, 25))]
    raio = (e.motor.AC / 2) if e.motor.AC else e.motor.H
    for rot, p in zip(("motor 0 %", "motor 3 %"), pos, strict=True):
        if p.Cx is None:
            continue
        series[rot] = [
            cad(
                (p.Cx + raio * math.cos(k * math.pi / 18), p.Cy + raio * math.sin(k * math.pi / 18))
            )
            for k in range(37)
        ]
        series[f"centro {rot}"] = [cad((p.Cx, p.Cy))]
        series[f"raio {rot}"] = [(0.0, 0.0), cad((p.Cx, p.Cy))]
    series["O (centro dos raios)"] = [(0.0, 0.0)]
    return series


CORES_SERIES = {
    "arco R_min": "7F7F7F",
    "arco R_max": "BFBFBF",
    "piso": "8B5A2B",
    "chapa (topo)": "000000",
    "tubo → L": "2F5597",
    "limite ranhura 1": "C00000",
    "limite ranhura 2": "C00000",
    "motor 0 %": "00B050",
    "motor 3 %": "ED7D31",
    "O (centro dos raios)": "000000",
    # tubo horizontal
    "laje": "8B5A2B",
    "tubo": "2F5597",
    "linha de centro": "7F7F7F",
    "O1": "000000",
    "O2": "2F75B5",
    "arco R2_min": "9DC3E6",
    "arco R2_max": "BDD7EE",
}


def _cor_serie(nome: str) -> str:
    for chave, cor in CORES_SERIES.items():
        if nome == chave:
            return cor
    if "0 %" in nome:
        return CORES_SERIES["motor 0 %"]
    if "3 %" in nome:
        return CORES_SERIES["motor 3 %"]
    return "404040"


def _arredonda(v: float, passo: float, para_cima: bool) -> float:
    return (math.ceil(v / passo) if para_cima else math.floor(v / passo)) * passo


def _grafico_geometria(
    ws: Worksheet, series: dict[str, list[tuple[float, float]]], ancora: str, col_dados: int
) -> None:
    """Escreve as séries a partir de `col_dados` (colunas X/Y) e cria o gráfico."""
    graf = ScatterChart()
    graf.title = "Esboço (vista do desenho, mm)"
    graf.style = 13
    graf.x_axis.title, graf.y_axis.title = "X (mm)", "Y (mm)"
    graf.x_axis.delete = graf.y_axis.delete = False
    todos = [p for pts in series.values() for p in pts]
    xmin, xmax = min(p[0] for p in todos), max(p[0] for p in todos)
    ymin, ymax = min(p[1] for p in todos), max(p[1] for p in todos)
    lado = max(xmax - xmin, ymax - ymin) * 1.05
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    passo = 250.0 if lado <= 3000 else 500.0
    graf.x_axis.scaling.min = _arredonda(cx - lado / 2, passo, False)
    graf.x_axis.scaling.max = _arredonda(cx + lado / 2, passo, True)
    graf.y_axis.scaling.min = _arredonda(cy - lado / 2, passo, False)
    graf.y_axis.scaling.max = _arredonda(cy + lado / 2, passo, True)
    graf.x_axis.majorUnit = graf.y_axis.majorUnit = passo
    graf.x_axis.number_format = graf.y_axis.number_format = "0"
    graf.x_axis.crosses = graf.y_axis.crosses = "min"
    col = col_dados
    for nome, pts in series.items():
        ws.cell(1, col, nome).font = NEGRITO
        ws.cell(2, col, "X")
        ws.cell(2, col + 1, "Y")
        for i, (x, y) in enumerate(pts, start=3):
            ws.cell(i, col, x)
            ws.cell(i, col + 1, y)
        fim = 2 + len(pts)
        s = Series(
            Reference(ws, min_col=col + 1, min_row=3, max_row=fim),
            Reference(ws, min_col=col, min_row=3, max_row=fim),
            title=nome,
        )
        cor = _cor_serie(nome)
        s.smooth = False
        if len(pts) == 1:
            s.marker.symbol = "circle"
            s.marker.size = 7
            s.marker.graphicalProperties.solidFill = cor
            s.marker.graphicalProperties.line.solidFill = cor
            s.graphicalProperties.line.noFill = True
        else:
            s.marker.symbol = "none"
            s.graphicalProperties.line.solidFill = cor
            grossa = nome in ("chapa (topo)", "tubo") or nome.startswith(("limite", "chapa "))
            s.graphicalProperties.line.width = 30000 if grossa else 15000
        if nome.startswith(("arco", "raio")) or nome in ("piso", "laje", "linha de centro"):
            s.graphicalProperties.line.dashStyle = "dash"
        graf.series.append(s)
        col += 3
    graf.legend.position = "b"
    graf.width, graf.height = 16, 20
    ws.add_chart(graf, ancora)


def _grafico_folgas(ws: Worksheet, r: ResultadoProjeto, cfg: ConfigProjeto, linha: int) -> int:
    """Tabela folga mínima × cota (0 % e 3 %) em torno da cota de desenho + gráfico."""
    c0 = _cota_desenho(r)
    if c0 is None:
        return linha
    cotas = [round(c0) + k for k in range(-60, 61, 5)]
    linhas = []
    for c in cotas:
        p0, p3 = (posicao(r.entrada, cfg, R, c) for R in (r.entrada.R_min, r.entrada.R_max))
        linhas.append([c, p0.margem, p3.margem])
    ws.cell(linha, 1, "Folga mínima × altura H do apoio").font = NEGRITO
    ini = linha + 1
    ws.cell(ini, 1, "cota")
    ws.cell(ini, 2, "folga mín. 0 %")
    ws.cell(ini, 3, "folga mín. 3 %")
    for i, lin in enumerate(linhas, start=ini + 1):
        for j, v in enumerate(lin, start=1):
            c = ws.cell(i, j, v)
            c.number_format = FMT_MM
    fim = ini + len(linhas)
    graf = ScatterChart()
    graf.title = "Folga mínima nas ranhuras × altura H do apoio"
    graf.style = 13
    graf.x_axis.title, graf.y_axis.title = "altura H do centro do apoio (mm)", "folga mínima (mm)"
    graf.x_axis.delete = graf.y_axis.delete = False
    xs = Reference(ws, min_col=1, min_row=ini + 1, max_row=fim)
    for j in (2, 3):
        s = Series(Reference(ws, min_col=j, min_row=ini, max_row=fim), xs, title_from_data=True)
        s.marker.symbol = "none"
        s.smooth = False
        graf.series.append(s)
    graf.width, graf.height = 16, 8
    ws.add_chart(graf, f"E{ini}")
    return fim + 2


def escrever_aba_caso(
    ws: Worksheet,
    r: ResultadoProjeto,
    cfg: ConfigProjeto,
    ajustes: dict[str, Any] | None = None,
    banco: bd.AvaliacaoBancoDuplo | None = None,
) -> None:
    e = r.entrada
    ws["A1"] = f"Caso {e.caso_id}"
    ws["A1"].font = TITULO
    lin = _bloco(
        ws,
        3,
        "Entradas",
        [
            ("motor", e.motor.motor_id),
            ("carcaça", e.motor.carcaca),
            ("R_min (0 %)", e.R_min),
            ("R_max (3 %)", e.R_max),
            ("altura H do apoio informada", e.cota_informada),
        ],
    )
    rh = e.ranhuras
    lin = _bloco(
        ws,
        lin,
        "Chapa padrão e motor",
        [
            ("chapa", e.chapa.chapa_id),
            ("origem dos dados da chapa", e.chapa.origem.value),
            ("θ (graus)", e.chapa.theta_deg),
            ("comprimento", e.chapa.comprimento),
            ("dx tubo → L", e.chapa.dx_L),
            ("cota L acima do tubo", e.chapa.cota_L_tubo),
            ("h (centro do motor ↑ chapa)", r.h),
            ("A / K do motor", f"{e.motor.A:g} / {e.motor.K:g}"),
            ("ranhura 1: d_fim (lado do arco)", -rh[1].u_ini if 1 in rh else None),
            ("ranhura 2: d_ini", -rh[2].u_fim if 2 in rh else None),
        ],
    )
    if ajustes:
        pares = ajustes_mod.descrever(ajustes.get("chapa") or {}, ajustes.get("motor") or {})
        lin = _bloco(
            ws,
            lin,
            "Ajustes de dimensões (diferentes do padrão)",
            [(rot, "vazio" if v is None else float(v)) for rot, v in pares],
        )
    if banco is not None:
        pares: list[tuple[str, Any]] = [
            ("O1 → O2 (acima)", banco.config.deslocamento_y),
            ("R2_min (0 %) a partir de O2", banco.config.R2_min),
            ("R2_max (3 %) a partir de O2", banco.config.R2_max),
            ("verificado em H", banco.H),
        ]
        for q in banco.posicoes:
            pares += [
                (f"{q.rotulo} %: distância a O2 sobre o arco R1", q.dist_O2),
                (f"{q.rotulo} %: curso entre os arcos R1 e R2", q.curso),
            ]
        pares.append(("situação", "OK" if banco.ok else "; ".join(banco.avisos)))
        lin = _bloco(ws, lin, "Tensionamento para banco duplo", pares)
    ini_resultado = lin
    lin = _bloco(
        ws,
        lin,
        "Resultado",
        [
            ("status", r.status.value),
            ("mensagem", r.mensagem),
            ("faixa admissível de H", _faixas_txt(r)),
            ("H recomendada (máx. folga mínima)", r.cota_recomendada),
            ("folga mínima na recomendada", r.margem_recomendada),
            ("ajuste dos oblongos na obra", "±50 mm"),
        ],
    )
    status_cel = f"B{ini_resultado + 1}"
    cor = CORES_STATUS.get(r.status.value)
    if cor:
        ws[status_cel].fill = cor
    ws.cell(
        lin, 1, "Posições (d_motor = centro do motor medido de L, subindo a chapa)"
    ).font = NEGRITO
    cols = [
        "cota de",
        "tensão",
        "R",
        "cota",
        "d_motor",
        "Cx",
        "Cy",
        "folga_neg",
        "folga_pos",
        "status",
        "mensagem",
    ]
    for j, c in enumerate(cols, start=1):
        ws.cell(lin + 1, j, c).font = NEGRITO
    linhas = _linhas_posicoes(r)
    for i, valores in enumerate(linhas, start=lin + 2):
        for j, v in enumerate(valores, start=1):
            c = ws.cell(i, j, v)
            if isinstance(v, float):
                c.number_format = FMT_MM
    if linhas:
        _cor_status(ws, f"J{lin + 2}:J{lin + 1 + len(linhas)}")
    lin = lin + 3 + len(linhas)
    _grafico_folgas(ws, r, cfg, lin)
    cota = _cota_desenho(r)
    if cota is not None:
        _grafico_geometria(ws, _pontos_geometria(r, cfg, cota), "N3", 40)
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 22
    for col in "CDEFGHIJ":
        ws.column_dimensions[col].width = 12


# --------------------------------------------------------------------------- projeto


def _aba_projeto(
    ws: Worksheet,
    cfg: ConfigProjeto,
    resultados: Sequence[ResultadoProjeto],
    horizontais: Sequence[th.ResultadoTH] = (),
) -> None:
    ws["A1"] = f"Projeto {cfg.nome}"
    ws["A1"].font = TITULO
    ws["A2"] = f"Gerado em {datetime.now():%Y-%m-%d %H:%M} — tensorcad {tensorcad.__version__}"
    ws["A4"], ws["B4"] = "centro dos raios → piso (y_piso)", cfg.y_piso
    ws["A5"], ws["B5"] = "centro dos raios → tubo de apoio (x_tubo)", cfg.x_tubo
    ws["A6"] = "Altura H do apoio = centro do tubo de apoio → piso do banco de cilindros."
    ws["A7"] = "Convenções: O = centro dos raios; x+ esquerda; y+ baixo (ver docs/geometria.md)."
    cols = [
        "caso_id",
        "motor",
        "chapa",
        "R_min",
        "R_max",
        "cota_informada",
        "status",
        "cota_recomendada",
        "folga_min",
        "faixa_cota",
        "mensagem",
    ]
    tab = []
    for r in resultados:
        e = r.entrada
        tab.append(
            [
                e.caso_id,
                e.motor.motor_id,
                e.chapa.chapa_id,
                e.R_min,
                e.R_max,
                e.cota_informada,
                r.status.value,
                r.cota_recomendada,
                r.margem_recomendada,
                _faixas_txt(r),
                r.mensagem,
            ]
        )
    n = len(tab)
    ini = 9
    for j, c in enumerate(cols, start=1):
        ws.cell(ini, j, c).font = NEGRITO
    for i, lin in enumerate(tab, start=ini + 1):
        for j, v in enumerate(lin, start=1):
            c = ws.cell(i, j, v)
            if isinstance(v, float):
                c.number_format = FMT_MM
            if j == 1:
                c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{nome_aba(v)}'!A1")
                c.font = Font(color="0563C1", underline="single")
    if tab:
        _cor_status(ws, f"G{ini + 1}:G{ini + n}")
    if horizontais:
        _indice_horizontal(ws, ini + n + 3, horizontais)
    ws.column_dimensions["A"].width = 44
    for col in "BCDEFGHIJ":
        ws.column_dimensions[col].width = 16
    ws.column_dimensions["K"].width = 70


def _faixas_th(r: th.ResultadoTH) -> str:
    if not r.faixas_altura:
        return "nenhuma"
    return "; ".join(f"{a:.2f} a {b:.2f}" for a, b in r.faixas_altura)


def _indice_horizontal(ws: Worksheet, ini: int, resultados: Sequence[th.ResultadoTH]) -> None:
    """Tabela dos casos do layout tubo horizontal no índice do projeto."""
    ws.cell(ini, 1, "Layout tubo horizontal").font = NEGRITO
    cols = [
        "caso_id",
        "motor",
        "motor invertido",
        "R_min",
        "R_max",
        "altura informada",
        "status",
        "altura recomendada",
        "folga_min",
        "faixa da altura",
        "mensagem",
    ]
    for j, c in enumerate(cols, start=1):
        ws.cell(ini + 1, j, c).font = NEGRITO
    for i, r in enumerate(resultados, start=ini + 2):
        e = r.entrada
        lin = [
            e.caso_id,
            e.motor.motor_id,
            "sim" if r.parametros.invertido else "não",
            e.R_min,
            e.R_max,
            e.altura_informada,
            r.status.value,
            r.altura_recomendada,
            r.margem_recomendada,
            _faixas_th(r),
            r.mensagem,
        ]
        for j, v in enumerate(lin, start=1):
            c = ws.cell(i, j, v)
            if isinstance(v, float):
                c.number_format = FMT_MM
            if j == 1:
                c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{nome_aba(v)}'!A1")
                c.font = Font(color="0563C1", underline="single")
    _cor_status(ws, f"G{ini + 2}:G{ini + 1 + len(resultados)}")


# séries do esboço do tubo horizontal: id da primitiva (desenho_th) → nome da série
SERIES_TH = {
    "arco-R_min": "arco R_min",
    "arco-R_max": "arco R_max",
    "arco-R2_min": "arco R2_min",
    "arco-R2_max": "arco R2_max",
    "laje": "laje",
    "tubo": "tubo",
    "eixo-centro": "linha de centro",
    "chapa-0": "chapa 0 %",
    "chapa-3": "chapa 3 %",
    "motor-0": "motor 0 %",
    "motor-3": "motor 3 %",
    "centro-0": "centro motor 0 %",
    "centro-3": "centro motor 3 %",
    "raio-0": "raio motor 0 %",
    "raio-3": "raio motor 3 %",
    "O1": "O1",
    "O2": "O2",
}


def _pontos_primitiva(q: dict[str, Any]) -> list[tuple[float, float]]:
    """Pontos (X, Y) de uma primitiva do desenho, para série de gráfico."""
    if q["id"] in ("O1", "O2"):  # centros: um ponto
        return [tuple(q["c"])]
    tipo = q["tipo"]
    if tipo == "linha":
        return [tuple(q["p0"]), tuple(q["p1"])]
    if tipo == "ponto":
        return [tuple(q["p"])]
    if tipo == "poligono":
        return [tuple(v) for v in [*q["pts"], q["pts"][0]]]
    cx, cy = q["c"]
    if tipo == "circulo":
        return [
            (cx + q["r"] * math.cos(k * math.pi / 18), cy + q["r"] * math.sin(k * math.pi / 18))
            for k in range(37)
        ]
    # arco
    a0, a1 = math.radians(q["a0"]), math.radians(q["a1"])
    return [
        (
            cx + q["r"] * math.cos(a0 + (a1 - a0) * k / 30),
            cy + q["r"] * math.sin(a0 + (a1 - a0) * k / 30),
        )
        for k in range(31)
    ]


def _pontos_geometria_th(r: th.ResultadoTH) -> dict[str, list[tuple[float, float]]]:
    """Séries do esboço do tubo horizontal (mesma vista do desenho da interface)."""
    d = desenho_th.gerar(r)
    if d is None:
        return {}
    por_id = {q["id"]: q for q in d["primitivas"]}
    return {nome: _pontos_primitiva(por_id[i]) for i, nome in SERIES_TH.items() if i in por_id}


def _grafico_folgas_th(ws: Worksheet, r: th.ResultadoTH, linha: int) -> int:
    """Tabela folga mínima (g, x e R2) × altura do tubo, em 0 % e 3 %, e gráfico."""
    a0 = desenho_th.altura_desenho(r)
    if a0 is None:
        return linha
    e, par = r.entrada, r.parametros
    b2 = e.banco2
    tensoes = ((e.R_min, b2 and (b2, b2.R2_min)), (e.R_max, b2 and (b2, b2.R2_max)))

    def folga(R: float, altura: float, b: Any) -> float | None:
        p = th.posicao(par, e.motor, R, altura, b or None)
        if p.margem is None:
            return None
        return p.margem if p.folga_R2 is None else min(p.margem, p.folga_R2)

    alturas = [round(a0) + k for k in range(-150, 151, 10)]
    linhas = [[a, *(folga(R, a, b) for R, b in tensoes)] for a in alturas]
    ws.cell(linha, 1, "Folga mínima × altura do tubo").font = NEGRITO
    ini = linha + 1
    ws.cell(ini, 1, "altura do tubo")
    ws.cell(ini, 2, "folga mín. 0 %")
    ws.cell(ini, 3, "folga mín. 3 %")
    for i, lin in enumerate(linhas, start=ini + 1):
        for j, v in enumerate(lin, start=1):
            ws.cell(i, j, v).number_format = FMT_MM
    fim = ini + len(linhas)
    graf = ScatterChart()
    graf.title = "Folga mínima (g, x e R2) × altura do tubo"
    graf.style = 13
    graf.x_axis.title, graf.y_axis.title = "altura do tubo (mm)", "folga mínima (mm)"
    graf.x_axis.delete = graf.y_axis.delete = False
    xs = Reference(ws, min_col=1, min_row=ini + 1, max_row=fim)
    for j in (2, 3):
        s = Series(Reference(ws, min_col=j, min_row=ini, max_row=fim), xs, title_from_data=True)
        s.marker.symbol = "none"
        s.smooth = False
        graf.series.append(s)
    graf.width, graf.height = 16, 8
    ws.add_chart(graf, f"E{ini}")
    return fim + 2


def escrever_aba_horizontal(ws: Worksheet, r: th.ResultadoTH) -> None:
    """Aba de um caso do layout tubo horizontal."""
    e, par = r.entrada, r.parametros
    ws["A1"] = f"Caso {e.caso_id} — layout tubo horizontal"
    ws["A1"].font = TITULO
    lin = _bloco(
        ws,
        3,
        "Entradas",
        [
            ("layout", "tubo horizontal"),
            ("motor", e.motor.motor_id),
            ("carcaça", e.motor.carcaca),
            ("motor invertido", "sim" if par.invertido else "não"),
            ("R_min (0 %)", e.R_min),
            ("R_max (3 %)", e.R_max),
            ("comprimento do tubo", par.comprimento_tubo),
            ("altura do tubo informada", e.altura_informada),
        ],
    )
    lin = _bloco(
        ws,
        lin,
        "Pilha e limites",
        [
            ("H do motor (WEG)", float(e.motor.H)),
            ("A do motor (furação)", float(e.motor.A)),
            ("espessura do tubo", par.espessura_tubo),
            ("porca (×2)", par.espessura_porca),
            ("chapa", par.espessura_chapa),
            ("pilha sem g (tubo → centro do motor)", th.pilha(par, e.motor)),
            ("g (distância entre porcas)", f"{par.g_min:g} a {par.g_max:g}"),
            ("curso em x (da linha de centro)", f"0 a {r.x_max:.2f}"),
            ("O1 → linha de centro (x) / → laje (y)", f"{par.x_linha:g} / {par.y_laje:g}"),
        ],
    )
    if e.banco2 is not None:
        lin = _bloco(
            ws,
            lin,
            "Tensionamento para banco duplo",
            [
                ("O1 → O2 (acima)", e.banco2.deslocamento_y),
                ("R2_min (0 %) a partir de O2", e.banco2.R2_min),
                ("R2_max (3 %) a partir de O2", e.banco2.R2_max),
            ],
        )
    ini_resultado = lin
    lin = _bloco(
        ws,
        lin,
        "Resultado",
        [
            ("status", r.status.value),
            ("mensagem", r.mensagem),
            ("faixa admissível da altura do tubo", _faixas_th(r)),
            ("altura do tubo recomendada", r.altura_recomendada),
            ("folga mínima na recomendada (mm)", r.margem_recomendada),
        ],
    )
    cor = CORES_STATUS.get(r.status.value)
    if cor:
        ws[f"B{ini_resultado + 1}"].fill = cor
    ws.cell(lin, 1, "Posições (x da linha de centro; y do motor abaixo da laje)").font = NEGRITO
    cols = [
        "altura de",
        "tensão",
        "R",
        "altura do tubo",
        "g",
        "x",
        "y_motor",
        "folga_g",
        "folga_x",
        "folga_R2",
        "status",
        "mensagem",
    ]
    for j, c in enumerate(cols, start=1):
        ws.cell(lin + 1, j, c).font = NEGRITO
    linhas = []
    for rotulo, par_pos in (("recomendada", r.em_recomendada), ("informada", r.em_informada)):
        for tensao, p in zip(("0 %", "3 %"), par_pos or (), strict=False):
            linhas.append(
                [
                    rotulo,
                    tensao,
                    p.R,
                    p.altura_tubo,
                    p.g,
                    p.x,
                    p.y_motor,
                    p.folga_g,
                    p.folga_x,
                    p.folga_R2,
                    p.status.value,
                    "; ".join(p.mensagens),
                ]
            )
    for i, valores in enumerate(linhas, start=lin + 2):
        for j, v in enumerate(valores, start=1):
            c = ws.cell(i, j, v)
            if isinstance(v, float):
                c.number_format = FMT_MM
    if linhas:
        _cor_status(ws, f"K{lin + 2}:K{lin + 1 + len(linhas)}")
    lin = lin + 3 + len(linhas)
    _grafico_folgas_th(ws, r, lin)
    series = _pontos_geometria_th(r)
    if series:
        _grafico_geometria(ws, series, "N3", 40)
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 22
    for col in "CDEFGHIJK":
        ws.column_dimensions[col].width = 12


def ler_entradas(caminho: Path) -> tuple[ConfigProjeto, list[EntradaPlanilha]]:
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if ABA_ENTRADAS not in wb.sheetnames:
            raise ValueError(f"{caminho} não é uma planilha de projeto do tensorcad")
        linhas = list(wb[ABA_ENTRADAS].iter_rows(values_only=True))
    finally:
        wb.close()
    cfg_vals = dict(zip(linhas[0][1::2], linhas[0][2::2], strict=False))
    cfg = ConfigProjeto(
        nome=str(cfg_vals.get("nome", "PROJETO")),
        y_piso=float(cfg_vals.get("y_piso", 767)),
        x_tubo=float(cfg_vals.get("x_tubo", 465)),
    )
    cab = list(linhas[1])
    entradas = []
    for lin in linhas[2:]:
        if lin[0] is None:
            continue
        d = dict(zip(cab, lin, strict=False))
        entradas.append(
            EntradaPlanilha(
                caso_id=str(d["caso_id"]),
                motor_id=str(d["motor_id"]),
                R_min=float(d["R_min"]),
                R_max=float(d["R_max"]),
                cota_informada=None
                if d.get("cota_informada") is None
                else float(d["cota_informada"]),
                chapa_id=None if d.get("chapa_id") in (None, "") else str(d["chapa_id"]),
                ajustes=json.loads(d["ajustes"]) if d.get("ajustes") else None,
                banco_duplo=json.loads(d["banco_duplo"]) if d.get("banco_duplo") else None,
            )
        )
    return cfg, entradas


def gerar_projeto(
    caminho: Path | str | BinaryIO,
    cfg: ConfigProjeto,
    entradas: Sequence[EntradaPlanilha],
    base: BaseDados,
    pad: Padroes,
    horizontais: Sequence[EntradaHorizontal] = (),
    fixos_th: dict[str, float] | None = None,
) -> Path | BinaryIO:
    """Gera a planilha completa do projeto (PROJETO + uma aba por caso + _entradas).
    `caminho` pode ser um arquivo em memória (exportação pela interface). Os casos do
    layout tubo horizontal (`horizontais`) ganham aba própria, tabela no índice e a aba
    oculta _entradas_horizontal."""
    ids = [nome_aba(e.caso_id) for e in [*entradas, *horizontais]]
    if len(set(ids)) != len(ids):
        raise ValueError("casos com nomes de aba repetidos")
    resolvidos = [resolver_entrada(e, base, pad, cfg) for e in entradas]
    resultados = [r for r, _ in resolvidos]
    res_th = [resolver_horizontal(e, base, cfg, fixos_th) for e in horizontais]
    wb = Workbook()
    _aba_projeto(wb.active, cfg, resultados, res_th)
    wb.active.title = ABA_PROJETO
    for e, (r, banco) in zip(entradas, resolvidos, strict=True):
        aba = wb.create_sheet(nome_aba(r.entrada.caso_id))
        escrever_aba_caso(aba, r, cfg, e.ajustes, banco)
    for rt in res_th:
        escrever_aba_horizontal(wb.create_sheet(nome_aba(rt.entrada.caso_id)), rt)
    we = wb.create_sheet(ABA_ENTRADAS)
    we.append(["config", "nome", cfg.nome, "y_piso", cfg.y_piso, "x_tubo", cfg.x_tubo])
    we.append(list(CAMPOS_ENTRADA))
    for e in entradas:
        d = asdict(e)
        d["ajustes"] = json.dumps(e.ajustes, ensure_ascii=False) if e.ajustes else None
        d["banco_duplo"] = json.dumps(e.banco_duplo) if e.banco_duplo else None
        we.append([d[c] for c in CAMPOS_ENTRADA])
    we.sheet_state = "hidden"
    if horizontais:
        wh = wb.create_sheet(ABA_ENTRADAS_TH)
        wh.append(["caso_json"])
        for e in horizontais:
            wh.append([json.dumps(asdict(e), ensure_ascii=False)])
        wh.sheet_state = "hidden"
    if not isinstance(caminho, (str, Path)):
        wb.save(caminho)
        return caminho
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)
    return caminho


def ler_entradas_horizontais(caminho: Path) -> list[EntradaHorizontal]:
    """Casos do tubo horizontal gravados na aba oculta (vazio se não houver)."""
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        if ABA_ENTRADAS_TH not in wb.sheetnames:
            return []
        linhas = list(wb[ABA_ENTRADAS_TH].iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()
    return [EntradaHorizontal(**json.loads(lin[0])) for lin in linhas if lin and lin[0]]


def adicionar_caso(
    caminho: Path | str,
    entrada: EntradaPlanilha,
    base: BaseDados,
    pad: Padroes,
    *,
    cfg: ConfigProjeto | None = None,
    substituir: bool = False,
) -> Path:
    """Adiciona (ou substitui) um caso na planilha do projeto, criando-a se não existir.
    `cfg` só é usado na criação; depois vale a configuração gravada no arquivo."""
    caminho = Path(caminho)
    if caminho.exists():
        cfg_arq, entradas = ler_entradas(caminho)
        cfg = cfg_arq
    else:
        cfg, entradas = cfg or ConfigProjeto(), []
    existentes = [nome_aba(e.caso_id) for e in entradas]
    novo = nome_aba(entrada.caso_id)
    if novo in existentes:
        if not substituir:
            raise ValueError(f"caso '{entrada.caso_id}' já existe no projeto (use substituir)")
        entradas = [e for e in entradas if nome_aba(e.caso_id) != novo]
    montar_entrada(entrada, base, pad)  # valida antes de gravar
    horizontais = ler_entradas_horizontais(caminho) if caminho.exists() else []
    return gerar_projeto(caminho, cfg, [*entradas, entrada], base, pad, horizontais)


def status_do_caso(caminho: Path | str, caso_id: str) -> str:
    """Lê o status gravado na aba PROJETO (útil para testes e CLI)."""
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        for lin in wb[ABA_PROJETO].iter_rows(min_row=10, values_only=True):
            if lin[0] == caso_id:
                return str(lin[6])
    finally:
        wb.close()
    raise KeyError(caso_id)
