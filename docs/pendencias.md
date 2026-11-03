# Pendências e suposições

Toda suposição adotada no código fica registrada aqui. Itens marcados TODO geram
aviso em tempo de execução quando afetam um cálculo.

Fonte das pendências: `data/pendencias.csv` (também na aba `pendencias` da planilha).
Os IDs P1–P7 abaixo devem ficar sincronizados com o CSV (verificado em teste).

| id | Item | Impacto | Status |
|----|------|---------|--------|
| P1 | Confirmar carcaça do motor do desenho (160?) e e_apoio=20 mm | h de todos os casos | ABERTO |
| P2 | Confirmar lado das folgas 9 e 49 (ranhura 1 = lado do centro do arco?) | u_ini/u_fim e status | RESOLVIDO |
| P3 | Medir u_fim da ranhura 1, u_ini da ranhura 2 e largura real das ranhuras | Desenho CAD | PARCIAL (falta largura) |
| P4 | Curso da ranhura (~49 mm) menor que o necessário R2086→R2161 (~83 mm) | Projeto da chapa | RESOLVIDO (chapa real: 155 mm) |
| P5 | Catálogo de motores (AC, HD, L, massa) — fabricante a definir | Desenho e interferência | ABERTO |
| P6 | Coordenadas X_O_cad/Y_O_cad do centro do arco | Exportação CAD | ABERTO |
| P7 | Dimensões da chapa (espessura, comprimento, largura) | Desenho CAD | ABERTO |
| P8 | Banco duplo: O2 fica 500 mm acima de O | Banco duplo — posição de O2 | RESOLVIDO (acima) |
| P9 | Banco duplo: raios R2_min/R2_max do banco 2 | Banco duplo — R2_min/R2_max | RESOLVIDO (independentes do banco 1, por caso) |
| P10 | Banco duplo: critério de posição do motor único | Banco duplo — status e H recomendada | RESOLVIDO (≥ R1 de O1 e ≤ R2 de O2 a 0 % e 3 %, obrigatório: FORA_TENSIONAMENTO) |
| P11 | Tubo horizontal: origem e definição das cotas 1375, 65, 927, 1699, (248) e, invertido, 1120, 170, 2242, 93 | Tubo horizontal — referencial e dados | RESOLVIDO (cotas confirmadas) |
| P12 | Tubo horizontal: qual movimento faz o tensionamento de 0 % a 3 % (x ao longo do tubo, y nas barras roscadas ou ambos) | Tubo horizontal — graus de liberdade | RESOLVIDO (x e y ajustam juntos, fixo: altura do tubo) |
| P13 | Tubo horizontal: distância entre porcas g (30 a 150 mm) — entre quais faces e se depende de espessura de porca e chapa | Tubo horizontal — status FORA_PORCAS | RESOLVIDO (pilha: tubo + 2 porcas de 27,5 + g + chapa de 15 + H) |
| P14 | Tubo horizontal: limites de x ao longo do tubo e dimensões por carcaça (altura do motor sobre a chapa, normal e invertido) | Tubo horizontal — tabela por carcaça | RESOLVIDO (H pelo padrão WEG, curso em x pelo comprimento do tubo informado) |
| P15 | Tubo horizontal: R1839 e R2349 são os arcos do banco 1 e do banco 2 (banco duplo)? | Tubo horizontal — banco duplo | RESOLVIDO (sim, só neste caso) |
| P16 | Tubo horizontal: com g = 65 e H = 250 o centro do motor fica 910 abaixo da laje e o desenho mostra 927 (com H = 225 daria 935) — qual carcaça está no desenho? | Tubo horizontal — caso de referência | RESOLVIDO (carcaça 250, chapa do desenho 15 mm alta: vale 910) |
| P17 | Tubo horizontal invertido: qual ponto do tubo é o fixo de projeto e de onde se mede 1120 (fundo da laje → fundo da chapa?) | Tubo horizontal — motor invertido | RESOLVIDO (altura do tubo recomendada pelo cálculo, mesmo ponto de referência, invertido com carcaça 180) |
| P18 | Tubo horizontal: x medido de onde (linha de centro?) e interferência = chapa com A + 75 dentro do comprimento do tubo? | Tubo horizontal — limites em x | RESOLVIDO (x da linha de centro, chapa A + 75 dentro do curso do tubo) |
| P19 | Tubo horizontal: desempate da altura recomendada — com g no meio (90), centrar no tubo o curso em x entre 0 % e 3 % (suposição) | Tubo horizontal — altura recomendada | ABERTO |

Pendência do repositório (fora do CSV): licença (LICENSE provisório, TODO).

Correspondência com as pendências iniciais da especificação: 1 → P1; 2 → P2/P3;
3 → P5/P7; 4 → P6.

## Suposições adotadas (F1 — modelo de dados)

- **S1 — `carcacas_compat`**: lista separada por vírgula. Um item igual à carcaça é
  compatível; um item só numérico (ex. `160`) aceita todas as carcaças desse número
  (`160M`, `160L`). Lista vazia = nenhuma carcaça compatível.
- **S2 — CH-REF `carcacas_compat = 160M,160L`**: derivado da hipótese de carcaça 160
  (pendência 1). Espessura, comprimento e largura da chapa: vazios (TODO).
- **S3 — REF-4 (h=150)**: a tabela `casos` não tem override de `h`. Representado como
  motor `IEC-132S-4P` (H=132) com `e_apoio_override=18` → h=150. Como 132S não está
  em `carcacas_compat` de CH-REF, o caso será marcado INCOMPATIVEL na verificação de
  ranhuras (F3), mas a geometria é calculada normalmente.
