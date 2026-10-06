@echo off
chcp 65001 >nul
title FarmaControl - Respaldo
cd /d "%~dp0"
if not exist respaldos mkdir respaldos
for /f "usebackq delims=" %%f in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"`) do set FECHA=%%f
docker compose exec -T db sh -c "mysqldump -uroot -p$MYSQL_ROOT_PASSWORD --routines --single-transaction medicalife > /tmp/respaldo.sql"
if errorlevel 1 (
  echo [!] No se pudo generar el respaldo. Revisa que el sistema este encendido.
  pause
  exit /b 1
)
docker compose cp db:/tmp/respaldo.sql "respaldos\respaldo_%FECHA%.sql"
echo.
echo Respaldo guardado en: respaldos\respaldo_%FECHA%.sql
echo Copialo a una USB o a la nube de vez en cuando.
pause
