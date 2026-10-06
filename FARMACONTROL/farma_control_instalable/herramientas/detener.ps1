# FarmaControl · apaga los contenedores (los datos se conservan)
. (Join-Path $PSScriptRoot 'comun.ps1')
Add-Type -AssemblyName System.Windows.Forms
try {
    if (-not (Docker-Listo)) { [System.Windows.Forms.MessageBox]::Show('FarmaControl ya está apagado (Docker no está corriendo).', 'FarmaControl') | Out-Null; exit }
    Set-Location $Sistema
    & docker compose stop 2>&1 | ForEach-Object { Escribir-Log "$_" }
    [System.Windows.Forms.MessageBox]::Show('FarmaControl se apagó. Los datos están guardados.', 'FarmaControl') | Out-Null
} catch {
    [System.Windows.Forms.MessageBox]::Show("Error al apagar: $($_.Exception.Message)", 'FarmaControl', 'OK', 'Error') | Out-Null
}
