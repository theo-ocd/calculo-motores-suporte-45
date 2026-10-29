# Pendências e suposições

Toda suposição adotada no código fica registrada aqui. Itens marcados TODO geram
aviso em tempo de execução quando afetam um cálculo.

| # | Pendência | Situação / hipótese adotada |
|---|-----------|-----------------------------|
| 1 | Confirmar `e_apoio` (h=180 = H160 + 20?) | Hipótese: CH-REF `e_apoio=20`, motor de referência carcaça 160. TODO confirmar. |
| 2 | Lado das folgas 9 e 49 mm (qual é ranhura 1 / 2) e coordenadas `u_ini/u_fim` reais | TODO. Função de calibração disponível (F3). |
| 3 | Catálogo real de motores (AC, HD, L, massa) e de chapas | Semente IEC com `fonte=IEC-REF-VALIDAR`; AC/HD/L/massa vazios. |
| 4 | Coordenadas `X_O_cad/Y_O_cad` do centro do arco no desenho | TODO. |
| 5 | Licença do repositório | TODO (LICENSE provisório). |

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
- Pendências P1–P7 do usuário: ver `data/pendencias.csv` (serão consolidadas aqui no
  passo 5).

## Suposições adotadas (F3 — ranhuras)

- **S9 — Sem ranhuras cadastradas** para (chapa, carcaça): status OK com AVISO e folgas
  vazias (não há como verificar). Ordem de verificação: carcaça → largura < K → folgas.
- **S10 — Calibração**: as folgas medidas determinam apenas `u_ini` da ranhura 1 e
  `u_fim` da ranhura 2 (únicas pontas usadas no cálculo). O comprimento de cada
  ranhura é opcional; sem ele as pontas internas ficam vazias (TODO, pendência P3).
- **S11 — Seleção de chapas**: usa o ponto P (`a_ref`, `b_ref`) da montagem para todas
  as chapas avaliadas e `e_apoio`/`theta` de cada chapa.
- **S12 — Precedência de status**: SEM_SOLUCAO (geometria) prevalece sobre o status das
  ranhuras; nos demais casos vale o status das ranhuras (INCOMPATIVEL → FORA_RANHURA →
  OK). Mensagens das ranhuras são somadas à mensagem do resultado.
