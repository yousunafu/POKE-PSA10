"""
アプリで表示するカード（利益 5001 円以上）について GAS を呼び出し、PSA9 相場を取得して
psa9_stats.json に保存する。

対象: merged_card_data.csv のうち、利益が 5001 円以上の行（表示されるカードと同一）。
     filtered_cards.csv だけだと利益率 20% 未満の 5000〜10000 円帯が抜けるため、
     merged ベースで利益閾値だけかけている。

実行: GAS_PSA9_API_URL を .env に書くか環境変数で設定してから
  python scripts/refresh_psa9_stats.py

プロジェクトルートに .env があれば GAS_PSA9_API_URL を自動で読み込む（Lightsail などで便利）。

cron 例（毎日 3:00）:
  0 3 * * * cd /path/to/project && GAS_PSA9_API_URL=... python scripts/refresh_psa9_stats.py
"""
import json
import os
import sys

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# プロジェクトルートの .env を読み込む（Lightsail 内で実行するとき用）
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip().replace("\r", "")
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip().lstrip("\ufeff").replace("\r", ""), v.strip().replace("\r", "")
                if k and v.startswith('"') and v.endswith('"'):
                    v = v[1:-1].replace('\\"', '"')
                elif k and v.startswith("'") and v.endswith("'"):
                    v = v[1:-1].replace("\\'", "'")
                if k:
                    os.environ.setdefault(k, v)
