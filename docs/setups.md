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

### S0: Definições e dados (só documentação e tabelas, sem código de interface)
- Confirmar o que é lista fixa e o que é entrada livre, o significado do sufixo, os
  setups com banco duplo e onde os setups ficam salvos (perguntas abaixo).
- `data/padrao/transmissao.csv` com as listas confirmadas (polias, correias e perfil).
- **Conferência:** tabela de conferência com a planilha.

### S1: Núcleo do cálculo da correia (funções puras)
- `src/tensorcad/correia.py`: distância entre eixos (0 %, 2 % e 3 %) e rpm da máquina,
  com validação (raiz negativa = correia curta demais para as polias).
- Testes contra os valores da planilha (L 5000 e 5500, todas as polias do motor).
- **Conferência:** tabela calculada × planilha.

### S2: Modelo de setup, API e .json
- Setup = nome, polia da máquina, polia do motor, correia, rpm do motor, R_min/R_max
  calculados e sufixo, mais os dados do banco 2, se confirmados.
- API `POST /api/setup` (calcula e valida). O projeto `.json` ganha a lista `setups`, que
  é opcional, para arquivos antigos continuarem abrindo.
- **Conferência:** salvar e abrir um .json com setups.

### S3: Tela "Setups" (nova aba, antes do layout)
- Navegação no topo: **Setups | Layout**. A aba Setups troca a tela inteira: formulário
  com as listas, resultado do cálculo (R 0 %, 2 % e 3 %, rpm) e botão salvar.
- Os setups salvos aparecem no menu lateral (renomear, duplicar, excluir).
- **Conferência:** prints e teste de navegador.

### S4: Usar um setup na edição de layout
- No layout (45° ou horizontal), "novo caso a partir de um setup": R_min/R_max e o sufixo
  ficam **travados** (somente leitura, com indicação do setup de origem). O nome do caso
  continua editável. "Novo caso" do zero continua como hoje.
- Mudar o setup atualiza os casos ligados a ele (a confirmar).
- **Conferência:** caso criado de um setup, com o cálculo igual ao feito à mão.

### S5: Saídas
- `.xlsx`: dados do setup na aba do caso (polias, correia, rpm do motor e da máquina, R) e
  tabela de setups no índice.
- **Conferência:** exportar um projeto com casos de setups nos dois layouts.

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

### Pendente de confirmação (S0)
- rpm WEG: valores síncronos de 60 Hz (3600 / 1800 / 1200 / 900) ou nominais do catálogo
  (por exemplo 1770 para IV polos)? Entra 50 Hz?
