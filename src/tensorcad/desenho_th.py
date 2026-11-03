"""Primitivas do desenho do layout tubo horizontal (T5), funções puras.

Mesmo formato de desenho.py (vista do CAD: X → direita, Y ↑ cima, mm, origem O1).
A linha de centro fica em X = x_linha (O1 à esquerda, como no desenho de referência), o
motor em X = x_linha + x, e o topo da laje em Y = −y_laje. Uma profundidade y abaixo da
laje fica em Y = −(y_laje + y).
"""

from __future__ import annotations

import math
from typing import Any

from tensorcad.desenho import ABERTURA_ARCO_GRAUS, RAIO_SIMBOLO_O
from tensorcad.tubo_horizontal import PosicaoTH, ResultadoTH, pilha

CAMADAS = ("construcao", "banco2", "estrutura", "cotas", "chapa", "motor")  # ordem de pintura
LARGURA_PORCA = 46.0  # visual (porca M30 ~ 46 entre faces)
SOBRA_CHAPA = 40.0  # visual: chapa além das furações
ACIMA_DE_O = 150.0


def altura_desenho(r: ResultadoTH) -> float | None:
    """Altura do tubo usada no desenho: a informada; senão, a recomendada."""
    if r.entrada.altura_informada is not None:
        return r.entrada.altura_informada
    return r.altura_recomendada


