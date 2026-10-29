import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad.planilha import ABAS, gerar_planilha


@pytest.fixture(scope="module")
def xlsx(tmp_path_factory) -> Path:
    data = Path(__file__).resolve().parents[1] / "data"
    return gerar_planilha(data, tmp_path_factory.mktemp("out") / "tensorcad_base.xlsx")


def test_abre_com_13_abas_na_ordem(xlsx: Path) -> None:
    wb = load_workbook(xlsx)
    assert wb.sheetnames == list(ABAS)
    assert len(ABAS) == 13
    for nome in ABAS:
        if nome not in ("LEIAME", "calculadora"):
            assert nome in wb[nome].tables, nome
            assert wb[nome].freeze_panes == "A2"


def test_resultados_e_formatos(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["resultados"]
    cab = [c.value for c in ws[1]]
    linhas = {
        r[0]: dict(zip(cab, r, strict=True)) for r in ws.iter_rows(min_row=2, values_only=True)
    }
    assert linhas["REF-1"]["s"] == pytest.approx(7.81, abs=0.1)
    assert ws.cell(2, cab.index("s") + 1).number_format == "0.00"
    assert ws.cell(2, cab.index("theta_deg") + 1).number_format == "0.0"
    assert ws.cell(2, cab.index("ds_ddy") + 1).number_format == "0.000"
    assert len(ws.conditional_formatting) >= 1


def test_casos_tem_validacao_de_dados(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["casos"]
    formulas = [dv.formula1 for dv in ws.data_validations.dataValidation]
    assert any("motores!" in f for f in formulas)
    assert any("min" in f for f in formulas)


def test_varredura_tem_grafico(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["varredura_dy"]
    assert ws.tables["varredura_dy"].ref == "A1:G22"  # cabeçalho + 21 pontos (-100..100/10)
    assert len(ws._charts) == 1
    assert ws["A2"].value == -100 and ws["A22"].value == 100


def test_calculadora_tem_formulas_reais(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["calculadora"]
    assert ws["B14"].value.startswith("=IF(")
    assert ws["B1"].value == 2086


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice indisponível")
def test_calculadora_reproduz_ref1(xlsx: Path, tmp_path: Path) -> None:
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--calc",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(tmp_path),
            str(xlsx),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    ws = load_workbook(tmp_path / xlsx.name, data_only=True)["calculadora"]
    assert ws["B14"].value == pytest.approx(7.81, abs=0.1)
    assert ws["B17"].value == pytest.approx(-1.051, abs=0.005)
    assert ws["B18"].value == pytest.approx(0.486, abs=0.005)


def test_testes_referencia_todos_aprovados(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["testes_referencia"]
    aprovados = [r[6] for r in ws.iter_rows(min_row=2, values_only=True)]
    assert len(aprovados) == 27
    assert set(aprovados) == {"SIM"}


def test_varredura_com_limites_das_ranhuras(xlsx: Path) -> None:
    ws = load_workbook(xlsx)["varredura_dy"]
    cab = [c.value for c in ws[1] if c.value]
    assert cab == ["delta_y", "s", "folga_neg", "folga_pos", "status", "s_min", "s_max"]
    assert ws["F2"].value == pytest.approx(-9.0) and ws["G2"].value == pytest.approx(49.0)
    assert "Δy admissível" in ws["I24"].value
