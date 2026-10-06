@echo off
chcp 65001 >nul
cd /d "%~dp0..\sistema"
docker compose ps
echo.
echo Ultimos mensajes del sistema:
docker compose logs --tail=30 web
echo.
echo Bitacora del acceso directo: herramientas\ultimo_inicio.log
pause
