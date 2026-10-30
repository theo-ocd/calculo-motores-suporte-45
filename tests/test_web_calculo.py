import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tensorcad.loader import carregar_diretorio, carregar_padroes
from tensorcad.projeto import ConfigProjeto, EntradaCaso, resolver_caso
from tensorcad.web import api, servidor

DADOS = Path(__file__).resolve().parents[1] / "data"
CAB = (
    "carcaca;theta_deg;e_apoio;comprimento_chapa;dx_L_tubo;dy_L_tubo;dist_L_ranhura;"
    "comprimento_ranhura;dist_entre_ranhuras;dist_ranhura_topo;largura_ranhura;origem;"
    "observacao\n"
)


@pytest.fixture(scope="module")
def ctx() -> api.Contexto:
    return api.Contexto(
        carregar_diretorio(DADOS),
        carregar_padroes(DADOS / "padrao", estrito=False),
        DADOS,
        DADOS / "padrao",
    )


def test_calcular_igual_ao_nucleo(ctx) -> None:
    r = api.calcular(ctx, {"carcaca": "180", "R_min": 2086, "R_max": 2161, "cota": 1646})
    base = ctx.base
    m = base.motores["IEC-180L-4P"]  # primeiro motor da carcaça (ordem alfabética)
    ch = ctx.padroes.chapa_para("180")
    nucleo = resolver_caso(
        EntradaCaso(
            "caso", m, ch, ctx.padroes.ranhuras_de(ch.chapa_id, m.carcaca), 2086, 2161, 1646
        ),
        ConfigProjeto(),
    )
    assert r["status"] == "OK" == nucleo.status.value
    assert r["cota_recomendada"] == nucleo.cota_recomendada
    assert r["margem_recomendada"] == pytest.approx(28.56, abs=0.01)
    p0 = r["em_informada"][0]
    assert (p0["Cx"], p0["Cy"]) == pytest.approx((681.53, 1971.53), abs=0.01)
    assert (p0["folga_neg"], p0["folga_pos"]) == pytest.approx((16.30, 123.70), abs=0.01)
    assert r["em_informada"][1]["folga_pos"] == pytest.approx(40.64, abs=0.01)
    assert r["motor"]["motor_id"] == "IEC-180L-4P" and r["h"] == 180
    assert r["chapa"]["ranhura1_d_fim"] == 544 and r["chapa"]["ranhura2_d_ini"] == 110


def test_calcular_alt_2110_e_motor_escolhido(ctx) -> None:
    r = api.calcular(
        ctx,
        {"carcaca": "180", "motor_id": "IEC-180M-4P", "R_min": "2086", "R_max": "2110,0"},
    )
    assert r["status"] == "OK" and r["em_informada"] is None
    assert r["faixas_cota"][0] == pytest.approx([1551.88, 1661.47], abs=0.01)
    assert r["cota_recomendada"] == pytest.approx(1607.26, abs=0.01)
    assert r["motor"]["motor_id"] == "IEC-180M-4P"


@pytest.mark.parametrize(
    ("corpo", "esperado"),
    [
        ({}, {"carcaca": "obrigatório", "R_min": "obrigatório", "R_max": "obrigatório"}),
        ({"carcaca": "200", "R_min": 1, "R_max": 2}, {"carcaca": "medidas da chapa a preencher"}),
        ({"carcaca": "315", "R_min": 1, "R_max": 2}, {"carcaca": "fora da faixa"}),
        ({"carcaca": "180", "R_min": 2161, "R_max": 2086}, {"R_max": "maior ou igual"}),
        (
            {"carcaca": "180", "R_min": -1, "R_max": "x"},
            {"R_min": "maior que zero", "R_max": "inválido"},
        ),
        ({"carcaca": "180", "R_min": 1, "R_max": 2, "cota": "nan"}, {"cota": "inválido"}),
        (
            {"carcaca": "180", "motor_id": "IEC-160L-4P", "R_min": 1, "R_max": 2},
            {"motor_id": "não pertence"},
        ),
    ],
)
def test_calcular_valida_campos(ctx, corpo, esperado) -> None:
    with pytest.raises(api.ErroEntrada) as exc:
        api.calcular(ctx, corpo)
    assert set(exc.value.erros) == set(esperado)
    for campo, trecho in esperado.items():
        assert trecho in exc.value.erros[campo]
    with pytest.raises(api.ErroEntrada):
        api.calcular(ctx, [])  # type: ignore[arg-type]


