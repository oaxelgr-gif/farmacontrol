@echo off
chcp 65001 >nul
title FarmaControl - Instalacion
cd /d "%~dp0"
echo ==========================================================
echo   FarmaControl - instalacion / actualizacion
echo ==========================================================
docker version >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [!] Docker Desktop no esta abierto o no esta instalado.
  echo      Abre Docker Desktop, espera a que diga "Engine running" y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
echo.
echo Construyendo y arrancando el sistema (la primera vez tarda varios minutos)...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo  [!] Hubo un error. Toma una foto de esta ventana.
  pause
  exit /b 1
)
echo.
echo Esperando a que la base de datos termine de prepararse...
timeout /t 40 /nobreak >nul
docker compose ps
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback' } | Select-Object -First 1).IPAddress"`) do set IP=%%i
echo.
echo ==========================================================
echo   LISTO
echo   En esta computadora:      http://localhost:5010
echo   Desde otros equipos:      http://%IP%:5010
echo   Usuario: admin            Contrasena: 131004131004
echo   (cambiala en Usuarios despues de entrar)
echo ==========================================================
start "" http://localhost:5010
pause