MERGED_CSV = os.path.join(BASE_DIR, "merged_card_data.csv")
FILTERED_CSV = os.path.join(BASE_DIR, "filtered_cards.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "psa9_stats.json")
BATCH_SIZE = 20
SLEEP_MS = 600
MIN_PROFIT_TO_SHOW = 5001  # フロントと一致（この利益以上のカードを対象）


def _normalize_stock_status(stock_status):
    s = str(stock_status or "")
    if not s or "取得失敗" in s or s.lower() == "nan":
        return "在庫なし"
    return s


def _calculate_profit(row):
    """バックエンドと同一ロジックで利益を計算"""
    stock_status = _normalize_stock_status(row.get("ラッシュ在庫状況", ""))

    if "在庫なし" in stock_status:
        sell_raw = row.get("ラッシュ販売価格")
        if sell_raw is not None and sell_raw != "" and str(sell_raw) != "取得失敗":
            try:
                buy = float(row.get("買取金額", 0) or 0)
                sell = float(str(sell_raw).replace(",", ""))
                if buy > 0 and sell > 0:
                    return int(buy - sell)
            except (ValueError, TypeError):
                pass
        return 0

    expect_raw = row.get("期待利益")
    if expect_raw is not None and expect_raw != "" and str(expect_raw) != "取得失敗":
        try:
            return int(float(str(expect_raw).replace(",", "")))
        except (ValueError, TypeError):
            pass

    try:
        buy = float(row.get("買取金額", 0) or 0)
        sell_raw = row.get("ラッシュ販売価格", 0)
        sell = float(str(sell_raw).replace(",", "")) if sell_raw else 0
        if sell == 0:
            return 0
        return int(buy - sell)
    except (ValueError, TypeError):
        return 0


def load_gas_url():
    url = os.environ.get("GAS_PSA9_API_URL", "").strip()
    if not url:
        print("エラー: GAS_PSA9_API_URL 環境変数を設定してください")
        sys.exit(1)
    return url


def build_card_list():
    """
    取得対象: merged_card_data のうち利益 >= MIN_PROFIT_TO_SHOW のカード（表示と一致）。
    composite_key で重複を除き、id は composite_key（API の psa9_stats 照合に使用）。
    merged が無い場合は filtered_cards のみで従来どおり構築（後方互換）。
    """
    if os.path.exists(MERGED_CSV):
        merged_df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
        seen = set()
        cards = []
        for _, row in merged_df.iterrows():
            profit = _calculate_profit(row)
            if profit < MIN_PROFIT_TO_SHOW:
                continue
            no = str(row.get("No", "") or "").strip()
            cn = str(row.get("card_number", "") or row.get("No", "") or "").strip()
            name = str(row.get("カード名", "") or "").strip()
            rarity = str(row.get("レア", "") or "").strip() if pd.notna(row.get("レア")) else ""
            composite_key = f"{cn}|{name}" if cn and name else None
            if not composite_key or composite_key in seen:
                continue
            seen.add(composite_key)
            cards.append({
                "id": composite_key,
                "card_name": name,
                "card_number": cn,
                "rarity": rarity,
            })
        if cards:
            return cards

    # 後方互換: merged が無い or 対象 0 件のときは filtered_cards のみ
    if not os.path.exists(FILTERED_CSV):
        print(f"エラー: {MERGED_CSV} または {FILTERED_CSV} が必要です")
        sys.exit(1)
    merged_df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig") if os.path.exists(MERGED_CSV) else None
    filtered_df = pd.read_csv(FILTERED_CSV, encoding="utf-8-sig")
    merged_key_to_idx = {}
    if merged_df is not None:
        for i, row in merged_df.iterrows():
            no = str(row.get("No", "") or "").strip()
            cn = str(row.get("card_number", "") or row.get("No", "") or "").strip()
            name = str(row.get("カード名", "") or "").strip()
            key = (no, cn, name)
            if key not in merged_key_to_idx:
                merged_key_to_idx[key] = i
    cards = []
    for filtered_idx, (_, row) in enumerate(filtered_df.iterrows()):
        no = str(row.get("No", "") or "").strip()
        cn = str(row.get("card_number", "") or row.get("No", "") or "").strip()
        name = str(row.get("カード名", "") or "").strip()
        rarity = str(row.get("レア", "") or "").strip() if pd.notna(row.get("レア")) else ""
        key = (no, cn, name)
        if merged_df is not None and merged_key_to_idx.get(key) is None:
            continue
        composite_key = f"{cn}|{name}" if cn and name else f"{no}_{cn}_{filtered_idx}"
        cards.append({
            "id": composite_key,
            "card_name": name,
            "card_number": cn,
            "rarity": rarity,
        })
    return cards


def fetch_batch(gas_url, batch):
    payload = {
        "cards": [
            {
                "id": c["id"],
                "cardName": c["card_name"],
                "cardNum": c["card_number"],
                "rarity": c["rarity"],
            }
            for c in batch
        ]
    }
    r = requests.post(
        gas_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("results", [])


def main():
    gas_url = load_gas_url()
    cards = build_card_list()
    if not cards:
        print("取得対象のカードがありません")
        sys.exit(0)

    print(f"対象: {len(cards)} 件、{BATCH_SIZE} 件ずつバッチ実行")

    # 既存の psa9_stats を読み込み（上書き更新）
    existing = {}
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    total = 0
    for i in range(0, len(cards), BATCH_SIZE):
        batch = cards[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        print(f"  バッチ {batch_num}: {len(batch)} 件...", end=" ", flush=True)
        try:
            results = fetch_batch(gas_url, batch)
            # 結果は送った順で返る。キーは card_number|カード名（バックエンドと一致）
            for j, r in enumerate(results):
                if j >= len(batch):
                    break
                card = batch[j]
                composite_key = f"{card['card_number']}|{card['card_name']}"
                existing[composite_key] = {
                    "yahooAvg": r.get("yahooAvg"),
                    "yahooMedian": r.get("yahooMedian"),
                    "recent1": r.get("recent1"),
                    "recent2": r.get("recent2"),
                    "recent3": r.get("recent3"),
                    "mercariUrl": r.get("mercariUrl"),
                    "hasHistory": r.get("hasHistory"),
                    "error": r.get("error"),
                }
                total += 1
            print("OK")
        except Exception as e:
            print(f"エラー: {e}")
            # ここまでで保存
            break
        # GAS 側のレート制限を考慮（バッチ間に少し待機）
        import time
        time.sleep(1)

    # 旧形式キー（No_cardNumber_idx）を削除し、composite_key 形式のみ残す
    cleaned = {k: v for k, v in existing.items() if "|" in k}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"完了: {total} 件を {OUTPUT_JSON} に保存しました")


if __name__ == "__main__":
    main()
