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
    largura: NaoNegativo
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
