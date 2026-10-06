# =====================================================================
# FarmaControl · ACCESO DIRECTO: enciende Docker, los contenedores y abre el sistema
# (se ejecuta oculto desde iniciar.vbs)
# =====================================================================
. (Join-Path $PSScriptRoot 'comun.ps1')
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$aviso = New-Object System.Windows.Forms.NotifyIcon
try { $aviso.Icon = New-Object System.Drawing.Icon (Join-Path $Herramientas 'farmacontrol.ico') } catch { $aviso.Icon = [System.Drawing.SystemIcons]::Information }
$aviso.Text = 'FarmaControl'
$aviso.Visible = $true
function Avisar([string]$titulo, [string]$texto, [string]$tipo = 'Info') {
    $aviso.BalloonTipTitle = $titulo; $aviso.BalloonTipText = $texto
    $aviso.BalloonTipIcon = $tipo; $aviso.ShowBalloonTip(5000)
}

try {
    Escribir-Log '=== Inicio de FarmaControl ==='
    Avisar 'FarmaControl' 'Iniciando el sistema, espera un momento...'
    Iniciar-Docker | Out-Null
    $ip = Actualizar-IP
    Set-Location $Sistema
    Escribir-Log 'Encendiendo contenedores...'
    & docker compose up -d 2>&1 | ForEach-Object { Escribir-Log "$_" }
    if ($LASTEXITCODE -ne 0) { throw 'docker compose no pudo encender los contenedores (ver herramientas\ultimo_inicio.log).' }
    if (-not (Esperar-Sistema 240)) { throw 'El sistema tardó demasiado en responder. Revisa ESTADO en el menú Inicio.' }
    $puerto = Leer-Env 'WEB_PORT' '5010'
    Start-Process "http://localhost:$puerto"
    $red = if ($ip) { "Otros equipos: http://${ip}:$puerto" } else { 'Sin red detectada' }
    Escribir-Log "Sistema listo. $red"
    Avisar 'FarmaControl listo' $red
    Start-Sleep -Seconds 6
} catch {
    Escribir-Log "ERROR: $($_.Exception.Message)"
    [System.Windows.Forms.MessageBox]::Show("No se pudo iniciar FarmaControl:`n`n$($_.Exception.Message)", 'FarmaControl', 'OK', 'Error') | Out-Null
} finally {
    $aviso.Visible = $false; $aviso.Dispose()
}
