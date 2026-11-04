"""Cálculo da transmissão por correia (setups, S1) — funções puras.

Planilha "Belt transmission – Riemenberechnung" (docs/setups.md). Para uma correia de
comprimento L, polia da máquina D e polia do motor d:

    b  = (L − (π/2)·(D + d)) / 4
    a0 = b + √(b² − (D − d)²/8)          distância entre eixos sem alongamento
    a(ε) = a0 + L·ε/2                    com a correia alongada ε (2 %, 3 %)

R_min = a(0 %) e R_max = a(3 %); a(2 %) é só informação. rpm da máquina = rpm do
motor · d / D. Sufixo do caso: "-<d>-<L>" (ex.: -170-5000).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TENSAO_MIN = 0.0
TENSAO_INFO = 0.02
TENSAO_MAX = 0.03


@dataclass(frozen=True)
class Correia:
    """Uma transmissão: polia da máquina D, polia do motor d e comprimento da correia L."""

    polia_maquina: float
    polia_motor: float
    comprimento: float


@dataclass(frozen=True)
class RaiosCorreia:
    R_min: float  # 0 %
    R_info: float  # 2 % (informativo)
    R_max: float  # 3 %


def distancia_eixos(c: Correia, alongamento: float = 0.0) -> float:
    """Distância entre eixos com a correia alongada `alongamento` (0,03 = 3 %).

    ValueError se a correia é curta demais para as polias."""
    L, D, d = c.comprimento, c.polia_maquina, c.polia_motor
    if min(L, D, d) <= 0:
        raise ValueError("polias e correia devem ser maiores que zero")
    b = (L - math.pi / 2 * (D + d)) / 4
    disc = b * b - (D - d) ** 2 / 8
    if b <= 0 or disc < 0:
        raise ValueError(f"correia de {L:g} mm curta demais para as polias {D:g} e {d:g}")
    return b + math.sqrt(disc) + L * alongamento / 2


def raios(c: Correia) -> RaiosCorreia:
    return RaiosCorreia(
        distancia_eixos(c, TENSAO_MIN),
        distancia_eixos(c, TENSAO_INFO),
        distancia_eixos(c, TENSAO_MAX),
    )


def rpm_maquina(rpm_motor: float, c: Correia) -> float:
    return rpm_motor * c.polia_motor / c.polia_maquina


def sufixo(c: Correia) -> str:
    """Sufixo travado do caso: -<polia do motor>-<correia> (sem o perfil)."""
    return f"-{c.polia_motor:g}-{c.comprimento:g}"
