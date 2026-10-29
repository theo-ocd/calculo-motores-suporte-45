# tensorcad — cálculo de motores sobre suporte inclinado

Ferramenta em Python que calcula a posição de um motor sobre uma chapa-guia inclinada
(base tensora de correia), valida as ranhuras e exporta o desenho para AutoCAD
(`.lsp`/`.scr`, compiláveis para `.fas`, e `.dxf`).

Problema original: estabelecer a equação que dá o deslocamento `s` ao longo da reta
inclinada (45° na referência) em função do raio R (entre-centros), da posição do
conjunto, da altura do motor `h` e do deslocamento vertical do conjunto `Δy` (cota verde).

Formulação e convenções: [docs/geometria.md](docs/geometria.md).
Pendências/suposições: [docs/pendencias.md](docs/pendencias.md).

## Como rodar (desenvolvimento)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
```

## Executável Windows

`tensorcad.exe` (artefato do workflow "Executável Windows"): duplo clique abre o modo
interativo; também aceita os comandos abaixo. Detalhes: [docs/executavel.md](docs/executavel.md).

## Protótipo F6 — planilha do projeto (motor 180)

Cada caso vira uma aba na planilha do projeto; rode o comando de novo para adicionar casos.

```bash
pip install -e .
tensorcad caso --projeto output/obra.xlsx --id REF-180 --carcaca 180M --rmin 2086 --rmax 2161 --cota 1646 --nome-projeto OBRA
tensorcad caso --projeto output/obra.xlsx --id ALT --carcaca 180M --rmin 2086 --rmax 2110 --abrir
tensorcad validar
tensorcad --help
```

A aba do caso mostra a faixa admissível da cota 1646 (0 % e 3 % dentro das ranhuras), a
cota recomendada (máxima folga mínima), as posições do motor, o gráfico folga × cota e um
esboço da geometria. Chapas padrão: `data/padrao/` (só CH-180 por enquanto).

## Uso (módulos da F4)

```bash
# planilha consolidada com todas as abas (cadastros, resultados, varredura, calculadora...)
python -m tensorcad.planilha --dados data --saida output/tensorcad_base.xlsx

# lote: casos de CSV ou xlsx → output/resultados.csv e output/resultados.xlsx
python -m tensorcad.lote --dados data --saida output --caso-varredura VAR-BASE --dy-ini -100 --dy-fim 100 --passo 10

# cadastros de uma planilha e casos de outro arquivo
python -m tensorcad.lote --dados output/tensorcad_base.xlsx --casos meus_casos.csv --saida output

# calculadora com fórmulas Excel, preenchida com um caso
python -m tensorcad.calculadora --caso REF-1 --saida output/calculadora.xlsx
```

Roteiro e decisões de escopo: [docs/roadmap.md](docs/roadmap.md).

## Estrutura

```
src/tensorcad/   pacote
tests/           testes (pytest)
data/            tabelas CSV (UTF-8, ';', decimal '.')
docs/            documentação técnica
examples/        exemplos de entrada/saída
```
