# F6 — especificação

Fonte: definições do usuário em 2026-10-29 (prints do desenho de referência).
Nada aqui foi implementado ainda; as hipóteses marcadas **H** precisam de confirmação.

## 1. Cotas do desenho de referência

| Cota | Significado | Natureza |
|------|-------------|----------|
| 767 | Altura do centro dos raios (O) em relação ao piso do banco de cilindros | Fixa |
| 465 | Distância em x do centro do tubo de apoio (T) até O | Fixa |
| 1646 | Centro do tubo de apoio → piso do banco de cilindros (instalação) | **Saída do projeto**: definida pelos raios/correia (pode ser ~1250 ou outra); oblongos dão ±50 mm de ajuste na obra |
| 45° | Inclinação do conjunto (θ) | Fixa no padrão atual |
| 45 | Distância vertical entre o ponto mais baixo do topo da chapa inclinada (L) e o centro do tubo | Estrutura |
| 635 | Comprimento total da chapa de apoio do motor do desenho | Por carcaça (tabela da empresa) |
| 180 | Altura do centro do motor em relação à chapa → carcaça 180 (WEG) | Por carcaça |
| R_min = 2086 | Entre-centros com tensionamento 0 % | Entrada do caso |
| R_max = 2161 | Entre-centros com tensionamento 3 % | Entrada do caso (não calculado) |

## 2. Referencial (convenções de docs/geometria.md: O na origem, x+ esquerda, y+ baixo)

- Piso do banco de cilindros: y = 767.
- Tubo de apoio: T = (465, 767 + cota_1646) → no desenho T = (465, 2413).
- Guia = **topo da chapa** (h medido da chapa) → para a chapa do desenho, h = 180 = H(180)
  e e_apoio = 0 (**H1**: corrige a hipótese anterior "carcaça 160 + e_apoio 20").
- Δy (cota verde do núcleo) = cota_1646 − 1646 (aumentar 1646 = conjunto desce).

## 3. Verificação de consistência com a calibração atual (a = 548.72, b = 2093.28)

A reta da guia calibrada cruza a altura de L em:

| Hipótese para a cota 45 | y de L | x de L | x(L) − x(T) | chapa (635) em u, origem P |
|---|---|---|---|---|
| **H2: L 45 mm acima do tubo** | 2368 | 823.4 | 358.4 | [−246.5, 388.5] |
| L 45 mm abaixo do tubo | 2458 | 913.4 | 448.4 | [−119.2, 515.8] |

Com o motor 180 (A = 279, K = 15) e as folgas 9/49 em s = 0, as ranhuras ficam em
u_ini(1) = −156 e u_fim(2) = 196. Só a hipótese **H2** mantém as ranhuras dentro da
chapa (na outra, u = −156 cai fora de [−119.2, 515.8]). Adota-se H2 como provável.

Consequência: o ponto P pode ser substituído pela ponta baixa da chapa L, com
coordenadas derivadas da estrutura:

```
a_L = 465 + dx_L          (dx_L = 358.4 calibrado; H3: fixo da estrutura)
b_L = 767 + cota_1646 − 45
u medido a partir de L, ao longo da chapa (cotas dos desenhos de chapa)
```

## 4. Algoritmo proposto para o executável

Entradas por caso: carcaça (160…250), R_min, R_max; projeto: cota_1646 nominal (±50).

1. Carregar a chapa padrão da carcaça (tabela da empresa, a partir dos PDFs): comprimento,
   h (= H + espessura/calço, se houver), posição e largura das ranhuras em relação a L.
2. Para R_min e R_max, calcular a faixa de Δy em que o motor fica dentro das ranhuras
   (`faixa_dy`, já existente).
3. Interseção das duas faixas, limitada a ±50 mm → **faixa admissível da cota 1646**.
4. Recomendar a cota 1646 (**H4**: centro da faixa admissível; alternativa: mais próxima
   do nominal) e mostrar folgas a 0 % e 3 %.
5. Sem interseção → status FORA_RANHURA com o déficit em mm (substitui a tentativa e erro).

Saída: planilha do projeto, **uma aba por caso**, com possibilidade de adicionar casos
individualmente ao mesmo arquivo.

Observação (P4): no desenho de referência, s(R_max) − s(R_min) = 83 mm e o curso das
ranhuras é 58 mm. Nenhuma cota 1646 atende 0 % e 3 % simultaneamente com as ranhuras
calibradas, a menos que a calibração das folgas mude.

## 5. Respostas do usuário (2026-10-29)

- H1 confirmada: motor do desenho é carcaça 180; h medido do topo da chapa (e_apoio = 0).
- H2 confirmada: L está 45 mm acima do centro do tubo.
- H3: dx_L e cota 45 **variam por carcaça/chapa** → passam a ser colunas da chapa padrão
  (`data/padrao/chapas_padrao.csv`); valores da CH-180 a confirmar nos PDFs.
- H4: a cota 1646 é resultado do projeto (definida por R/correia), sem limite de ±50 mm.
  Protótipo: recomenda a cota que **maximiza a menor folga** entre 0 % e 3 % e mostra
  a faixa admissível inteira.
- R_max é dado de entrada.

## 6. Pendências

- PDFs das chapas padrão 160–250: comprimento, dx_L, cota_L_tubo, ranhuras (d a partir
  de L, comprimento e largura), e_apoio/calço.
- Confirmar dx_L = 358.44 da CH-180 (derivado da calibração).
- Critério de recomendação da cota (máxima folga mínima) — validar com o usuário.

## 7. Protótipo (branch feature/prototipo-180)

- `projeto.py`: núcleo puro (referencial pelo tubo, faixa admissível, cota recomendada).
- `planilha_projeto.py`: planilha do projeto (PROJETO + uma aba por caso + _entradas oculta).
- `tensorcad caso|validar|lote` (CLI typer; base do executável PyInstaller).
- Resultado de referência (CH-180, R 2086/2161): inviável; melhor cota 1673.99 com
  déficit de 12.74 mm em cada extremo. Com R_max = 2110 (exemplo): faixa 1632.07–1661.96,
  recomendada 1647.09 (folga mínima 15.67).
