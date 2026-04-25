# Agora SPSS Builder - versao online

Esta pasta e a versao irma do app local, preparada para deploy futuro em Streamlit.

Objetivo:
- manter o app local original como sandbox de melhorias
- manter esta copia separada para desacoplamento e preparacao de subida

## Estrutura

- `streamlit_app.py`: interface principal
- `spss_builder_app_utils.py`: leitura, serializacao e utilidades do documento tecnico
- `scripts/spss_sanity_check.py`: validacao estrutural
- `scripts/spss_questionnaire_v2.py`: parser e geracao de schema/.sav
- `assets/Logo_Agora.png`: logo local do app
- `requirements.txt`: dependencias
- `run_app.ps1`: atalho local para subir esta versao

## Diferenca para o app local

Esta versao nao depende mais do caminho fixo da maquina para localizar o parser.
Ela usa apenas caminhos relativos internos:

- `assets/` para o logo
- `scripts/` para parser e sanity check

## Como rodar localmente

```powershell
cd "C:\Users\luna_\Codex_Luna\planejamentos\Projeto APP SPSS Builder\app_streamlit_online"
python -m pip install -r requirements.txt
.\run_app.ps1
```

## Pendencias antes do deploy real

1. validar se `pyreadstat` e `savReaderWriter` sobem bem no ambiente do Streamlit Cloud
2. decidir se o deploy sera privado/interno
3. revisar encoding de alguns textos antes da subida final
