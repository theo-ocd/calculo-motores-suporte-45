# Setups de transmissão: roteiro de desenvolvimento

Branch de integração: `feature/setups`, criada a partir de `feature/tubo-horizontal` depois
dos ajustes do PR #40. Cada entrega vira uma branch `feature/st-<entrega>` com PR para
`feature/setups`. O merge só acontece com CI verde e conferência do usuário. **Qualquer
decisão que afete o código é confirmada com o usuário antes.**

## Objetivo

Uma nova aba da aplicação, **antes da seleção de layout**, que muda a tela por completo e
serve para criar os casos à parte:

- O usuário **pré-nomeia setups**. Em cada setup escolhe: polia da máquina, correia, rpm do
  motor e polia do motor.
- Os **raios de tensionamento** (R_min a 0 %, R_max a 3 %) saem de um cálculo baseado na
  planilha "Belt transmission – Riemenberechnung" e ficam **travados** no caso. O
  **sufixo do caso** também fica travado.
- Ao salvar, o setup fica no **menu lateral** e pode ser aberto depois na aba de edição de
  layout (45° ou tubo horizontal), onde vira um caso. O nome do caso continua editável lá.
- **Criar o caso do zero** continua possível, como hoje.

## Cálculo (planilha anexada pelo usuário)

Distância entre eixos para uma correia de comprimento L (polia da máquina D, polia do
motor d):

    b  = (L − (π/2)·(D + d)) / 4
    a0 = b + √(b² − (D − d)²/8)          tensionamento 0 %  → R_min
    a2 = a0 + L·0,02/2                    tensionamento 2 %  (informativo na planilha)
    a3 = a0 + L·0,03/2                    tensionamento 3 %  → R_max
    rpm da máquina = rpm do motor · d / D

Conferência com a planilha: D 355, d 170, L 5000 → **2085,61 / 2135,61 / 2160,61**
(planilha: 2086 / 2136 / 2161), rpm 1200 → 574,6 (planilha: 575). É exatamente o caso de
referência R 2086 / 2161 usado até aqui. Com L 5500: 2335,83 / 2390,83 / 2418,33.

Valores que aparecem na planilha (a confirmar como listas, S0):
- polia da máquina (Ø Walzen): 355;
- polias do motor: 125, 132, 140, 150, 160, 170, 180, 190, 200, 212, 224, 236, 250, 280;
- correias SPB (SPBX): 5000, 5300, 5500, 6000;
- rpm do motor: 900 e 1200 nos exemplos.

## Entregas

S0 foi feita no PR #43. S1 a S5 foram feitas de uma vez (pedido do usuário), na branch
`feature/st-setups`, para avaliação antes do merge.

### S1: Núcleo do cálculo da correia — feita
- `src/tensorcad/correia.py` (puro): `distancia_eixos(Correia, alongamento)`, `raios`
  (0 % / 2 % / 3 %), `rpm_maquina` e `sufixo` (`-<polia do motor>-<correia>`). Correia
  curta demais para as polias dá erro.
- Conferido com a planilha nas 14 polias × L 5000 e 5500 × 0 %, 2 % e 3 % (84 valores) e
  no rpm a 1200.

### S2: Setup, API e biblioteca — feita
- `GET /api/transmissao`: listas de `data/padrao/transmissao.csv` (polia da máquina 355,
  14 polias do motor, rpm WEG 60 Hz).
- `POST /api/setup`: valida (listas, correia livre > 0 e compatível) e calcula R_min,
  R_info (2 %), R_max, rpm da máquina e sufixo. O banco 2 é opcional (polias e correia;
  mesmo rpm) e dá R2_min / R2_info / R2_max.
- `POST /api/biblioteca`: confere e **recalcula** um arquivo `tensorcad-setups` v1, sem
  nomes repetidos.
- A biblioteca fica no navegador (`tensorcad.setups.v1`, separada do projeto) e pode ser
  salva e aberta como arquivo próprio (`setups.json`). Ao abrir, os setups são **mesclados**:
  os de mesmo nome ou id são substituídos.

### S3: Tela "Setups" — feita
- Abas **Setups | Layout** na barra superior. A aba Setups troca a página inteira:
  - biblioteca à esquerda: novo, duplicar, excluir, salvar e abrir arquivo;
  - formulário no centro: nome, polia da máquina, polia do motor, correia, rpm e switch
    do banco 2;
  - resultado à direita: sufixo, R 0 % / 2 % / 3 %, rpm da máquina e banco 2.
