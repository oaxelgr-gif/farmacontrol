. (Join-Path $PSScriptRoot 'comun.ps1')
$destino = Join-Path $Raiz 'respaldos'
New-Item -ItemType Directory -Force -Path $destino | Out-Null
if (-not (Docker-Listo)) { Write-Host 'Docker no está corriendo: enciende FarmaControl primero.' -ForegroundColor Red; exit 1 }
Set-Location $Sistema
$fecha = Get-Date -Format 'yyyyMMdd_HHmm'
& docker compose exec -T db sh -c 'mysqldump -uroot -p$MYSQL_ROOT_PASSWORD --routines --single-transaction medicalife > /tmp/respaldo.sql'
if ($LASTEXITCODE -ne 0) { Write-Host 'No se pudo generar el respaldo. ¿Está encendido el sistema?' -ForegroundColor Red; exit 1 }
$archivo = Join-Path $destino "respaldo_$fecha.sql"
& docker compose cp db:/tmp/respaldo.sql $archivo
Write-Host ''
Write-Host "Respaldo guardado en: $archivo" -ForegroundColor Green
Write-Host 'Cópialo a una USB o a la nube de vez en cuando.'
# Conserva solo los 30 respaldos más recientes
Get-ChildItem $destino -Filter 'respaldo_*.sql' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -ErrorAction SilentlyContinue
