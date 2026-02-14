# PC Price Monitor Bot (LINE OA Edition)

這是一個自動化機器人，用於監控台灣「原價屋」與「欣亞數位」的特定電腦零件價格。它會每天自動爬取價格，將數據存入 Google Sheets，並透過 LINE 官方帳號 (Official Account) 發送包含趨勢圖與詳細報表連結的通知。

## 功能特色
- **自動爬取**: 支援 Coolpc (原價屋) 與 Sinya (欣亞) 網站。
- **精準匹配**: 針對特定零件型號 (Core Ultra 7 265KF, Z890-PRO WIFI 等) 進行追蹤。
- **數據存儲**: Google Sheets。
- **視覺化通知**: 
    - 透過 Imgur 自動託管趨勢圖。
    - 透過 LINE Flex Message 發送圖文並茂的價格報告。
    - 內建「查看詳細清單」按鈕，直接跳轉至 Google Sheets。

## 安裝與設定

### 1. 取得 API 金鑰

#### A. Google Sheets API
1.  到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案並啟用 **Google Sheets API** 和 **Google Drive API**。
2.  建立 **Service Account** 並下載 JSON 金鑰檔案。
3.  建立新的 Google Sheet，將 Service Account email 加入為 **編輯者 (Editor)**。
4.  複製 Google Sheet 的公開網址 (或是您能檢視的網址)，這將用於 LINE 的按鈕連結。

#### B. LINE Messaging API (官方帳號)
1.  登入 [LINE Developers Console](https://developers.line.biz/)。
2.  建立一個新的 **Provider**，然後建立一個 **Messaging API** Channel。
3.  在 **Messaging API** 分頁中，生成並複製 **Channel Access Token (Long-lived)**。
4.  用您的手機加入該 LINE 官方帳號好友。
5.  獲取您的 **User ID**:
    - 在 **Basic settings** 分頁下方可以看到 `Your User ID` (通常是 U 開頭的一長串字串)。
    - *注意: 這不是 Channel ID，是您個人的 User ID。*

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
| `IMGBB_API_KEY` | ImgBB 的 API Key。 (原 Imgur 服務替換) |
| `GOOGLE_SHEET_URL` | Google Sheet 的網址 (例如 `https://docs.google.com/spreadsheets/d/XXXX...`)。 |

## 執行
程式會於每天台灣時間早上 10:00 自動執行。您也可以在 Actions 頁面手動觸發 `Daily PC Price Scrape` 工作流程。

## 疑難排解
- **LINE 收不到圖片**: 檢查 `IMGBB_API_KEY` 是否正確。若圖片上傳失敗，機器人會改發純文字通知。
- **爬蟲找不到商品**: 原價屋與欣亞的網頁結構可能變動，請檢查 GitHub Actions 的 Log 查看是哪個商品抓不到，可能需要更新 `TARGETS` 列表中的關鍵字。
