import shutil
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def data_dir() -> Path:
    return DATA


@pytest.fixture
def copia_data(tmp_path: Path) -> Path:
    destino = tmp_path / "data"
    shutil.copytree(DATA, destino)
    return destino
