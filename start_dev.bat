@echo off
REM Contract Analysis System - Local Development Start Script
REM This script starts both the backend and frontend servers

echo.
echo ========================================
echo Contract Analysis System - Dev Setup
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then activate with: .venv\Scripts\activate
    echo Then install dependencies: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1] Checking if backend port 8000 is available...
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port 8000 is already in use!
    echo Please close the application using port 8000 or change the port.
    pause
    exit /b 1
)

echo [2] Checking if frontend port 3000 is available...
netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port 3000 is already in use!
    echo Please close the application using port 3000 or change the port.
    pause
    exit /b 1
)

echo [3] Checking .env file...
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please create .env file with your OPENAI_API_KEY
    echo Refer to ENV_TEMPLATE.txt for the template
    pause
    exit /b 1
)

echo [4] Checking frontend/.env.local...
if not exist "frontend\.env.local" (
    echo [ERROR] frontend/.env.local file not found!
    echo Creating frontend/.env.local with default values...
    (
        echo NEXT_PUBLIC_API_URL=http://localhost:8000
    ) > frontend\.env.local
    echo [OK] Created frontend/.env.local
)

echo.
echo ========================================
echo Starting Development Servers...
echo ========================================
echo.
echo [INFO] Backend will start at: http://localhost:8000
echo [INFO] Frontend will start at: http://localhost:3000
echo.
echo Press Ctrl+C in each terminal to stop the server
echo.
pause

REM Activate virtual environment
call .venv\Scripts\activate.bat

echo.
echo ========== BACKEND SERVER STARTING ==========
echo.
python main.py


