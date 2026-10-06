. (Join-Path $PSScriptRoot 'comun.ps1')
$ip = Obtener-IP
$puerto = Leer-Env 'WEB_PORT' '5010'
Write-Host ''
if ($ip) {
    Write-Host 'Dirección para los demás equipos de la red:' -ForegroundColor Green
    Write-Host ''
    Write-Host "     http://${ip}:$puerto" -ForegroundColor Cyan
    Write-Host ''
    Write-Host "También la ves en el sistema: Reportes → Acceso desde otros equipos (con código QR)."
} else { Write-Host 'No hay conexión de red detectada.' -ForegroundColor Yellow }
Write-Host ''
