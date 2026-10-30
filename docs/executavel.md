# tensorcad.exe — uso

Executável Windows autônomo: não precisa de Python instalado. Os cadastros e as chapas
padrão já vêm dentro do arquivo.

## Duplo clique (modo interativo)

O programa pergunta:
1. o arquivo da planilha do projeto (novo ou existente);
2. o nome do projeto (só se o arquivo for novo);
3. para cada caso: nome da aba, carcaça, R_min (0 %), R_max (3 %) e a cota 1646 a
   verificar (Enter para só calcular).

Cada caso vira uma aba. No fim o programa oferece abrir a planilha.

## Linha de comando

```bat
tensorcad.exe --help
tensorcad.exe caso --projeto obra.xlsx --id REF-180 --carcaca 180M --rmin 2086 --rmax 2161 --cota 1646
tensorcad.exe caso --projeto obra.xlsx --id ALT --carcaca 180M --rmin 2086 --rmax 2110 --abrir
tensorcad.exe validar
tensorcad.exe lote --saida resultados
```

## Dados próprios

Para usar cadastros próprios, coloque uma pasta `data\` (com `padrao\`) ao lado de onde o
programa é executado, defina a variável `TENSORCAD_DADOS`, ou use `--dados` e `--padroes`.

## Build

`python scripts/build_exe.py` (requer `pip install ".[build]"`). No GitHub: workflow
"Executável Windows" (manual, em PRs que mexem no código, em pushes na develop e em tags
`v*`). O .exe testado é publicado na pré-release **exe-dev**, substituído a cada build, em
Releases do repositório. Também fica como artefato `tensorcad-exe`, se houver cota de
armazenamento.
