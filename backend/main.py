import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# プロジェクトルートの CSV とリンクマッピングを参照
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "merged_card_data.csv")
POKECA_LINKS_PATH = os.path.join(BASE_DIR, "pokeca_chart_links.json")


def load_pokeca_links() -> dict:
    """pokeca_chart_links.json を読み込み"""
    if not os.path.exists(POKECA_LINKS_PATH):
        return {}
    try:
        with open(POKECA_LINKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def normalize_stock_status(stock_status):
    s = str(stock_status)
    if pd.isna(stock_status) or stock_status == "" or "取得失敗" in s or s.lower() == "nan":
        return "在庫なし"
    return s


def calculate_profit(row):
    stock_status = normalize_stock_status(row.get("ラッシュ在庫状況", ""))

    if "在庫なし" in stock_status:
        sell_price = row.get("ラッシュ販売価格", 0)
        if pd.notna(sell_price) and sell_price != 0:
            try:
                buy_price = float(row.get("買取金額", 0))
                sell_price = float(sell_price)
                if buy_price > 0 and sell_price > 0:
                    return buy_price - sell_price
            except Exception:
                pass
        return 0

    if pd.notna(row.get("期待利益")) and row.get("期待利益") != "":
        try:
            return float(row["期待利益"])
        except Exception:
            pass

    try:
        buy_price = float(row.get("買取金額", 0))
        sell_price = float(row.get("ラッシュ販売価格", 0))
        if sell_price == 0:
            return 0
        return buy_price - sell_price
    except Exception:
        return 0


@app.get("/api/cards")
def get_cards():
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=500, detail=f"CSV not found: {CSV_PATH}")
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    pokeca_links = load_pokeca_links()
    processed_data = []
    for i, row in df.iterrows():
        profit = calculate_profit(row)
        stock_norm = normalize_stock_status(row.get("ラッシュ在庫状況"))
        card_number = (row.get("card_number", "") or row.get("No", "") or "").strip()
        card_name = (row.get("カード名") or "不明").strip()
        composite_key = f"{card_number}|{card_name}" if card_number and card_name else None
        pokeca_url = None
        if composite_key and composite_key in pokeca_links:
            pokeca_url = pokeca_links[composite_key]
        elif card_number and card_number in pokeca_links:
            pokeca_url = pokeca_links[card_number]

        buy_val = row.get("買取金額", 0)
        sell_val = row.get("ラッシュ販売価格", 0)
        item = {
            "id": f"{row.get('No', '')}_{row.get('card_number', '')}_{i}",
            "no": row.get("No"),
            "card_name": card_name,
            "card_number": card_number,
            "buy_price": float(buy_val) if pd.notna(buy_val) and buy_val != "" else 0,
            "sell_price": float(sell_val) if pd.notna(sell_val) and sell_val != "" else 0,
            "stock_original": row.get("ラッシュ在庫状況"),
            "stock_normalized": stock_norm,
            "image_url": row.get("画像URL") if pd.notna(row.get("画像URL")) and str(row.get("画像URL")).strip() and str(row.get("画像URL")) != "取得失敗" else None,
            "profit": profit,
            "pokeca_chart_url": pokeca_url,
        }
        processed_data.append(item)

    return processed_data
