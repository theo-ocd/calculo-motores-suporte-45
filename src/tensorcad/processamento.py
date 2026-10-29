"""Processamento de casos: resolve parâmetros a partir da base e aplica o núcleo.

Funções puras (sem I/O): recebem a BaseDados já carregada.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tensorcad import geometry as g
from tensorcad.loader import BaseDados
from tensorcad.models import Caso, Resultado


@dataclass(frozen=True)
class Parametros:
    caso_id: str
    a: float
    b: float
    delta_y: float
    h: float
    theta_deg: float
    R: float
    X_O_cad: float | None
    Y_O_cad: float | None


def parametros(caso: Caso, base: BaseDados) -> Parametros:
    """Parâmetros efetivos do caso (overrides aplicados). Base deve estar validada."""
    mont = base.montagens[caso.montagem_id]
    chapa = base.chapas[mont.chapa_id]
    motor = base.motores[caso.motor_id]
    R = caso.R_efetivo(base.transmissoes[caso.transmissao_id])
    if R is None:
        raise ValueError(f"{caso.caso_id}: R_alvo='nom' sem R_nom na transmissão")
    h = g.calcular_h(motor.H, chapa.e_apoio, caso.e_apoio_override, caso.h_override)
    theta = chapa.theta_deg if caso.theta_override is None else caso.theta_override
    return Parametros(
        caso.caso_id,
        mont.a_ref,
        mont.b_ref,
        caso.delta_y,
        h,
        theta,
        R,
        mont.X_O_cad,
        mont.Y_O_cad,
    )


def calcular(p: Parametros) -> Resultado:
    """Resultado geométrico de um conjunto de parâmetros."""
    sol = g.resolver(p.a, p.b, p.delta_y, p.h, p.theta_deg, p.R)
    msgs: list[str] = []
    X_cad = Y_cad = None
    if sol.status is g.Status.SEM_SOLUCAO:
        msgs.append(f"R²<d_perp²: R={p.R:.2f}, |d_perp|={abs(sol.d_perp):.2f}")
    elif p.X_O_cad is None or p.Y_O_cad is None:
        msgs.append("AVISO: X_O_cad/Y_O_cad vazios (TODO); X_cad/Y_cad não calculados")
    else:
        X_cad, Y_cad = g.para_cad(sol.Cx, sol.Cy, p.X_O_cad, p.Y_O_cad)
    if sol.status is g.Status.OK and sol.ds_ddy is None:
        msgs.append("AVISO: tangência (R=|d_perp|); sensibilidades indefinidas")
    return Resultado(
        caso_id=p.caso_id,
        h=p.h,
        theta_deg=p.theta_deg,
        R=p.R,
        l_proj=sol.l_proj,
        d_perp=sol.d_perp,
        s=sol.s,
        Cx=sol.Cx,
        Cy=sol.Cy,
        X_cad=X_cad,
        Y_cad=Y_cad,
        ds_ddy=sol.ds_ddy,
        ds_dh=sol.ds_dh,
        status=sol.status.value,
        mensagem="; ".join(msgs),
    )


def calcular_caso(caso: Caso, base: BaseDados) -> Resultado:
    return calcular(parametros(caso, base))


def calcular_todos(base: BaseDados) -> list[Resultado]:
    return [calcular_caso(c, base) for c in base.casos.values()]


def faixa(inicio: float, fim: float, passo: float) -> list[float]:
    """Valores de inicio a fim (inclusive) com o passo dado."""
    if passo <= 0:
        raise ValueError("passo deve ser positivo")
    if fim < inicio:
        raise ValueError("fim deve ser ≥ inicio")
    n = int(round((fim - inicio) / passo))
    vals = [inicio + i * passo for i in range(n + 1)]
    return [v for v in vals if v <= fim + 1e-9]


def varredura_dy(
    caso: Caso, base: BaseDados, inicio: float, fim: float, passo: float
) -> list[Resultado]:
    """Resultados do caso variando Δy (demais parâmetros fixos)."""
    p = parametros(caso, base)
    return [calcular(replace(p, delta_y=dy)) for dy in faixa(inicio, fim, passo)]