def gerar(r: ResultadoTH) -> dict[str, Any] | None:
    """Primitivas na altura de exibição (None se não há altura ou posições)."""
    altura = altura_desenho(r)
    pos = r.em_informada if r.entrada.altura_informada is not None else r.em_recomendada
    if altura is None or pos is None:
        return None
    par, e = r.parametros, r.entrada
    m = e.motor
    yl = par.y_laje

    def P(x: float, y: float) -> list[float]:
        """(x da linha de centro, y abaixo da laje) → vista do CAD."""
        return [par.x_linha + x, -(yl + y)]

    prim: list[dict[str, Any]] = []

    def add(tipo: str, camada: str, id_: str, rotulo: str, info: dict | None = None, **geo):
        prim.append(
            {"tipo": tipo, "camada": camada, "id": id_, "rotulo": rotulo, "info": info or {}, **geo}
        )

    def retangulo(x0: float, x1: float, y0: float, y1: float) -> list[list[float]]:
        return [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]

    def octogono(c: list[float]) -> list[list[float]]:
        return [
            [
                c[0] + RAIO_SIMBOLO_O * math.cos(math.radians(22.5 + 45 * k)),
                c[1] + RAIO_SIMBOLO_O * math.sin(math.radians(22.5 + 45 * k)),
            ]
            for k in range(8)
        ]

    validas = {k: p for k, p in zip(("0", "3"), pos, strict=True) if p.x is not None}

    # ---------------------------------------------------------------- construção
    add(
        "poligono",
        "construcao",
        "O1",
        "O1 — centro dos raios",
        {"X": 0, "Y": 0},
        pts=octogono([0.0, 0.0]),
        c=[0.0, 0.0],
    )
    angs = [math.degrees(math.atan2(*reversed(_cad(par, p)))) for p in validas.values()]
    a_med = sum(angs) / len(angs) if angs else -60.0
    for nome, R in (("R_min", e.R_min), ("R_max", e.R_max)):
        add(
            "arco",
            "construcao",
            f"arco-{nome}",
            f"{nome} = {R:g}",
            {"R": R},
            c=[0.0, 0.0],
            r=R,
            a0=a_med - ABERTURA_ARCO_GRAUS,
            a1=a_med + ABERTURA_ARCO_GRAUS,
        )
    for k, p in validas.items():
        add(
            "linha",
            "construcao",
            f"raio-{k}",
            f"raio do motor {k} %",
            {"R": p.R},
            p0=[0.0, 0.0],
            p1=_cad(par, p),
        )
    fundo = altura + (pilha(par, m) + par.g_max + 200 if par.invertido else 0) + 150
    add(
        "linha",
        "construcao",
        "eixo-centro",
        "linha de centro",
        {"X": par.x_linha},
        p0=[par.x_linha, ACIMA_DE_O],
        p1=P(0, fundo),
    )

    # ---------------------------------------------------------------- banco duplo (O2)
    b2 = e.banco2
    if b2 is not None:
        c2 = [0.0, b2.deslocamento_y]
        add(
            "poligono",
            "banco2",
            "O2",
            "O2 — centro dos raios (tensionamento para banco duplo)",
            {"deslocamento_y": b2.deslocamento_y},
            pts=octogono(c2),
            c=c2,
        )
        add(
            "cota",
            "banco2",
            "cota-O2",
            f"{b2.deslocamento_y:g}",
            {"deslocamento_y": b2.deslocamento_y},
            p0=[-RAIO_SIMBOLO_O * 2, 0.0],
            p1=[-RAIO_SIMBOLO_O * 2, c2[1]],
        )
        angs2 = [
            math.degrees(math.atan2(_cad(par, p)[1] - c2[1], _cad(par, p)[0]))
            for p in validas.values()
        ]
        a2 = sum(angs2) / len(angs2) if angs2 else a_med
        for nome, R in (("R2_min", b2.R2_min), ("R2_max", b2.R2_max)):
            add(
                "arco",
                "banco2",
                f"arco-{nome}",
                f"{nome} = {R:g}",
                {"R": R},
                c=c2,
                r=R,
                a0=a2 - ABERTURA_ARCO_GRAUS,
                a1=a2 + ABERTURA_ARCO_GRAUS,
            )
        for k, p in validas.items():
            ok = p.folga_R2 is not None and p.folga_R2 >= 0
            add(
                "linha",
                "banco2",
                f"raio2-{k}",
                f"O2 → motor {k} %",
                {"dist_O2": p.dist_O2, "R2": p.R2, "folga_R2": p.folga_R2},
                p0=c2,
                p1=_cad(par, p),
                status="OK" if ok else "AVISO",
            )

    # ---------------------------------------------------------------- estrutura
    meio = par.comprimento_tubo / 2
    add(
        "linha",
        "estrutura",
        "laje",
        "topo da laje",
        {"Y": -yl},
        p0=P(-meio - 400, 0),
        p1=P(meio + 200, 0),
    )
    add(
        "poligono",
        "estrutura",
        "tubo",
        "tubo de sustentação",
        {"comprimento": par.comprimento_tubo, "espessura": par.espessura_tubo},
        pts=retangulo(-meio, meio, altura, altura - par.espessura_tubo),
    )

    # ---------------------------------------------------------------- chapa, porcas, motor
    vao = (m.A + par.acrescimo_furacao) / 2  # meia distância entre as barras roscadas
    for k, p in validas.items():
        assert p.x is not None and p.g is not None and p.y_motor is not None
        _conjunto(add, retangulo, P, par, m, altura, k, p, vao)

    # ---------------------------------------------------------------- cotas
    add(
        "cota",
        "cotas",
        "cota-x-linha",
        f"{par.x_linha:g}",
        {"x_linha": par.x_linha},
        p0=[0.0, ACIMA_DE_O / 2],
        p1=[par.x_linha, ACIMA_DE_O / 2],
    )
    add(
        "cota",
        "cotas",
        "cota-y-laje",
        f"{yl:g}",
        {"y_laje": yl},
        p0=[-150.0, 0.0],
        p1=[-150.0, -yl],
    )
    add(
        "cota",
        "cotas",
        "cota-altura",
        f"altura do tubo = {altura:.2f}",
        {"altura": altura},
        p0=P(-meio - 120, 0),
        p1=P(-meio - 120, altura),
    )
    p0 = validas.get("0")
    if p0 is not None and p0.x is not None and p0.y_motor is not None:
        yc = p0.y_motor + (m.H + 120) * (1 if par.invertido else -1)
        add("cota", "cotas", "cota-x", f"x = {p0.x:.2f}", {"x": p0.x}, p0=P(0, yc), p1=P(p0.x, yc))

    todos: list[list[float]] = []
    for q in prim:
        for chave in ("p", "c", "p0", "p1"):
            if chave in q:
                todos.append(q[chave])
        todos.extend(q.get("pts", []))
    xs = [q[0] for q in todos]
    ys = [q[1] for q in todos]
    return {
        "altura": altura,
        "camadas": list(CAMADAS),
        "limites": [min(xs), min(ys), max(xs), max(ys)],
        "primitivas": prim,
    }


