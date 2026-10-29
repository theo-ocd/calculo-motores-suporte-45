# Chapas padrão (protótipo F6)

Tabelas das chapas de apoio padronizadas por carcaça. Por enquanto só a CH-180, montada
com as medidas conhecidas do desenho de referência. As demais chapas virão dos PDFs da empresa.

## chapas_padrao.csv

| campo | unidade | descrição |
|-------|---------|-----------|
| chapa_id | - | chave |
| carcacas_compat | - | carcaças aceitas, separadas por `\|` (número sozinho aceita M/L/S) |
| theta_deg | graus | inclinação da chapa (guia) |
| e_apoio | mm | topo da chapa → plano de apoio dos pés (h = H + e_apoio); 0 se os pés apoiam direto na chapa |
| comprimento | mm | comprimento total da chapa ao longo da inclinação |
| dx_L | mm | distância horizontal do centro do tubo de apoio até L (ponta baixa do topo da chapa), x+ para a esquerda |
| cota_L_tubo | mm | distância vertical do centro do tubo até L (L acima do tubo) |
| origem | - | MEDIDO, CALCULADO, HIPOTESE ou TODO |

## ranhuras_padrao.csv

As distâncias `d` são medidas a partir de L, subindo ao longo da chapa. A ranhura 1 fica
do lado do centro do arco, ou seja, mais longe de L.

| campo | descrição |
|-------|-----------|
| d_ini, d_fim | início/fim da ranhura em d. Ranhura 1 exige d_fim; ranhura 2 exige d_ini |
| largura | largura da ranhura (≥ K do motor) |

## Origem dos valores da CH-180

- **dx_L = 358.44** e **cota_L_tubo = 45:** vêm da reta da guia calibrada no desenho
  (centro do motor 676/1966, h 180, 45°), com L 45 mm acima do tubo (confirmado). O dx_L
  ainda precisa ser confirmado no desenho da chapa.
- **Ranhuras:** calibradas com as folgas 9 (lado do arco) e 49, com o motor na posição do
  desenho. Carcaça 180: A = 279, K = 15. A largura de 17 é hipótese.
