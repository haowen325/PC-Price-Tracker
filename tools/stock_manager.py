
import json
import os
import sys

# Windows console encoding fix
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stocks.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"stocks": {}}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"stocks": {}}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"✅ 設定已儲存: {CONFIG_PATH}")

def main():
    while True:
        config = load_config()
        stocks = config.get("stocks", {})
        
        print("\n" + "="*30)
        print("📈 股票清單管理工具")
        print("="*30)
        print("目前追蹤的股票:")
        if not stocks:
            print("  (尚無資料)")
        else:
            for code, name in stocks.items():
                print(f"  [{code}] {name}")
        
        print("\n選項:")
        print("1. 新增股票")
        print("2. 刪除股票")
        print("3. 保存並退出")
        choice = input("請輸入選項 (1-3): ").strip()
        
        if choice == "1":
            code = input("請輸入股票代號 (如 2330.TW): ").strip().upper()
            if not code: continue
            if not (code.endswith(".TW") or code.endswith(".TWO")):
                print("⚠️ 提示: 台灣股票通常以 .TW (上市) 或 .TWO (上櫃) 結尾。")
                confirm = input("確定要使用這個代號嗎? (Y/n): ").strip().lower()
                if confirm == "n": continue
                
            name = input(f"請輸入顯示名稱 (如 台積電): ").strip()
            if not name: name = code
            
            stocks[code] = name
            config["stocks"] = stocks
            save_config(config)
            print(f"✅ 已新增: {name} ({code})")
            
        elif choice == "2":
            code = input("請輸入要刪除的代號: ").strip().upper()
            if code in stocks:
                del stocks[code]
                config["stocks"] = stocks
                save_config(config)
                print(f"🗑️ 已刪除: {code}")
            else:
                print("❌ 找不到該代號。")
                
        elif choice == "3":
            print("👋 再見！記得執行爬蟲更新資料喔。")
            break
        else:
            print("無效輸入。")

if __name__ == "__main__":
    main()
