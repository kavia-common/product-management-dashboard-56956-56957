@echo off
setlocal

REM Tails docker compose logs for the full stack.
REM This script is intentionally located under a user-visible workspace folder.

REM Move to repo root so compose build contexts resolve correctly.
cd /d "%~dp0\..\.."

echo [logs-all] Tailing logs (Ctrl+C to stop)...
docker compose -f "product-management-dashboard-56956-56957\windows-scripts\docker-compose.yml" logs -f
