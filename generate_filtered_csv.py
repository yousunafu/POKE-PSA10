"""
merged_card_data.csv を読み込み、フィルタ条件を満たすカードを抽出して
鑑定費・手取り利益・利益率・月換算利益率を追加した filtered_cards.csv を生成する。

実行順: scrape_otachu.py → scrape_rush.py → generate_filtered_csv.py
"""
import csv
import os
import sys

# 鑑定費・利益率の定数（フロントの profitCalc.js と同一）
GRADE_FEE_STANDARD = 3000
GRADE_FEE_EXPRESS = 10000
MIN_PROFIT_TO_SHOW = 5001
EXPRESS_THRESHOLD = 30000
DEFAULT_PROFIT_RATE_MIN = 20


def get_grading_fee(max_profit):
    """予想最大利益に応じた鑑定費を返す。5,000円以下なら None（非表示対象）"""
    p = int(max_profit) if max_profit is not None and max_profit != "" else 0
    if p < MIN_PROFIT_TO_SHOW:
        return None
    if p >= EXPRESS_THRESHOLD:
        return GRADE_FEE_EXPRESS
    return GRADE_FEE_STANDARD


def _normalize_stock_status(stock_status):
    """バックエンドと同じ正規化"""
    s = str(stock_status or "")
    if not s or "取得失敗" in s or s.lower() == "nan":
        return "在庫なし"
    return s


def _calculate_profit(row):
    """
    バックエンド backend/main.py の calculate_profit と同一ロジック。
    在庫なしの場合は期待利益を使わず買取-販売で計算する。
    """
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


def calc_card_profit(row):
    """
    1行のデータから鑑定・利益を計算。
    Returns: dict with grading_fee, net_profit, profit_rate, monthly_rate
    または None（非表示対象の場合）
    """
    max_profit = _calculate_profit(row)

    buy_raw = row.get("買取金額")
    buy = float(buy_raw) if buy_raw not in (None, "", "取得失敗") else 0
    sell_raw = row.get("ラッシュ販売価格")
    sell = 0
    if sell_raw is not None and sell_raw != "" and str(sell_raw) != "取得失敗":
        try:
            sell = float(str(sell_raw).replace(",", ""))
        except (ValueError, TypeError):
            pass

    grading_fee = get_grading_fee(max_profit)
    if grading_fee is None:
        return None

    net_profit = max_profit - grading_fee
    total_cost = sell + grading_fee
    # フロントと同一: 丸めずに計算（フィルタ比較用）。CSV出力時に丸める
    profit_rate_raw = (net_profit / total_cost) * 100 if total_cost > 0 else 0
    profit_rate_display = round(profit_rate_raw, 1)
    monthly_rate = round(profit_rate_raw / 2, 1) if grading_fee == GRADE_FEE_STANDARD else None

    return {
        "鑑定費": grading_fee,
        "手取り利益": net_profit,
        "利益率": profit_rate_display,
        "利益率_比較用": profit_rate_raw,
        "月換算利益率": monthly_rate,
    }


def generate_filtered_csv(
    input_csv="merged_card_data.csv",
    output_csv="filtered_cards.csv",
    profit_rate_min=DEFAULT_PROFIT_RATE_MIN,
):
    """
    フィルタ済みCSVを生成
    - 予想最大利益 5,001円以上
    - 利益率 profit_rate_min 以上
    - 新列: 鑑定費, 手取り利益, 利益率, 月換算利益率
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(base_dir, input_csv)
    output_path = os.path.join(base_dir, output_csv)

    if not os.path.exists(input_path):
        print(f"エラー: {input_csv} が見つかりません")
        return 1

    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # 新列を追加
    new_cols = ["鑑定費", "手取り利益", "利益率", "月換算利益率"]
    out_fieldnames = list(fieldnames) + new_cols

    filtered_rows = []
    for row in rows:
        info = calc_card_profit(row)
        if info is None:
            continue
        # フロントと同じく丸めずに比較（19.999... < 20 で除外）
        if info["利益率_比較用"] < profit_rate_min:
            continue
        row_copy = dict(row)
        row_copy["鑑定費"] = info["鑑定費"]
        row_copy["手取り利益"] = info["手取り利益"]
        row_copy["利益率"] = info["利益率"]
        row_copy["月換算利益率"] = info.get("月換算利益率", "") if info.get("月換算利益率") is not None else ""
        filtered_rows.append(row_copy)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filtered_rows)

    print(f"filtered_cards.csv を生成しました: {len(filtered_rows)} 件")
    return 0


def main():
    profit_rate_min = DEFAULT_PROFIT_RATE_MIN
    if "--profit-rate" in sys.argv:
        idx = sys.argv.index("--profit-rate")
        if idx + 1 < len(sys.argv):
            try:
                profit_rate_min = int(sys.argv[idx + 1])
            except ValueError:
                pass

    sys.exit(generate_filtered_csv(profit_rate_min=profit_rate_min))


if __name__ == "__main__":
    main()
