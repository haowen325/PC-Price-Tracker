@echo off
chcp 65001
setlocal enabledelayedexpansion

:: Get current directory
set "WORK_DIR=%~dp0"
:: Remove trailing backslash
if "%WORK_DIR:~-1%"=="\" set "WORK_DIR=%WORK_DIR:~0,-1%"

echo ===================================================
echo      PC Price Tracker - 自動排程設定精靈
echo ===================================================
echo.
echo 目前工作目錄: %WORK_DIR%
echo Python 路徑: python (請確認已安裝 Python 並加入 PATH)
echo.
echo 正在註冊 5 個排程任務到 Windows 工作排程器...
echo ---------------------------------------------------

:: 1. Weather (06:50)
schtasks /create /tn "PCTracker_Weather" /tr "cmd /c cd /d \"%WORK_DIR%\" && python tools/weather_scraper.py" /sc daily /st 06:50 /f
if %errorlevel% equ 0 ( echo [O] 氣象預報 (06:50) 設定成功 ) else ( echo [X] 氣象預報 設定失敗 - 請以系統管理員身分執行 )

:: 2. PC Price (08:00)
schtasks /create /tn "PCTracker_PCPrice" /tr "cmd /c cd /d \"%WORK_DIR%\" && python main.py" /sc daily /st 08:00 /f
if %errorlevel% equ 0 ( echo [O] 電腦報價 (08:00) 設定成功 ) else ( echo [X] 電腦報價 設定失敗 )

:: 3. News (09:00)
schtasks /create /tn "PCTracker_News" /tr "cmd /c cd /d \"%WORK_DIR%\" && python tools/news_scraper.py" /sc daily /st 09:00 /f
if %errorlevel% equ 0 ( echo [O] 每日新聞 (09:00) 設定成功 ) else ( echo [X] 每日新聞 設定失敗 )

:: 4. Games (12:00)
schtasks /create /tn "PCTracker_Games" /tr "cmd /c cd /d \"%WORK_DIR%\" && python tools/game_scraper.py" /sc daily /st 12:00 /f
if %errorlevel% equ 0 ( echo [O] 遊戲特價 (12:00) 設定成功 ) else ( echo [X] 遊戲特價 設定失敗 )

:: 5. Metal (18:00)
schtasks /create /tn "PCTracker_Metal" /tr "cmd /c cd /d \"%WORK_DIR%\" && python tools/metal_scraper.py" /sc daily /st 18:00 /f
if %errorlevel% equ 0 ( echo [O] 金屬行情 (18:00) 設定成功 ) else ( echo [X] 金屬行情 設定失敗 )

echo.
echo ---------------------------------------------------
echo 設定完成！
echo 注意：電腦必須在上述時間處於「開機」或「睡眠」狀態才能運作。
echo (若要移除排程，請開啟「工作排程器」刪除 PCTracker_ 開頭的任務)
echo.
pause
