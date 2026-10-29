import os
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad import processamento as proc
from tensorcad.calculadora import entradas, gerar_calculadora, main
from tensorcad.geometry import calibrar_P
from tensorcad.loader import carregar_diretorio

DATA = Path(__file__).resolve().parents[1] / "data"
MODELO = DATA / "calculadora.csv"
BASE = carregar_diretorio(DATA)


def _exigir_soffice() -> None:
    if shutil.which("soffice") is None:
        if os.environ.get("TENSORCAD_EXIGIR_SOFFICE"):
            pytest.fail("LibreOffice (soffice) exigido mas não encontrado")
        pytest.skip("LibreOffice indisponível")


def _recalcular(arquivos: list[Path], destino: Path) -> None:
    subprocess.run(
        ["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(destino)]
        + [str(a) for a in arquivos],
        check=True,
        capture_output=True,
        timeout=300,
    )


def test_entradas_invertem_calibracao() -> None:
    p = proc.parametros(BASE.casos["REF-3"], BASE)
    e = entradas(p)
    a, b = calibrar_P(e["B2"], e["B3"], e["B4"], e["B5"])
    assert (a, b) == pytest.approx((p.a, p.b))
    assert (e["B1"], e["B6"], e["B7"], e["B8"]) == (p.R, p.h, p.theta_deg, p.delta_y)


def test_aba_unica_com_formulas(tmp_path: Path) -> None:
    ws = load_workbook(gerar_calculadora(tmp_path / "c.xlsx", MODELO))["calculadora"]
    assert ws.parent.sheetnames == ["calculadora"]
    for cel in ("B10", "B12", "B14", "B17"):
        assert str(ws[cel].value).startswith("="), cel
    for funcao in ("SIN(", "COS(", "SQRT(", "RADIANS("):
        assert any(funcao in str(ws[f"B{i}"].value) for i in range(10, 19)), funcao


def test_formulas_reproduzem_nucleo_em_todos_os_casos(tmp_path: Path) -> None:
    _exigir_soffice()
    arquivos = []
    for caso in BASE.casos.values():
        p = proc.parametros(caso, BASE)
        arquivos.append(gerar_calculadora(tmp_path / "in" / f"{caso.caso_id}.xlsx", MODELO, p))
    _recalcular(arquivos, tmp_path / "out")
    for caso in BASE.casos.values():
        r = proc.calcular_caso(caso, BASE)
        ws = load_workbook(tmp_path / "out" / f"{caso.caso_id}.xlsx", data_only=True)["calculadora"]
        calc = [ws[c].value for c in ("B12", "B13", "B14", "B15", "B16", "B17", "B18")]
        nucleo = [r.l_proj, r.d_perp, r.s, r.Cx, r.Cy, r.ds_ddy, r.ds_dh]
        assert calc == pytest.approx(nucleo, abs=1e-6), caso.caso_id


def test_sem_solucao_na_calculadora(tmp_path: Path) -> None:
    _exigir_soffice()
    from dataclasses import replace

    p = replace(proc.parametros(BASE.casos["REF-1"], BASE), R=100.0)
    _recalcular([gerar_calculadora(tmp_path / "x.xlsx", MODELO, p)], tmp_path / "out")
    ws = load_workbook(tmp_path / "out" / "x.xlsx", data_only=True)["calculadora"]
    assert ws["B14"].value == "SEM_SOLUCAO"


def test_cli(tmp_path: Path, capsys) -> None:
    main(["--dados", str(DATA), "--caso", "REF-5", "--saida", str(tmp_path / "c.xlsx")])
    ws = load_workbook(tmp_path / "c.xlsx")["calculadora"]
    assert ws["B7"].value == 40 and "REF-5" in ws["D2"].value
