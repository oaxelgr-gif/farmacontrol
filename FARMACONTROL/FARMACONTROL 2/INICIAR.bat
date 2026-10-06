@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose up -d
start "" http://localhost:5010
