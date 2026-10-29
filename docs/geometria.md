# Geometria — convenções e formulação

Este documento é a referência normativa do núcleo geométrico (`tensorcad.geometry`).
Conteúdo copiado integralmente da especificação do projeto.

## Contexto do problema

- Um conjunto (estrutura + chapa-guia + motor) está posicionado abaixo de um centro de
  arco O (centro do eixo acionado). O motor deve ficar com o centro do eixo a uma
  distância R de O (entre-centros da correia; R_min=2086, R_max=2161 no caso de referência).
- O motor desliza sobre uma reta (guia) inclinada θ (45° no caso de referência).
- O centro do motor fica a uma altura h acima da reta da guia: h = H (altura de eixo
  IEC da carcaça) + e_apoio (reta da guia → plano de apoio dos pés, vem da chapa).
- O conjunto inteiro desloca-se verticalmente Δy (cota "verde"); é a variável principal
  dos estudos. Também variam: motor (h, A, K), inclinação θ e R.

## Convenções (obrigatórias)

- Origem O = centro do arco. x positivo para a ESQUERDA, y positivo para BAIXO.
- P = (a, b): ponto de referência da chapa sobre a reta da guia, relativo a O com Δy=0.
- u = (cosθ, sinθ): direção da guia; s>0 = afastar o motor de O (tensionar).
- n = (sinθ, −cosθ): normal da guia, lado do motor.
- Ângulos em graus nas tabelas, radianos internamente. Unidades: mm.
- Conversão para o CAD (y para cima): X_cad = X_O_cad − x ; Y_cad = Y_O_cad − y.
- Nomes: use l_proj e d_perp (NÃO "D", que conflita com o diâmetro do eixo D_eixo).

## Formulação

```
  l_proj = a·cosθ + (b+Δy)·sinθ
  d_perp = a·sinθ − (b+Δy)·cosθ + h
  se R² < d_perp² → status SEM_SOLUCAO
  s  = −l_proj + sqrt(R² − d_perp²)
  Cx = a + s·cosθ + h·sinθ
  Cy = b + Δy + s·sinθ − h·cosθ
  ∂s/∂Δy = −sinθ + d_perp·cosθ / sqrt(R² − d_perp²)
  ∂s/∂h  = −d_perp / sqrt(R² − d_perp²)
```

Calibração de P a partir de um desenho existente (centro do motor Cx0, Cy0, h0, θ0):

```
  a = Cx0 − h0·sinθ0 ;  b = Cy0 + h0·cosθ0
  Referência: Cx0=676 (=465+211), Cy0=1966, h0=180, θ0=45 → a=548.72, b=2093.28
```

## Ranhuras

Vista de topo do eixo: cota A do motor fica ao longo da guia.

```
  furos em u = s ± A/2
  folga_neg = (s − A/2 − K/2) − u_ini(ranhura 1)
  folga_pos = u_fim(ranhura 2) − (s + A/2 + K/2)
  largura da ranhura < K → INCOMPATIVEL ; folga < 0 → FORA_RANHURA
  carcaça fora de chapas.carcacas_compat → INCOMPATIVEL
```

No desenho de referência as folgas medidas são 9 e 49 mm (lado exato: TODO confirmar);
há função para CALIBRAR u_ini/u_fim a partir de folgas medidas.

## Nota de derivação

C = P + Δy·ŷ + s·u + h·n. Impondo |C| = R:
(s + l_proj)² + d_perp² = R², com l_proj = (P+Δy·ŷ)·u e d_perp = (P+Δy·ŷ)·n + h.
Toma-se a raiz positiva (motor do lado "afastado" de O ao longo de u).
