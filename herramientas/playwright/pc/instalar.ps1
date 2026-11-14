# Instalación (una sola vez) de la lectura automática de precios en el PC Windows del dueño.
# Abrir PowerShell y pegar:
#   irm https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/playwright/pc/instalar.ps1 | iex
$ErrorActionPreference = 'Stop'
Write-Host "1/5 Instalando Git y Node.js (si faltan)..." -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements }
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

$repo = Join-Path $env:USERPROFILE 'cualmeconviene-pc'
Write-Host "2/5 Bajando la página en $repo ..." -ForegroundColor Cyan
if (-not (Test-Path $repo)) { git clone --depth 20 https://github.com/COMPARACHILE/cualmeconviene.git $repo }
Set-Location $repo
git config user.name 'Precios PC'
git config user.email 'adictosdigitalesla@gmail.com'

Write-Host "3/5 Instalando Playwright y su navegador..." -ForegroundColor Cyan
npm i --no-save playwright@1
npx playwright install chromium

Write-Host "4/5 Programando la lectura diaria (8:00 y al iniciar sesión)..." -ForegroundColor Cyan
$accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$repo\herramientas\playwright\pc\leer-pc.ps1`""
$cuando = @((New-ScheduledTaskTrigger -Daily -At 8:00am), (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME))
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'Precios cualmeconviene' -Action $accion -Trigger $cuando -Settings $ajustes -Force | Out-Null

Write-Host "5/5 Primera lectura de prueba (se abrirá GitHub para iniciar sesión con la cuenta COMPARACHILE)..." -ForegroundColor Cyan
& "$repo\herramientas\playwright\pc\leer-pc.ps1"
Write-Host "Listo. Desde mañana se lee solo. Registro: $repo\lectura-pc.log" -ForegroundColor Green
