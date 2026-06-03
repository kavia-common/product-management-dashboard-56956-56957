@echo off
setlocal enabledelayedexpansion

REM Starts db + backend + frontend using a user-reachable compose file in this folder.
REM Requirements:
REM  - Docker Desktop running
REM  - docker compose v2 available (command: "docker compose")
REM
REM This script is intentionally located under a user-visible workspace folder.

REM Move to repo root so compose build contexts resolve correctly.
cd /d "%~dp0\..\.."

echo [start-all] Building and starting services...
docker compose -f "product-management-dashboard-56956-56957\windows-scripts\docker-compose.yml" up -d --build
if errorlevel 1 (
  echo [start-all] ERROR: docker compose up failed.
  exit /b 1
)

echo.
echo [start-all] Services started.
echo   - Frontend: http://localhost:3000
echo   - Backend : http://localhost:8000  (docs: http://localhost:8000/docs)
echo   - DB      : localhost:5001 (mapped to container 5432)
echo.
echo [start-all] Tip: View logs with: product-management-dashboard-56956-56957\windows-scripts\logs-all.bat
exit /b 0
