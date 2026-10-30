"""Ajustes de dimensões-chave (chapa e motor) sobre os valores padrão.

Compartilhado entre a interface web e a planilha do projeto. Erros vêm como
{"ajustes.<grupo>.<campo>": mensagem} (ou "ajustes.<grupo>" para a soma das cotas).
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import ValidationError

from tensorcad.models import ChapaCarcaca, Motor

# Dimensões-chave editáveis (campo, rótulo, unidade); x do tubo e piso são fixos.
CAMPOS_CHAPA: tuple[tuple[str, str, str], ...] = (
    ("comprimento_chapa", "Comprimento da chapa", "mm"),
    ("dx_L_tubo", "Tubo → ponta baixa (x)", "mm"),
    ("dy_L_tubo", "Tubo → ponta baixa (y)", "mm"),
    ("dist_L_ranhura", "Ponta baixa → ranhura", "mm"),
    ("comprimento_ranhura", "Comprimento das ranhuras", "mm"),
    ("dist_entre_ranhuras", "Vão entre ranhuras", "mm"),
    ("dist_ranhura_topo", "Ranhura → ponta alta", "mm"),
    ("largura_ranhura", "Largura das ranhuras", "mm"),
    ("e_apoio", "Chapa → apoio dos pés", "mm"),
    ("theta_deg", "Inclinação", "°"),
)
CAMPOS_MOTOR: tuple[tuple[str, str, str], ...] = (
    ("H", "Altura de eixo", "mm"),
    ("A", "A — entre furos dos pés", "mm"),
    ("K", "K — diâmetro do furo", "mm"),
)
OPCIONAIS_CHAPA = frozenset({"comprimento_ranhura", "dist_entre_ranhuras", "largura_ranhura"})
ROTULOS = {c: r for c, r, _ in CAMPOS_CHAPA + CAMPOS_MOTOR}

_LIMITES = {
    "greater_than": "deve ser maior que {gt:g}",
    "greater_than_equal": "deve ser maior ou igual a {ge:g}",
    "less_than": "deve ser menor que {lt:g}",
    "less_than_equal": "deve ser menor ou igual a {le:g}",
}


def _numero(valor: Any) -> float | None:
    try:
        x = float(valor.replace(",", ".")) if isinstance(valor, str) else float(valor)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _ler_grupo(
    bruto: Any,
    campos_validos: tuple[tuple[str, str, str], ...],
    grupo: str,
    erros: dict[str, str],
    opcionais: frozenset[str],
) -> dict[str, float | None]:
    if bruto is None:
        return {}
    if not isinstance(bruto, dict):
        erros[f"ajustes.{grupo}"] = "esperado um objeto"
        return {}
    validos = {c for c, _, _ in campos_validos}
    out: dict[str, float | None] = {}
    for campo, valor in bruto.items():
        chave = f"ajustes.{grupo}.{campo}"
        if campo not in validos:
            erros[chave] = "campo não editável"
        elif valor is None or (isinstance(valor, str) and not valor.strip()):
            if campo in opcionais:
                out[campo] = None  # apaga o valor opcional
            else:
                erros[chave] = "obrigatório"
        elif (x := _numero(valor)) is None:
            erros[chave] = "número inválido"
        else:
            out[campo] = x
    return out


def ler(
    bruto: Any, erros: dict[str, str]
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """(ajustes da chapa, ajustes do motor) a partir de {"chapa": {...}, "motor": {...}}."""
    if bruto is None:
        return {}, {}
    if not isinstance(bruto, dict):
        erros["ajustes"] = "esperado um objeto"
        return {}, {}
    return (
        _ler_grupo(bruto.get("chapa"), CAMPOS_CHAPA, "chapa", erros, OPCIONAIS_CHAPA),
        _ler_grupo(bruto.get("motor"), CAMPOS_MOTOR, "motor", erros, frozenset()),
    )


def traduzir(e: Any) -> str:
    """Mensagem de validação do pydantic em português."""
    modelo = _LIMITES.get(e.get("type", ""))
    if modelo:
        try:
            return modelo.format(**e.get("ctx", {}))
        except (KeyError, ValueError):
            pass
    return str(e["msg"]).removeprefix("Value error, ")


def _erros_pydantic(exc: ValidationError, grupo: str) -> dict[str, str]:
    out = {}
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"])
        out[f"ajustes.{grupo}.{loc}" if loc else f"ajustes.{grupo}"] = traduzir(e)
    return out


def aplicar(
    linha: ChapaCarcaca,
    motor: Motor,
    aj_chapa: dict[str, float | None],
    aj_motor: dict[str, float | None],
    erros: dict[str, str],
) -> tuple[ChapaCarcaca, Motor]:
    """Linha da chapa e motor com os ajustes (validados como na tabela)."""
    if aj_chapa:
        try:
            linha = ChapaCarcaca.model_validate({**linha.model_dump(), **aj_chapa})
        except ValidationError as exc:
            erros.update(_erros_pydantic(exc, "chapa"))
    if aj_motor:
        try:
            motor = Motor.model_validate({**motor.model_dump(), **aj_motor})
        except ValidationError as exc:
            erros.update(_erros_pydantic(exc, "motor"))
    return linha, motor


def descrever(aj_chapa: dict[str, Any], aj_motor: dict[str, Any]) -> list[tuple[str, Any]]:
    """Pares (rótulo, valor) dos ajustes, para relatórios."""
    return [(ROTULOS.get(c, c), v) for c, v in {**aj_chapa, **aj_motor}.items()]
