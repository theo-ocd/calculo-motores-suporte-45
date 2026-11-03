"""Layout "tubo horizontal" (T2): núcleo geométrico, funções puras.

Referencial (docs/tubo_horizontal.md): origem em O1 (centro dos raios do banco 1).
- O topo da laje fica `y_laje` abaixo de O1; a linha de centro fica `x_linha` de O1.
- x: deslocamento do conjunto (motor + chapa) ao longo do tubo, medido da linha de
  centro; positivo afastando-se de O1 (como a cota 248 do desenho).
- y_motor: centro do motor abaixo do topo da laje.
    normal:    y_motor = altura_tubo − espessura_tubo − 2·porca − g − chapa − H
    invertido: y_motor = altura_tubo + 2·porca + g + chapa + H
- Distância a O1: R = √((x_linha + x)² + (y_laje + y_motor)²).

Para cada R (0 % e 3 %), x e g ajustam juntos: o motor fica num ponto do arco R com
g_min ≤ g ≤ g_max e |x| + (A + acréscimo)/2 ≤ comprimento_tubo/2. A folga de uma posição
é a menor entre g − g_min, g_max − g e a sobra em x. Como no H do 45°, a altura do tubo
é entrada opcional (verificação); o cálculo devolve a faixa admissível e a altura
recomendada (máxima folga mínima entre 0 % e 3 %).

Desempate: como x e g ajustam juntos, a folga em g chega ao máximo (g no meio do curso)
numa faixa larga de alturas. Nela, a recomendada é a que maximiza a menor folga em x,
ou seja, centraliza no tubo o curso do motor entre 0 % e 3 %.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tensorcad.geometry import Status
from tensorcad.models import Motor

X_LINHA_PADRAO = 465.0  # O1 → linha de centro (x), fixo como x_tubo no 45°
Y_LAJE_PADRAO = 767.0  # O1 → topo da laje (y), fixo como y_piso no 45°
PASSO = 1.0  # mm, varredura antes do refinamento
TOL = 1e-6


@dataclass(frozen=True)
class ParametrosTH:
    """Parâmetros do layout (data/padrao/tubo_horizontal.csv) e do projeto."""

    comprimento_tubo: float
    espessura_tubo: float = 80.0
    espessura_porca: float = 27.5
    espessura_chapa: float = 15.0
    g_min: float = 30.0
    g_max: float = 150.0
    acrescimo_furacao: float = 75.0
    invertido: bool = False
    x_linha: float = X_LINHA_PADRAO
    y_laje: float = Y_LAJE_PADRAO


@dataclass(frozen=True)
class EntradaTH:
    caso_id: str
    motor: Motor
    R_min: float
    R_max: float
    altura_informada: float | None = None


@dataclass(frozen=True)
class PosicaoTH:
    R: float
    altura_tubo: float
    status: Status
    g: float | None = None
    x: float | None = None
    y_motor: float | None = None  # centro do motor abaixo do topo da laje
    folga_g: float | None = None  # min(g − g_min, g_max − g)
    folga_x: float | None = None  # sobra do curso em x
    mensagens: tuple[str, ...] = ()

    @property
    def margem(self) -> float | None:
        if self.folga_g is None or self.folga_x is None:
            return None
        return min(self.folga_g, self.folga_x)

    @property
    def centro(self) -> tuple[float, float] | None:
        """(horizontal, vertical) de O1 ao centro do motor, ambos positivos no desenho."""
        if self.x is None or self.y_motor is None:
            return None
        return self.x, self.y_motor


@dataclass(frozen=True)
class ResultadoTH:
    entrada: EntradaTH
    parametros: ParametrosTH
    x_max: float  # |x| máximo pela interferência da chapa
    faixas_altura: tuple[tuple[float, float], ...]
    altura_recomendada: float | None
    margem_recomendada: float | None
    status: Status
    mensagem: str
    em_recomendada: tuple[PosicaoTH, PosicaoTH] | None
    em_informada: tuple[PosicaoTH, PosicaoTH] | None


# --------------------------------------------------------------------------- pilha


def pilha(par: ParametrosTH, motor: Motor) -> float:
    """Distância fixa da pilha (sem g): do ponto do tubo usado ao centro do motor."""
    base = 2 * par.espessura_porca + par.espessura_chapa + motor.H
    return base if par.invertido else par.espessura_tubo + base


def y_motor(par: ParametrosTH, motor: Motor, altura_tubo: float, g: float) -> float:
    """Centro do motor abaixo do topo da laje."""
    k = pilha(par, motor)
    return altura_tubo + k + g if par.invertido else altura_tubo - k - g


def x_max(par: ParametrosTH, motor: Motor) -> float:
    """|x| máximo: a chapa (A + acréscimo) dentro de comprimento_tubo / 2."""
    return par.comprimento_tubo / 2 - (motor.A + par.acrescimo_furacao) / 2


def raio(par: ParametrosTH, x: float, y: float) -> float:
    return math.hypot(par.x_linha + x, par.y_laje + y)


def x_no_arco(par: ParametrosTH, R: float, y: float) -> float | None:
    """x (lado afastado de O1) em que o centro, a y abaixo da laje, fica sobre o arco R."""
    v = par.y_laje + y
    d = R * R - v * v
    if d < 0:
        return None
    return math.sqrt(d) - par.x_linha


# --------------------------------------------------------------------------- otimização


def _maximo(
    f: Callable[[float], Any], lo: float, hi: float, passo: float = PASSO
) -> tuple[float, Any]:
    """Máximo de f em [lo, hi] (valores comparáveis: números ou tuplas, ordem
    lexicográfica): varredura com `passo` e refinamento por seção áurea."""
    n = max(2, int((hi - lo) / passo))
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    melhor = max(xs, key=f)
    a, b = max(lo, melhor - (hi - lo) / n), min(hi, melhor + (hi - lo) / n)
    r = (math.sqrt(5) - 1) / 2
    while b - a > TOL:
        c1, c2 = b - r * (b - a), a + r * (b - a)
        if f(c1) < f(c2):
            a = c1
        else:
            b = c2
    c = (a + b) / 2
    return (c, f(c)) if f(c) >= f(melhor) else (melhor, f(melhor))


def _faixas(f: Callable[[float], float], lo: float, hi: float) -> list[tuple[float, float]]:
    """Intervalos de [lo, hi] em que f ≥ 0 (varredura + bissecção nas bordas)."""
    n = max(2, int((hi - lo) / PASSO))
    xs = [lo + (hi - lo) * i / n for i in range(n + 1)]
    ok = [f(x) >= 0 for x in xs]

    def borda(a: float, b: float) -> float:
        va = f(a) >= 0
        while b - a > TOL:
            m = (a + b) / 2
            if (f(m) >= 0) == va:
                a = m
            else:
                b = m
        return (a + b) / 2

    out: list[tuple[float, float]] = []
    inicio = xs[0] if ok[0] else None
    for i in range(1, len(xs)):
        if ok[i] and not ok[i - 1]:
            inicio = borda(xs[i - 1], xs[i])
        elif ok[i - 1] and not ok[i]:
            assert inicio is not None
            out.append((inicio, borda(xs[i - 1], xs[i])))
            inicio = None
    if inicio is not None:
        out.append((inicio, xs[-1]))
    return out


def _margem_em(par: ParametrosTH, motor: Motor, R: float, altura: float, g: float) -> float:
    x = x_no_arco(par, R, y_motor(par, motor, altura, g))
    if x is None:
        return -math.inf
    return min(g - par.g_min, par.g_max - g, x_max(par, motor) - abs(x))


def posicao(par: ParametrosTH, motor: Motor, R: float, altura: float) -> PosicaoTH:
    """Melhor posição (g, x) sobre o arco R com o tubo na altura dada."""
    # g fora de [g_min, g_max] também é avaliado, para medir quanto falta
    lo, hi = par.g_min - 100, par.g_max + 100
    g, m = _maximo(lambda gg: _margem_em(par, motor, R, altura, gg), lo, hi, passo=2.0)
    if m == -math.inf:
        return PosicaoTH(R, altura, Status.SEM_SOLUCAO, mensagens=("arco R fora do alcance",))
    y = y_motor(par, motor, altura, g)
    x = x_no_arco(par, R, y)
    assert x is not None
    folga_g = min(g - par.g_min, par.g_max - g)
    folga_x = x_max(par, motor) - abs(x)
    msgs = []
    if folga_g < 0:
        msgs.append(f"g = {g:.2f} fora de {par.g_min:g}–{par.g_max:g}")
    if folga_x < 0:
        msgs.append(f"x = {x:.2f} além do curso (±{x_max(par, motor):.2f})")
    status = Status.FORA_PORCAS if msgs else Status.OK
    return PosicaoTH(R, altura, status, g, x, y, folga_g, folga_x, tuple(msgs))


def _avaliacao(par: ParametrosTH, e: EntradaTH, altura: float) -> tuple[float, float]:
    """(folga mínima, menor folga em x) entre 0 % e 3 %; a 2ª desempata a recomendação."""
    ms, xs = [], []
    for R in (e.R_min, e.R_max):
        p = posicao(par, e.motor, R, altura)
        if p.margem is None or p.folga_x is None:
            return -math.inf, -math.inf
        ms.append(p.margem)
        xs.append(p.folga_x)
    return min(ms), min(xs)


def dominio_altura(par: ParametrosTH, e: EntradaTH) -> tuple[float, float]:
    """Faixa de alturas do tubo em que os arcos podem ser alcançados com g e x no curso."""
    xm = max(0.0, x_max(par, e.motor))
    h_min = max(0.0, par.x_linha - xm)
    v_lo = min(math.sqrt(max(0.0, R * R - (par.x_linha + xm) ** 2)) for R in (e.R_min, e.R_max))
    v_hi = max(math.sqrt(max(0.0, R * R - h_min**2)) for R in (e.R_min, e.R_max))
    k = pilha(par, e.motor)
    # y_motor = v − y_laje; altura = y_motor ± (k + g)
    y_lo, y_hi = v_lo - par.y_laje, v_hi - par.y_laje
    if par.invertido:
        return y_lo - k - par.g_max - 50, y_hi - k - par.g_min + 50
    return y_lo + k + par.g_min - 50, y_hi + k + par.g_max + 50


def resolver(par: ParametrosTH, e: EntradaTH) -> ResultadoTH:
    """Faixa admissível da altura do tubo, altura recomendada e verificação da informada."""
    xm = x_max(par, e.motor)

    def nas(altura: float | None) -> tuple[PosicaoTH, PosicaoTH] | None:
        if altura is None:
            return None
        return posicao(par, e.motor, e.R_min, altura), posicao(par, e.motor, e.R_max, altura)

    informada = nas(e.altura_informada)
    if xm < 0:
        msg = (
            f"a chapa (A {e.motor.A:g} + {par.acrescimo_furacao:g}) não cabe no curso do tubo "
            f"({par.comprimento_tubo:g} / 2)"
        )
        return ResultadoTH(e, par, xm, (), None, None, Status.INCOMPATIVEL, msg, None, informada)
    lo, hi = dominio_altura(par, e)
    altura, (margem, _) = _maximo(lambda a: _avaliacao(par, e, a), lo, hi)
    if margem == -math.inf:
        msg = "sem solução geométrica para R_min/R_max"
        return ResultadoTH(e, par, xm, (), None, None, Status.SEM_SOLUCAO, msg, None, informada)
    faixas = tuple(_faixas(lambda a: _avaliacao(par, e, a)[0], lo, hi))
    if faixas:
        status, msg = Status.OK, f"altura do tubo admissível em {len(faixas)} faixa(s)"
    else:
        status = Status.FORA_PORCAS
        msg = (
            "nenhuma altura do tubo atende R_min e R_max com g entre "
            f"{par.g_min:g} e {par.g_max:g} e x no curso: faltam {-margem:.2f} mm"
        )
    return ResultadoTH(e, par, xm, faixas, altura, margem, status, msg, nas(altura), informada)
