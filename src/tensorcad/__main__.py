"""Ponto de entrada: python -m tensorcad (e do executável PyInstaller)."""

import contextlib
import sys

from tensorcad.cli import app


def _saida_tolerante() -> None:
    """Em pipes no Windows a codificação é cp1252: caracteres como '→' viram '?' em vez de
    derrubar o programa."""
    for fluxo in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            fluxo.reconfigure(errors="replace")  # type: ignore[union-attr]


if __name__ == "__main__":
    _saida_tolerante()
    app(prog_name="tensorcad")
