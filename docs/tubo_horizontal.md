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

## Definições (T0, respostas do usuário)

Referencial: origem em **O1** (centro dos raios do banco 1), como no 45°. O topo da laje
fica `y_piso` = 767 abaixo de O1 e a linha de centro fica `x_tubo` = 465 de O1. Esses
valores são fixos, como nas outras vertentes.

| item | definição |
|---|---|
| fixo de projeto | `altura_tubo`: topo da laje → **ponto mais baixo** do tubo de sustentação (1375 no desenho) |
| tubo | `espessura_tubo` = 80 (só neste caso) |
| pilha até o centro do motor | tubo (topo, ou fundo se invertido) + 2 porcas de 27,5 + **g** + chapa de 15 + **H** do motor |
| H | altura do centro do motor sobre a base, no padrão WEG da carcaça (250M → 250) |
| g | distância entre porcas, com **30 < g < 150**: é o ajuste em **y** |
| x | deslocamento do conjunto (motor + chapa) ao longo do tubo: é o ajuste em **x** |
| curso em x | `comprimento_tubo / 2`, informado no projeto |
| interferência | furação da chapa = furação do motor (A) + 75 |
| tensionamento | **x e y** ajustam juntos (0 % → 3 %); para cada R existe um trecho do arco que atende g e x |
| motor invertido | switch: a pilha vai para baixo a partir do fundo do tubo, e a altura ideal muda |
| banco duplo | igual ao 45°: neste caso, R1839 é o banco 1 (O1) e R2349 é o banco 2 (O2) |

Centro do motor (motor normal), medido para baixo a partir do topo da laje:

    y_motor = altura_tubo − espessura_tubo − 2·27,5 − g − 15 − H

### Conferência com os desenhos

| verificação | desenho | calculado | nota |
|---|---|---|---|
| O1 → topo da laje | 1699 − 927 = 772 | 767 (fixo) | diferença de 5 |
| centro do motor abaixo da laje, g = 65, H = 250 | 927 | **910** | diferença de 17 (P16) |
| idem, com H = 225 | 927 | 935 | diferença de 8: o desenho parece ser de uma carcaça 225? |
| raio a 0 %: √((465+248)² + 1699²) | R1839 | 1842,5 | ok (diferença de 3,5) |
| invertido: centro abaixo da laje (2242 − 767) | 1475 | — | o fundo da chapa fica 170 + 1120 = 1290 abaixo da laje: centro 185 abaixo da chapa, perto de H = 180 (P17) |
| invertido: raio √((465+93)² + 2242²) | — | 2310,4 | — |

## Entregas

Cada entrega é pequena, tem testes e termina com um comentário no PR (o que foi feito,
testes, pendências) para conferência.

### T0: Definições e dados (só documentação e tabela, sem cálculo) — esta entrega
- Definições acima, a partir das respostas do usuário.
- `data/padrao/tubo_horizontal.csv`: parâmetros do layout (tubo, porcas, chapa, limites de
  g, acréscimo da furação). Os dados por carcaça (H, A) vêm do catálogo WEG de motores.
- Diagrama da pilha em `data/padrao/LEIAME.md`.
- **Conferência:** tabela de conferência acima e pendências P16–P18.

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
