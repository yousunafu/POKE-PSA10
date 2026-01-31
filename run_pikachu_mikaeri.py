#!/usr/bin/env python3
"""
ピカチュウ(見返り美人) 227/S-P だけをカードラッシュで検索して結果を出力する。

- 本番の merged_card_data.csv は上書きしない（出力先: merged_card_data_pikachu_mikaeri.csv）
- 実行: python3 run_pikachu_mikaeri.py
"""
import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrape_rush import scrape_cardrush_data

if __name__ == "__main__":
    input_csv = "otachu_psa10.csv"
    output_csv = "merged_card_data_pikachu_mikaeri.csv"
    card_number = "227/S-P"

    print("=" * 50)
    print(f"ピカチュウ(見返り美人) {card_number} のみ実行")
    print(f"出力先: {output_csv}")
    print("=" * 50)

    scrape_cardrush_data(
        input_csv=input_csv,
        output_csv=output_csv,
        debug_mode=False,
        filter_card_number=card_number,
    )

    print("\n完了。結果は merged_card_data_pikachu_mikaeri.csv を確認してください。")
