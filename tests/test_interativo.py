import re
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook
from typer.testing import CliRunner

from tensorcad import cli, recursos
from tensorcad.cli import app

RAIZ = Path(__file__).resolve().parents[1]
runner = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def sem_abrir(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    abertos: list[Path] = []
    monkeypatch.setattr(cli, "_abrir", abertos.append)
    return abertos


def test_dados_padrao_resolvidos_sem_opcao(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # sem ./data: cai nos dados do pacote/repositório
    assert recursos.dir_dados() == RAIZ / "data"
    assert recursos.dir_padroes() == RAIZ / "data" / "padrao"
    r = runner.invoke(app, ["validar"])
    assert r.exit_code == 0 and "CH-180" in r.output


def test_ordem_de_busca(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "data"
    local.mkdir()
    (local / "motores.csv").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert recursos.dir_dados() == local
    outro = tmp_path / "outro"
    outro.mkdir()
    (outro / "motores.csv").write_text("x", encoding="utf-8")
    monkeypatch.setenv(recursos.VAR_AMBIENTE, str(outro))
    assert recursos.dir_dados() == outro


def test_dados_embutidos_no_executavel(tmp_path: Path, monkeypatch) -> None:
    emb = tmp_path / "meipass" / "data"
    emb.mkdir(parents=True)
    (emb / "motores.csv").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    assert recursos.dir_dados() == emb


def test_sem_dados_erro_claro(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(recursos, "candidatos", lambda: [tmp_path / "nada"])
    with pytest.raises(FileNotFoundError, match="TENSORCAD_DADOS"):
        recursos.dir_dados()
    r = runner.invoke(app, ["validar"])
    assert r.exit_code == 1 and "dados não encontrados" in ANSI.sub("", r.output)


def test_versao() -> None:
    r = runner.invoke(app, ["--versao"])
    assert r.exit_code == 0 and r.output.startswith("tensorcad ")


def test_interativo_sem_argumentos_cria_projeto(tmp_path: Path, monkeypatch, sem_abrir) -> None:
    monkeypatch.chdir(tmp_path)
    respostas = "\n".join(
        [
            "obra.xlsx",  # arquivo
            "OBRA-X",  # nome do projeto
            "REF",  # caso
            "180M",  # carcaça
            "2086",
            "2161",
            "1646",  # cota informada
            "s",  # outro caso
            "ALT",
            "",  # carcaça padrão
            "abc",  # inválido → pergunta de novo
            "2086",
            "2110,0",  # vírgula decimal
            "",  # sem cota
            "n",
            "s",  # abrir
        ]
    )
    r = runner.invoke(app, [], input=respostas + "\n")
    saida = ANSI.sub("", r.output)
    assert r.exit_code == 0, saida
    assert "Carcaças com chapa padrão: 180L, 180M" in saida
    assert "Caso REF: FORA_RANHURA" in saida and "Caso ALT: OK" in saida
    assert "número inválido" in saida
    wb = load_workbook(tmp_path / "obra.xlsx")
    assert wb.sheetnames[:3] == ["PROJETO", "REF", "ALT"]
    assert wb["PROJETO"]["A1"].value == "Projeto OBRA-X"
    assert sem_abrir == [Path("obra.xlsx")]


def test_interativo_projeto_existente_e_erro(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    entrada = "p\nP1\nA\n180M\n2086\n2110\n\ntalvez\nn\nn\n"
    r1 = runner.invoke(app, ["interativo"], input=entrada)
    assert r1.exit_code == 0 and (tmp_path / "p.xlsx").exists()
    assert "responda s ou n" in r1.output
    r2 = runner.invoke(
        app, ["interativo"], input="p.xlsx\nA\n180M\n2086\n2110\n\ns\nB\n999\n2086\n2110\n\nn\nn\n"
    )
    saida = ANSI.sub("", r2.output)
    assert "Projeto existente 'P1' com 1 caso(s)" in saida
    assert "já existe" in saida and "999" in saida


def test_main_saida_tolerante(monkeypatch) -> None:
    import io

    from tensorcad import __main__ as entrada

    buf = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", buf)
    monkeypatch.setattr(sys, "stderr", object())  # sem reconfigure: ignorado
    entrada._saida_tolerante()
    print("Caso X: OK → arquivo")  # '→' não existe em cp1252
    buf.flush()
    assert buf.buffer.getvalue().decode("cp1252") == "Caso X: OK ? arquivo\n"
