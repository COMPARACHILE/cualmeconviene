# Lectura de las tiendas que bloquean a GitHub, desde el PC del dueño (sin Git; cada 2 horas desde el 17-11-2026).
# La corre sola la tarea programada "Precios cualmeconviene" (8:00 a 22:00 cada 2 horas, y al iniciar sesión). No usa Claude.
# Baja el lector desde GitHub, lee con Playwright usando el Google Chrome instalado y sube el resultado
# a la rama lecturas-pc (pc/<dd-mm-aaaa>-<HH>h/) por la API de GitHub. Allí avisar-pc.yml lanza la lectura completa,
# que suma estas tiendas, aplica y publica.
# Se actualiza solo: si en GitHub hay una versión nueva de este archivo, la deja lista para la próxima vuelta.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$base = Join-Path $env:USERPROFILE 'cualmeconviene-pc'
$dia = Get-Date -Format 'dd-MM-yyyy'
$hora = [int](Get-Date -Format 'HH'); $hora = $hora - ($hora % 2)
$vuelta = '{0}-{1:D2}h' -f $dia, $hora
Set-Location $base
Start-Transcript -Path (Join-Path $base 'lectura-pc.log') -Append | Out-Null
try {
  $raw = 'https://raw.githubusercontent.com/COMPARACHILE/cualmeconviene/main/herramientas'
  # Esperar internet hasta 15 minutos: al prender el PC la red tarda en conectarse
  # (el 18-11-2026 la vuelta de las 8 se perdió por "No se puede resolver el nombre remoto").
  for ($n = 0; $n -lt 30; $n++) {
    try { [Net.Dns]::GetHostEntry('api.github.com') | Out-Null; break } catch { if ($n -eq 0) { Write-Output 'Sin internet todavía: espero hasta 15 minutos.' }; Start-Sleep 30 }
  }
  # Este mismo script al día (vale desde la próxima vuelta)
  try {
    $nuevo = (Invoke-WebRequest "$raw/playwright/pc/leer-pc.ps1?$(Get-Random)" -UseBasicParsing).Content
    $actual = Get-Content (Join-Path $base 'leer-pc.ps1') -Raw
    # Se compara sin la marca BOM ni saltos de línea finales, para no reescribirlo en cada vuelta
    if ($nuevo -and $nuevo.Length -gt 500 -and $nuevo.TrimStart([char]0xFEFF).TrimEnd() -ne ($actual -replace "`r`n", "`n").TrimStart([char]0xFEFF).TrimEnd()) { Set-Content (Join-Path $base 'leer-pc.ps1') $nuevo -Encoding UTF8; Write-Output 'leer-pc.ps1 actualizado' }
  } catch {}
  if ($hora -lt 8 -or $hora -gt 22) { Write-Output "Fuera del horario de lectura ($vuelta)."; exit 0 }
  $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR((Get-Content (Join-Path $base 'clave.txt') | ConvertTo-SecureString)))
  $H = @{ Authorization = "Bearer $token"; 'User-Agent' = 'cualmeconviene-pc'; Accept = 'application/vnd.github+json' }
  $api = 'https://api.github.com/repos/COMPARACHILE/cualmeconviene/contents'
  # ¿Ya se subió esta vuelta?
  # (un 404 aquí es lo normal: quiere decir que falta leerla)
  try { Invoke-RestMethod -Headers $H "$api/pc/$vuelta/informe.json?ref=lecturas-pc" | Out-Null; Write-Output "Ya se leyó esta vuelta ($vuelta)."; exit 0 } catch { Write-Output "Leyendo la vuelta $vuelta" }
  # Lector al día
  New-Item -ItemType Directory -Force -Path 'herramientas\playwright' | Out-Null
  Invoke-WebRequest "$raw/playwright/leer.mjs" -OutFile 'herramientas\playwright\leer.mjs'
  Invoke-WebRequest "$raw/rutas.json" -OutFile 'herramientas\rutas.json'
  try { Invoke-WebRequest "$raw/nombres.json" -OutFile 'herramientas\nombres.json' } catch {}
  $env:CMC_CANAL = 'chrome'
  node herramientas\playwright\leer.mjs "pc\$vuelta" falabella paris hp lg easy xiaomi nespresso dolcegusto ripley
  # Subir: primero las tiendas, al final informe.json (ese es el que avisa a GitHub)
  $archivos = Get-ChildItem "pc\$vuelta" -File | Sort-Object { $_.Name -eq 'informe.json' }
  foreach ($f in $archivos) {
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.FullName))
    $body = @{ message = "Lectura del PC $vuelta ($($f.Name))"; content = $b64; branch = 'lecturas-pc' } | ConvertTo-Json
    for ($i = 0; $i -lt 3; $i++) {
      try { Invoke-RestMethod -Method Put -Headers $H -Body $body -ContentType 'application/json' "$api/pc/$vuelta/$($f.Name)" | Out-Null; Write-Output "Subido $($f.Name)"; break }
      catch { Write-Output "Error subiendo $($f.Name): $($_.Exception.Message)"; Start-Sleep 15 }
    }
  }
} finally { Stop-Transcript | Out-Null }