def test_faixa_do_projeto_reduz_opcoes(ctx) -> None:
    estreito = api.Contexto(ctx.base, ctx.padroes, DADOS, DADOS / "padrao", faixa=(170, 200))
    assert [c["carcaca"] for c in api.carcacas(estreito)] == ["180", "200"]
    amplo = api.Contexto(ctx.base, ctx.padroes, DADOS, DADOS / "padrao", faixa=(90, 250))
    assert "90" in [c["carcaca"] for c in api.carcacas(amplo)]
    assert api.saude(estreito)["faixa"] == [170, 200]
    assert api.saude(ctx)["fixos"] == {"y_piso": 767, "x_tubo": 465}


def test_planilha_com_erro_marca_so_a_carcaca(tmp_path: Path) -> None:
    (tmp_path / "chapas_carcaca.csv").write_text(
        CAB
        + "180;45;0;635;358.44;45;192.51;;;90.49;17;CALCULADO;\n"
        + "200;45;0;700;380;45;150;150;100;100;20;MEDIDO;\n"  # não fecha
        + "225;45;0;800;400;45;150;200;150;100;20;MEDIDO;\n"
        + "225;45;0;800;400;45;150;200;150;100;20;MEDIDO;\n",  # duplicada
        encoding="utf-8",
    )
    pad = carregar_padroes(tmp_path, estrito=False)
    assert list(pad.chapas) == ["CH-180"]
    assert set(pad.com_erro) == {"200", "225"}
    c = api.Contexto(carregar_diretorio(DADOS), pad, DADOS, tmp_path)
    lista = {x["carcaca"]: x for x in api.carcacas(c)}
    assert lista["180"]["status"] == api.PARCIAL
    assert lista["200"]["status"] == api.ERRO and "cotas não fecham" in lista["200"]["detalhe"]
    assert lista["225"]["status"] == api.ERRO and "duplicada" in lista["225"]["detalhe"]
    assert api.saude(c)["erros_chapas"] == 2


def test_motor_sem_chapa_e_chapa_sem_motor(tmp_path: Path, ctx) -> None:
    (tmp_path / "chapas_carcaca.csv").write_text(
        CAB + "240;45;0;700;380;45;150;150;150;100;20;MEDIDO;\n", encoding="utf-8"
    )
    c = api.Contexto(ctx.base, carregar_padroes(tmp_path), DADOS, tmp_path)
    lista = {x["carcaca"]: x for x in api.carcacas(c)}
    assert lista["240"]["status"] == api.ERRO and "nenhum motor" in lista["240"]["detalhe"]


def _post(url: str, dados: object, bruto: bytes | None = None) -> tuple[int, dict]:
    corpo = bruto if bruto is not None else json.dumps(dados).encode()
    req = urllib.request.Request(
        url, data=corpo, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_post_calcular_no_servidor(ctx) -> None:
    srv = servidor.iniciar_em_thread(ctx)
    url = servidor.url_de(srv)
    try:
        st, r = _post(url + "api/calcular", {"carcaca": "180", "R_min": 2086, "R_max": 2110})
        assert st == 200 and r["status"] == "OK"
        st, r = _post(url + "api/calcular", {"carcaca": "180"})
        assert st == 400 and set(r["erros"]) == {"R_min", "R_max"}
        st, r = _post(url + "api/calcular", None, bruto=b"{nao json")
        assert st == 400 and r["erro"] == "JSON inválido"
        st, r = _post(url + "api/nada", {})
        assert st == 404
        st, r = _post(url + "api/calcular", None, bruto=b"x" * (servidor.LIMITE_CORPO + 1))
        assert st == 413
    finally:
        srv.shutdown()
        srv.server_close()
