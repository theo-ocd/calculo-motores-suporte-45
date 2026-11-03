# Chapas padrão por carcaça — `chapas_carcaca.csv`

Uma linha por carcaça. Os valores são lidos dos prints de cada chapa. Formato: UTF-8,
separador `;` e decimal `.`. Medidas em mm.

## Esquema (vista do desenho; a chapa sobe da ponta baixa L para a ponta alta)

```
                                      ponta alta
                                     /   ┐
                                    /    │ dist_ranhura_topo
                        ranhura 1  ▓▓    ┘ ┐
                  (lado dos raios) ▓▓      │ comprimento_ranhura
                                  /        ┘ ┐
                                 /           │ dist_entre_ranhuras
                     ranhura 2  ▓▓           ┘ ┐
                                ▓▓             │ comprimento_ranhura
                               /               ┘ ┐
                              /                  │ dist_L_ranhura
           ponta baixa (L)   ●                   ┘
                             │ dy_L_tubo (L acima do tubo)
            tubo de apoio ○──┘
                          └─ dx_L_tubo ─┘ (horizontal, do centro do tubo até L)
```

A soma ao longo da chapa tem que fechar com o comprimento total:

`dist_L_ranhura + 2·comprimento_ranhura + dist_entre_ranhuras + dist_ranhura_topo = comprimento_chapa`

A tolerância é de 0,5 mm. Se a soma não fechar, o programa indica erro na linha da carcaça.

## Colunas

| coluna | obrigatória | descrição |
|--------|-------------|-----------|
| carcaca | sim | tamanho da carcaça (`160`, `180`, ...); `180` vale para 180M e 180L |
| theta_deg | sim | inclinação da chapa (graus) |
| e_apoio | sim | topo da chapa → plano dos pés do motor; 0 se o pé apoia direto na chapa (h = H + e_apoio) |
| comprimento_chapa | sim | comprimento total da chapa ao longo da inclinação |
| dx_L_tubo | sim | distância horizontal do centro do tubo de apoio até a ponta baixa L; positiva quando L fica do lado oposto ao centro dos raios (como no desenho) |
| dy_L_tubo | sim | distância vertical do centro do tubo até L; positiva quando L fica acima do tubo |
| dist_L_ranhura | sim | da ponta baixa L até o início da ranhura mais próxima (ranhura 2) |
| comprimento_ranhura | não* | comprimento de cada ranhura, ao longo da chapa |
| dist_entre_ranhuras | não* | do fim da ranhura 2 ao início da ranhura 1 (vão entre elas) |
| dist_ranhura_topo | sim | do fim da ranhura 1 até a ponta alta da chapa |
| largura_ranhura | não | largura da ranhura; se vazia, a verificação com o furo K do motor não é feita (gera aviso) |
| origem | sim | MEDIDO, CALCULADO, HIPOTESE ou TODO |
| observacao | não | texto livre |

\* Para o cálculo bastam as pontas externas, ou seja, `dist_L_ranhura` e `dist_ranhura_topo`.
Se só um entre `comprimento_ranhura` e `dist_entre_ranhuras` for informado, o outro é
deduzido pela soma.

Linhas com todas as medidas vazias, como as de 160, 200, 225 e 250 hoje, são modelos a
preencher. O programa as ignora e mostra um aviso.

## CH-180 (atual)

Medidas do desenho da chapa: a partir da ponta baixa L, 110 | ranhura 155 | 124 | ranhura
155 | 91, total 635. dx 358,44 e dy 45 foram validados pelas folgas 16 (topo, 0 %) e 41
(base, 3 %) do desenho em H = 1646. A largura da ranhura ainda está pendente.

## tubo_horizontal.csv (layout tubo horizontal, T0)

São parâmetros do layout, um por linha (`parametro;valor;unidade;origem;observacao`), e não
dependem da carcaça. Os dados por carcaça vêm do catálogo de motores (padrão WEG):
**H** (centro do motor → base dos pés) e **A** (furação transversal ao eixo).

Pilha vertical, do tubo ao centro do motor (motor normal, acima do tubo):

```
 centro do motor ─┐
                  │ H                    (padrão WEG da carcaça)
 base do motor ───┤
                  │ espessura_chapa      15
 ── chapa ────────┤
                  │ espessura_porca      27,5
                  │ g (entre porcas)     30 < g < 150
                  │ espessura_porca      27,5
 topo do tubo ────┤
                  │ espessura_tubo       80
 ponto mais baixo ┘  ← altura_tubo (1375) abaixo do topo da laje
```

Centro do motor abaixo do topo da laje:
`altura_tubo − espessura_tubo − 2·espessura_porca − g − espessura_chapa − H`.
Com o motor invertido, a pilha vai para baixo a partir do fundo do tubo (a confirmar).

Em x, o motor desloca junto com a chapa ao longo do tubo. A chapa ocupa
`A + acrescimo_furacao` e o curso máximo é `comprimento_tubo / 2`.

