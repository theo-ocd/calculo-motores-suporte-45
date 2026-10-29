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

## Estrutura

```
src/tensorcad/   pacote
tests/           testes (pytest)
data/            tabelas CSV (UTF-8, ';', decimal '.')
docs/            documentação técnica
examples/        exemplos de entrada/saída
```
