from pathlib import Path

import pytest

from tensorcad.loader import (
    ErroCarga,
    analisar_diretorio,
    carregar_diretorio,
    relatorio,
    validar_diretorio,
)
from tensorcad.models import Caso, Chapa, Origem, Ranhura, Transmissao

TR = Transmissao(transmissao_id="T", R_min=2086, R_max=2161)


def test_carrega_sementes(data_dir: Path) -> None:
    base = carregar_diretorio(data_dir)
    assert len(base.motores) == 14
    m = base.motores["IEC-160L-4P"]
    assert (m.H, m.A, m.K, m.potencia_kw) == (160, 254, 15, 15)
    assert m.AC is None
    ch = base.chapas["CH-REF"]
    assert ch.theta_deg == 45 and ch.origem is Origem.HIPOTESE
    assert ch.carcacas_compat == ("160M", "160L")
    mont = base.montagens["M-REF"]
    assert (mont.a_ref, mont.b_ref) == pytest.approx((548.7208, 2093.2792))
    assert base.transmissoes["TR-REF"].R_max == 2161
    assert len(base.casos) == 10
    assert base.casos["REF-4"].h_override == 150
    assert base.casos["REF-5"].theta_override == 40
    assert base.casos["VAR-DY-M100"].delta_y == -100
    rs = base.ranhuras_de("CH-REF", "160L")
    assert rs[1].u_ini == -143.5 and rs[1].u_fim is None
    assert rs[2].u_fim == 183.5 and rs[2].u_ini is None
    assert validar_diretorio(data_dir) == []


def test_avisos_origem_e_fonte(data_dir: Path) -> None:
    base, erros = analisar_diretorio(data_dir)
    assert erros == []
    txt = [str(a) for a in base.avisos]
    assert all(a.nivel == "AVISO" for a in base.avisos)
    assert any("chapas.csv linha 2" in t and "HIPOTESE" in t and "espessura" in t for t in txt)
    assert sum("ranhuras.csv" in t for t in txt) == 4
    assert not any("montagens.csv" in t for t in txt)  # origem CALCULADO: sem aviso
    assert any("14 motor(es) com fonte=IEC-REF-VALIDAR" in t for t in txt)
    assert "AVISO:" in relatorio(base.avisos)


def test_R_alvo_simbolico_e_numerico() -> None:
    base = dict(caso_id="C", montagem_id="M", motor_id="X", transmissao_id="T", delta_y=0)
    assert Caso(**base, R_alvo="min").R_efetivo(TR) == 2086
    assert Caso(**base, R_alvo=" MAX ").R_efetivo(TR) == 2161
    assert Caso(**base, R_alvo="nom").R_efetivo(TR) is None
    assert Caso(**base, R_alvo="2100.5").R_efetivo(TR) == 2100.5
    for ruim in ("abc", "-5", "0"):
        with pytest.raises(ValueError, match="R_alvo"):
            Caso(**base, R_alvo=ruim)


def _anexar(caminho: Path, linha: str) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def test_fk_invalida_gera_erro_claro(copia_data: Path) -> None:
    _anexar(copia_data / "casos.csv", "REF-X;M-REF;MOTOR-INEXISTENTE;TR-REF;min;0;;;;")
    with pytest.raises(ErroCarga) as exc:
        carregar_diretorio(copia_data)
    erros = exc.value.erros
    assert len(erros) == 1
    e = erros[0]
    assert (e.tabela, e.linha, e.campo) == ("casos", 12, "motor_id")
    assert "MOTOR-INEXISTENTE" in str(exc.value)
    assert "não existe em motores.csv" in str(exc.value)


def test_R_nom_vazio_com_R_alvo_nom_e_erro(copia_data: Path) -> None:
    _anexar(copia_data / "casos.csv", "REF-N;M-REF;IEC-160L-4P;TR-REF;nom;0;;;;")
    erros = validar_diretorio(copia_data)
    assert [(e.linha, e.campo) for e in erros] == [(12, "R_alvo")]
    assert "R_nom vazio" in erros[0].mensagem


def test_valores_invalidos_reportam_linha_e_campo(copia_data: Path) -> None:
    _anexar(copia_data / "motores.csv", "M-RUIM;X;X;100L;;4;-100;160;140;;12;;;;;;;")
    _anexar(copia_data / "ranhuras.csv", "CH-REF;180M;1;50;10;-1;MEDIDO")
    _anexar(copia_data / "ranhuras.csv", "CH-INEXISTENTE;180M;2;0;10;20;MEDIDO")
    _anexar(copia_data / "ranhuras.csv", "CH-REF;200L;1;;10;20;ORIGEM-RUIM")
    erros = validar_diretorio(copia_data)
    chaves = {(e.tabela, e.linha, e.campo) for e in erros}
    assert ("motores", 16, "H") in chaves
    assert ("ranhuras", 6, "largura") in chaves
    assert ("ranhuras", 7, "chapa_id") in chaves
    assert ("ranhuras", 8, "origem") in chaves
    assert "motores.csv linha 16 campo 'H'" in relatorio(erros)


def test_ranhura_coordenadas_condicionais() -> None:
    kw = dict(chapa_id="C", carcaca="160M", largura=20, origem="MEDIDO")
    with pytest.raises(ValueError, match="u_ini"):
        Ranhura(**kw, ranhura_n=1, u_ini=10, u_fim=5)
    with pytest.raises(ValueError, match="ranhura 1 exige u_ini"):
        Ranhura(**kw, ranhura_n=1, u_fim=5)
    with pytest.raises(ValueError, match="ranhura 2 exige u_fim"):
        Ranhura(**kw, ranhura_n=2, u_ini=5)
    assert Ranhura(**kw, ranhura_n=1, u_ini=-10).u_fim is None
    assert Ranhura(**kw, ranhura_n=2, u_fim=10).u_ini is None


def test_id_duplicado_e_arquivo_ausente(copia_data: Path) -> None:
    _anexar(copia_data / "chapas.csv", "CH-REF;45;20;;;;160M;MEDIDO")
    (copia_data / "transmissoes.csv").unlink()
    msgs = [str(e) for e in validar_diretorio(copia_data)]
    assert any("id duplicado" in m for m in msgs)
    assert any("arquivo ausente" in m for m in msgs)


def test_transmissao_ordem() -> None:
    with pytest.raises(ValueError):
        Transmissao(transmissao_id="T", R_min=2200, R_max=2100)
    with pytest.raises(ValueError):
        Transmissao(transmissao_id="T", R_min=2000, R_nom=3000, R_max=2100)


def test_compatibilidade_carcaca() -> None:
    ch = Chapa(
        chapa_id="C", theta_deg=45, e_apoio=20, carcacas_compat="160 | 180M", origem="MEDIDO"
    )
    assert ch.aceita_carcaca("160M") and ch.aceita_carcaca("160L")
    assert ch.aceita_carcaca("180M") and not ch.aceita_carcaca("180L")
    vazia = Chapa(chapa_id="C", theta_deg=45, e_apoio=20, origem="TODO")
    assert not vazia.aceita_carcaca("160M")


def test_relatorio_vazio() -> None:
    assert "OK" in relatorio([])
