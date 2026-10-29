"""Modelos de dados (pydantic) das tabelas de entrada e saída.

Unidades: mm; ângulos em graus. Campos opcionais vazios no CSV representam valores
ainda desconhecidos (TODO) e geram aviso quando usados.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Positivo = Annotated[float, Field(gt=0)]
NaoNegativo = Annotated[float, Field(ge=0)]
Id = Annotated[str, Field(min_length=1)]


class Origem(StrEnum):
    """Procedência de um dado geométrico."""

    MEDIDO = "MEDIDO"
    CALCULADO = "CALCULADO"
    HIPOTESE = "HIPOTESE"
    TODO = "TODO"
    IEC_REF_VALIDAR = "IEC-REF-VALIDAR"


SEP_LISTA = "|"
R_ALVO_SIMBOLICO = ("min", "nom", "max")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class Motor(_Base):
    motor_id: Id
    fabricante: str = ""
    modelo: str = ""
    carcaca: Id
    potencia_kw: Positivo | None = None
    polos: Annotated[int, Field(gt=0)] | None = None
    H: Positivo
    A: Positivo
    B: Positivo | None = None
    C: Positivo | None = None
    K: Positivo
    D_eixo: Positivo | None = None
    E_eixo: Positivo | None = None
    AC: Positivo | None = None
    HD: Positivo | None = None
    L: Positivo | None = None
    massa_kg: Positivo | None = None
    fonte: str = ""


def _carcaca_num(carcaca: str) -> str:
    m = re.match(r"\d+", carcaca)
    return m.group(0) if m else carcaca


class Chapa(_Base):
    chapa_id: Id
    theta_deg: Annotated[float, Field(gt=0, lt=90)]
    e_apoio: NaoNegativo
    espessura: Positivo | None = None
    comprimento: Positivo | None = None
    largura: Positivo | None = None
    carcacas_compat: tuple[str, ...] = ()
    origem: Origem

    @field_validator("carcacas_compat", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if v is None:
            return ()
        if isinstance(v, str):
            return tuple(t.strip() for t in v.split(SEP_LISTA) if t.strip())
        return v

    def aceita_carcaca(self, carcaca: str) -> bool:
        """Carcaça compatível se listada exatamente, ou se o item da lista é só o
        número da carcaça (ex.: "160" aceita "160M" e "160L"). Lista vazia = nenhuma."""
        for tok in self.carcacas_compat:
            if tok == carcaca or (tok.isdigit() and tok == _carcaca_num(carcaca)):
                return True
        return False


class Ranhura(_Base):
    chapa_id: Id
    carcaca: Id
    ranhura_n: Annotated[int, Field(ge=1, le=2)]
    u_ini: float | None = None
    u_fim: float | None = None
    largura: NaoNegativo | None  # obrigatório no CSV; None só para chapas sem largura medida
    origem: Origem

    @model_validator(mode="after")
    def _coordenadas(self) -> Ranhura:
        # obrigatoriedade condicional: a ranhura 1 limita o lado negativo (u_ini) e a
        # ranhura 2 o lado positivo (u_fim); a outra ponta pode ficar vazia (TODO).
        if self.ranhura_n == 1 and self.u_ini is None:
            raise ValueError("ranhura 1 exige u_ini")
        if self.ranhura_n == 2 and self.u_fim is None:
            raise ValueError("ranhura 2 exige u_fim")
        if self.u_ini is not None and self.u_fim is not None and not self.u_ini < self.u_fim:
            raise ValueError(f"u_ini ({self.u_ini}) deve ser menor que u_fim ({self.u_fim})")
        return self


class Transmissao(_Base):
    transmissao_id: Id
    R_min: Positivo
    R_nom: Positivo | None = None
    R_max: Positivo
    descricao: str = ""

    @model_validator(mode="after")
    def _ordem(self) -> Transmissao:
        if self.R_min > self.R_max:
            raise ValueError(f"R_min ({self.R_min}) > R_max ({self.R_max})")
        if self.R_nom is not None and not self.R_min <= self.R_nom <= self.R_max:
            raise ValueError(f"R_nom ({self.R_nom}) fora de [R_min, R_max]")
        return self


class Montagem(_Base):
    montagem_id: Id
    chapa_id: Id
    a_ref: float
    b_ref: float
    X_O_cad: float | None = None
    Y_O_cad: float | None = None
    origem: Origem


class Caso(_Base):
    caso_id: Id
    montagem_id: Id
    motor_id: Id
    transmissao_id: Id
    R_alvo: str
    delta_y: float
    theta_override: Annotated[float, Field(gt=0, lt=90)] | None = None
    e_apoio_override: NaoNegativo | None = None
    h_override: Positivo | None = None
    descricao: str = ""

    @field_validator("R_alvo", mode="before")
    @classmethod
    def _r_alvo(cls, v: object) -> str:
        """'min' | 'nom' | 'max' (da transmissão) ou valor numérico positivo."""
        txt = str(v).strip().lower()
        if txt in R_ALVO_SIMBOLICO:
            return txt
        try:
            num = float(txt)
        except ValueError:
            raise ValueError(f"R_alvo deve ser min|nom|max ou número; recebido '{v}'") from None
        if num <= 0:
            raise ValueError(f"R_alvo deve ser positivo; recebido {num}")
        return repr(num)

    def R_efetivo(self, transmissao: Transmissao) -> float | None:
        """R em mm (None se 'nom' e R_nom vazio)."""
        match self.R_alvo:
            case "min":
                return transmissao.R_min
            case "max":
                return transmissao.R_max
            case "nom":
                return transmissao.R_nom
        return float(self.R_alvo)


class Resultado(_Base):
    caso_id: str
    h: float
    theta_deg: float
    R: float
    l_proj: float | None = None
    d_perp: float | None = None
    s: float | None = None
    Cx: float | None = None
    Cy: float | None = None
    X_cad: float | None = None
    Y_cad: float | None = None
    ds_ddy: float | None = None
    ds_dh: float | None = None
    folga_neg: float | None = None
    folga_pos: float | None = None
    status: str
    mensagem: str = ""


COLUNAS_RESULTADO: tuple[str, ...] = tuple(Resultado.model_fields)


class ChapaPadrao(_Base):
    """Chapa de apoio padronizada, referenciada ao tubo de apoio da estrutura."""

    chapa_id: Id
    carcacas_compat: tuple[str, ...] = ()
    theta_deg: Annotated[float, Field(gt=0, lt=90)]
    e_apoio: NaoNegativo
    comprimento: Positivo
    dx_L: float
    cota_L_tubo: float
    origem: Origem

    _split = field_validator("carcacas_compat", mode="before")(Chapa._split.__func__)

    def como_chapa(self) -> Chapa:
        return Chapa(
            chapa_id=self.chapa_id,
            theta_deg=self.theta_deg,
            e_apoio=self.e_apoio,
            comprimento=self.comprimento,
            carcacas_compat=self.carcacas_compat,
            origem=self.origem,
        )


class RanhuraPadrao(_Base):
    """Ranhura em coordenada d (a partir de L, subindo a chapa)."""

    chapa_id: Id
    ranhura_n: Annotated[int, Field(ge=1, le=2)]
    d_ini: float | None = None
    d_fim: float | None = None
    largura: NaoNegativo | None = None
    origem: Origem

    @model_validator(mode="after")
    def _coordenadas(self) -> RanhuraPadrao:
        if self.ranhura_n == 1 and self.d_fim is None:
            raise ValueError("ranhura 1 (lado do arco) exige d_fim")
        if self.ranhura_n == 2 and self.d_ini is None:
            raise ValueError("ranhura 2 exige d_ini")
        if self.d_ini is not None and self.d_fim is not None and not self.d_ini < self.d_fim:
            raise ValueError(f"d_ini ({self.d_ini}) deve ser menor que d_fim ({self.d_fim})")
        return self

    def como_ranhura(self, carcaca: str) -> Ranhura:
        """Converte para u (direção de s, origem L): u = −d."""
        return Ranhura(
            chapa_id=self.chapa_id,
            carcaca=carcaca,
            ranhura_n=self.ranhura_n,
            u_ini=None if self.d_fim is None else -self.d_fim,
            u_fim=None if self.d_ini is None else -self.d_ini,
            largura=self.largura,
            origem=self.origem,
        )


TOL_CADEIA = 0.5  # mm: tolerância da soma das cotas da chapa


class ChapaCarcaca(_Base):
    """Linha de chapas_carcaca.csv: medidas da chapa padrão de uma carcaça, como nos
    prints (todas ao longo da chapa, a partir da ponta baixa L, exceto dx/dy)."""

    carcaca: Id
    theta_deg: Annotated[float, Field(gt=0, lt=90)]
    e_apoio: NaoNegativo
    comprimento_chapa: Positivo
    dx_L_tubo: float
    dy_L_tubo: float
    dist_L_ranhura: NaoNegativo
    comprimento_ranhura: Positivo | None = None
    dist_entre_ranhuras: NaoNegativo | None = None
    dist_ranhura_topo: NaoNegativo
    largura_ranhura: Positivo | None = None
    origem: Origem
    observacao: str = ""

    @model_validator(mode="after")
    def _cadeia(self) -> ChapaCarcaca:
        livre = self.comprimento_chapa - self.dist_L_ranhura - self.dist_ranhura_topo
        if livre <= 0:
            raise ValueError(
                f"dist_L_ranhura + dist_ranhura_topo ({self.comprimento_chapa - livre:g}) "
                f"≥ comprimento_chapa ({self.comprimento_chapa:g})"
            )
        tam, entre = self.comprimento_ranhura, self.dist_entre_ranhuras
        if tam is not None and entre is not None:
            soma = 2 * tam + entre
            if abs(soma - livre) > TOL_CADEIA:
                raise ValueError(
                    "cotas não fecham: dist_L_ranhura + 2·comprimento_ranhura + "
                    "dist_entre_ranhuras + dist_ranhura_topo = "
                    f"{self.comprimento_chapa - livre + soma:g} ≠ comprimento_chapa "
                    f"{self.comprimento_chapa:g}"
                )
        elif tam is not None and 2 * tam > livre + TOL_CADEIA:
            raise ValueError("2·comprimento_ranhura maior que o trecho entre as pontas")
        elif entre is not None and entre > livre + TOL_CADEIA:
            raise ValueError("dist_entre_ranhuras maior que o trecho entre as pontas")
        return self

    @property
    def chapa_id(self) -> str:
        return f"CH-{self.carcaca}"

    def ranhuras_d(self) -> tuple[tuple[float | None, float], tuple[float, float | None]]:
        """((d_ini, d_fim) da ranhura 1, (d_ini, d_fim) da ranhura 2), d a partir de L.
        Ranhura 2 = mais perto de L; ranhura 1 = lado do centro dos raios. Se só um entre
        comprimento_ranhura e dist_entre_ranhuras for dado, o outro é deduzido."""
        livre = self.comprimento_chapa - self.dist_L_ranhura - self.dist_ranhura_topo
        tam = self.comprimento_ranhura
        if tam is None and self.dist_entre_ranhuras is not None:
            tam = (livre - self.dist_entre_ranhuras) / 2
        d_ini2 = self.dist_L_ranhura
        d_fim1 = self.comprimento_chapa - self.dist_ranhura_topo
        if tam is None:
            return (None, d_fim1), (d_ini2, None)
        return (d_fim1 - tam, d_fim1), (d_ini2, d_ini2 + tam)

    def como_padrao(self) -> tuple[ChapaPadrao, list[RanhuraPadrao]]:
        chapa = ChapaPadrao(
            chapa_id=self.chapa_id,
            carcacas_compat=self.carcaca,
            theta_deg=self.theta_deg,
            e_apoio=self.e_apoio,
            comprimento=self.comprimento_chapa,
            dx_L=self.dx_L_tubo,
            cota_L_tubo=self.dy_L_tubo,
            origem=self.origem,
        )
        (i1, f1), (i2, f2) = self.ranhuras_d()
        ranhuras = [
            RanhuraPadrao(
                chapa_id=self.chapa_id,
                ranhura_n=n,
                d_ini=ini,
                d_fim=fim,
                largura=self.largura_ranhura,
                origem=self.origem,
            )
            for n, ini, fim in ((1, i1, f1), (2, i2, f2))
        ]
        return chapa, ranhuras


CAMPOS_MEDIDAS_CHAPA = (
    "comprimento_chapa",
    "dx_L_tubo",
    "dy_L_tubo",
    "dist_L_ranhura",
    "dist_ranhura_topo",
)
