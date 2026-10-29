from pathlib import Path

import pytest

from tensorcad.loader import ErroCarga, carregar_diretorio, relatorio, validar_diretorio
from tensorcad.models import Chapa, Ranhura, Transmissao


def test_carrega_sementes(data_dir: Path) -> None:
    base = carregar_diretorio(data_dir)
    assert len(base.motores) == 14
    assert base.motores["IEC-160M-4P"].H == 160
    assert base.motores["IEC-160M-4P"].AC is None
    assert base.chapas["CH-REF"].theta_deg == 45
    assert base.montagens["M-REF"].a_ref == pytest.approx(548.72)
    assert base.transmissoes["TR-REF"].R_max == 2161
    assert set(base.casos) == {f"REF-{i}" for i in range(1, 6)}
    assert validar_diretorio(data_dir) == []


def _anexar(caminho: Path, linha: str) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def test_fk_invalida_gera_erro_claro(copia_data: Path) -> None:
    _anexar(copia_data / "casos.csv", "REF-X;M-REF;MOTOR-INEXISTENTE;TR-REF;2086;0;;")
    with pytest.raises(ErroCarga) as exc:
        carregar_diretorio(copia_data)
    erros = exc.value.erros
    assert len(erros) == 1
    e = erros[0]
    assert (e.tabela, e.linha, e.campo) == ("casos", 7, "motor_id")
    assert "MOTOR-INEXISTENTE" in str(exc.value)
    assert "não existe em motores.csv" in str(exc.value)


def test_valores_invalidos_reportam_linha_e_campo(copia_data: Path) -> None:
    _anexar(copia_data / "motores.csv", "M-RUIM;X;X;100L;;4;-100;160;;;12;;;;;;;")
    _anexar(copia_data / "ranhuras.csv", "CH-REF;160M;1;50;10;-1")
    _anexar(copia_data / "ranhuras.csv", "CH-INEXISTENTE;160M;2;0;10;20")
    erros = validar_diretorio(copia_data)
    chaves = {(e.tabela, e.linha, e.campo) for e in erros}
    assert ("motores", 16, "H") in chaves
    assert ("ranhuras", 2, "largura") in chaves
    assert ("ranhuras", 3, "chapa_id") in chaves
    rel = relatorio(erros)
    assert "motores.csv linha 16 campo 'H'" in rel


def test_ranhura_u_ini_menor_que_u_fim() -> None:
    with pytest.raises(ValueError, match="u_ini"):
        Ranhura(chapa_id="C", carcaca="160M", ranhura_n=1, u_ini=10, u_fim=5, largura=20)


def test_id_duplicado_e_arquivo_ausente(copia_data: Path) -> None:
    _anexar(copia_data / "chapas.csv", "CH-REF;45;20;;;;160M")
    (copia_data / "transmissoes.csv").unlink()
    erros = validar_diretorio(copia_data)
    msgs = [str(e) for e in erros]
    assert any("id duplicado" in m for m in msgs)
    assert any("arquivo ausente" in m for m in msgs)


def test_transmissao_ordem() -> None:
    with pytest.raises(ValueError):
        Transmissao(transmissao_id="T", R_min=2200, R_max=2100)
    with pytest.raises(ValueError):
        Transmissao(transmissao_id="T", R_min=2000, R_nom=3000, R_max=2100)


def test_compatibilidade_carcaca() -> None:
    ch = Chapa(chapa_id="C", theta_deg=45, e_apoio=20, carcacas_compat="160, 180M")
    assert ch.aceita_carcaca("160M") and ch.aceita_carcaca("160L")
    assert ch.aceita_carcaca("180M") and not ch.aceita_carcaca("180L")
    assert not Chapa(chapa_id="C", theta_deg=45, e_apoio=20).aceita_carcaca("160M")


def test_relatorio_vazio() -> None:
    assert "OK" in relatorio([])
