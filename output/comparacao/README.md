# Comparação da planilha: v1 (sem F3) × v2 (com F3)

Gerado por `python -m tensorcad.planilha` antes e depois de integrar as ranhuras (F3).
Ranhuras de CH-REF: hipótese P2 (folga 9 do lado do centro do arco).

## resultados

| caso | s | folga_neg v1 | folga_neg v2 | folga_pos v1 | folga_pos v2 | status v1 | status v2 |
|---|---:|---:|---:|---:|---:|---|---|
| REF-1 | 7.82 | — | 16.82 | — | 41.18 | OK | OK |
| REF-2 | 90.87 | — | 99.87 | — | -41.87 | OK | FORA_RANHURA |
| REF-3 | -98.96 | — | -89.96 | — | 147.96 | OK | FORA_RANHURA |
| REF-4 | -7.07 | — | 1.93 | — | 56.07 | OK | OK |
| REF-5 | 24.29 | — | 33.29 | — | 24.71 | OK | OK |
| VAR-BASE | 7.82 | — | 16.82 | — | 41.18 | OK | OK |
| VAR-DY-M100 | 111.29 | — | 120.29 | — | -62.29 | OK | FORA_RANHURA |
| VAR-DY-M50 | 59.95 | — | 68.95 | — | -10.95 | OK | FORA_RANHURA |
| VAR-DY-P50 | -45.15 | — | -36.15 | — | 94.15 | OK | FORA_RANHURA |
| VAR-DY-P100 | -98.96 | — | -89.96 | — | 147.96 | OK | FORA_RANHURA |

## testes_referencia (27 linhas)

| | SIM | NAO | N/D |
|---|---:|---:|---:|
| v1 | 14 | 5 | 8 |
| v2 | 27 | 0 | 0 |

## varredura_dy (VAR-BASE, Δy −100…+100 passo 10)

- v1: só s × Δy; folgas e status das ranhuras vazios/OK.
- v2: folgas, status e linhas s_min = −9.00 / s_max = 49.00 no gráfico;
  Δy admissível = [−39.43, 15.96] mm.

## Leitura

- s, Cx, Cy e sensibilidades são idênticos nas duas versões (núcleo inalterado).
- Com as ranhuras, REF-2, REF-3 e as varreduras ±50/±100 saem FORA_RANHURA:
  a ranhura limita s a [−9, 49] mm, mas R2161 exige s = 90.87 mm (≈83 mm além de
  REF-1) — pendência P4.
