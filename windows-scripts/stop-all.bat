@echo off
setlocal

REM Stops services started via docker compose.
REM This script is intentionally located under a user-visible workspace folder.

REM Move to repo root so compose build contexts resolve correctly.
cd /d "%~dp0\..\.."

echo [stop-all] Stopping services...
docker compose -f "product-management-dashboard-56956-56957\windows-scripts\docker-compose.yml" down
if errorlevel 1 (
  echo [stop-all] ERROR: docker compose down failed.
  exit /b 1
)

echo [stop-all] Done.
exit /b 0
