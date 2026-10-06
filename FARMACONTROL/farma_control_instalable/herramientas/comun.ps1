# =====================================================================
# FarmaControl · funciones compartidas por el instalador y el acceso directo
# =====================================================================
# 'Continue': docker escribe su progreso en la salida de errores y no debe detener el script;
# los fallos se revisan con $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$Herramientas = $PSScriptRoot
$Raiz         = Split-Path -Parent $Herramientas
$Sistema      = Join-Path $Raiz 'sistema'
$ArchivoEnv   = Join-Path $Sistema '.env'
$Bitacora     = Join-Path $Herramientas 'ultimo_inicio.log'

function Escribir-Log([string]$texto) {
    $linea = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $texto
    Add-Content -Path $Bitacora -Value $linea -Encoding UTF8
    Write-Host $texto
}

function Leer-Env([string]$clave, [string]$defecto = '') {
    if (-not (Test-Path $ArchivoEnv)) { return $defecto }
    foreach ($l in [IO.File]::ReadAllLines($ArchivoEnv)) {
        if ($l -match "^\s*$([regex]::Escape($clave))\s*=(.*)$") { $v = $Matches[1].Trim(); if ($v) { return $v } }
    }
    return $defecto
}

function Guardar-Env([hashtable]$valores) {
    $lineas = New-Object System.Collections.Generic.List[string]
    if (Test-Path $ArchivoEnv) { $lineas.AddRange([string[]][IO.File]::ReadAllLines($ArchivoEnv)) }
    foreach ($clave in $valores.Keys) {
        $hecho = $false
        for ($i = 0; $i -lt $lineas.Count; $i++) {
            if ($lineas[$i] -match "^\s*$([regex]::Escape($clave))\s*=") { $lineas[$i] = "$clave=$($valores[$clave])"; $hecho = $true }
        }
        if (-not $hecho) { $lineas.Add("$clave=$($valores[$clave])") }
    }
    # UTF-8 sin BOM y saltos de línea LF: así lo lee Docker Compose sin problemas
    [IO.File]::WriteAllText($ArchivoEnv, (($lineas.ToArray() -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding $false))
}

function Obtener-IP {
    # La interfaz con puerta de enlace es la conexión real a la red (Wi-Fi o cable)
    try {
        $conf = Get-NetIPConfiguration -ErrorAction Stop |
            Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|VirtualBox|VMware' } |
            Select-Object -First 1
        if ($conf) { return ($conf.IPv4Address | Select-Object -First 1).IPAddress }
    } catch { }
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|Loopback' } |
        Select-Object -First 1
    if ($ip) { return $ip.IPAddress }
    return ''
}

function Docker-Listo {
    try { & docker info --format '{{.ServerVersion}}' 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

function Iniciar-Docker([int]$segundos = 240) {
    if (Docker-Listo) { return $true }
    $candidatos = @()
    foreach ($base in @($env:ProgramFiles, $env:ProgramW6432, $env:LOCALAPPDATA)) {
        if ($base) { $candidatos += (Join-Path $base 'Docker\Docker\Docker Desktop.exe') }
    }
    $exe = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) { throw 'No se encontró Docker Desktop. Instálalo (ver LEEME_INSTALACION).' }
    Escribir-Log 'Abriendo Docker Desktop...'
    Start-Process -FilePath $exe | Out-Null
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        Start-Sleep -Seconds 4
        if (Docker-Listo) { return $true }
    }
    throw 'Docker Desktop no terminó de arrancar. Ábrelo manualmente, espera a "Engine running" y vuelve a intentar.'
}

function Actualizar-IP {
    $ip = Obtener-IP
    $apiPort = Leer-Env 'API_PORT' '8000'
    $anterior = Leer-Env 'HOST_IP' ''
    $publica = if ($ip) { "http://${ip}:$apiPort" } else { "http://localhost:$apiPort" }
    if ($ip -ne $anterior -or (Leer-Env 'API_PUBLIC_URL') -ne $publica) {
        Guardar-Env @{ HOST_IP = $ip; API_PUBLIC_URL = $publica }
        Escribir-Log "IP de la red: $ip (antes: $anterior)"
    }
    return $ip
}

function Esperar-Sistema([int]$segundos = 240) {
    $puerto = Leer-Env 'WEB_PORT' '5010'
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$puerto/health" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}
