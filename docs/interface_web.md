# Interface web (navegador) — plano de desenvolvimento

Branch de integração: `feature/interface-web` (a partir de `develop`).
Cada etapa abaixo é uma branch `feature/web-<etapa>` com PR para `feature/interface-web`,
CI verde e aprovação do usuário. Ao final, um PR de `feature/interface-web` para `develop`.

## Objetivo

Substituir as perguntas sequenciais do prompt por uma interface visual no navegador,
servida localmente pelo próprio `tensorcad.exe`. Colegas abrem o .exe e o navegador já abre
na página do programa: não é preciso internet, Python nem instalação.

## Arquitetura proposta

```
tensorcad.exe ──► servidor HTTP local (127.0.0.1, porta livre) ──► abre o navegador
                    │
                    ├─ /            página única (HTML + CSS + JS embutidos, sem CDN)
                    └─ /api/...     JSON: cadastros, cálculo, desenho, projeto, exportação
                                    (usa o núcleo atual: projeto.py, planilha_projeto.py)
```

- **Servidor:** biblioteca padrão do Python (`http.server`, com threads), sem dependências
  novas. Fica leve no .exe e funciona sem internet.
- **Frontend:** HTML/CSS/JS puros, sem etapa de build. O desenho é em **SVG** gerado no
  navegador a partir de primitivas (linhas, arcos, círculos, cotas) calculadas no servidor.
  Assim a geometria continua num só lugar, o núcleo testado.
- **Cálculo:** sempre no servidor (Python). O navegador só envia as entradas e desenha o
  retorno, sem duplicar fórmulas em JS.
- **Testes:** pytest para a API; Playwright (navegador headless) para os fluxos da página,
  no CI Linux e Windows.

## Identidade visual

Tema escuro, no estilo do model space do AutoCAD, com destaques verde-azulados. A paleta é
*inspirada* nos tons da Bühler, **sem** usar logotipo, nome ou marca da empresa na interface.

| uso | token | cor proposta |
|-----|-------|--------------|
| fundo do desenho | `--bg-desenho` | `#0E1418` |
| fundo da página / painéis | `--bg`, `--painel` | `#11191D`, `#16232A` |
| texto / texto secundário | `--txt`, `--txt-2` | `#DCE6E8`, `#8FA3A8` |
| destaque principal (verde-azulado) | `--acento` | `#00A39A` |
| destaque secundário (verde) | `--acento-2` | `#4CC38A` |
| linhas de construção (arcos, raios) | `--construcao` | `#5E7C85` |
| chapa / guia | `--chapa` | `#E6EEF0` |
| motor 0 % / 3 % | `--m0`, `--m3` | `#4CC38A`, `#F2A65A` |
| ranhuras / alerta / erro | `--ranhura`, `--alerta`, `--erro` | `#FF5C5C`, `#F2C94C`, `#FF5C5C` |
| grade | `--grade` | `#1C2A30` |

Status: OK verde, FORA_RANHURA amarelo, SEM_SOLUCAO/INCOMPATIVEL vermelho, como na planilha.

## Etapas (ordem sequencial)

### W0 — Fundação
- Comando `tensorcad web`, que sobe o servidor local em porta livre e abre o navegador. O
  .exe com duplo clique passa a abrir a interface web; o modo de perguntas continua
  disponível em `tensorcad interativo`.
- Página vazia com o layout e o tema: barra superior, painel lateral de entradas, área do
  desenho e painel de resultados.
- API mínima: `GET /api/saude`, `GET /api/carcacas`.
- **Aceite:** abrir o .exe abre o navegador com a página; testes da API e um teste
  Playwright de carregamento.

### W1 — Formulário e cálculo ao vivo

Status das carcaças: **OK** (verde, chapa completa), **PARCIAL** (amarelo, dados a
confirmar), **ERRO** (vermelho: a preencher, sem chapa, cotas que não fecham, sem motor).
As opções vêm da planilha, e a faixa de carcaças é configurável
(`tensorcad web --carcaca-min/--carcaca-max`). No projeto, só a **cota 1646** é editável; o x
do tubo (465) e o piso (767) são fixos e aparecem apenas para consulta.

- **Seletor de carcaça:** lista 160 a 250, indicando quais têm chapa completa, parcial ou a
  preencher. As a preencher ficam desabilitadas, com aviso.
- **Campos dedicados:** R_min (0 %), R_max (3 %), cota 1646 (opcional) e nome do caso, com
  validação no campo.
- `POST /api/calcular` → status, faixa admissível da cota, cota recomendada, folgas a 0 % e
  3 % e mensagens. Recalcula ao editar, com um pequeno atraso.
- **Aceite:** valores da tela iguais aos da planilha/núcleo para REF-180 e ALT-2110.

