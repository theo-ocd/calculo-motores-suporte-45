# Tensionamento para banco duplo

Branch `feature/banco-duplo`, a partir de `feature/interface-web`. Ligado/desligado por
um switch no painel **Projeto** da interface web. Desligado, nada muda nos cálculos.## Modelo (P8–P10 confirmados pelo usuário)

O primeiro centro dos arcos passa a se chamar **O1**, no mesmo padrão de O2.

- **O2**: segundo centro de arcos, **500 mm acima** de O1. É fixo, igual a x_tubo e y_piso
  (`Contexto.dy_banco2`) — P8.
- **Raios do banco 2**: R2_min (0 %) e R2_max (3 %), informados por caso e
  **independentes** do banco 1 — P9.
- **Motor único** (P10, obrigatório): em cada tensão, o centro do motor deve ficar a uma
  distância **≥ R1** de O1 e **≤ R2** de O2 (0 %: R1_min/R2_min; 3 %: R1_max/R2_max).
  Ao longo da chapa, isso define um **trecho** (curso, em mm) entre o arco R1 (ponta alta,
  posição do banco 1) e o arco R2 (ponta baixa).

### Efeito no cálculo (com o switch ligado)

- A **faixa admissível de H** é a interseção da faixa das ranhuras com as alturas em que
  o curso, a 0 % e a 3 %, é ≥ 0.
- A **H recomendada** maximiza a menor folga, agora incluindo o curso como mais uma folga
  (mm ao longo da chapa). Por isso, a "folga mínima" pode ser o curso.
- **Status**: se as ranhuras admitem alguma H e o curso não, o caso fica
  **FORA_TENSIONAMENTO** (amarelo). Precedência: SEM_SOLUCAO > INCOMPATIVEL >
  FORA_RANHURA > FORA_TENSIONAMENTO > OK.

Referência: CH-180, R1 2086/2161 (sem H informada; sem banco duplo, a H recomendada é 1634,32).

| R2_min / R2_max | status | faixa de H | H recomendada | folga mínima |
|---|---|---|---|---|
| 2620 / 2700 | OK | 1606,55–1661,47 | 1634,32 | 28,56 (ranhuras) |
| 2570 / 2650 | OK | 1606,55–1661,47 | 1615,24 | 8,91 (curso a 0 %) |
| 2563 / 2643 | OK | 1606,55–1630,71 | 1607,86 | 1,34 (curso) |
| 2560 / 2640 | FORA_TENSIONAMENTO | — | 1604,70 | −1,90 (curso) |



## Onde está

- Núcleo puro: `src/tensorcad/banco_duplo.py` (`ConfigBancoDuplo`, `curso_minimo`, `resolver`,
  `avaliar`). A restrição entra por `projeto.resolver_caso(..., restricao)`.
- API: `POST /api/calcular` aceita `banco_duplo: {ativo, R2_min, R2_max}` e devolve
  `banco_duplo`: por tensão, dist_O2, folga_R2, d_R1, d_R2, curso e dentro, além dos
  avisos. Em `/api/saude`, o valor sai em `fixos.dy_banco2`.
- Desenho: camada **tensionamento banco duplo**, com o octógono O2, a cota de 500, os arcos R2_min/R2_max,
  os raios O2 → motor (amarelos sem trecho) e o trecho admissível do centro (traço grosso).
- Projeto `.json`: `banco_duplo` (projeto) e `R2_min/R2_max` (por caso), campos
  opcionais. Arquivos antigos continuam abrindo.

- Planilha `.xlsx`: bloco "Tensionamento para banco duplo" na aba do caso, com status e H
  calculados com a restrição. A aba oculta `_entradas` guarda R2_min/R2_max.

## Fora do escopo por enquanto

- Banco duplo na CLI (`caso`, `lote`).
