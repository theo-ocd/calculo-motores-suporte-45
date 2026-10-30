"""Esboço do modo "banco duplo" (funções puras).

Um segundo centro de arcos O2, `deslocamento_y` mm ACIMA de O (P8), com raios próprios
R2_min e R2_max, independentes do banco 1 (P9). O motor é único; para cada tensão
(0 %: R1_min/R2_min; 3 %: R1_max/R2_max) o centro do motor deve ficar a uma distância
de O MAIOR OU IGUAL a R1 e de O2 MENOR OU IGUAL a R2 (P10): um trecho da chapa entre o
arco R1 e o arco R2. Sem esse trecho, gera aviso — não muda o status do caso.

Referencial de docs/geometria.md (x+ esquerda, y+ baixo); s ao longo da guia (s+ desce).
A posição do motor do banco 1 (|C − O| = R1) é a ponta alta do trecho; a ponta baixa é
onde |C − O2| = R2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tensorcad import geometry as g
from tensorcad.projeto import ConfigProjeto, EntradaCaso, Posicao, ponto_base

DESLOCAMENTO_Y_PADRAO = 500.0


@dataclass(frozen=True)
class ConfigBancoDuplo:
    R2_min: float  # raio do banco 2 para a tensão mínima (0 %)
    R2_max: float  # raio do banco 2 para a tensão máxima (3 %)
    deslocamento_y: float = DESLOCAMENTO_Y_PADRAO  # O2 acima de O

    @property
    def centro(self) -> tuple[float, float]:
        """O2 no referencial do núcleo (x+ esquerda, y+ baixo)."""
        return 0.0, -self.deslocamento_y


@dataclass(frozen=True)
class PosicaoBanco2:
    rotulo: str  # "0" (R1_min/R2_min) ou "3" (R1_max/R2_max)
    R1: float
    R2: float  # raio do banco 2 nesta tensão
    dist_O2: float  # |C − O2| com o motor na posição do banco 1 (|C − O| = R1)
    s_R1: float  # ponta alta do trecho (motor sobre o arco R1)
    s_R2: float | None  # ponta baixa (motor sobre o arco R2); None se não há trecho

    @property
    def curso(self) -> float | None:
        """Comprimento do trecho entre os arcos ao longo da chapa (mm); < 0 = não existe."""
        return None if self.s_R2 is None else self.s_R2 - self.s_R1

    @property
    def dentro(self) -> bool:
        return self.curso is not None and self.curso >= 0.0

    @property
    def folga_R2(self) -> float:
        """R2 − |C − O2| na posição do banco 1 (≥ 0: dentro do arco R2)."""
        return self.R2 - self.dist_O2


@dataclass(frozen=True)
class AvaliacaoBancoDuplo:
    config: ConfigBancoDuplo
    H: float | None
    posicoes: tuple[PosicaoBanco2, ...]
    avisos: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.avisos


def _cruzamentos_o2(
    cfg: ConfigBancoDuplo, e: EntradaCaso, pcfg: ConfigProjeto, H: float, R2: float
) -> tuple[float, float] | None:
    """(s_alto, s_baixo) em que a trajetória do centro cruza o arco R2 de O2."""
    a0, b0 = ponto_base(pcfg, e.chapa)
    h = g.calcular_h(e.motor.H, e.chapa.e_apoio)
    ox, oy = cfg.centro
    l_proj, d_perp = g.projecoes(a0 - ox, b0 - oy, H, h, e.chapa.theta_deg)
    disc = R2 * R2 - d_perp * d_perp
    if disc < 0:
        return None
    raiz = math.sqrt(disc)
    return -l_proj - raiz, -l_proj + raiz


def centro_em(e: EntradaCaso, pcfg: ConfigProjeto, H: float, s: float) -> tuple[float, float]:
    """Centro do motor (referencial do núcleo) na posição s da guia, na altura H."""
    a0, b0 = ponto_base(pcfg, e.chapa)
    h = g.calcular_h(e.motor.H, e.chapa.e_apoio)
    return g.centro_motor(a0, b0, H, h, e.chapa.theta_deg, s)


def avaliar(
    cfg: ConfigBancoDuplo,
    e: EntradaCaso,
    pcfg: ConfigProjeto,
    H: float | None,
    posicoes: tuple[Posicao, Posicao] | None,
) -> AvaliacaoBancoDuplo:
    """Confere, a 0 % e 3 %, se existe trecho da chapa com |C−O| ≥ R1 e |C−O2| ≤ R2."""
    avisos: list[str] = []
    if cfg.R2_min > cfg.R2_max:
        avisos.append(f"banco 2: R2_min ({cfg.R2_min:g}) maior que R2_max ({cfg.R2_max:g})")
    ox, oy = cfg.centro
    if H is None or posicoes is None:
        avisos.append("banco 2: sem posição do motor para verificar (sem altura H)")
        return AvaliacaoBancoDuplo(cfg, H, (), tuple(avisos))
    itens: list[PosicaoBanco2] = []
    for rotulo, R2, p in zip(("0", "3"), (cfg.R2_min, cfg.R2_max), posicoes, strict=True):
        if p.s is None or p.Cx is None or p.Cy is None:
            avisos.append(f"banco 2: motor {rotulo} % sem posição (banco 1 sem solução)")
            continue
        cruza = _cruzamentos_o2(cfg, e, pcfg, H, R2)
        # o trecho começa em s_R1 e termina onde a trajetória sai do círculo R2 de O2
        s_R2 = None if cruza is None or cruza[0] > p.s else cruza[1]
        q = PosicaoBanco2(rotulo, p.R, R2, math.hypot(p.Cx - ox, p.Cy - oy), p.s, s_R2)
        itens.append(q)
        if not q.dentro:
            avisos.append(
                f"banco 2: a {rotulo} % não há posição a ≥ R1 ({p.R:g}) de O e ≤ R2 "
                f"({R2:g}) de O2 — sobre o arco R1, a distância a O2 é {q.dist_O2:.2f} "
                f"({-q.folga_R2:.2f} mm além de R2)"
            )
    return AvaliacaoBancoDuplo(cfg, H, tuple(itens), tuple(avisos))