def _cad(par, p: PosicaoTH) -> list[float]:
    assert p.x is not None and p.y_motor is not None
    return [par.x_linha + p.x, -(par.y_laje + p.y_motor)]


def _conjunto(add, retangulo, P, par, m, altura: float, k: str, p: PosicaoTH, vao: float) -> None:
    """Porcas, barras, chapa e motor de uma tensão (k = "0" ou "3")."""
    x, g, yc = p.x, p.g, p.y_motor
    s = 1.0 if par.invertido else -1.0  # sentido da pilha a partir do tubo (y abaixo da laje)
    face = altura if par.invertido else altura - par.espessura_tubo  # face do tubo usada
    porca, ch = par.espessura_porca, par.espessura_chapa
    # pilha: face → porca → g → porca → chapa → motor
    y_p1 = (face, face + s * porca)
    y_p2 = (face + s * (porca + g), face + s * (2 * porca + g))
    y_ch = (y_p2[1], y_p2[1] + s * ch)
    info = {"g": g, "x": x, "status": p.status.value, "folga_g": p.folga_g, "folga_x": p.folga_x}
    # a barra atravessa o tubo: começa na face oposta à pilha
    y_barra = altura - par.espessura_tubo if par.invertido else altura
    for lado, sx in (("e", -1.0), ("d", 1.0)):
        xr = x + sx * vao
        lp = LARGURA_PORCA / 2
        add(
            "poligono",
            "chapa",
            f"porca-tubo-{k}-{lado}",
            f"porca no tubo ({k} %)",
            info,
            pts=retangulo(xr - lp, xr + lp, *y_p1),
            status=p.status.value,
        )
        add(
            "poligono",
            "chapa",
            f"porca-chapa-{k}-{lado}",
            f"porca na chapa ({k} %)",
            info,
            pts=retangulo(xr - lp, xr + lp, *y_p2),
            status=p.status.value,
        )
        add(
            "linha",
            "chapa",
            f"barra-{k}-{lado}",
            f"barra roscada ({k} %)",
            info,
            p0=P(xr, y_barra),
            p1=P(xr, y_ch[1]),
        )
    add(
        "poligono",
        "chapa",
        f"chapa-{k}",
        f"chapa do motor ({k} %)",
        {**info, "largura_furacao": 2 * vao},
        pts=retangulo(x - vao - SOBRA_CHAPA, x + vao + SOBRA_CHAPA, *y_ch),
        status=p.status.value,
    )
    if k == "0":
        xg = x + vao + LARGURA_PORCA
        add(
            "cota",
            "cotas",
            "cota-g",
            f"g = {g:.2f}",
            {"g": g},
            p0=P(xg, y_p1[1]),
            p1=P(xg, y_p2[0]),
        )
    raio = (m.AC / 2) if m.AC else m.H
    add(
        "circulo",
        "motor",
        f"motor-{k}",
        f"motor {k} % ({'invertido' if par.invertido else 'normal'})",
        {**info, "y_motor": yc, "R": p.R},
        c=P(x, yc),
        r=raio,
        status=p.status.value,
    )
    add(
        "ponto",
        "motor",
        f"centro-{k}",
        f"centro do motor {k} %",
        {**info, "y_motor": yc},
        p=P(x, yc),
        status=p.status.value,
    )
