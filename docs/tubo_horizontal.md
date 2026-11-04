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
| altura do tubo | `altura_tubo`: topo da laje → **topo** do tubo de sustentação com o motor normal, ou → **fundo** do tubo com o motor invertido (ajuste após a 0.6.37). Funciona como o H do 45°: **entrada opcional** (verificar um valor, ex.: 1375) e o cálculo devolve a **faixa admissível** e a **altura recomendada** (máxima folga mínima). No desenho de referência, 1375 até o fundo equivale a 1295 até o topo |
| tubo | `espessura_tubo` = 80 (só neste caso) |
| pilha até o centro do motor | face do tubo (topo no normal, fundo no invertido) + 2 porcas de 27,5 + **g** + chapa de 15 + **H** do motor |
| H | altura do centro do motor sobre a base, no padrão WEG da carcaça (250M → 250) |
| g | distância entre porcas, com **30 < g < 150**: é o ajuste em **y** |
| x | deslocamento do conjunto (motor + chapa) ao longo do tubo: é o ajuste em **x** |
| curso em x | `comprimento_tubo / 2`, informado no projeto |
| interferência | furação da chapa = furação do motor (A) + 75 |
| tensionamento | **x e y** ajustam juntos (0 % → 3 %); para cada R existe um trecho do arco que atende g e x |
| motor invertido | switch: a pilha vai para baixo a partir do fundo do tubo, e a altura recomendada muda |
| banco duplo | igual ao 45°: neste caso, R1839 é o banco 1 (O1) e R2349 é o banco 2 (O2) |

Centro do motor, medido para baixo a partir do topo da laje:

    normal:    y_motor = altura_tubo − 2·27,5 − g − 15 − H      (altura até o topo do tubo)
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
- **Curso em x:** 0 ≤ x ≤ x_max = comprimento/2 − (A + 75)/2, medido da linha de centro.
  O motor **nunca troca de lado**: x ≥ 0, sempre afastado de O1 (P19, usuário).
- **Posição em cada tensão:** sobre o arco R, escolhe g e x que maximizam a menor
  **folga relativa**, em que cada folga é dividida pela metade do seu curso: g − 30 e
  150 − g por 60, x e x_max − x por x_max/2.
- **Altura do tubo:** a faixa admissível são as alturas em que 0 % e 3 % têm folgas ≥ 0.
  A recomendada maximiza a menor folga relativa. Assim a passagem de 0 % a 3 % se divide
  entre g e x na proporção dos cursos, e não fica só em x (P19, usuário).
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
| pilha (2×27,5 + chapa 15 + H 250, a partir do topo do tubo) | 320 |
| centro do motor com altura 1295 (topo; 1375 até o fundo) e g = 65 | 910 abaixo da laje |
| curso em x (0 a x_max) | 0 – 759,5 |
| faixa admissível da altura do tubo | 1027,93 – 1482,24 |
| altura recomendada / menor folga em mm | **1306,96** / 52,68 |
| na recomendada, 0 % → 3 % | g 97,32 → 82,68, x 333,41 → 426,09 (g e x simétricos nos seus cursos) |
| altura 1295 informada | OK: g 94,40 → 79,97, x 351,90 → 443,23 |

### T3: Motor invertido (switch) — feita
- Switch por projeto (`horizontal.invertido` no .json, desde a T1); só um modo vale de
  cada vez. Núcleo: `ParametrosTH(invertido=True)`.
- Pilha invertida, descendo do **fundo** do tubo (o mesmo ponto de referência da altura):
  `y_motor = altura_tubo + 2·27,5 + g + 15 + H`. A espessura do tubo não entra.
- Com o mesmo raio, o centro do motor recomendado é o mesmo do motor normal; muda a
  altura do tubo. Exemplo 180L, tubo de 2000, R 2310,4 / 2379,7: recomendada **1067,28**
  invertido × 1747,28 normal.
- Tensionar (0 % → 3 %): no normal **g diminui**, porque o motor desce afastando-se de
  O1; no invertido **g aumenta**, e o motor também desce.
- Interface: dica no switch explicando os dois modos. O cálculo na tela entra na T6.

