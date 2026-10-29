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

## Suposições adotadas (F3 — ranhuras)

- **S9 — Sem ranhuras cadastradas** para (chapa, carcaça): status OK com AVISO e folgas
  vazias (não há como verificar). Ordem de verificação: carcaça → largura < K → folgas.
- **S10 — Calibração**: as folgas medidas determinam apenas `u_ini` da ranhura 1 e
  `u_fim` da ranhura 2. Para montar as ranhuras completas é preciso informar o
  comprimento (ao longo de u) de cada ranhura — dado a confirmar (TODO).
- **S11 — Seleção de chapas**: usa o ponto P (`a_ref`, `b_ref`) da montagem para todas
  as chapas avaliadas e `e_apoio`/`theta` de cada chapa.
