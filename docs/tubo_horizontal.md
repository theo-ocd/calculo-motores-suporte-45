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
| altura do tubo | `altura_tubo`: topo da laje → **ponto mais baixo** do tubo de sustentação. Funciona como o H do 45°: **entrada opcional** (verificar um valor, ex.: 1375) e o cálculo devolve a **faixa admissível** e a **altura recomendada** (máxima folga mínima). Mesmo ponto de referência no motor normal e no invertido |
| tubo | `espessura_tubo` = 80 (só neste caso) |
| pilha até o centro do motor | tubo (topo, ou fundo se invertido) + 2 porcas de 27,5 + **g** + chapa de 15 + **H** do motor |
| H | altura do centro do motor sobre a base, no padrão WEG da carcaça (250M → 250) |
| g | distância entre porcas, com **30 < g < 150**: é o ajuste em **y** |
| x | deslocamento do conjunto (motor + chapa) ao longo do tubo: é o ajuste em **x** |
| curso em x | `comprimento_tubo / 2`, informado no projeto |
| interferência | furação da chapa = furação do motor (A) + 75 |
| tensionamento | **x e y** ajustam juntos (0 % → 3 %); para cada R existe um trecho do arco que atende g e x |
| motor invertido | switch: a pilha vai para baixo a partir do fundo do tubo, e a altura recomendada muda |
| banco duplo | igual ao 45°: neste caso, R1839 é o banco 1 (O1) e R2349 é o banco 2 (O2) |

Centro do motor, medido para baixo a partir do topo da laje:

    normal:    y_motor = altura_tubo − espessura_tubo − 2·27,5 − g − 15 − H
    invertido: y_motor = altura_tubo + 2·27,5 + g + 15 + H

Limites em x, medido da linha de centro (P18): a chapa ocupa A + 75, centrada no motor, e
precisa ficar dentro do curso do tubo, ou seja, |x| + (A + 75)/2 ≤ comprimento_tubo / 2.

### Conferência com os desenhos

| verificação | desenho | calculado | nota |
|---|---|---|---|
| O1 → topo da laje | 1699 − 927 = 772 | 767 (fixo) | diferença de 5 |
| centro do motor abaixo da laje, g = 65, H = 250 (carcaça 250) | 927 | **910** | o desenho tem a chapa 15 mm alta (deveria estar 15 mais baixa): vale o cálculo (P16) |
| raio a 0 %: √((465+248)² + 1699²) | R1839 | 1842,5 | ok (diferença de 3,5) |
| invertido: centro abaixo da laje (2242 − 767) | 1475 | — | carcaça 180: o fundo da chapa fica 170 + 1120 = 1290 abaixo da laje, centro 185 abaixo da chapa (H = 180, diferença de 5) |
| invertido: raio √((465+93)² + 2242²) | — | 2310,4 | — |

## Entregas

Cada entrega é pequena, tem testes e termina com um comentário no PR (o que foi feito,
testes, pendências) para conferência.

### T0: Definições e dados (só documentação e tabela, sem cálculo) — esta entrega
- Definições acima, a partir das respostas do usuário.
- `data/padrao/tubo_horizontal.csv`: parâmetros do layout (tubo, porcas, chapa, limites de
  g, acréscimo da furação). Os dados por carcaça (H, A) vêm do catálogo WEG de motores.
- Diagrama da pilha em `data/padrao/LEIAME.md`.
- **Conferência:** tabela de conferência acima. P16–P18 respondidas.

### T1: Seletor de layout no projeto (interface + .json) — feita
- O projeto ganha o campo `layout`: `inclinado_45` (padrão, para arquivos antigos) ou
  `horizontal`. O seletor fica no topo do painel Projeto.
- Cada layout tem a **sua lista de casos**, e trocar de layout não apaga nada. O tubo
  horizontal tem campos próprios: altura do tubo (opcional), comprimento do tubo e o
  switch de motor invertido. Os campos só do 45° (H do apoio, dimensões da chapa) ficam
  ocultos.
- `.json`: `layout` e o bloco `horizontal` (`altura_tubo`, `comprimento_tubo`, `invertido`,
  `casos`) são opcionais. Os casos do 45° continuam na raiz do arquivo, como antes.
- O cálculo, o desenho e a exportação do tubo horizontal ainda não existem: a tela avisa
  "T2", e o .xlsx segue só com os casos do 45° até a T6.
- **Conferência:** abrir um .json antigo (vira 45°), trocar de layout e salvar.
- Pendente para a T2: no tubo horizontal, a lista de carcaças deve depender só do catálogo
  de motores, e não das chapas do 45°. Hoje a 250 aparece como "a preencher" por falta da
  chapa 45°.

### T2: Núcleo geométrico do tubo horizontal (funções puras) — feita
- `src/tensorcad/tubo_horizontal.py`: pilha, y do motor, curso em x, raio, posição
  (g, x) sobre cada arco, faixa admissível e altura recomendada. Os parâmetros vêm de
  `data/padrao/tubo_horizontal.csv` (`loader.carregar_parametros_th`). O comprimento do
  tubo é obrigatório.
- **Posição em cada tensão:** sobre o arco R, escolhe g e x para maximizar a menor folga
  entre g − 30, 150 − g e a sobra em x (|x| + (A + 75)/2 ≤ comprimento/2). O motor fica do
  lado de x ≥ −465, entre O1 e além da linha de centro.
- **Altura do tubo:** a faixa admissível são as alturas em que 0 % e 3 % têm folga ≥ 0. A
  recomendada maximiza a folga mínima. Desempate (suposição P19): como x e g ajustam
  juntos, a folga em g chega a 60 (g = 90) numa faixa larga; nela vale a altura que
  maximiza a menor folga em x, centrando no tubo o curso entre 0 % e 3 %.
- **Status:** `FORA_PORCAS` quando nenhuma altura atende (g ou x fora do curso);
  `INCOMPATIVEL` se a chapa (A + 75) não cabe no tubo; `SEM_SOLUCAO` se o arco não é
  alcançável.
- Motor invertido já entra no núcleo (`invertido=True`: a pilha desce do fundo do tubo).
  A T3 cuida da interface e da conferência.
- Ainda sem interface: a tela do tubo horizontal continua avisando "T2" até a entrega
  de resultados (T6).

Conferência (carcaça 250M: H 250, A 406; tubo de 2000; R 1839 / 1894, sendo 1894 um valor
de teste para 3 %):

| item | valor |
|---|---|
| pilha (tubo 80 + 2×27,5 + chapa 15 + H 250) | 400 |
| centro do motor com altura 1375 e g = 65 | 910 abaixo da laje |
| curso em x: 1000 − (406 + 75)/2 | ±759,5 |
| faixa admissível da altura do tubo | 1107,93 – 1622,00 |
| altura recomendada / folga mínima | 1527,49 / 60 (g = 90 a 0 % e 3 %, x = ∓110,38) |
| altura 1375 informada | OK: g = 90, x = 342,97 (0 %) e 461,35 (3 %) |

### T3: Motor invertido (switch)
- A pilha vai para baixo a partir do fundo do tubo e a altura recomendada muda; só um
  modo vale de cada vez.
- **Conferência:** carcaça 180 invertida conferida com o desenho (1120 / 2242 / 93).

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
