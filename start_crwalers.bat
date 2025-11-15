@echo off
chcp 65001 > nul
REM Start all Chrome crawler instances and set environment variables

echo === Starting Chrome instances ===

@REM REM Start Chrome instance 1 - school_data
@REM start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\school_data" --download-default-directory="C:\school_data\data"

echo.
echo === Setting environment variables ===

set SUPABASE_URL=https://grsalbqdpcbdoqbojvcy.supabase.co
set SUPABASE_KEY=sb_secret_SeYI4MzFoiVLbeTmzwzs6Q_JlX7p4Lc

echo Environment variables set

echo.
echo === Configuring Python environment ===

REM Activate conda environment
call conda activate sele
if %errorlevel% neq 0 (
    echo Failed to activate conda environment
    pause
    exit /b 1
)

REM Switch to working directory
cd /d C:\school_data\Profiles_crawler\update_data\
if %errorlevel% neq 0 (
    echo Failed to switch directory
    pause
    exit /b 1
)

echo Conda environment activated: sele
echo Working directory switched: %CD%

echo === Starting all crawlers in parallel ===
echo Each crawler runs in an independent window

REM Start first crawler
start "Crawler_9222" "python" "Curtin University.py" --port 9222

REM Wait 3 seconds to avoid port conflicts
timeout /t 3 /nobreak >nul

echo.
echo ==================================================
echo All crawlers started!
echo Each runs on its own port: 9222, 9223, 9225, 9226
echo.
echo You can close this window, crawlers will keep running
echo ==================================================