- **S4 — ranhuras.csv** sem linhas (coordenadas reais desconhecidas, pendência 2).
- **S5 — TR-REF `R_nom`** vazio (não informado). `R_alvo` de cada caso é obrigatório
  na prática; se vazio, usar `R_nom` (definido no processamento, F4).
- **S6 — `e_apoio` e `e_apoio_override` ≥ 0**; `theta` em (0°, 90°).
- **S7 — `potencia_kw`** vazio na semente IEC (não fornecido).
- **S8 — `X_O_cad/Y_O_cad`** vazios em M-REF (pendência 4); a exportação CAD usa 0,0
  com aviso.

## Atualização — dados semente revisados (branch feature/dados-semente-planilha)

Substitui S2, S3, S4 e S5 acima:
- `casos.csv` ganhou `h_override` (prioridade sobre H + e_apoio) e `descricao`;
  REF-4 agora é `IEC-160L-4P` com `h_override=150` (S3 obsoleta).
- `R_alvo` aceita `min|nom|max` (da transmissão) ou número. `nom` com `R_nom` vazio
  é ERRO de validação (caso não calculável).
- `carcacas_compat` usa `|` como separador (S1 mantida quanto ao prefixo numérico).
- Ranhuras: `u_ini` obrigatório só na ranhura 1 e `u_fim` só na ranhura 2 (as pontas
  internas podem ficar vazias). Valores de CH-REF calibrados com hipótese P2.
- Coluna `origem` (MEDIDO|CALCULADO|HIPOTESE|TODO|IEC-REF-VALIDAR) em chapas, ranhuras
  e montagens. Registro com origem TODO/HIPOTESE gera AVISO listando células vazias.
  Campos obrigatórios continuam obrigatórios mesmo com origem=TODO (confirmado pelo usuário).
- Pendências P1–P7 do usuário consolidadas na tabela do topo deste arquivo.

## Suposições adotadas (F3 — ranhuras)

- **S9 — Sem ranhuras cadastradas** para (chapa, carcaça): status OK com AVISO e folgas
  vazias (não há como verificar). Ordem de verificação: carcaça → largura < K → folgas.
- **S10 — Calibração**: as folgas medidas determinam apenas `u_ini` da ranhura 1 e
  `u_fim` da ranhura 2 (únicas pontas usadas no cálculo). O comprimento de cada
  ranhura é opcional; sem ele as pontas internas ficam vazias (TODO, pendência P3).
- **S11 — Seleção de chapas**: usa o ponto P (`a_ref`, `b_ref`) da montagem para todas
  as chapas avaliadas e `e_apoio`/`theta` de cada chapa.
- **S12 — Precedência de status** (confirmada pelo usuário): SEM_SOLUCAO (geometria) prevalece sobre o status das
  ranhuras; nos demais casos vale o status das ranhuras (INCOMPATIVEL → FORA_RANHURA →
  OK). Mensagens das ranhuras são somadas à mensagem do resultado.

## Protótipo F6 (motor 180)

- P1 resolvida: motor do desenho é carcaça 180, h = 180 medido do topo da chapa (e_apoio = 0).
  Os dados da M-REF/CH-REF (160L + e_apoio 20) dão o mesmo h e foram mantidos para os
  testes de referência; o protótipo usa `data/padrao/` (CH-180).
- **S13 — Cota recomendada**: a que maximiza a menor folga entre R_min e R_max (varredura
  de 1 mm + seção áurea). Quando inviável, a mesma cota dá o menor déficit.
- **S14 — dx_L = 358.44 (CH-180)**: derivado da calibração; confirmar no desenho da chapa.

## Chapa CH-180 real (desenho do usuário)

- Ao longo da chapa, a partir da ponta baixa: 110 | ranhura 155 | 124 | ranhura 155 | 91
  (= 635). 155 é o comprimento total da ranhura. As folgas são medidas da borda externa do
  furo do motor ao fim da ranhura.
- Validação: em H = 1646, a folga de cima a 0 % é 16,30 (desenho: 16) e a de baixo a 3 %
  é 40,64 (desenho: 41); centro do motor a 216,53 do tubo (desenho: 217). Confirma
  dx 358,44 e dy 45.
- Critério: a 0 % a folga de cima é bloqueante (inserção das correias); a 3 %, a de baixo
  (deslizar para baixo). O cálculo exige todas as folgas ≥ 0, incluindo as das pontas
  internas, quando conhecidas.
- Pendente: largura das ranhuras (por isso a carcaça 180 aparece como PARCIAL).

## Banco duplo — esboço (branch feature/banco-duplo)

Atrás do switch: desligado, nada muda. Detalhes em docs/banco_duplo.md.

- O2 fica 500 mm **acima** de O (P8, confirmado).
- R2_min e R2_max são entradas por caso, **independentes** do banco 1 (P9, confirmado).
- Motor único: a 0 % e a 3 %, o centro deve ficar a ≥ R1 de O e ≤ R2 de O2 (P10,
  confirmado). Sem trecho entre os arcos, gera **aviso**.
- Obrigatório (confirmado): sem trecho entre os arcos, o caso fica FORA_TENSIONAMENTO. O curso
  entra como folga na H recomendada.
- Suposição: o curso (mm ao longo da chapa) é tratado como mais uma folga na maximização da
  folga mínima.
- O centro dos raios O passa a se chamar O1 no desenho e na interface.

## Layout tubo horizontal (branch feature/tubo-horizontal)

Roteiro em docs/tubo_horizontal.md. T0: definições confirmadas e P11–P18 respondidas. A altura do tubo funciona como o H do
45°: entrada opcional, com faixa admissível e altura recomendada pelo cálculo.
