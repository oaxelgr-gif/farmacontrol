@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose ps
echo.
echo Ultimos mensajes del sistema:
docker compose logs --tail=30 web
pause
