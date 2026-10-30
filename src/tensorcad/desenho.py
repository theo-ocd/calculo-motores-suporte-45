"""Primitivas do desenho do caso (funções puras), na vista do CAD.

Coordenadas de desenho: origem O (centro dos raios), X para a DIREITA e Y para CIMA,
em mm — X = −x e Y = −y em relação às convenções de docs/geometria.md. Cada primitiva
traz a camada, um id estável, um rótulo e valores para exibição ao passar o mouse.
"""

from __future__ import annotations

import math
from typing import Any

from tensorcad.projeto import ConfigProjeto, ResultadoProjeto, posicao

CAMADAS = ("construcao", "estrutura", "cotas", "chapa", "motor")  # ordem de pintura
ESPESSURA_CHAPA = 10.0  # apenas visual (espessura real não cadastrada)
RAIO_TUBO = 30.0  # apenas visual (diâmetro do tubo não cadastrado)
ABERTURA_ARCO_GRAUS = 14.0


def _cad(x: float, y: float) -> list[float]:
    return [-x, -y]


def altura_desenho(r: ResultadoProjeto) -> float | None:
    """Altura H usada no desenho: a informada; senão, a recomendada."""
    if r.entrada.cota_informada is not None:
        return r.entrada.cota_informada
    return r.cota_recomendada


