# Banco duplo — esboço inicial

Branch `feature/banco-duplo`, a partir de `feature/interface-web`. Ligado/desligado por
um switch no painel **Projeto** da interface web. Desligado, nada muda nos cálculos.

## Modelo (P8–P10 confirmados pelo usuário)

- **O2**: segundo centro de arcos, **500 mm acima** de O. É fixo, igual a x_tubo e y_piso
  (`Contexto.dy_banco2`) — P8.
- **Raios do banco 2**: R2_min (0 %) e R2_max (3 %), informados por caso e
  **independentes** do banco 1 — P9.
- **Motor único**: em cada tensão, o centro do motor deve ficar a uma distância **maior ou
  igual a R1** de O e **menor ou igual a R2** de O2 (0 %: R1_min/R2_min; 3 %:
  R1_max/R2_max) — P10. Ao longo da chapa, isso define um **trecho** (curso) entre o
  arco R1 (ponta alta, posição do banco 1) e o arco R2 (ponta baixa). Sem esse trecho
  (curso < 0), gera **aviso**. O status do caso não muda, nem a H recomendada.

Referência: CH-180, R1 2086/2161, H = 1646. Sobre os arcos R1, as distâncias a O2 são
2563,77 (0 %) e 2636,32 (3 %).

| R2_min / R2_max | curso 0 % / 3 % | resultado |
|---|---|---|
| 2600 / 2680 | 41,57 / 49,67 | motor entre os arcos nas duas tensões |
| 2560 / 2640 | −4,34 / 4,20 | aviso a 0 %: sobre o arco R1 fica 3,77 mm além de R2 |

## Onde está

- Núcleo puro: `src/tensorcad/banco_duplo.py` (`ConfigBancoDuplo`, `avaliar`, `faixa_R2`).
- API: `POST /api/calcular` aceita `banco_duplo: {ativo, R2_min, R2_max}` e devolve
  `banco_duplo`: por tensão, dist_O2, folga_R2, d_R1, d_R2, curso e dentro, além dos
  avisos. Em `/api/saude`, o valor sai em `fixos.dy_banco2`.
- Desenho: camada **banco 2**, com o octógono O2, a cota de 500, os arcos R2_min/R2_max,
  os raios O2 → motor (amarelos sem trecho) e o trecho admissível do centro (traço grosso).
- Projeto `.json`: `banco_duplo` (projeto) e `R2_min/R2_max` (por caso), campos
  opcionais. Arquivos antigos continuam abrindo.

## Fora do esboço (próximos passos, a confirmar)

- Levar o banco 2 para a planilha `.xlsx` (aba do caso e índice).
- Avaliar se a H recomendada e a faixa admissível de H devem considerar o banco 2.
- Verificar o banco 2 também na CLI (`caso`, `lote`).