### W2 — Desenho interativo
- O SVG desenha O, os arcos R_min/R_max, as linhas de raio, o piso, o tubo, a chapa, as
  ranhuras e o motor a 0 % e a 3 %, nas convenções do desenho (y para cima).
- Zoom com a roda do mouse, pan arrastando e "ajustar à tela".
- Coordenadas do cursor (X, Y relativos a O).
- Camadas liga/desliga: construção, motor, ranhuras e cotas.
- Cotas principais desenhadas: 1646, 465, 767, dx/dy tubo→L e h.
- Ao passar o mouse sobre um elemento, aparecem os valores dele.
- **Aceite:** teste Playwright conferindo os elementos do SVG e a posição do centro do motor
  dentro da tolerância.

### W3 — Dimensões-chave editáveis
- **Painel "Dimensões":** valores padrão da chapa da carcaça (comprimento, dx, dy, L→ranhura,
  comprimento das ranhuras, vão, ranhura→topo, largura, e_apoio, θ) e do projeto (x_tubo,
  y_piso).
- Editar um valor recalcula e redesenha. Os valores alterados ficam destacados, com botão
  "restaurar padrão" por campo e geral.
- A validação da soma das cotas da chapa aparece na própria tela.
- **Aceite:** um override muda o resultado como esperado, e o reset volta ao padrão.

### W4 — Projeto com vários casos e salvamento em .json

A altura H é do projeto, comum a todos os casos. Cada caso guarda carcaça, motor, R_min,
R_max e os ajustes de dimensões. O .json usa `"formato": "tensorcad-projeto", "versao": 1`.
O rascunho fica no navegador (`localStorage`).

- Lista de casos do projeto (adicionar, duplicar, renomear, excluir), um caso ativo por vez.
- Salvar e abrir o projeto em `.json` versionado (`"formato": "tensorcad-projeto", "versao": 1`)
  com entradas, overrides e nome. Rascunho automático no navegador para não perder o progresso.
- Exportar a planilha do projeto (.xlsx, uma aba por caso), reaproveitando `planilha_projeto.py`.
- **Aceite:** salvar → abrir reproduz o mesmo estado; o .xlsx exportado é igual ao gerado
  pela CLI.

### W5 — Fonte de dados por caminho pré-estabelecido (FUTURO — adiada, não será trabalhada agora)
- **Arquivo de dados padrão:** `tensorcad_dados.xlsx`, com abas `motores` e
  `chapas_carcaca`. Ele é procurado nesta ordem:
  1. ao lado do .exe;
  2. no caminho definido em `tensorcad.toml` ou em `TENSORCAD_DADOS`;
  3. nos dados embutidos.
- **Tela "Dados":** mostra de onde os dados foram lidos, as carcaças completas e as a
  preencher, além de avisos e erros (linha e campo). Tem botão "recarregar", para atualizar
  os dados sem reiniciar.
- Comando para gerar o modelo `tensorcad_dados.xlsx` a partir dos CSVs.
- **Aceite:** editar o .xlsx e clicar em recarregar atualiza o seletor de carcaças e os
  resultados.

### W6 — Gráficos e análise (FUTURO — adiada, não será trabalhada agora)
- Gráfico interativo folga mínima × cota 1646 (0 % e 3 %), com faixa admissível sombreada e
  a cota recomendada marcada. Clicar no gráfico aplica a cota.
- Comparação entre casos do projeto: tabela-resumo com status e cota de cada caso.
- **Aceite:** o gráfico bate com a tabela da planilha.

### W7 — Empacotamento e distribuição
- O .exe abre a interface. A página é servida só em `127.0.0.1`. O programa encerra ao
  fechar a janela do console ou pelo botão "Sair".
- O CI no Windows testa o .exe com Playwright: abre, calcula REF-180, salva o .json e
  exporta o .xlsx.
- A pré-release `exe-dev` é atualizada. O guia de uso para colegas fica em `docs/executavel.md`.
- **Aceite:** o .exe funciona num Windows limpo, sem Python e sem internet.

### W8 — Carcaças completas (quando as medidas chegarem)
- Preencher `chapas_carcaca` com as medidas de 160 a 250 a partir dos prints. A interface
  passa a liberar cada carcaça automaticamente, sem mudança de código.
- Teste paramétrico sobre todas as carcaças preenchidas: soma das cotas, caso nominal sem
  erro e desenho gerado.
- Revisar os valores calculados da CH-180 com o print real.

## Dependências entre etapas

`W0 → W1 → W2 → W3 → W4 → W5 → W6 → W7`; W8 pode entrar a qualquer momento depois da W5.
O que os dados pendentes afetam já está isolado em `chapas_carcaca`: a interface lê tudo de
lá e não tem medidas fixas no código.