def gerar(r: ResultadoProjeto, cfg: ConfigProjeto) -> dict[str, Any] | None:
    """Primitivas do desenho na altura H de exibição (None se não há H)."""
    H = altura_desenho(r)
    if H is None:
        return None
    e = r.entrada
    t = math.radians(e.chapa.theta_deg)
    u = (math.cos(t), math.sin(t))  # direção da guia (s+ desce para a esquerda)
    n = (math.sin(t), -math.cos(t))  # normal, lado do motor
    L = (r.a0, r.b0 + H)  # ponta baixa do topo da chapa (convenção x esq., y baixo)
    T = (cfg.x_tubo, cfg.y_piso + H)  # centro do tubo de apoio

    def na_chapa(d: float, alt: float = 0.0) -> tuple[float, float]:
        """Ponto a d mm de L subindo a chapa, deslocado `alt` na normal (lado do motor)."""
        return (L[0] - d * u[0] + alt * n[0], L[1] - d * u[1] + alt * n[1])

    prim: list[dict[str, Any]] = []

    def add(
        tipo: str,
        camada: str,
        id_: str,
        rotulo: str,
        info: dict[str, Any] | None = None,
        **geo: Any,
    ) -> None:
        prim.append(
            {"tipo": tipo, "camada": camada, "id": id_, "rotulo": rotulo, "info": info or {}, **geo}
        )

    pos = {"0": posicao(e, cfg, e.R_min, H), "3": posicao(e, cfg, e.R_max, H)}

    # ---------------------------------------------------------------- construção
    add("ponto", "construcao", "O", "O — centro dos raios", {"X": 0, "Y": 0}, p=[0.0, 0.0])
    angulos = [math.degrees(math.atan2(-p.Cy, -p.Cx)) for p in pos.values() if p.Cx is not None]
    a_med = sum(angulos) / len(angulos) if angulos else -110.0
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
    for k, p in pos.items():
        if p.Cx is not None:
            add(
                "linha",
                "construcao",
                f"raio-{k}",
                f"raio do motor {k} %",
                {"R": p.R},
                p0=[0.0, 0.0],
                p1=_cad(p.Cx, p.Cy),
            )

    # ---------------------------------------------------------------- estrutura
    x_piso = [-300.0, max(1300.0, r.a0 + e.chapa.comprimento + 200)]
    add(
        "linha",
        "estrutura",
        "piso",
        "piso do banco de cilindros",
        {"Y": -cfg.y_piso},
        p0=_cad(x_piso[0], cfg.y_piso),
        p1=_cad(x_piso[1], cfg.y_piso),
    )
    add(
        "circulo",
        "estrutura",
        "tubo",
        "tubo de apoio",
        {"x": T[0], "H": H},
        c=_cad(*T),
        r=RAIO_TUBO,
    )
    add(
        "polilinha",
        "estrutura",
        "tubo-L",
        "tubo de apoio → ponta baixa L",
        {"dx": e.chapa.dx_L, "dy": e.chapa.cota_L_tubo},
        pts=[_cad(*T), _cad(T[0] + e.chapa.dx_L, T[1]), _cad(*L)],
    )

    # ---------------------------------------------------------------- chapa e ranhuras
    c = e.chapa.comprimento
    topo = [na_chapa(0), na_chapa(c)]
    fundo = [na_chapa(c, -ESPESSURA_CHAPA), na_chapa(0, -ESPESSURA_CHAPA)]
    add(
        "poligono",
        "chapa",
        "chapa",
        f"chapa {e.chapa.chapa_id}",
        {"comprimento": c, "theta": e.chapa.theta_deg, "origem": e.chapa.origem.value},
        pts=[_cad(*q) for q in topo + fundo],
    )
    add("ponto", "chapa", "L", "L — ponta baixa da chapa", {"x": L[0], "y": L[1]}, p=_cad(*L))
    for num, rh in sorted(e.ranhuras.items()):
        d_ini = None if rh.u_fim is None else -rh.u_fim
        d_fim = None if rh.u_ini is None else -rh.u_ini
        info = {"d_ini": d_ini, "d_fim": d_fim, "largura": rh.largura}
        if d_ini is not None and d_fim is not None:
            add(
                "linha",
                "chapa",
                f"ranhura-{num}",
                f"ranhura {num}",
                info,
                p0=_cad(*na_chapa(d_ini, -ESPESSURA_CHAPA / 2)),
                p1=_cad(*na_chapa(d_fim, -ESPESSURA_CHAPA / 2)),
            )
        else:
            d = d_fim if d_fim is not None else d_ini
            assert d is not None
            add(
                "linha",
                "chapa",
                f"ranhura-{num}",
                f"limite da ranhura {num} (outra ponta TODO)",
                info,
                p0=_cad(*na_chapa(d, 4)),
                p1=_cad(*na_chapa(d, -ESPESSURA_CHAPA - 4)),
            )

    # ---------------------------------------------------------------- motor
    raio = (e.motor.AC / 2) if e.motor.AC else e.motor.H
    for k, p in pos.items():
        if p.Cx is None:
            continue
        info = {
            "status": p.status.value,
            "Cx": p.Cx,
            "Cy": p.Cy,
            "d_motor": p.d_motor,
            "folga_neg": p.folga_neg,
            "folga_pos": p.folga_pos,
            "R": p.R,
        }
        add(
            "circulo",
            "motor",
            f"motor-{k}",
            f"motor {k} % (contorno aproximado)",
            info,
            c=_cad(p.Cx, p.Cy),
            r=raio,
            status=p.status.value,
        )
        add(
            "ponto",
            "motor",
            f"centro-{k}",
            f"centro do motor {k} %",
            info,
            p=_cad(p.Cx, p.Cy),
            status=p.status.value,
        )
        assert p.d_motor is not None
        for lado, sinal in (("inferior", -1), ("superior", 1)):
            d_furo = p.d_motor + sinal * e.motor.A / 2
            add(
                "circulo",
                "motor",
                f"furo-{k}-{lado}",
                f"furo do pé {lado} ({k} %)",
                {"d": d_furo, "K": e.motor.K},
                c=_cad(*na_chapa(d_furo, -ESPESSURA_CHAPA / 2)),
                r=e.motor.K / 2,
                status=p.status.value,
            )

    # ---------------------------------------------------------------- cotas
    x_cota_H = T[0] + e.chapa.dx_L + 150
    add(
        "cota",
        "cotas",
        "cota-H",
        f"H = {H:.2f}",
        {"H": H},
        p0=_cad(x_cota_H, cfg.y_piso),
        p1=_cad(x_cota_H, T[1]),
    )
    add(
        "cota",
        "cotas",
        "cota-x-tubo",
        f"{cfg.x_tubo:g}",
        {"x_tubo": cfg.x_tubo},
        p0=_cad(0, T[1] + 120),
        p1=_cad(T[0], T[1] + 120),
    )
    add(
        "cota",
        "cotas",
        "cota-y-piso",
        f"{cfg.y_piso:g}",
        {"y_piso": cfg.y_piso},
        p0=_cad(-150, 0),
        p1=_cad(-150, cfg.y_piso),
    )
    add(
        "cota",
        "cotas",
        "cota-dy",
        f"{e.chapa.cota_L_tubo:g}",
        {"dy": e.chapa.cota_L_tubo},
        p0=_cad(L[0] + 60, T[1]),
        p1=_cad(L[0] + 60, L[1]),
    )
    p0 = pos["0"]
    if p0.Cx is not None and p0.d_motor is not None:
        pe = na_chapa(p0.d_motor)
        add(
            "cota",
            "cotas",
            "cota-h",
            f"h = {r.h:g}",
            {"h": r.h},
            p0=_cad(*pe),
            p1=_cad(p0.Cx, p0.Cy),
        )

    todos = []
    for q in prim:
        for chave in ("p", "c", "p0", "p1"):
            if chave in q:
                todos.append(q[chave])
        todos.extend(q.get("pts", []))
    xs = [q[0] for q in todos]
    ys = [q[1] for q in todos]
    return {
        "H": H,
        "camadas": list(CAMADAS),
        "limites": [min(xs), min(ys), max(xs), max(ys)],
        "primitivas": prim,
    }
