# =====================================================================
# FarmaControl · INSTALADOR para Windows 10/11 (se ejecuta como administrador)
# =====================================================================
. (Join-Path $PSScriptRoot 'comun.ps1')
$Host.UI.RawUI.WindowTitle = 'FarmaControl - Instalación'

function Paso([string]$t) { Write-Host ''; Write-Host "==> $t" -ForegroundColor Cyan }
function Fallo([string]$t) { Write-Host ''; Write-Host "[!] $t" -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar'; exit 1 }

Write-Host '==========================================================' -ForegroundColor Green
Write-Host '   FarmaControl · instalación del sistema' -ForegroundColor Green
Write-Host '==========================================================' -ForegroundColor Green
Write-Host "Carpeta: $Raiz"

Paso 'Desbloqueando archivos descargados'
Get-ChildItem -Path $Raiz -Recurse -File | Unblock-File -ErrorAction SilentlyContinue

Paso 'Revisando Docker'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fallo 'Docker Desktop no está instalado. Sigue los pasos 1 y 2 del LEEME_INSTALACION y vuelve a ejecutar INSTALAR.bat.'
}
try { Iniciar-Docker 300 | Out-Null } catch { Fallo $_.Exception.Message }
& docker compose version
if ($LASTEXITCODE -ne 0) { Fallo 'Docker Compose no está disponible. Actualiza Docker Desktop.' }

Paso 'Detectando la IP de esta computadora en la red'
$ip = Actualizar-IP
if ($ip) { Write-Host "IP: $ip" } else { Write-Host 'No se detectó red; el sistema funcionará en esta PC y podrás revisarlo después.' -ForegroundColor Yellow }

Paso 'Construyendo y encendiendo el sistema (la primera vez tarda de 5 a 15 minutos)'
Set-Location $Sistema
& docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Fallo 'Error al construir el sistema. Revisa tu conexión a internet y toma foto de esta ventana.' }

Paso 'Permitiendo el acceso desde la red (firewall de Windows)'
$web = Leer-Env 'WEB_PORT' '5010'; $api = Leer-Env 'API_PORT' '8000'
Get-NetFirewallRule -DisplayName 'FarmaControl' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'FarmaControl' -Direction Inbound -Protocol TCP -LocalPort $web, $api -Action Allow -Profile Private, Domain | Out-Null
Write-Host "Puertos $web y $api abiertos para redes privadas."
try {
    $perfil = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -ne 'Disconnected' } | Select-Object -First 1
    if ($perfil -and $perfil.NetworkCategory -eq 'Public') {
        Set-NetConnectionProfile -InterfaceIndex $perfil.InterfaceIndex -NetworkCategory Private
        Write-Host "La red «$($perfil.Name)» se cambió a Privada para permitir el acceso de los demás equipos."
    }
} catch { Write-Host 'No se pudo revisar el tipo de red: ponla como Privada manualmente.' -ForegroundColor Yellow }

Paso 'Evitando que la computadora se suspenda (conectada a la corriente)'
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null

Paso 'Creando accesos directos'
$shell = New-Object -ComObject WScript.Shell
$wscript = Join-Path $env:SystemRoot 'System32\wscript.exe'
function Crear-Acceso([string]$ruta, [string]$destino, [string]$argumentos, [string]$icono, [string]$descripcion) {
    $a = $shell.CreateShortcut($ruta)
    $a.TargetPath = $destino; $a.Arguments = $argumentos; $a.WorkingDirectory = $Herramientas
    $a.IconLocation = $icono; $a.Description = $descripcion; $a.Save()
}
$icono = Join-Path $Herramientas 'farmacontrol.ico'
$iconoApagar = Join-Path $Herramientas 'apagar.ico'
$escritorio = [Environment]::GetFolderPath('CommonDesktopDirectory')
$menu = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'FarmaControl'
New-Item -ItemType Directory -Force -Path $menu | Out-Null
$vbsIniciar = '"' + (Join-Path $Herramientas 'iniciar.vbs') + '"'
$vbsDetener = '"' + (Join-Path $Herramientas 'detener.vbs') + '"'
Crear-Acceso (Join-Path $escritorio 'FarmaControl.lnk') $wscript $vbsIniciar $icono 'Enciende FarmaControl y abre el sistema'
Crear-Acceso (Join-Path $menu 'FarmaControl.lnk') $wscript $vbsIniciar $icono 'Enciende FarmaControl y abre el sistema'
Crear-Acceso (Join-Path $menu 'Apagar FarmaControl.lnk') $wscript $vbsDetener $iconoApagar 'Apaga los contenedores de FarmaControl'
foreach ($b in 'RESPALDO', 'ESTADO', 'VER_DIRECCION') {
    Crear-Acceso (Join-Path $menu "$b.lnk") (Join-Path $Herramientas "$b.bat") '' $icono "FarmaControl - $b"
}
$leeme = Join-Path $Raiz 'LEEME_INSTALACION.pdf'
if (Test-Path $leeme) { Crear-Acceso (Join-Path $menu 'Guía de instalación.lnk') $leeme '' $icono 'Guía de FarmaControl' }
# Arranque automático al iniciar sesión (actualiza la IP y enciende los contenedores)
$inicio = [Environment]::GetFolderPath('CommonStartup')
Crear-Acceso (Join-Path $inicio 'FarmaControl.lnk') $wscript $vbsIniciar $icono 'Inicia FarmaControl al encender'
Write-Host 'Escritorio: «FarmaControl». Menú Inicio: carpeta FarmaControl. También arranca solo al iniciar sesión.'

Paso 'Esperando a que el sistema responda'
if (Esperar-Sistema 300) {
    $puerto = Leer-Env 'WEB_PORT' '5010'
    Write-Host ''
    Write-Host '==========================================================' -ForegroundColor Green
    Write-Host '  ¡FarmaControl está instalado!' -ForegroundColor Green
    Write-Host "  En esta computadora:  http://localhost:$puerto"
    if ($ip) { Write-Host "  Otros equipos:        http://${ip}:$puerto" }
    Write-Host '  Usuario: admin    Contraseña: 131004131004  (cámbiala al entrar)'
    Write-Host '==========================================================' -ForegroundColor Green
    Start-Process "http://localhost:$puerto"
} else {
    Write-Host 'El sistema aún no responde; espera un par de minutos y usa el acceso directo FarmaControl.' -ForegroundColor Yellow
}
Read-Host 'Presiona Enter para cerrar'