Conferência com o desenho do invertido (carcaça 180, H 180):

| item | desenho | calculado |
|---|---|---|
| centro do motor abaixo da laje | 2242 − 767 = 1475 | 1470, com o fundo da chapa a 170 + 1120 = 1290 (Δ 5) |
| raio a O1 com x = 93 | — | √(558² + 2242²) = 2310,4 |
| altura do tubo + g | — | 1290 − 55 − 15 = 1220 (ex.: 1155 + 65) |

### T4: Tensionamento para banco duplo no tubo horizontal — feita
- Mesmas regras do 45°: O2 fica 540 acima de O1, e R2_min e R2_max são entradas por
  caso, independentes de R1. Em cada tensão, o motor fica sobre o arco R1 (distância a O1
  = R1) e precisa ficar a **≤ R2 de O2**. É obrigatório.
- Núcleo: `EntradaTH(banco2=ConfigBancoDuplo(...))`. A condição entra na escolha de (g, x)
  e da altura recomendada como restrição: a folga positiva não muda nada e só a falta
  pesa. Cada posição informa R2, |C − O2| e folga_R2.
- Status `FORA_TENSIONAMENTO` quando g e x admitem alguma altura, mas nenhuma atende R2.
- O tubo horizontal usa o mesmo switch e os mesmos campos R2 da interface. O cálculo na
  tela entra na T6.

Conferência (250M, tubo de 2000, R1 1839 / 1894):

| R2_min / R2_max | status | faixa de altura | altura recomendada | folga_R2 0 % / 3 % |
|---|---|---|---|---|
| sem banco duplo | OK | 1027,93 – 1482,24 | 1306,96 | — |
| 2400 / 2470 | OK | 1027,93 – 1482,24 | 1306,96 | 62,76 / 85,92 |
| 2349 / 2420 (R2349 do desenho) | OK | 1027,93 – 1410,67 | 1306,96 | 11,76 / 35,92 |
| 2300 / 2380 | OK | 1027,93 – 1199,74 | 1173,43 | 0,00 / 20,02 |
| 2240 / 2300 | FORA_TENSIONAMENTO | — | 969,14 | −12,56 / −13,85 |

(valores com O2 a 540 e a altura até o topo do tubo, após o teste da 0.6.37)

### T5: Desenho 2D do tubo horizontal — feita
- `src/tensorcad/desenho_th.py` (puro), no mesmo formato de primitivas do 45°. Vista do
  CAD com origem em O1; linha de centro em X = 465 e topo da laje em Y = −767.
- Camadas:
  - construção: O1, arcos R_min/R_max, raios e linha de centro;
  - tensionamento banco duplo: O2, cota de 540, arcos R2 e raios de O2;
  - estrutura: laje e tubo (comprimento × espessura);
  - chapa: porcas do tubo e da chapa, barras roscadas a ±(A + 75)/2 e chapa de 15;
  - motor: 0 % e 3 %, normal ou invertido;
  - cotas: 465, 767, altura do tubo, g e x.
- API `POST /api/calcular_horizontal`. O desenho aparece na tela do tubo horizontal com
  status, faixa admissível, altura recomendada, folga mínima e curso em x. O painel
  completo (g e x por tensão) e o .xlsx ficam para a T6.
- A lista de carcaças no tubo horizontal passa a depender só do catálogo de motores (a 250
  fica calculável) e continua dependendo da chapa no 45°.
- **Conferência:** prints (normal 250M, invertido 180L, banco duplo R2349) no PR.

### T6: Resultados, planilha e .json — feita
- Painel do tubo horizontal: status, faixa admissível, altura recomendada, folga mínima
  (recomendada e informada) e curso em x. Tabela de posições (recomendada e informada,
  0 % e 3 %) com g, x e as folgas em g, em x e até o arco R2.
- A lista de casos atualiza o status dos outros casos do horizontal.
- `.xlsx` com os **dois layouts** no mesmo arquivo:
  - aba por caso do horizontal: entradas, pilha e limites, banco duplo, resultado e
    posições;
  - tabela "Layout tubo horizontal" no índice PROJETO;
  - aba oculta `_entradas_horizontal`, preservada pelo `adicionar_caso` da CLI.
