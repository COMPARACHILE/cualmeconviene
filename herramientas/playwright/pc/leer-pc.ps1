# Lectura diaria de las tiendas que bloquean a GitHub, desde el PC del dueño (sin Git, 15-11-2026).
# La corre sola la tarea programada "Precios cualmeconviene" (8:00 y al iniciar sesión). No usa Claude.
# Baja el lector desde GitHub, lee con Playwright usando el Google Chrome instalado y sube el resultado
# a la rama lecturas-pc por la API de GitHub. Allí avisar-pc.yml lanza la aplicación y publicación.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$base = Join-Path $env:USERPROFILE 'cualmeconviene-pc'
$dia = Get-Date -Format 'dd-MM-yyyy'
Set-Location $base
Start-Transcript -Path (Join-Path $base 'lectura-pc.log') -Append | Out-Null
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR((Get-Content (Join-Path $base 'clave.txt') | ConvertTo-SecureString)))
  $H = @{ Authorization = "Bearer $token"; 'User-Agent' = 'cualmeconviene-pc'; Accept = 'application/vnd.github+json' }
  $api = 'https://api.github.com/repos/COMPARACHILE/cualmeconviene/contents'
  # ¿Ya se subió hoy?
  try { Invoke-RestMethod -Headers $H "$api/pc/$dia/informe.json?ref=lecturas-pc" | Out-Null; Write-Output "Ya se leyó hoy ($dia)."; exit 0 } catch {}
  # Lector al día
  $raw = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas'
  New-Item -ItemType Directory -Force -Path 'herramientas\playwright' | Out-Null
  Invoke-WebRequest "$raw/playwright/leer.mjs" -OutFile 'herramientas\playwright\leer.mjs'
  Invoke-WebRequest "$raw/rutas.json" -OutFile 'herramientas\rutas.json'
  $env:CMC_CANAL = 'chrome'
  node herramientas\playwright\leer.mjs "pc\$dia" falabella paris hp lg easy xiaomi nespresso dolcegusto ripley
  # Subir: primero las tiendas, al final informe.json (ese es el que avisa a GitHub)
  $archivos = Get-ChildItem "pc\$dia" -File | Sort-Object { $_.Name -eq 'informe.json' }
  foreach ($f in $archivos) {
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.FullName))
    $body = @{ message = "Lectura del PC $dia ($($f.Name))"; content = $b64; branch = 'lecturas-pc' } | ConvertTo-Json
    for ($i = 0; $i -lt 3; $i++) {
      try { Invoke-RestMethod -Method Put -Headers $H -Body $body -ContentType 'application/json' "$api/pc/$dia/$($f.Name)" | Out-Null; Write-Output "Subido $($f.Name)"; break }
      catch { Write-Output "Error subiendo $($f.Name): $($_.Exception.Message)"; Start-Sleep 15 }
    }
  }
} finally { Stop-Transcript | Out-Null }
