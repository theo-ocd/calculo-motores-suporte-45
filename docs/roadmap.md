# Roteiro de fases

| Fase | Situação |
|------|----------|
| F0 — setup do repositório | Concluída (PR #2) |
| F1 — modelo de dados | Concluída (PR #4) |
| F2 — núcleo geométrico | Concluída (PR #6) |
| F3 — ranhuras e limites | Concluída junto com dados/planilha (PR #8) |
| F4 — processamento em lote | Em andamento (issue #9) |
| F5 — exportação CAD (.dxf/.lsp/.scr/.fas) | **Adiada** por decisão do usuário (2026-10-29) |
| F6 — executável | **A reformular** (ver abaixo) |
| F7 — release v0.1.0 | Pendente |

## F5 — adiada

A exportação para AutoCAD fica para depois. As conversões de coordenadas já existem
no núcleo (`geometry.para_cad`) e os campos `X_cad/Y_cad` seguem em `resultados`.

## F6 — escopo reformulado (pedido do usuário, a detalhar)

- O algoritmo deve ser alimentado com as dimensões-base padrão para motores de
  carcaça 160 a 250.
- Inicialmente só as cotas em **verde** do desenho são conhecidas; as demais devem
  ser **inferidas** a partir do padrão conhecido das chapas e do tamanho do motor.
- Interação visual; a saída é a planilha do caso.
- Cada caso é **uma aba**; é possível adicionar casos individualmente, formando uma
  única planilha completa por projeto.

Especificação detalhada e hipóteses: [f6_especificacao.md](f6_especificacao.md).

Pontos em aberto antes de implementar: identificação de cada cota verde do desenho
de referência e as regras de inferência (padrão de chapa por carcaça).