- "salvar setup" recalcula na hora, sem gravar valores antigos se o usuário salvar logo
  após digitar.
- Na aba Layout, a lista **Setups (biblioteca)** fica no painel lateral, cada setup com
  o botão **"+ caso"**.

### S4: Casos a partir de setups — feita
- "+ caso" cria um caso no layout ativo (45° ou tubo horizontal):
  - o nome é `<nome do setup><sufixo>` (com `-2`, `-3`… se repetir);
  - **R_min / R_max travados** (somente leitura), e R2 também, se o setup tiver banco 2;
  - o **sufixo travado** aparece ao lado do nome, e só a parte antes dele é editável;
  - o caso marca ⚙ na lista e mostra o setup de origem.
- O caso guarda uma **cópia** do setup (`setup` no .json). Se o setup da biblioteca mudar,
  o caso **fica como estava** e mostra um aviso. O botão **"atualizar do setup"** copia os
  dados novos (R e sufixo). Se o setup não estiver na biblioteca deste navegador, também
  há aviso.
- "duplicar" um caso de setup mantém o sufixo no fim. "+ novo caso" do zero continua igual.

### S5: Saídas — feita
- `.xlsx`: bloco **"Setup de transmissão"** na aba do caso (nome + sufixo, polias,
  correia, rpm do motor e da máquina, R 0 / 2 / 3 % e banco 2), nos dois layouts.
- Tabela **"Setups de transmissão"** no índice PROJETO, com os casos de cada setup.
- `_entradas` e `_entradas_horizontal` guardam o setup. A exportação recalcula o setup
  gravado e aponta erro no caso se ele for inválido.

### Decisões de implementação (para conferência)
- Aba inicial ao abrir o programa: **Layout**, como antes. A aba Setups vem primeiro na
  barra.
- Os R travados ficam arredondados a 0,01 mm no caso (o cálculo usa o valor completo do
  setup).
- Excluir um setup da biblioteca não mexe nos casos já criados; eles mostram o aviso.
- O switch de banco duplo continua sendo do projeto. Se o setup tem banco 2, o R2 do caso
  vem travado do setup, mas só entra no cálculo com o switch ligado.

Depois: **T8** (tutorial, incluindo a aba Setups) e **T7** (release 1.0 com LEIA-ME).

## Definições (S0, respostas do usuário)

| item | definição |
|---|---|
| polia da máquina | só **355** por enquanto (lista em `data/padrao/transmissao.csv`) |
| polia do motor | lista das **14** da planilha: 125, 132, 140, 150, 160, 170, 180, 190, 200, 212, 224, 236, 250, 280 |
| correia (comprimento L) | **entrada livre** (mm) |
| rpm do motor | **lista padrão WEG**. Proposta: 60 Hz síncrono, II/IV/VI/VIII polos = 3600 / 1800 / 1200 / 900 (a planilha usa 900 e 1200). Confirmar se é síncrono ou nominal e se entra 50 Hz |
| sufixo do caso | **`-<polia do motor>-<correia>`**, sem o perfil (ex.: `-170-5000`). Fica travado; só o nome antes dele é editável |
| tensionamento | R_min = **0 %**; R_max = **3 %**; o 2 % é só informação |
| banco duplo | R2 escolhido **da mesma forma que R1**: o setup pode ter a transmissão do banco 2 (polia da máquina, polia do motor e correia), que calcula R2_min e R2_max, também travados |
| onde ficam | **biblioteca de setups exportável à parte** (arquivo próprio, reaproveitável entre projetos). Os casos guardam uma cópia dos valores e a referência ao setup |
| setup alterado | os casos criados antes **ficam como estavam**, mas mostram um **aviso**; um botão **atualiza** os dados do caso a partir do setup |
| interface | abas **Setups \| Layout** na barra superior; a aba Setups ocupa a página inteira e a lista de setups salvos fica no painel lateral |

### Consequências no roteiro
- **S2:** além do `.json` do projeto, há um arquivo de biblioteca (`tensorcad-setups`,
  versão 1) para salvar e abrir. A biblioteca também fica no navegador entre sessões.
- **S4:** o caso criado de um setup guarda `setup_id` e uma cópia dos dados. Se o setup
  mudar (mesmo id, dados diferentes), o caso mostra o aviso e o botão "atualizar do setup".
- **Banco duplo:** o setup tem uma transmissão do banco 2 opcional; sem ela, R2 continua
  digitado no caso.

### Confirmado depois da S0
- rpm WEG: **síncrono 60 Hz** (3600 / 1800 / 1200 / 900).
