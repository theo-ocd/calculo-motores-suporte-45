"""Gera o executável do tensorcad com PyInstaller (onefile), embutindo data/.

Uso: python scripts/build_exe.py [--saida dist]
No Windows gera dist/tensorcad.exe; em Linux/macOS, dist/tensorcad.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", default=str(RAIZ / "dist"))
    a = ap.parse_args()
    import PyInstaller.__main__

    trabalho = RAIZ / "build" / "pyinstaller"
    shutil.rmtree(trabalho, ignore_errors=True)
    PyInstaller.__main__.run(
        [
            str(RAIZ / "src" / "tensorcad" / "__main__.py"),
            "--name=tensorcad",
            "--onefile",
            "--console",
            "--noconfirm",
            "--clean",
            f"--distpath={a.saida}",
            f"--workpath={trabalho}",
            f"--specpath={trabalho}",
            f"--paths={RAIZ / 'src'}",
            f"--add-data={RAIZ / 'data'}{os.pathsep}data",
            "--collect-submodules=tensorcad",
            "--collect-data=tensorcad",  # página da interface web (web/static)
            "--exclude-module=ezdxf",
            "--exclude-module=matplotlib",
            "--exclude-module=tkinter",
        ]
    )


if __name__ == "__main__":
    main()
