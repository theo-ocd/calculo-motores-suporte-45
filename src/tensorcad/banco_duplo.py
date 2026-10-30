"""Esboço do modo "banco duplo" (funções puras).

Um segundo centro de arcos O2, deslocado `deslocamento_y` mm na vertical em relação a O,
com raios próprios R2 = R + adicional. O motor é único: sua posição continua definida
pelo banco 1 (R_min a 0 % e R_max a 3 % sobre a chapa). Para cada uma dessas posições
mede-se a distância do centro do motor a O2 e confere-se se ela fica entre as duas
linhas de raio do banco 2 (R2_min ≤ R2 ≤ R2_max); fora disso, gera aviso — não muda o
status do caso.

Referencial de docs/geometria.md (x+ esquerda, y+ baixo). `deslocamento_y` > 0 põe O2
ACIMA de O (pendência P8: confirmar o sentido).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tensorcad.projeto import Posicao

DESLOCAMENTO_Y_PADRAO = 500.0


@dataclass(frozen=True)
class ConfigBancoDuplo:
    adicional_R_min: float  # R2_min = R_min + adicional_R_min
    adicional_R_max: float  # R2_max = R_max + adicional_R_max
    deslocamento_y: float = DESLOCAMENTO_Y_PADRAO  # + = O2 acima de O

    @property
    def centro(self) -> tuple[float, float]:
        """O2 no referencial do núcleo (x+ esquerda, y+ baixo)."""
        return 0.0, -self.deslocamento_y


@dataclass(frozen=True)
class PosicaoBanco2:
    rotulo: str  # "0" (motor em R_min) ou "3" (motor em R_max)
    R1: float
    R2: float  # distância centro do motor → O2
    R2_min: float
    R2_max: float

    @property
    def desvio(self) -> float:
        """0 entre as linhas; < 0 abaixo de R2_min; > 0 acima de R2_max (mm)."""
        if self.R2_min > self.R2:
            return self.R2 - self.R2_min
        if self.R2_max < self.R2:
            return self.R2 - self.R2_max
        return 0.0

    @property
    def dentro(self) -> bool:
        return self.desvio == 0.0


@dataclass(frozen=True)
class AvaliacaoBancoDuplo:
    config: ConfigBancoDuplo
    R2_min: float
    R2_max: float
    posicoes: tuple[PosicaoBanco2, ...]
    avisos: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.avisos


def faixa_R2(cfg: ConfigBancoDuplo, R_min: float, R_max: float) -> tuple[float, float]:
    return R_min + cfg.adicional_R_min, R_max + cfg.adicional_R_max


def avaliar(
    cfg: ConfigBancoDuplo,
    R_min: float,
    R_max: float,
    posicoes: tuple[Posicao, Posicao] | None,
) -> AvaliacaoBancoDuplo:
    """Confere o motor (posições a 0 % e 3 % do banco 1) entre as linhas R2_min e R2_max."""
    r2_min, r2_max = faixa_R2(cfg, R_min, R_max)
    avisos: list[str] = []
    if r2_min > r2_max:
        avisos.append(f"banco 2: R2_min ({r2_min:g}) maior que R2_max ({r2_max:g})")
    ox, oy = cfg.centro
    itens: list[PosicaoBanco2] = []
    if posicoes is None:
        avisos.append("banco 2: sem posição do motor para verificar (sem altura H)")
    else:
        for rotulo, p in zip(("0", "3"), posicoes, strict=True):
            if p.Cx is None or p.Cy is None:
                avisos.append(f"banco 2: motor {rotulo} % sem posição (banco 1 sem solução)")
                continue
            q = PosicaoBanco2(rotulo, p.R, math.hypot(p.Cx - ox, p.Cy - oy), r2_min, r2_max)
            itens.append(q)
            if not q.dentro:
                lado = "abaixo de R2_min" if q.desvio < 0 else "acima de R2_max"
                avisos.append(
                    f"banco 2: motor {rotulo} % fora das linhas de raio — R2 = {q.R2:.2f}, "
                    f"{abs(q.desvio):.2f} mm {lado}"
                )
    return AvaliacaoBancoDuplo(cfg, r2_min, r2_max, tuple(itens), tuple(avisos))
