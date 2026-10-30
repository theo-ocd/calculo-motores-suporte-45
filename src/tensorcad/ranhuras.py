"""Ranhuras da chapa: folgas, status, calibração, limites de s e de Δy, seleção.

Funções puras (sem I/O). Coordenada u medida ao longo da guia, mesma origem de s
(ponto P da chapa). Ver docs/geometria.md, seção Ranhuras.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from tensorcad import geometry as g
from tensorcad.geometry import Status
from tensorcad.models import Chapa, Montagem, Motor, Origem, Ranhura

EPS = 1e-9


@dataclass(frozen=True)
class AvaliacaoRanhuras:
    status: Status
    folga_neg: float | None = None
    folga_pos: float | None = None
    mensagens: tuple[str, ...] = ()
    # folgas nas pontas internas (fim da ranhura 1, início da ranhura 2), se conhecidas
    folgas_internas: tuple[float, ...] = ()

    @property
    def margem(self) -> float | None:
        """Menor folga (externas e internas); None se não calculadas."""
        if self.folga_neg is None or self.folga_pos is None:
            return None
        return min(self.folga_neg, self.folga_pos, *self.folgas_internas)


def folgas_internas(
    s: float, A: float, K: float, u_fim_1: float, u_ini_2: float
) -> tuple[float, float]:
    """Folgas dos furos nas pontas internas: (fim da ranhura 1, início da ranhura 2)."""
    return u_fim_1 - (s - A / 2 + K / 2), (s + A / 2 - K / 2) - u_ini_2


def folgas(s: float, A: float, K: float, u_ini_1: float, u_fim_2: float) -> tuple[float, float]:
    """(folga_neg, folga_pos) dos furos (u = s ± A/2, diâmetro K) nas ranhuras 1 e 2."""
    folga_neg = (s - A / 2 - K / 2) - u_ini_1
    folga_pos = u_fim_2 - (s + A / 2 + K / 2)
    return folga_neg, folga_pos


def avaliar(
    s: float | None, motor: Motor, chapa: Chapa, ranhuras: Mapping[int, Ranhura]
) -> AvaliacaoRanhuras:
    """Status das ranhuras para o motor na posição s.

    Ordem: carcaça incompatível → INCOMPATIVEL; largura < K → INCOMPATIVEL;
    folga < 0 → FORA_RANHURA. Sem ranhuras cadastradas: OK com aviso (TODO).
    """
    if not chapa.aceita_carcaca(motor.carcaca):
        return AvaliacaoRanhuras(
            Status.INCOMPATIVEL,
            mensagens=(
                f"carcaça {motor.carcaca} fora de carcacas_compat da chapa {chapa.chapa_id}",
            ),
        )
    if 1 not in ranhuras or 2 not in ranhuras:
        return AvaliacaoRanhuras(
            Status.OK,
            mensagens=(
                f"AVISO: ranhuras 1/2 não cadastradas para {chapa.chapa_id}/{motor.carcaca}"
                " (TODO); folgas não verificadas",
            ),
        )
    sem_largura = [n for n in (1, 2) if ranhuras[n].largura is None]
    estreitas = [
        n for n in (1, 2) if ranhuras[n].largura is not None and ranhuras[n].largura < motor.K
    ]
    if estreitas:
        return AvaliacaoRanhuras(
            Status.INCOMPATIVEL,
            mensagens=tuple(
                f"largura da ranhura {n} ({ranhuras[n].largura}) < K ({motor.K})" for n in estreitas
            ),
        )
    if s is None:
        return AvaliacaoRanhuras(Status.SEM_SOLUCAO, mensagens=("sem solução geométrica",))
    fn, fp = folgas(s, motor.A, motor.K, ranhuras[1].u_ini, ranhuras[2].u_fim)
    msgs = []
    if fn < 0:
        msgs.append(f"furo excede o início da ranhura 1 em {-fn:.2f} mm")
    if fp < 0:
        msgs.append(f"furo excede o fim da ranhura 2 em {-fp:.2f} mm")
    internas: tuple[float, ...] = ()
    if ranhuras[1].u_fim is not None and ranhuras[2].u_ini is not None:
        internas = folgas_internas(s, motor.A, motor.K, ranhuras[1].u_fim, ranhuras[2].u_ini)
        for n, f in zip((1, 2), internas, strict=True):
            if f < 0:
                msgs.append(f"furo excede a ponta interna da ranhura {n} em {-f:.2f} mm")
    status = Status.FORA_RANHURA if msgs else Status.OK
    if sem_largura:
        msgs.append("AVISO: largura da ranhura não informada; verificação com K não feita")
    return AvaliacaoRanhuras(status, fn, fp, tuple(msgs), internas)


def calibrar_ranhuras(
    s_ref: float, A: float, K: float, folga_neg: float, folga_pos: float
) -> tuple[float, float]:
    """(u_ini da ranhura 1, u_fim da ranhura 2) que reproduzem as folgas medidas com o
    motor em s_ref. A atribuição de qual folga é 'neg' ou 'pos' é do chamador
    (no desenho de referência, 9 e 49 mm: lado TODO confirmar)."""
    u_ini_1 = s_ref - A / 2 - K / 2 - folga_neg
    u_fim_2 = s_ref + A / 2 + K / 2 + folga_pos
    return u_ini_1, u_fim_2


def ranhuras_calibradas(
    chapa_id: str,
    carcaca: str,
    s_ref: float,
    A: float,
    K: float,
    folga_neg: float,
    folga_pos: float,
    largura: float,
    comprimento: float | None = None,
    origem: Origem = Origem.CALCULADO,
) -> tuple[Ranhura, Ranhura]:
    """Monta as ranhuras 1 e 2 calibradas. As folgas só determinam u_ini(1) e u_fim(2);
    as pontas internas são preenchidas apenas se o comprimento (ao longo de u) for dado."""
    u_ini_1, u_fim_2 = calibrar_ranhuras(s_ref, A, K, folga_neg, folga_pos)
    r1 = Ranhura(
        chapa_id=chapa_id,
        carcaca=carcaca,
        ranhura_n=1,
        u_ini=u_ini_1,
        u_fim=None if comprimento is None else u_ini_1 + comprimento,
        largura=largura,
        origem=origem,
    )
    r2 = Ranhura(
        chapa_id=chapa_id,
        carcaca=carcaca,
        ranhura_n=2,
        u_ini=None if comprimento is None else u_fim_2 - comprimento,
        u_fim=u_fim_2,
        largura=largura,
        origem=origem,
    )
    return r1, r2


def s_admissivel(ranhuras: Mapping[int, Ranhura], motor: Motor) -> tuple[float, float] | None:
    """[s_min, s_max] com todas as folgas ≥ 0 (externas e, se conhecidas, internas).
    None se ranhuras ausentes ou intervalo vazio."""
    if 1 not in ranhuras or 2 not in ranhuras:
        return None
    meio = motor.A / 2 + motor.K / 2
    s_min = ranhuras[1].u_ini + meio
    s_max = ranhuras[2].u_fim - meio
    if ranhuras[1].u_fim is not None and ranhuras[2].u_ini is not None:
        interno = motor.A / 2 - motor.K / 2  # pontas internas, quando conhecidas
        s_max = min(s_max, ranhuras[1].u_fim + interno)
        s_min = max(s_min, ranhuras[2].u_ini - interno)
    if s_min > s_max:
        return None
    return s_min, s_max


def _dy_para_s(
    a: float, b: float, h: float, theta_deg: float, R: float, s_alvo: float
) -> list[float]:
    """Valores de Δy com s(Δy) = s_alvo (ramo da raiz positiva)."""
    Qx, Qy = g.centro_motor(a, b, 0.0, h, theta_deg, s_alvo)  # C com Δy = 0
    disc = R * R - Qx * Qx
    if disc < 0:
        return []
    r = math.sqrt(disc)
    out = []
    for dy in {-Qy + r, -Qy - r}:
        s = g.resolver_s(a, b, dy, h, theta_deg, R)
        if s is not None and math.isclose(s, s_alvo, abs_tol=1e-6 * max(1.0, R)):
            out.append(dy)
    return out


def faixa_dy(
    a: float, b: float, h: float, theta_deg: float, R: float, s_min: float, s_max: float
) -> list[tuple[float, float]]:
    """Intervalos de Δy em que existe solução e s_min ≤ s(Δy) ≤ s_max (solução
    analítica: fronteiras = raízes de s(Δy)=s_lim e limites do domínio |d_perp|≤R)."""
    t = math.radians(theta_deg)
    c = math.cos(t)
    base = (a * math.sin(t) + h) / c - b
    dom = (base - R / c, base + R / c)
    pts = {dom[0], dom[1]}
    for lim in (s_min, s_max):
        pts.update(dy for dy in _dy_para_s(a, b, h, theta_deg, R, lim) if dom[0] <= dy <= dom[1])
    ordenados = sorted(pts)

    def valido(dy: float) -> bool:
        s = g.resolver_s(a, b, dy, h, theta_deg, R)
        return s is not None and s_min - 1e-9 <= s <= s_max + 1e-9

    intervalos: list[tuple[float, float]] = []
    for lo, hi in zip(ordenados, ordenados[1:], strict=False):
        if hi - lo < EPS or not valido((lo + hi) / 2):
            continue
        if intervalos and abs(intervalos[-1][1] - lo) < EPS:
            intervalos[-1] = (intervalos[-1][0], hi)
        else:
            intervalos.append((lo, hi))
    return intervalos


@dataclass(frozen=True)
class OpcaoChapa:
    chapa_id: str
    status: Status
    s: float | None
    avaliacao: AvaliacaoRanhuras = field(repr=False)

    @property
    def margem(self) -> float | None:
        return self.avaliacao.margem


def selecionar_chapas(
    motor: Motor,
    montagem: Montagem,
    chapas: Iterable[Chapa],
    ranhuras: Iterable[Ranhura],
    R: float,
    delta_y: float = 0.0,
) -> list[OpcaoChapa]:
    """Avalia o motor em cada chapa (usando P da montagem) e ordena: status OK
    primeiro, por maior margem mínima de folga (sem folgas calculadas por último
    dentro do grupo); depois as demais."""
    ranhuras = list(ranhuras)
    opcoes = []
    for ch in chapas:
        h = g.calcular_h(motor.H, ch.e_apoio)
        s = g.resolver_s(montagem.a_ref, montagem.b_ref, delta_y, h, ch.theta_deg, R)
        rs = {
            r.ranhura_n: r
            for r in ranhuras
            if (r.chapa_id, r.carcaca) == (ch.chapa_id, motor.carcaca)
        }
        av = avaliar(s, motor, ch, rs)
        if s is None and av.status is Status.OK:
            av = AvaliacaoRanhuras(Status.SEM_SOLUCAO, mensagens=("sem solução geométrica",))
        opcoes.append(OpcaoChapa(ch.chapa_id, av.status, s, av))

    def chave(o: OpcaoChapa) -> tuple[int, int, float]:
        m = o.margem
        return (o.status is not Status.OK, m is None, -(m if m is not None else 0.0))

    return sorted(opcoes, key=chave)


def compativeis(opcoes: Iterable[OpcaoChapa]) -> list[OpcaoChapa]:
    return [o for o in opcoes if o.status is Status.OK]
