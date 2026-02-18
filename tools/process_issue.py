
import os
import sys
import json
import re
import subprocess

# Expected Issue Title Formats:
# "Add Stock: 2330.TW 台積電"
# "Remove Stock: 2330.TW"

def main():
    title = os.environ.get("ISSUE_TITLE", "")
    print(f"Processing Issue: {title}")
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "stocks.json")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except:
        config = {"stocks": {}}

    stocks = config.get("stocks", {})
    changed = False
    
    # 1. Add Stock
    # Regex: Add Stock: (\S+) (.+)
    match_add = re.match(r"Add Stock:\s*(\S+)\s*(.*)", title, re.IGNORECASE)
    if match_add:
        code = match_add.group(1).upper()
        # Auto-fix: Append .TW if it's a 4-digit code (Taiwan Stock)
        if re.match(r"^\d{4}$", code):
            code += ".TW"
            print(f"Auto-appended suffix: {code}")
            
        name = match_add.group(2).strip()
        if not name: name = code
        
        print(f"Adding stock: {code} ({name})")
        stocks[code] = name
        changed = True
        
    # 2. Remove Stock
    # Regex: Remove Stock: (\S+)
    match_remove = re.match(r"Remove Stock:\s*(\S+)", title, re.IGNORECASE)
    if match_remove:
        code = match_remove.group(1).upper()
        print(f"Removing stock: {code}")
        if code in stocks:
            del stocks[code]
            changed = True
        else:
            print("Stock not found.")

    if changed:
        config["stocks"] = stocks
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print("Config updated.")
        
        # Trigger Backfill if Added
        if match_add:
            print("Running backfill...")
            try:
                # Import and run backfill function directly or via subprocess
                # Subprocess is safer to avoid pollution
                subprocess.run(["python", "tools/backfill_dynamic.py"], check=True)
            except Exception as e:
                print(f"Backfill failed: {e}")
                
    else:
        print("No valid command found in title.")

if __name__ == "__main__":
    main()
