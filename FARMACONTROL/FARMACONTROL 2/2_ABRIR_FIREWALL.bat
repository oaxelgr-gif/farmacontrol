@echo off
chcp 65001 >nul
title FarmaControl - Permitir acceso desde la red
net session >nul 2>&1
if errorlevel 1 (
  echo Pidiendo permisos de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall delete rule name="FarmaControl" >nul 2>&1
netsh advfirewall firewall add rule name="FarmaControl" dir=in action=allow protocol=TCP localport=5010,8000 profile=private,domain
echo.
echo Listo: los equipos de la red ya pueden entrar por los puertos 5010 (sistema) y 8000 (API).
echo Si la red de Windows esta como "Publica", cambiala a "Privada" (Configuracion - Red e Internet - Propiedades).
pause
