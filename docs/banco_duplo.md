# Banco duplo — esboço inicial

Branch `feature/banco-duplo`, a partir de `feature/interface-web`. Ligado/desligado por
um switch no painel **Projeto** da interface web. Desligado, nada muda nos cálculos.

## Modelo do esboço

- **O2**: segundo centro de arcos, deslocado **500 mm** na vertical em relação a O.
  Esse valor é fixo, igual a x_tubo e y_piso (`Contexto.dy_banco2`). No esboço, O2 fica
  **acima** de O (pendência P8).
- **Raios do banco 2**: `R2_min = R_min + adicional_R_min` e `R2_max = R_max + adicional_R_max`.
  Os adicionais são informados por caso (pendência P9).
- **Motor único**: a posição continua definida pelo banco 1 (R_min a 0 %, R_max a 3 %) na
  altura H do desenho (a informada ou, se não houver, a recomendada).
- **Verificação**: para cada posição (0 % e 3 %), `R2 = |C − O2|`. O motor deve ficar
  **entre as duas linhas de raio do banco 2**, `R2_min ≤ R2 ≤ R2_max`. Fora delas, gera
  **aviso** com o desvio em mm. O status do caso (S12) não muda (pendência P10).

Referência: CH-180, R 2086/2161, H = 1646. As distâncias a O2 são 2563,77 (0 %) e
2636,32 (3 %): o R2 acompanha o R1 com ~73 mm de curso, contra 75 mm do R1.

| adicional min / max | R2_min–R2_max | resultado |
|---|---|---|
| 470 / 480 | 2556–2641 | motor entre as linhas |
| 500 / 480 | 2586–2641 | aviso: 0 % fica 22,23 mm abaixo de R2_min |

## Onde está

- Núcleo puro: `src/tensorcad/banco_duplo.py` (`ConfigBancoDuplo`, `avaliar`, `faixa_R2`).
- API: `POST /api/calcular` aceita `banco_duplo: {ativo, adicional_R_min, adicional_R_max}`
  e devolve `banco_duplo` (R2_min/max, R2 por posição, desvio, avisos). Em `/api/saude`,
  o valor sai em `fixos.dy_banco2`.
- Desenho: camada **banco 2**, com o octógono O2, a cota de 500, os arcos R2_min/R2_max
  e os raios O2 → motor. O raio fica amarelo quando a posição está fora das linhas.
- Projeto `.json`: `banco_duplo` (projeto) e `adicional_R_min/max` (por caso), campos
  opcionais. Arquivos antigos continuam abrindo.

## Fora do esboço (próximos passos, a confirmar)

- Levar o banco 2 para a planilha `.xlsx` (aba do caso e índice).
- Avaliar se a H recomendada e a faixa admissível de H devem considerar o banco 2.
- Verificar o banco 2 também na CLI (`caso`, `lote`).
