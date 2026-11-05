# Inicia o El Orientador no Windows SEM Docker. Duplo clique em iniciar.bat ou: powershell -File scripts\windows\iniciar.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$venv = Join-Path $root ".venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
  Write-Host "Primeira execução: criando ambiente Python (alguns minutos)..."
  python -m venv $venv
  & "$venv\Scripts\python.exe" -m pip install --upgrade pip
  & "$venv\Scripts\python.exe" -m pip install -r services\pipeline\requirements.txt pixeltable-pgserver
}
$web = Join-Path $root "apps\web"
if (-not (Test-Path "$web\node_modules")) { Write-Host "Instalando dependências do site..."; Push-Location $web; npm install; Pop-Location }
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
if (-not (Test-Path "$web\.next\BUILD_ID")) { Write-Host "Compilando o site (uma vez)..."; Push-Location $web; npm run build; Pop-Location }
$siteProc = Start-Process npm -ArgumentList "run","start" -WorkingDirectory $web -PassThru -WindowStyle Minimized
Write-Host "Abra http://localhost:3000  (Ctrl+C para encerrar)"
try { & "$venv\Scripts\python.exe" scripts\windows\stack_local.py } finally { Stop-Process -Id $siteProc.Id -Force -ErrorAction SilentlyContinue }
