# Lectura diaria de las tiendas que bloquean a GitHub, desde el PC del dueño (14-11-2026).
# La corre sola la tarea programada "Precios cualmeconviene" (8:00 y al iniciar sesión). No usa Claude.
# Lee con Playwright, sube el resultado a la rama lecturas-pc y GitHub lo aplica y publica solo.
$ErrorActionPreference = 'Continue'
$repo = Join-Path $env:USERPROFILE 'cualmeconviene-pc'
$dia = Get-Date -Format 'dd-MM-yyyy'
$log = Join-Path $repo "lectura-pc.log"
Set-Location $repo
Start-Transcript -Path $log -Append | Out-Null
try {
  git fetch -q origin main
  git fetch -q origin lecturas-pc 2>$null
  if ($LASTEXITCODE -eq 0) { git checkout -q -B lecturas-pc origin/lecturas-pc } else { git checkout -q -B lecturas-pc origin/main }
  if (Test-Path "pc/$dia/informe.json") { Write-Output "Ya se leyó hoy ($dia)."; exit 0 }
  # Herramientas y flujo al día con main
  git checkout -q origin/main -- herramientas .github/workflows/precios-diarios.yml
  node herramientas/playwright/leer.mjs "pc/$dia" falabella paris hp lg easy xiaomi nespresso dolcegusto ripley
  git add "pc/$dia" herramientas .github/workflows/precios-diarios.yml
  git commit -q -m "Lectura del PC $dia"
  for ($i = 0; $i -lt 3; $i++) { git push -q origin lecturas-pc; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 20 }
} finally { Stop-Transcript | Out-Null }
