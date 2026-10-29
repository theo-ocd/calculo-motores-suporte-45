from pathlib import Path

import pytest
from openpyxl import load_workbook
from typer.testing import CliRunner

from tensorcad import cli
from tensorcad.cli import app

RAIZ = Path(__file__).resolve().parents[1]
DADOS = ["--dados", str(RAIZ / "data"), "--padroes", str(RAIZ / "data" / "padrao")]
runner = CliRunner()


def _caso(projeto: Path, *extra: str):
    return runner.invoke(app, ["caso", "--projeto", str(projeto), "--rmin", "2086", *DADOS, *extra])


def test_help_documentado() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("validar", "caso", "lote"):
        assert cmd in r.output
    r = runner.invoke(app, ["caso", "--help"])
    assert "--rmin" in r.output and "--carcaca" in r.output and "--cota" in r.output


def test_caso_cria_e_adiciona_abas(tmp_path: Path) -> None:
    proj = tmp_path / "p.xlsx"
    r = _caso(
        proj,
        "--id",
        "REF",
        "--rmax",
        "2161",
        "--carcaca",
        "180M",
        "--cota",
        "1646",
        "--nome-projeto",
        "OBRA-1",
    )
    assert r.exit_code == 0, r.output
    assert "Caso REF: FORA_RANHURA" in r.output
    r = _caso(proj, "--id", "ALT", "--rmax", "2110", "--motor", "IEC-180L-4P")
    assert r.exit_code == 0 and "Caso ALT: OK" in r.output
    wb = load_workbook(proj)
    assert wb.sheetnames[:3] == ["PROJETO", "REF", "ALT"]
    assert wb["PROJETO"]["A1"].value == "Projeto OBRA-1"


def test_caso_erros(tmp_path: Path) -> None:
    proj = tmp_path / "p.xlsx"
    r = _caso(proj, "--id", "X", "--rmax", "2161")
    assert r.exit_code != 0 and "exatamente um" in r.output
    r = _caso(proj, "--id", "X", "--rmax", "2161", "--carcaca", "999")
    assert r.exit_code != 0 and "999" in r.output
    r = _caso(proj, "--id", "X", "--rmax", "2161", "--carcaca", "160M")
    assert r.exit_code == 1 and "nenhuma chapa padrão" in r.output
    assert not proj.exists()
    _caso(proj, "--id", "X", "--rmax", "2161", "--carcaca", "180M")
    r = _caso(proj, "--id", "X", "--rmax", "2161", "--carcaca", "180M")
    assert r.exit_code == 1 and "já existe" in r.output
    r = _caso(proj, "--id", "X", "--rmax", "2110", "--carcaca", "180M", "--substituir")
    assert r.exit_code == 0 and "OK" in r.output


def test_caso_cadastro_invalido(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "caso",
            "--projeto",
            str(tmp_path / "p.xlsx"),
            "--id",
            "X",
            "--rmin",
            "2086",
            "--rmax",
            "2161",
            "--carcaca",
            "180M",
            "--dados",
            str(tmp_path),
            "--padroes",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 1 and "ausente" in r.output


def test_abrir_chama_visualizador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    abertos = []
    monkeypatch.setattr(cli, "_abrir", abertos.append)
    _caso(tmp_path / "p.xlsx", "--id", "X", "--rmax", "2110", "--carcaca", "180M", "--abrir")
    assert abertos == [tmp_path / "p.xlsx"]


def test_validar(tmp_path: Path) -> None:
    r = runner.invoke(app, ["validar", *DADOS])
    assert r.exit_code == 0 and "Validação OK" in r.output and "CH-180" in r.output
    r = runner.invoke(app, ["validar", "--dados", str(tmp_path), "--padroes", str(tmp_path)])
    assert r.exit_code == 1


def test_lote(tmp_path: Path) -> None:
    r = runner.invoke(
        app, ["lote", "--dados", str(RAIZ / "data"), "--saida", str(tmp_path), "--passo", "50"]
    )
    assert r.exit_code == 0 and "10 caso(s)" in r.output
