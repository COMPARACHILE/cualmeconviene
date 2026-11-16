# Instalación (una sola vez) de la lectura automática de precios en el PC Windows del dueño. No usa Git.
# Abrir PowerShell y pegar:
#   irm https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/playwright/pc/instalar.ps1 | iex
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-ExecutionPolicy -Scope Process Bypass -Force
$base = Join-Path $env:USERPROFILE 'cualmeconviene-pc'
New-Item -ItemType Directory -Force -Path $base | Out-Null
Set-Location $base

Write-Host "1/4 Instalando Node.js (si falta)..." -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  winget install -e --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
node --version

Write-Host "2/4 Instalando Playwright (usará tu Google Chrome)..." -ForegroundColor Cyan
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'
if (-not (Test-Path 'package.json')) { '{"name":"cualmeconviene-pc","private":true,"type":"module"}' | Set-Content 'package.json' }
npm.cmd i playwright@1 --no-audit --no-fund --loglevel=error

Write-Host "3/4 Clave de GitHub para subir las lecturas" -ForegroundColor Cyan
if (-not (Test-Path 'clave.txt')) {
  Write-Host "Se abrirá GitHub para crear una clave (token). Usa la cuenta COMPARACHILE y elige:" -ForegroundColor Yellow
  Write-Host "  - Repository access: Only select repositories -> cualmeconviene" -ForegroundColor Yellow
  Write-Host "  - Permissions -> Repository -> Contents: Read and write" -ForegroundColor Yellow
  Write-Host "  - Expiration: 1 año. Luego 'Generate token' y copia la clave (empieza con github_pat_)." -ForegroundColor Yellow
  Start-Process 'https://github.com/settings/personal-access-tokens/new?name=Precios+PC+cualmeconviene&description=Sube+las+lecturas+de+precios+del+PC&target_name=COMPARACHILE&expires_in=366&contents=write'
  $s = Read-Host 'Pega aquí la clave y aprieta Enter' -AsSecureString
  $s | ConvertFrom-SecureString | Set-Content 'clave.txt'
}

Write-Host "4/4 Programando la lectura diaria (8:00 y al iniciar sesión)..." -ForegroundColor Cyan
Invoke-WebRequest 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas/playwright/pc/leer-pc.ps1' -OutFile (Join-Path $base 'leer-pc.ps1')
$accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$base\leer-pc.ps1`""
$cuando = @((New-ScheduledTaskTrigger -Daily -At 8:00am), (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME))
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'Precios cualmeconviene' -Action $accion -Trigger $cuando -Settings $ajustes -Force | Out-Null

Write-Host "Primera lectura (30 a 60 minutos; no cierres esta ventana)..." -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $base 'leer-pc.ps1')
Write-Host "Listo. Desde mañana se lee solo. Registro: $base\lectura-pc.log" -ForegroundColor Green
