"""Núcleo geométrico: funções puras, sem I/O. Ver docs/geometria.md.

Convenções: origem O = centro do arco, x positivo para a ESQUERDA, y positivo para
BAIXO; mm; ângulos em graus na interface pública, radianos internamente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    OK = "OK"
    SEM_SOLUCAO = "SEM_SOLUCAO"
    FORA_RANHURA = "FORA_RANHURA"
    INCOMPATIVEL = "INCOMPATIVEL"


@dataclass(frozen=True)
class Solucao:
    """Resultado de `resolver`. Campos None quando status = SEM_SOLUCAO."""

    status: Status
    l_proj: float
    d_perp: float
    s: float | None = None
    Cx: float | None = None
    Cy: float | None = None
    ds_ddy: float | None = None
    ds_dh: float | None = None


def calcular_h(
    H: float,
    e_apoio: float,
    e_apoio_override: float | None = None,
    h_override: float | None = None,
) -> float:
    """h = H + e_apoio (e_apoio_override substitui e_apoio da chapa); h_override, se
    informado, tem prioridade sobre tudo."""
    if h_override is not None:
        return h_override
    return H + (e_apoio if e_apoio_override is None else e_apoio_override)


def calibrar_P(Cx0: float, Cy0: float, h0: float, theta0_deg: float) -> tuple[float, float]:
    """P = (a, b) a partir do centro do motor medido num desenho (com Δy = 0)."""
    t = math.radians(theta0_deg)
    return Cx0 - h0 * math.sin(t), Cy0 + h0 * math.cos(t)


def projecoes(a: float, b: float, dy: float, h: float, theta_deg: float) -> tuple[float, float]:
    """(l_proj, d_perp) do ponto P deslocado de Δy."""
    t = math.radians(theta_deg)
    by = b + dy
    l_proj = a * math.cos(t) + by * math.sin(t)
    d_perp = a * math.sin(t) - by * math.cos(t) + h
    return l_proj, d_perp


def resolver_s(a: float, b: float, dy: float, h: float, theta_deg: float, R: float) -> float | None:
    """Deslocamento s ao longo da guia para |C| = R; None se não há solução."""
    l_proj, d_perp = projecoes(a, b, dy, h, theta_deg)
    disc = R * R - d_perp * d_perp
    if disc < 0:
        return None
    return -l_proj + math.sqrt(disc)


def centro_motor(
    a: float, b: float, dy: float, h: float, theta_deg: float, s: float
) -> tuple[float, float]:
    """Centro C = P + Δy·ŷ + s·u + h·n (coordenadas relativas a O)."""
    t = math.radians(theta_deg)
    Cx = a + s * math.cos(t) + h * math.sin(t)
    Cy = b + dy + s * math.sin(t) - h * math.cos(t)
    return Cx, Cy


def sensibilidades(
    a: float, b: float, dy: float, h: float, theta_deg: float, R: float
) -> tuple[float, float] | None:
    """(∂s/∂Δy, ∂s/∂h). None se sem solução ou na tangência (raiz nula)."""
    _, d_perp = projecoes(a, b, dy, h, theta_deg)
    disc = R * R - d_perp * d_perp
    if disc <= 0:
        return None
    t = math.radians(theta_deg)
    q = math.sqrt(disc)
    return -math.sin(t) + d_perp * math.cos(t) / q, -d_perp / q


def resolver(a: float, b: float, dy: float, h: float, theta_deg: float, R: float) -> Solucao:
    """Solução completa para um caso."""
    l_proj, d_perp = projecoes(a, b, dy, h, theta_deg)
    s = resolver_s(a, b, dy, h, theta_deg, R)
    if s is None:
        return Solucao(Status.SEM_SOLUCAO, l_proj, d_perp)
    Cx, Cy = centro_motor(a, b, dy, h, theta_deg, s)
    sens = sensibilidades(a, b, dy, h, theta_deg, R)
    ds_ddy, ds_dh = sens if sens is not None else (None, None)
    return Solucao(Status.OK, l_proj, d_perp, s, Cx, Cy, ds_ddy, ds_dh)


def para_cad(x: float, y: float, X_O_cad: float, Y_O_cad: float) -> tuple[float, float]:
    """Converte (x, y) relativos a O (x à esquerda, y para baixo) para o CAD (y para cima)."""
    return X_O_cad - x, Y_O_cad - y
