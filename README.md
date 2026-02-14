# PC Price Monitor Bot (LINE OA Edition)

這是一個自動化機器人，用於監控台灣「原價屋」的特定電腦零件價格。它會每天自動爬取價格，將數據存入 Google Sheets，並透過 LINE 官方帳號發送包含趨勢圖與價格變動的通知。

## 功能特色
- **專注原價屋 (Coolpc)**: 確保數據來源穩定可靠。
- **智慧通知 (Smart Alerts)**: 自動比較昨日價格：
    - 🟢 **價格持平**: 顯示綠色通知，附上趨勢圖報平安。
    - 🔴 **價格上漲**: 顯示紅色通知，標示漲幅。
    - 🔵 **價格下跌**: 顯示藍色通知，標示跌幅。
- **精準匹配**: 針對特定零件型號 (Core Ultra 7 265KF, Z890-PRO WIFI, LancerBlade 64G 等) 進行追蹤。
- **數據存儲**: Google Sheets。
- **視覺化報表**: 
    - 每日自動生成價格趨勢圖 (ImgBB 託管)。
    - 內建「查看詳細清單」按鈕，直接跳轉至 Google Sheets。

## 安裝與設定

### 1. 取得 API 金鑰

#### A. Google Sheets API
1.  到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案並啟用 **Google Sheets API** 和 **Google Drive API**。
2.  建立 **Service Account** 並下載 JSON 金鑰檔案。
3.  建立新的 Google Sheet，將 Service Account email 加入為 **編輯者 (Editor)**。
4.  複製 Google Sheet 的公開網址，這將用於 LINE 的按鈕連結。

#### B. LINE Messaging API (官方帳號)
1.  登入 [LINE Developers Console](https://developers.line.biz/)。
2.  建立一個新的 **Provider**，然後建立一個 **Messaging API** Channel。
3.  在 **Messaging API** 分頁中，生成並複製 **Channel Access Token (Long-lived)**。
4.  用您的手機加入該 LINE 官方帳號好友。
5.  獲取您的 **User ID** (在 Basic settings 下方)。

#### C. ImgBB API Key (用於圖片託管)
1.  前往 [ImgBB API](https://api.imgbb.com/)。
2.  點選 **Get API Key** (需註冊/登入帳號)。
3.  複製您的 **API Key**。

### 2. GitHub Actions Secrets 設定
在 GitHub Repo 的 **Settings** -> **Secrets and variables** -> **Actions** 中新增以下 Secrets：

| Secret Name |值及說明 |
| :--- | :--- |
| `GSPREAD_JSON` | Google Service Account JSON 的完整內容。 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API 的 Channel Access Token。 |
| `LINE_USER_ID` | 您的 LINE User ID (接收通知用)。 |
| `IMGBB_API_KEY` | ImgBB 的 API Key。 |
| `GOOGLE_SHEET_URL` | Google Sheet 的完整網址。 |

## 執行
程式會於每天台灣時間早上 08:00 (UTC 00:00) 自動執行。您也可以在 GitHub Actions 頁面手動觸發 `Daily PC Price Scrape` 工作流程。

## 疑難排解
- **LINE 收不到圖片**: 檢查 `IMGBB_API_KEY` 是否正確。若圖片上傳失敗，機器人會改發純文字通知。
- **爬蟲找不到商品**: 原價屋網頁結構若有變動，請檢查 GitHub Actions 的 Log 查看是哪個商品抓不到，可能需要更新 `main.py` 中的 `TARGETS` 列表關鍵字。