- Casos sem R_min e R_max ficam fora da exportação, nos dois layouts. Nome de caso
  repetido entre layouts é recusado.
- **Conferência:** exportar um projeto com casos dos dois layouts. Depois do merge sai a
  pré-release `0.6.<PR>` para teste, antes do tutorial (T8).

### Ajustes após o teste da pré-release 0.6.37 — feitos
- **O1 → O2 = 540 mm** nos dois layouts (era 500).
- **Motor normal:** a altura do tubo vai da laje até o **topo** do tubo, então a espessura do
  tubo sai da pilha. Com o motor invertido continua até o fundo do tubo.
- **`.xlsx` do tubo horizontal com gráficos**, como no 45°:
  - folga mínima (g, x e R2) × altura do tubo, em 0 % e 3 %;
  - esboço da vista (laje, tubo, chapas, motores, arcos R1/R2, raios, O1 e O2).

### Ajuste manual de g com a altura do tubo fixa — feito
- Com a **altura do tubo informada**, o g de cada tensão (0 % e 3 %) pode ser ajustado à
  mão: botões − / + de 1 em 1 mm, valor digitado ou "auto" para voltar ao calculado. O
  motor anda sobre o arco da tensão e o x sai do arco, com os mesmos limites e status
  (g 30–150, x no curso, banco duplo).
- Clicar na cota g do desenho leva ao campo de g de 0 %.
- O ajuste fica no caso (`g_manual` no .json) e vai para o .xlsx (linhas "informada" e o
  campo "g manual" nas entradas). Não muda a altura recomendada nem a faixa admissível.
- Núcleo: `tubo_horizontal.posicao_em_g` e `EntradaTH.g_manual`.

### T7: Release da versão executável 1.0
- Teste ponta a ponta do .exe no Windows sem Python, com os dois layouts.
- **Release `v1.0`** (não pré-release): tag `v1.0`, com o `tensorcad.exe` e um
  **`LEIA-ME.md`** para ficar ao lado do executável. O LEIA-ME traz:
  - o que a ferramenta faz e os requisitos (Windows, sem instalação);
  - o passo a passo: abrir o .exe, escolher a opção de layout, preencher o projeto e os
    casos, ler os resultados, salvar e abrir o .json, exportar o .xlsx e limpar a memória;
  - as saídas: status (OK / FORA_RANHURA / FORA_PORCAS / FORA_TENSIONAMENTO /
    SEM_SOLUCAO / INCOMPATIVEL), faixa admissível, altura recomendada, folgas, desenho e
    planilha (abas e colunas);
  - onde ficam os dados (tabelas) e como avisar problemas.
- **Conferência:** .exe e LEIA-ME enviados no chat; release publicada.

### T8: Botão de tutorial interativo — feita
- Botão **tutorial** na barra superior, nas duas abas. Abre um passo a passo por cima da
  página: retângulo de destaque, legenda com título e explicação, botões anterior /
  próximo (concluir) / sair, ← → para navegar e Esc para sair.
- **Só ilustrativo** (pedido do usuário): `tutorial.js` é isolado.
  - Não chama funções do programa nem a API, e não altera dados.
  - A camada bloqueia cliques, rolagem e teclas na página enquanto está aberta.
  - O único efeito é mostrar a tela da etapa (Setups ou Layout) e voltar à aba original
    ao sair.
- 16 etapas (aba Setups, layout, projeto, banco duplo, casos, setups, caso ativo,
  dimensões, desenho, resultado, posições, salvar e exportar). As etapas de elementos
  ocultos são puladas (ex.: campos do outro layout).
- Teste de navegador: percorre todas as etapas e confere que projeto, biblioteca e
  resultado ficam idênticos, que nenhuma chamada à API é feita e que a aba é restaurada.

## Ordem

`T0 → T1 → T2 → T3 → T4 → T5 → T6 → pré-release 0.6.37 → setups (S0–S5) → T8 → T7 (v1.0)`. Decisão do
usuário: o tutorial (T8) entra antes da release 1.0, e as pré-releases para teste levam a
versão `0.<T>.<PR>` (ex.: 0.8.36).
