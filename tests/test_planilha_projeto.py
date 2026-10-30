import os
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.planilha_projeto import (
    ABA_ENTRADAS,
    EntradaPlanilha,
    adicionar_caso,
    ler_entradas,
    montar_entrada,
    nome_aba,
    status_do_caso,
)
from tensorcad.projeto import ConfigProjeto

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = carregar_diretorio(DATA)
PAD = carregar_padroes(DATA / "padrao")
REF = EntradaPlanilha("REF-180", "IEC-180M-4P", 2086, 2161, 1646)
ALT = EntradaPlanilha("ALT-2110", "IEC-180L-4P", 2086, 2110)


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    arq = tmp_path / "proj.xlsx"
    adicionar_caso(arq, REF, BASE, PAD, cfg=ConfigProjeto(nome="TESTE"))
    adicionar_caso(arq, ALT, BASE, PAD)
    return arq


def test_uma_aba_por_caso_e_indice(projeto: Path) -> None:
    wb = load_workbook(projeto)
    assert wb.sheetnames == ["PROJETO", "REF-180", "ALT-2110", ABA_ENTRADAS]
    assert wb[ABA_ENTRADAS].sheet_state == "hidden"
    assert wb["PROJETO"]["A1"].value == "Projeto TESTE"
    assert status_do_caso(projeto, "REF-180") == "FORA_RANHURA"
    assert status_do_caso(projeto, "ALT-2110") == "OK"
    assert wb["PROJETO"]["A10"].hyperlink.location == "'REF-180'!A1"


def test_aba_do_caso_tem_resultado_e_graficos(projeto: Path) -> None:
    ws = load_workbook(projeto)["ALT-2110"]
    valores = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(1, 60)}
    assert valores["status"] == "OK"
    assert valores["H recomendada (máx. folga mínima)"] == pytest.approx(1647.09, abs=0.01)
    assert valores["faixa admissível de H"] == "1632.07 a 1661.96"
    assert valores["chapa"] == "CH-180"
    assert len(ws._charts) == 2


def test_entradas_persistem_e_regeneram(projeto: Path) -> None:
    cfg, ents = ler_entradas(projeto)
    assert cfg.nome == "TESTE" and cfg.y_piso == 767 and cfg.x_tubo == 465
    assert ents == [REF, ALT]


def test_caso_repetido_e_substituicao(projeto: Path) -> None:
    with pytest.raises(ValueError, match="já existe"):
        adicionar_caso(projeto, REF, BASE, PAD)
    novo = EntradaPlanilha("REF-180", "IEC-180M-4P", 2086, 2110)
    adicionar_caso(projeto, novo, BASE, PAD, substituir=True)
    assert load_workbook(projeto).sheetnames == ["PROJETO", "ALT-2110", "REF-180", ABA_ENTRADAS]
    assert status_do_caso(projeto, "REF-180") == "OK"


def test_entrada_invalida_nao_altera_arquivo(projeto: Path) -> None:
    antes = projeto.read_bytes()
    for ruim, msg in (
        (EntradaPlanilha("X", "NADA", 2086, 2161), "não cadastrado"),
        (EntradaPlanilha("X", "IEC-160L-4P", 2086, 2161), "nenhuma chapa padrão"),
        (EntradaPlanilha("X", "IEC-180M-4P", 2161, 2086), "R_min"),
        (EntradaPlanilha("X", "IEC-180M-4P", 2086, 2161, chapa_id="CH-NADA"), "chapa padrão"),
    ):
        with pytest.raises(ValueError, match=msg):
            adicionar_caso(projeto, ruim, BASE, PAD)
    assert projeto.read_bytes() == antes


def test_nome_aba_e_arquivo_estranho(tmp_path: Path) -> None:
    assert nome_aba("A/B:C*D?" + "x" * 40) == ("A_B_C_D_" + "x" * 40)[:31]
    from openpyxl import Workbook

    Workbook().save(tmp_path / "outro.xlsx")
    with pytest.raises(ValueError, match="não é uma planilha de projeto"):
        ler_entradas(tmp_path / "outro.xlsx")
    e = montar_entrada(
        EntradaPlanilha("X", "IEC-180M-4P", 2086, 2161, chapa_id="CH-180"), BASE, PAD
    )
    assert e.chapa.chapa_id == "CH-180"


def test_abre_no_libreoffice(projeto: Path, tmp_path: Path) -> None:
    if shutil.which("soffice") is None:
        if os.environ.get("TENSORCAD_EXIGIR_SOFFICE"):
            pytest.fail("LibreOffice (soffice) exigido mas não encontrado")
        pytest.skip("LibreOffice indisponível")
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path / "pdf"),
            str(projeto),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    assert (tmp_path / "pdf" / "proj.pdf").stat().st_size > 10_000
