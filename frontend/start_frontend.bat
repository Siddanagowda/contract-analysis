@echo off
REM Contract Analysis System - Frontend Development Start Script

echo.
echo ========================================
echo Contract Analysis Frontend - Dev Setup
echo ========================================
echo.

echo [1] Checking if port 3000 is available...
netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port 3000 is already in use!
    echo Please close the application using port 3000 or change the port.
    pause
    exit /b 1
)

echo [2] Checking .env.local file...
if not exist ".env.local" (
    echo [WARNING] .env.local not found. Creating with default values...
    (
        echo NEXT_PUBLIC_API_URL=http://localhost:8000
    ) > .env.local
    echo [OK] Created .env.local
)

echo [3] Checking node_modules...
if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Starting Frontend Server...
echo ========================================
echo.
echo Frontend will start at: http://localhost:3000
echo Backend should be running at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.
pause

call npm run dev


