"""Localização dos dados (cadastros e chapas padrão), inclusive no executável.

Ordem: variável de ambiente TENSORCAD_DADOS → ./data (diretório atual) → dados embutidos
no executável PyInstaller → data/ do repositório (desenvolvimento).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

VAR_AMBIENTE = "TENSORCAD_DADOS"


def _valido(p: Path) -> bool:
    return (p / "motores.csv").is_file()


def candidatos() -> list[Path]:
    out = []
    if os.environ.get(VAR_AMBIENTE):
        out.append(Path(os.environ[VAR_AMBIENTE]))
    out.append(Path.cwd() / "data")
    embutido = getattr(sys, "_MEIPASS", None)
    if embutido:
        out.append(Path(embutido) / "data")
    out.append(Path(__file__).resolve().parents[2] / "data")
    return out


def dir_dados() -> Path:
    """Primeiro diretório de dados válido (com motores.csv)."""
    for p in candidatos():
        if _valido(p):
            return p
    raise FileNotFoundError("dados não encontrados; informe --dados ou defina " + VAR_AMBIENTE)


def dir_padroes(dados: Path | None = None) -> Path:
    return (dados or dir_dados()) / "padrao"
