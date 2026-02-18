@echo off
echo ===================================================
echo      PC Price Tracker - 環境安裝腳本
echo ===================================================
echo.
echo 正在安裝必要的 Python 套件...
pip install -r requirements.txt
echo.
echo 正在安裝 Playwright 瀏覽器核心...
playwright install
echo.
echo ===================================================
echo      安裝完成！您可以開始使用 setup_auto_schedule.bat 了。
echo ===================================================
pause
