@echo off
chcp 65001 >nul
title FarmaControl - Instalador
rem Se necesita administrador para el firewall y los accesos directos
net session >nul 2>&1
if errorlevel 1 (
  echo Pidiendo permisos de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0herramientas\instalar.ps1"
