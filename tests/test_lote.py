import csv
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad import processamento as proc
from tensorcad.loader import carregar_diretorio
from tensorcad.lote import executar_lote, main
from tensorcad.models import COLUNAS_RESULTADO

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def saida(tmp_path_factory):
    return executar_lote(DATA, tmp_path_factory.mktemp("lote"), varredura=(-50, 30, 5))


def test_csv_identico_ao_nucleo(saida) -> None:
    nucleo = {r.caso_id: r for r in proc.calcular_todos(carregar_diretorio(DATA))}
    with saida.csv.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    assert [d["caso_id"] for d in linhas] == list(nucleo)
    for d in linhas:
        r = nucleo[d["caso_id"]]
        for c in COLUNAS_RESULTADO:
            esperado = getattr(r, c)
            if isinstance(esperado, float):
                assert float(d[c]) == esperado, (r.caso_id, c)  # exato, sem tolerância
            else:
                assert d[c] == ("" if esperado is None else str(esperado)), (r.caso_id, c)


def test_xlsx_resultados_e_varredura(saida) -> None:
    wb = load_workbook(saida.xlsx)
    assert wb.sheetnames == ["resultados", "varredura_dy"]
    ws = wb["resultados"]
    assert [c.value for c in ws[1]] == list(COLUNAS_RESULTADO)
    s_xlsx = {r[0]: r[6] for r in ws.iter_rows(min_row=2, values_only=True)}
    # xlsx guarda 15 dígitos significativos (limite do Excel); o CSV é exato
    assert s_xlsx == pytest.approx({r.caso_id: r.s for r in saida.resultados}, rel=1e-12)
    wv = wb["varredura_dy"]
    assert wv.tables["varredura_dy"].ref == "A1:G18"  # -50..30 passo 5 = 17 pontos
    assert wv["A2"].value == -50 and wv["A18"].value == 30
    assert len(wv._charts) == 1


def test_caso_varredura_e_validacoes(tmp_path: Path) -> None:
    out = executar_lote(DATA, tmp_path, caso_varredura="REF-5", varredura=(0, 10, 10))
    ws = load_workbook(out.xlsx)["varredura_dy"]
    assert ws["B2"].value == pytest.approx(24.29, abs=0.01)  # REF-5, Δy=0
    with pytest.raises(ValueError, match="não existe"):
        executar_lote(DATA, tmp_path, caso_varredura="NADA")
    with pytest.raises(ValueError, match="passo"):
        executar_lote(DATA, tmp_path, varredura=(0, 10, 0))


def test_cli_modulo(tmp_path: Path, capsys) -> None:
    main(["--dados", str(DATA), "--saida", str(tmp_path), "--passo", "50"])
    assert "10 caso(s)" in capsys.readouterr().out
    assert (tmp_path / "resultados.csv").exists()


def test_xlsx_abre_no_libreoffice(saida, tmp_path: Path) -> None:
    if shutil.which("soffice") is None:
        if os.environ.get("TENSORCAD_EXIGIR_SOFFICE"):
            pytest.fail("LibreOffice (soffice) exigido mas não encontrado")
        pytest.skip("LibreOffice indisponível")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--calc",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(tmp_path),
            str(saida.xlsx),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    ws = load_workbook(tmp_path / "resultados.xlsx", data_only=True)["resultados"]
    assert ws["G2"].value == pytest.approx(7.8159, abs=1e-3)
