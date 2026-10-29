"""Modelos de dados (pydantic) das tabelas de entrada e saída.

Unidades: mm; ângulos em graus. Campos opcionais vazios no CSV representam valores
ainda desconhecidos (TODO) e geram aviso quando usados.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Positivo = Annotated[float, Field(gt=0)]
NaoNegativo = Annotated[float, Field(ge=0)]
Id = Annotated[str, Field(min_length=1)]


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

    @field_validator("carcacas_compat", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if v is None:
            return ()
        if isinstance(v, str):
            return tuple(t.strip() for t in v.split(",") if t.strip())
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
    u_ini: float
    u_fim: float
    largura: NaoNegativo

    @model_validator(mode="after")
    def _ordem(self) -> Ranhura:
        if not self.u_ini < self.u_fim:
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


class Caso(_Base):
    caso_id: Id
    montagem_id: Id
    motor_id: Id
    transmissao_id: Id
    R_alvo: Positivo | None = None
    delta_y: float = 0.0
    theta_override: Annotated[float, Field(gt=0, lt=90)] | None = None
    e_apoio_override: NaoNegativo | None = None


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
