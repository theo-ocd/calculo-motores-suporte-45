"""Protótipo F6: posição do conjunto referenciada ao tubo de apoio (funções puras).

Referencial de docs/geometria.md (O = centro dos raios, x+ esquerda, y+ baixo).
- Piso do banco de cilindros em y = y_piso (767 no padrão).
- Tubo de apoio T = (x_tubo, y_piso + cota), onde `cota` é a cota "1646" do desenho.
- L = ponta baixa do topo da chapa: L = T + (dx_L, −cota_L_tubo).
- A guia é o topo da chapa; s é medido a partir de L (s < 0 = subindo a chapa) e a
  posição do motor ao longo da chapa é d_motor = −s.

Como b(L) = y_piso + cota − cota_L_tubo, usa-se o ponto com cota = 0 como P do núcleo e
Δy = cota: as funções de geometry/ranhuras valem diretamente para a cota.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tensorcad import geometry as g
from tensorcad import ranhuras as rn
from tensorcad.geometry import Status
from tensorcad.models import ChapaPadrao, Motor, Ranhura

Y_PISO_PADRAO = 767.0
X_TUBO_PADRAO = 465.0

# Restrição extra sobre a cota (ex.: banco duplo): folga em mm ao longo da chapa,
# ≥ 0 atende. Entra na "folga mínima" que a cota recomendada maximiza.
Restricao = Callable[[float], float]


@dataclass(frozen=True)
class ConfigProjeto:
    """Dados fixos do projeto (redutor / banco de cilindros)."""

    nome: str = "PROJETO"
    y_piso: float = Y_PISO_PADRAO  # centro dos raios → piso (para baixo)
    x_tubo: float = X_TUBO_PADRAO  # centro dos raios → centro do tubo (x+ esquerda)


@dataclass(frozen=True)
class EntradaCaso:
    caso_id: str
    motor: Motor
    chapa: ChapaPadrao
    ranhuras: Mapping[int, Ranhura]
    R_min: float
    R_max: float
    cota_informada: float | None = None


@dataclass(frozen=True)
class Posicao:
    """Motor numa cota e num R."""

    R: float
    cota: float
    status: Status
    s: float | None = None
    d_motor: float | None = None
    Cx: float | None = None
    Cy: float | None = None
    folga_neg: float | None = None
    folga_pos: float | None = None
    mensagens: tuple[str, ...] = ()
    folgas_internas: tuple[float, ...] = ()

    @property
    def margem(self) -> float | None:
        if self.folga_neg is None or self.folga_pos is None:
            return None
        return min(self.folga_neg, self.folga_pos, *self.folgas_internas)


@dataclass(frozen=True)
class ResultadoProjeto:
    entrada: EntradaCaso
    h: float
    a0: float
    b0: float
    faixas_cota: tuple[tuple[float, float], ...]  # cota admissível (0 % e 3 % nas ranhuras)
    cota_recomendada: float | None
    margem_recomendada: float | None
    status: Status
    mensagem: str
    em_recomendada: tuple[Posicao, Posicao] | None  # (R_min, R_max)
    em_informada: tuple[Posicao, Posicao] | None


def ponto_base(cfg: ConfigProjeto, chapa: ChapaPadrao) -> tuple[float, float]:
    """(a0, b0) de L para cota = 0; com cota c, L = (a0, b0 + c)."""
    return cfg.x_tubo + chapa.dx_L, cfg.y_piso - chapa.cota_L_tubo


def posicao(e: EntradaCaso, cfg: ConfigProjeto, R: float, cota: float) -> Posicao:
    a0, b0 = ponto_base(cfg, e.chapa)
    h = g.calcular_h(e.motor.H, e.chapa.e_apoio)
    sol = g.resolver(a0, b0, cota, h, e.chapa.theta_deg, R)
    if sol.status is Status.SEM_SOLUCAO:
        return Posicao(R, cota, Status.SEM_SOLUCAO, mensagens=("R²<d_perp²",))
    av = rn.avaliar(sol.s, e.motor, e.chapa.como_chapa(), e.ranhuras)
    return Posicao(
        R,
        cota,
        av.status,
        sol.s,
        -sol.s,
        sol.Cx,
        sol.Cy,
        av.folga_neg,
        av.folga_pos,
        av.mensagens,
        av.folgas_internas,
    )


def _dominio(e: EntradaCaso, cfg: ConfigProjeto) -> tuple[float, float] | None:
    """Cotas em que existem soluções para R_min e R_max (|d_perp| ≤ R)."""
    a0, b0 = ponto_base(cfg, e.chapa)
    h = g.calcular_h(e.motor.H, e.chapa.e_apoio)
    t = math.radians(e.chapa.theta_deg)
    centro = (a0 * math.sin(t) + h) / math.cos(t) - b0
    raio = min(e.R_min, e.R_max) / math.cos(t)
    return centro - raio, centro + raio


def _margem_conjunta(
    e: EntradaCaso, cfg: ConfigProjeto, cota: float, restricao: Restricao | None = None
) -> float:
    ms = []
    for R in (e.R_min, e.R_max):
        p = posicao(e, cfg, R, cota)
        if p.s is None or p.margem is None:
            return -math.inf
        ms.append(p.margem)
    if restricao is not None:
        ms.append(restricao(cota))
    return min(ms)


def cota_max_margem(
    e: EntradaCaso,
    cfg: ConfigProjeto,
    passo: float = 1.0,
    tol: float = 1e-6,
    restricao: Restricao | None = None,
) -> tuple[float, float] | None:
    """Cota que maximiza a menor folga entre R_min e R_max (e a da `restricao`, se houver)
    — varredura + refinamento por seção áurea. Retorna (cota, margem) ou None se não há
    ranhuras/solução."""
    dom = _dominio(e, cfg)
    if dom is None:
        return None
    lo, hi = dom
    n = max(2, int((hi - lo) / passo))
    melhor = max(
        (lo + (hi - lo) * i / n for i in range(n + 1)),
        key=lambda c: _margem_conjunta(e, cfg, c, restricao),
    )
    if _margem_conjunta(e, cfg, melhor, restricao) == -math.inf:
        return None
    a, b = max(lo, melhor - passo), min(hi, melhor + passo)
    r = (math.sqrt(5) - 1) / 2
    while b - a > tol:
        c1, c2 = b - r * (b - a), a + r * (b - a)
        if _margem_conjunta(e, cfg, c1, restricao) < _margem_conjunta(e, cfg, c2, restricao):
            a = c1
        else:
            b = c2
    cota = (a + b) / 2
    return cota, _margem_conjunta(e, cfg, cota, restricao)


def _intersecao(
    f1: list[tuple[float, float]], f2: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    out = []
    for a1, b1 in f1:
        for a2, b2 in f2:
            lo, hi = max(a1, a2), min(b1, b2)
            if lo <= hi:
                out.append((lo, hi))
    return sorted(out)


def faixas_restricao(
    e: EntradaCaso, cfg: ConfigProjeto, restricao: Restricao, passo: float = 1.0, tol: float = 1e-6
) -> list[tuple[float, float]]:
    """Intervalos de cota (no domínio de solução) em que restricao(cota) ≥ 0."""
    dom = _dominio(e, cfg)
    if dom is None:
        return []
    lo, hi = dom
    n = max(2, int((hi - lo) / passo))
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    ok = [restricao(x) >= 0 for x in xs]

    def borda(a: float, b: float) -> float:
        """Bissecção da troca de sinal em [a, b] (restricao(a) e restricao(b) diferem)."""
        va = restricao(a) >= 0
        while b - a > tol:
            m = (a + b) / 2
            if (restricao(m) >= 0) == va:
                a = m
            else:
                b = m
        return (a + b) / 2

    faixas: list[tuple[float, float]] = []
    inicio = xs[0] if ok[0] else None
    for i in range(1, len(xs)):
        if ok[i] and not ok[i - 1]:
            inicio = borda(xs[i - 1], xs[i])
        elif ok[i - 1] and not ok[i]:
            assert inicio is not None
            faixas.append((inicio, borda(xs[i - 1], xs[i])))
            inicio = None
    if inicio is not None:
        faixas.append((inicio, xs[-1]))
    return faixas


def resolver_caso(
    e: EntradaCaso, cfg: ConfigProjeto, restricao: Restricao | None = None
) -> ResultadoProjeto:
    """Faixa admissível da cota, cota recomendada (máxima folga mínima) e verificações.

    `restricao` (opcional, ex.: banco duplo) restringe a faixa e entra na folga mínima;
    sem cota que a atenda (e com as ranhuras atendidas), o status é FORA_TENSIONAMENTO.
    """
    a0, b0 = ponto_base(cfg, e.chapa)
    h = g.calcular_h(e.motor.H, e.chapa.e_apoio)
    th = e.chapa.theta_deg

    def nas(cota: float | None) -> tuple[Posicao, Posicao] | None:
        if cota is None:
            return None
        return posicao(e, cfg, e.R_min, cota), posicao(e, cfg, e.R_max, cota)

    informada = nas(e.cota_informada)
    previa = rn.avaliar(0.0, e.motor, e.chapa.como_chapa(), e.ranhuras)
    if previa.status is Status.INCOMPATIVEL:
        return ResultadoProjeto(
            e,
            h,
            a0,
            b0,
            (),
            None,
            None,
            Status.INCOMPATIVEL,
            "; ".join(previa.mensagens),
            None,
            informada,
        )
    lim = rn.s_admissivel(e.ranhuras, e.motor)
    if lim is None:
        return ResultadoProjeto(
            e,
            h,
            a0,
            b0,
            (),
            None,
            None,
            Status.OK,
            "AVISO: ranhuras não cadastradas/insuficientes; faixa da cota não calculada",
            None,
            informada,
        )
    faixas = _intersecao(
        rn.faixa_dy(a0, b0, h, th, e.R_min, *lim), rn.faixa_dy(a0, b0, h, th, e.R_max, *lim)
    )
    faixas_ranhuras = faixas
    if restricao is not None:
        faixas = _intersecao(faixas, faixas_restricao(e, cfg, restricao))
    otimo = cota_max_margem(e, cfg, restricao=restricao)
    if otimo is None:
        return ResultadoProjeto(
            e,
            h,
            a0,
            b0,
            (),
            None,
            None,
            Status.SEM_SOLUCAO,
            "sem solução geométrica para R_min/R_max",
            None,
            informada,
        )
    cota, margem = otimo
    if faixas:
        status, msg = Status.OK, f"altura H admissível em {len(faixas)} faixa(s)"
    elif faixas_ranhuras:
        assert restricao is not None
        status = Status.FORA_TENSIONAMENTO
        msg = (
            "nenhuma altura H atende o tensionamento para banco duplo: na H recomendada, "
            f"curso entre os arcos R1 e R2 = {restricao(cota):.2f} mm "
            f"(folga mínima {margem:.2f} mm)"
        )
    else:
        status = Status.FORA_RANHURA
        msg = (
            f"nenhuma altura H atende R_min e R_max: faltam {-margem:.2f} mm de folga "
            f"em cada extremo (curso das ranhuras insuficiente)"
        )
    return ResultadoProjeto(
        e, h, a0, b0, tuple(faixas), cota, margem, status, msg, nas(cota), informada
    )
