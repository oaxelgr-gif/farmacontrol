@echo off
chcp 65001 >nul
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback' } | Select-Object -First 1).IPAddress"`) do set IP=%%i
echo.
echo Direccion para los demas equipos de la red:
echo.
echo     http://%IP%:5010
echo.
pause
