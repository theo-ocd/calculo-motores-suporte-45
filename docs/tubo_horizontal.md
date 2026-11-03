# Layout "tubo horizontal": roteiro de desenvolvimento

Branch de integração: `feature/tubo-horizontal`, criada a partir de `feature/interface-web`,
que já tem a W4 e o banco duplo. Cada entrega abaixo vira uma branch `feature/th-<entrega>`
com PR para `feature/tubo-horizontal`. O merge só acontece com CI verde e conferência do
usuário. No final, abre-se um PR de `feature/tubo-horizontal` para a integração.

## Objetivo

Criar uma segunda **opção de layout** no mesmo projeto, com o mesmo padrão de cálculo:

| layout | como o motor se ajusta | medida que controla |
|---|---|---|
| **tubo inclinado 45°** (atual, mantido sem mudanças) | desliza na chapa inclinada | folgas das ranhuras, altura H |
| **tubo horizontal** (novo) | motor fixo na horizontal sobre a chapa; o conjunto sobe/desce em y (barras roscadas) e desloca em x ao longo do tubo | **distância entre porcas** do tubo e da chapa, com 30 < g < 150 mm |

- O usuário escolhe o layout **antes** de começar os cálculos. Cada layout tem sua aba ou
  tela, e o projeto `.json` guarda os dois.
- No tubo horizontal há um switch **motor invertido** (de cabeça para baixo). Ele muda os
  parâmetros (altura ideal, lado da chapa), e só uma das duas posições vale de cada vez.
- O **tensionamento para banco duplo** (O1/O2, R1/R2, motor entre os arcos) funciona
  também no tubo horizontal, com o mesmo switch.

## Leitura dos desenhos enviados (a confirmar na T0)

| cota | motor normal | motor invertido | leitura proposta |
|---|---|---|---|
| altura ideal do tubo | 1375 | 1120 (+170?) | piso (topo da laje) → centro do tubo de sustentação |
| distância entre porcas | 65 | — | folga vertical entre a porca do tubo e a porca da chapa (30–150) |
| piso → centro do motor | 927 | 2242? | — |
| O → centro do motor (y) | 1699 | — | vertical do centro dos raios ao motor |
| linha de centro → motor (x) | (248) | 93 | deslocamento horizontal ao longo do tubo |
| raios | R1839 / R2349 | — | arcos do banco 1 e do banco 2? |
| laje | — | 170 | espessura da laje |

## Entregas

Cada entrega é pequena, tem testes e termina com um comentário no PR (o que foi feito,
testes, pendências) para conferência.

### T0: Definições e dados (só documentação e tabela, sem cálculo)
- Confirmar as cotas da tabela acima e a origem de cada uma (O1, piso, tubo, chapa).
- Definir os graus de liberdade: qual movimento faz o tensionamento de 0 % a 3 % (x, y
  ou os dois) e qual fica fixo no projeto.
- Criar `data/padrao/tubo_horizontal.csv` por carcaça: altura da chapa sobre o tubo,
  altura do centro do motor sobre a chapa (normal e invertido), espessura das porcas e da
  chapa, curso das barras roscadas e limites em x. O que não for conhecido fica TODO + aviso.
- **Conferência:** tabela preenchida para a carcaça 180 e diagrama em LEIAME.

### T1: Seletor de layout no projeto (interface + .json)
- O projeto ganha o campo `layout`: `inclinado_45` (padrão, para arquivos antigos) ou
  `horizontal`. O seletor aparece no início e troca a aba ou tela de entradas.
- O layout 45° não muda: os testes atuais continuam passando sem alteração.
- **Conferência:** abrir um .json antigo (vira 45°), trocar de layout e salvar.

### T2: Núcleo geométrico do tubo horizontal (funções puras)
- Centro do motor em função de (x ao longo do tubo, g entre porcas), da altura do tubo
  e das dimensões da carcaça.
- Para R_min e R_max: posições que tocam os arcos e a faixa de g/x admissível; status
  novo `FORA_PORCAS` quando g sai de 30–150.
- Recomendação: máxima folga mínima, no mesmo padrão do 45°, com g recomendado.
- **Conferência:** caso de referência da carcaça 180 conferido com o desenho (927 / 1699 /
  248 / 65).

### T3: Motor invertido (switch)
- O lado da chapa e a altura ideal mudam; só um modo vale de cada vez.
- **Conferência:** caso invertido conferido com o desenho (1120 / 2242 / 93).

### T4: Tensionamento para banco duplo no tubo horizontal
- Reaproveita O1/O2 e R1/R2: o motor fica a ≥ R1 de O1 e ≤ R2 de O2 a 0 % e 3 %.
- Status `FORA_TENSIONAMENTO` e restrição na recomendação, como no 45°.
- **Conferência:** caso com R1839 / R2349 (se forem os dois bancos).

### T5: Desenho 2D do tubo horizontal
- Camadas: tubo, barras roscadas e porcas com a cota g, chapa, motor (normal ou invertido),
  arcos e O1/O2.
- **Conferência:** prints lado a lado com os desenhos enviados.

### T6: Resultados, planilha e .json
- Painel de resultados próprio (g, x, folgas e status). A aba do caso no `.xlsx` informa o
  layout, e o índice do projeto também.
- **Conferência:** exportar um projeto com casos dos dois layouts.

### T7: Executável e teste ponta a ponta
- Pré-release `exe-dev`, testado no Windows sem Python.
- **Conferência:** .exe enviado no chat.

## Ordem

`T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7`. A T1 pode correr em paralelo à T0, porque não
depende das cotas.
