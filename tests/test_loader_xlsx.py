import csv
from pathlib import Path

import pytest
from openpyxl import Workbook

from tensorcad.loader import TABELAS, ErroCarga, analisar, carregar, carregar_diretorio
from tensorcad.planilha import gerar_planilha

DATA = Path(__file__).resolve().parents[1] / "data"


def _xlsx_dos_csv(destino: Path, alterar=None) -> Path:
    """Monta um xlsx simples com uma aba por tabela (valores numéricos como número)."""
    wb = Workbook()
    wb.remove(wb.active)
    for tabela in TABELAS:
        with (DATA / f"{tabela}.csv").open(encoding="utf-8") as f:
            linhas = list(csv.reader(f, delimiter=";"))
        if alterar:
            linhas = alterar(tabela, linhas)
        ws = wb.create_sheet(tabela)
        for linha in linhas:
            ws.append([_num(v) for v in linha])
    wb.save(destino)
    return destino


def _num(v: str):
    try:
        return float(v)
    except ValueError:
        return v or None


def test_xlsx_equivale_aos_csv(tmp_path: Path) -> None:
    a = carregar_diretorio(DATA)
    b = carregar(_xlsx_dos_csv(tmp_path / "base.xlsx"))
    for t in ("motores", "chapas", "transmissoes", "montagens", "casos", "ranhuras"):
        assert getattr(a, t) == getattr(b, t), t


def test_planilha_gerada_relida_como_fonte(tmp_path: Path) -> None:
    xlsx = gerar_planilha(DATA, tmp_path / "tensorcad_base.xlsx")
    assert carregar(xlsx).casos == carregar_diretorio(DATA).casos


def test_casos_de_arquivo_separado(tmp_path: Path) -> None:
    casos = tmp_path / "meus_casos.csv"
    casos.write_text(
        "caso_id;montagem_id;motor_id;transmissao_id;R_alvo;delta_y;theta_override;"
        "e_apoio_override;h_override;descricao\n"
        "X-1;M-REF;IEC-160L-4P;TR-REF;2100;-20;;;;teste\n",
        encoding="utf-8",
    )
    base = carregar(DATA, casos=casos)
    assert list(base.casos) == ["X-1"]
    assert base.casos["X-1"].R_alvo == "2100.0"
    # casos em xlsx (aba 'casos') sobre cadastros em CSV
    xlsx = _xlsx_dos_csv(tmp_path / "casos.xlsx")
    assert len(carregar(DATA, casos=xlsx).casos) == 10


def test_erro_em_xlsx_reporta_linha_da_aba(tmp_path: Path) -> None:
    def quebrar(tabela, linhas):
        if tabela == "casos":
            linhas[3][2] = "MOTOR-INEXISTENTE"  # linha 4 da aba
        return linhas

    _, erros = analisar(_xlsx_dos_csv(tmp_path / "ruim.xlsx", quebrar))
    assert [(e.tabela, e.linha, e.campo) for e in erros] == [("casos", 4, "motor_id")]


def test_aba_ou_fonte_ausente(tmp_path: Path) -> None:
    wb = Workbook()
    wb.active.title = "motores"
    wb.save(tmp_path / "parcial.xlsx")
    _, erros = analisar(tmp_path / "parcial.xlsx")
    assert any("tabela 'chapas' ausente" in str(e) for e in erros)
    with pytest.raises(ErroCarga, match="fonte ausente"):
        carregar(tmp_path / "nao_existe.xlsx")
