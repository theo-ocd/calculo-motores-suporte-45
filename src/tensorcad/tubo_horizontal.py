"""Layout "tubo horizontal" (T2): núcleo geométrico, funções puras.

Referencial (docs/tubo_horizontal.md): origem em O1 (centro dos raios do banco 1).
- O topo da laje fica `y_laje` abaixo de O1; a linha de centro fica `x_linha` de O1.
- x: deslocamento do conjunto (motor + chapa) ao longo do tubo, medido da linha de
  centro; positivo afastando-se de O1 (como a cota 248 do desenho).
- altura_tubo: topo da laje → TOPO do tubo (motor normal) ou → FUNDO do tubo (invertido).
- y_motor: centro do motor abaixo do topo da laje.
    normal:    y_motor = altura_tubo − 2·porca − g − chapa − H
    invertido: y_motor = altura_tubo + 2·porca + g + chapa + H
- Distância a O1: R = √((x_linha + x)² + (y_laje + y_motor)²).

Para cada R (0 % e 3 %), x e g ajustam juntos: o motor fica num ponto do arco R com
g_min ≤ g ≤ g_max e 0 ≤ x ≤ x_max, onde x_max = comprimento_tubo/2 − (A + acréscimo)/2.
O motor nunca troca de lado: x ≥ 0, ou seja, sempre afastado de O1 em relação à linha de
centro (P19).

Folga relativa (P19): cada folga é dividida pela metade do seu curso, ou seja,
(g − g_min)/m_g, (g_max − g)/m_g, x/m_x e (x_max − x)/m_x, com m_g = (g_max − g_min)/2 e
m_x = x_max/2. A posição em cada arco e a altura recomendada maximizam a menor folga
relativa. Assim a passagem de 0 % a 3 % se divide entre g e x, na proporção dos cursos,
em vez de ficar só em x. As folgas em mm (folga_g, folga_x) continuam no resultado. Como
no H do 45°, a altura do tubo é entrada opcional (verificação); o cálculo devolve a
faixa admissível (folgas ≥ 0) e a altura recomendada.

Tensionamento para banco duplo (T4), opcional por caso: O2 fica `deslocamento_y` acima de
O1 e, em cada tensão, o centro deve ficar a ≤ R2 de O2 (a distância a O1 é R1, sobre o
arco). É obrigatório: a posição e a altura recomendada só aceitam pontos com
folga_R2 = R2 − |C − O2| ≥ 0. A folga positiva não muda a escolha; só a negativa pesa
(dividida pelo meio curso de g). Sem altura que atenda, e com g e x atendidos, o caso fica
FORA_TENSIONAMENTO.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tensorcad.banco_duplo import ConfigBancoDuplo
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
    banco2: ConfigBancoDuplo | None = None  # tensionamento para banco duplo (opcional)


@dataclass(frozen=True)
class PosicaoTH:
    R: float
    altura_tubo: float
    status: Status
    g: float | None = None
    x: float | None = None
    y_motor: float | None = None  # centro do motor abaixo do topo da laje
    folga_g: float | None = None  # min(g − g_min, g_max − g)
    folga_x: float | None = None  # min(x, x_max − x)
    folga_rel: float | None = None  # menor folga relativa (1 = meio dos dois cursos)
    mensagens: tuple[str, ...] = ()
    R2: float | None = None  # banco duplo: raio de O2 nesta tensão
    dist_O2: float | None = None
    folga_R2: float | None = None  # R2 − |C − O2| (≥ 0 atende)

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
    margem_recomendada: float | None  # menor folga em mm na altura recomendada
    status: Status
    mensagem: str
    em_recomendada: tuple[PosicaoTH, PosicaoTH] | None
    em_informada: tuple[PosicaoTH, PosicaoTH] | None


# --------------------------------------------------------------------------- pilha


def pilha(par: ParametrosTH, motor: Motor) -> float:
    """Distância fixa da pilha (sem g): da face do tubo usada (topo no normal, fundo no
    invertido — a mesma da altura do tubo) ao centro do motor."""
    return 2 * par.espessura_porca + par.espessura_chapa + motor.H


def y_motor(par: ParametrosTH, motor: Motor, altura_tubo: float, g: float) -> float:
    """Centro do motor abaixo do topo da laje."""
    k = pilha(par, motor)
    return altura_tubo + k + g if par.invertido else altura_tubo - k - g


def x_max(par: ParametrosTH, motor: Motor) -> float:
    """|x| máximo: a chapa (A + acréscimo) dentro de comprimento_tubo / 2."""
    return par.comprimento_tubo / 2 - (motor.A + par.acrescimo_furacao) / 2


def raio(par: ParametrosTH, x: float, y: float) -> float:
    return math.hypot(par.x_linha + x, par.y_laje + y)


def raio_o2(par: ParametrosTH, b2: ConfigBancoDuplo, x: float, y: float) -> float:
    """Distância do centro do motor a O2 (deslocamento_y acima de O1, mesmo x)."""
    return math.hypot(par.x_linha + x, par.y_laje + b2.deslocamento_y + y)


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


def _folgas(par: ParametrosTH, motor: Motor, g: float, x: float) -> tuple[float, float, float]:
    """(folga_g, folga_x, folga relativa) em mm, mm e fração do meio curso."""
    xm = x_max(par, motor)
    m_g, m_x = (par.g_max - par.g_min) / 2, xm / 2
    fg = min(g - par.g_min, par.g_max - g)
    fx = min(x, xm - x)
    return fg, fx, min(fg / m_g, fx / m_x)


Banco2 = tuple[ConfigBancoDuplo, float] | None  # (configuração, R2 desta tensão)


def _rel_em(
    par: ParametrosTH, motor: Motor, R: float, altura: float, g: float, b2: Banco2 = None
) -> float:
    y = y_motor(par, motor, altura, g)
    x = x_no_arco(par, R, y)
    if x is None:
        return -math.inf
    rel = _folgas(par, motor, g, x)[2]
    if b2 is not None:
        folga_r2 = b2[1] - raio_o2(par, b2[0], x, y)
        if folga_r2 < 0:  # só a falta pesa (restrição obrigatória)
            rel = min(rel, folga_r2 / ((par.g_max - par.g_min) / 2))
    return rel


def posicao(
    par: ParametrosTH, motor: Motor, R: float, altura: float, b2: Banco2 = None
) -> PosicaoTH:
    """Melhor posição (g, x) sobre o arco R com o tubo na altura dada.

    `b2` = (banco duplo, R2 desta tensão): exige |C − O2| ≤ R2."""
    # g fora de [g_min, g_max] também é avaliado, para medir quanto falta
    lo, hi = par.g_min - 100, par.g_max + 100
    g, m = _maximo(lambda gg: _rel_em(par, motor, R, altura, gg, b2), lo, hi, passo=2.0)
    if m == -math.inf:
        return PosicaoTH(R, altura, Status.SEM_SOLUCAO, mensagens=("arco R fora do alcance",))
    y = y_motor(par, motor, altura, g)
    x = x_no_arco(par, R, y)
    assert x is not None
    folga_g, folga_x, rel = _folgas(par, motor, g, x)
    R2 = dist = folga_r2 = None
    if b2 is not None:
        R2, dist = b2[1], raio_o2(par, b2[0], x, y)
        folga_r2 = R2 - dist
        if folga_r2 < 0:
            rel = min(rel, folga_r2 / ((par.g_max - par.g_min) / 2))
    msgs = []
    if folga_g < 0:
        msgs.append(f"g = {g:.2f} fora de {par.g_min:g}–{par.g_max:g}")
    if x < 0:
        msgs.append(f"x = {x:.2f}: motor do lado de O1 (deve ficar ≥ 0)")
    elif folga_x < 0:
        msgs.append(f"x = {x:.2f} além do curso (0–{x_max(par, motor):.2f})")
    status = Status.FORA_PORCAS if msgs else Status.OK
    if folga_r2 is not None and folga_r2 < 0:
        msgs.append(
            f"tensionamento para banco duplo: |C−O2| = {dist:.2f} passa {-folga_r2:.2f} de R2"
        )
        if status is Status.OK:
            status = Status.FORA_TENSIONAMENTO
    return PosicaoTH(
        R, altura, status, g, x, y, folga_g, folga_x, rel, tuple(msgs), R2, dist, folga_r2
    )


def _tensoes(e: EntradaTH, com_banco2: bool = True) -> tuple[tuple[float, Banco2], ...]:
    """(R1, banco 2) de 0 % e 3 %."""
    b = e.banco2 if com_banco2 else None
    if b is None:
        return (e.R_min, None), (e.R_max, None)
    return (e.R_min, (b, b.R2_min)), (e.R_max, (b, b.R2_max))


def _avaliacao(par: ParametrosTH, e: EntradaTH, altura: float, com_banco2: bool = True) -> float:
    """Menor folga relativa entre 0 % e 3 %."""
    rs = []
    for R, b2 in _tensoes(e, com_banco2):
        p = posicao(par, e.motor, R, altura, b2)
        if p.folga_rel is None:
            return -math.inf
        rs.append(p.folga_rel)
    return min(rs)


def dominio_altura(par: ParametrosTH, e: EntradaTH) -> tuple[float, float]:
    """Faixa de alturas do tubo em que os arcos podem ser alcançados com g e x no curso."""
    xm = max(0.0, x_max(par, e.motor))
    # x de 0 a x_max: distância horizontal a O1 de x_linha a x_linha + x_max
    v_lo = min(math.sqrt(max(0.0, R * R - (par.x_linha + xm) ** 2)) for R in (e.R_min, e.R_max))
    v_hi = max(math.sqrt(max(0.0, R * R - par.x_linha**2)) for R in (e.R_min, e.R_max))
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
        (r0, b0), (r3, b3) = _tensoes(e)
        return posicao(par, e.motor, r0, altura, b0), posicao(par, e.motor, r3, altura, b3)

    informada = nas(e.altura_informada)
    if xm <= 0:
        msg = (
            f"a chapa (A {e.motor.A:g} + {par.acrescimo_furacao:g}) não cabe no curso do tubo "
            f"({par.comprimento_tubo:g} / 2)"
        )
        return ResultadoTH(e, par, xm, (), None, None, Status.INCOMPATIVEL, msg, None, informada)
    lo, hi = dominio_altura(par, e)
    f = lambda a: _avaliacao(par, e, a)  # noqa: E731
    altura, rel = _maximo(f, lo, hi)
    if rel == -math.inf:
        msg = "sem solução geométrica para R_min/R_max"
        return ResultadoTH(e, par, xm, (), None, None, Status.SEM_SOLUCAO, msg, None, informada)
    rec = nas(altura)
    assert rec is not None
    margem = min(p.margem for p in rec if p.margem is not None)
    faixas = tuple(_faixas(f, lo, hi))
    if faixas:
        status, msg = Status.OK, f"altura do tubo admissível em {len(faixas)} faixa(s)"
    elif e.banco2 is not None and _faixas(lambda a: _avaliacao(par, e, a, False), lo, hi):
        status = Status.FORA_TENSIONAMENTO
        pior = min((p.folga_R2 for p in rec if p.folga_R2 is not None), default=0.0)
        msg = (
            "nenhuma altura do tubo atende o tensionamento para banco duplo: na recomendada, "
            f"o motor passa {-pior:.2f} mm do arco R2 de O2"
        )
    else:
        status = Status.FORA_PORCAS
        msg = (
            "nenhuma altura do tubo atende R_min e R_max com g entre "
            f"{par.g_min:g} e {par.g_max:g} e x no curso: faltam {-margem:.2f} mm"
        )
    return ResultadoTH(e, par, xm, faixas, altura, margem, status, msg, rec, informada)
