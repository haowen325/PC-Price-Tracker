@echo off
chcp 65001
echo ===================================================
echo      PC Price Tracker - Manual Trigger Tool
echo ===================================================
echo.
echo [1/5] 正在執行：氣象預報 (Weather)...
python tools/weather_scraper.py
echo.

echo [2/5] 正在執行：電腦零組件報價 (PC Price)...
python main.py
echo.

echo [3/5] 正在執行：每日新聞 (News)...
python tools/news_scraper.py
echo.

echo [4/5] 正在執行：遊戲特價 (Games)...
python tools/game_scraper.py
echo.

echo [5/5] 正在執行：金屬行情 (Metal)...
python tools/metal_scraper.py
echo.

echo ===================================================
echo      全部執行完畢！請檢查 LINE 通知。
echo ===================================================
pause
