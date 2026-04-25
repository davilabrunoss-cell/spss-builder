$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appFile = Join-Path $appDir "streamlit_app.py"

python -m streamlit run $appFile --server.headless true --server.port 8501
