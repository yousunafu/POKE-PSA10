#!/usr/bin/env python3
"""
スプレッドシート（POKE PSA9 SOLD）を CSV でエクスポートしたファイルから、
ebay_links.json を一括生成する。

使い方:
  1. Google スプレッドシートで「ファイル → ダウンロード → カンマ区切り値 (.csv)」
  2. 保存した CSV のパスを指定して実行:

     python scripts/build_ebay_links.py sheet_export.csv

  3. オプション:
     --url-column "列名"      … eBay URL が入っている列名（省略時は先頭の http を含む列を探す）
     --english-name-column "列名" … 英名列の名前を指定
     --english-name-index N   … 英名列の 0 始まりインデックス（P列なら 16）。未指定時は「View Sold Prices」の左隣を自動検出
     --output path            … 出力 JSON パス

キー規則:
  - 同じ card_number が1件だけ → キーは "766/742"
  - 同じ card_number が複数（例: 173/086 が Nの筋書き と トウコ）→ キーは "173/086|Nの筋書き"
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "ebay_links.json")
EBAY_BASE = "https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"
CARD_NUMBER_INDEX = 3
CARD_NAME_INDEX = 2


def normalize(s):
    if s is None or (isinstance(s, float) and (s != s or s == 0)):
        return ""
    return str(s).strip()


def is_url(s):
    return isinstance(s, str) and s.strip().startswith("http")


def build_url_from_english_name(english_name: str, card_number: str) -> str:
    """英名 + 型番 で eBay 売却済み検索 URL を組み立てる"""
    query = f"{english_name} {card_number} Japanese PSA 9"
    return EBAY_BASE.format(query=quote(query, safe=""))


def read_rows_by_index(csv_path: str):
    """CSV を行リストで読み、データ行と英名列インデックス（View Sold Prices の左隣）を返す。"""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return rows[1:], None
    first_data = rows[1]
    view_sold_idx = None
    for j, cell in enumerate(first_data):
        if normalize(cell) == "View Sold Prices":
            view_sold_idx = j
            break
    if view_sold_idx is None or view_sold_idx < 1:
        return rows[1:], None
    return rows[1:], view_sold_idx - 1


def main():
    parser = argparse.ArgumentParser(description="Sheet export CSV → ebay_links.json")
    parser.add_argument("csv_path", help="スプレッドシートをエクスポートした CSV のパス")
    parser.add_argument(
        "--url-column",
        default=None,
        help="eBay URL が入っている列名（省略時は値が http で始まる列を自動検出）",
    )
    parser.add_argument(
        "--english-name-column",
        default=None,
        help="英名が入っている列名（空ヘッダーの場合は省略で自動検出）",
    )
    parser.add_argument(
        "--english-name-index",
        type=int,
        default=None,
        help="英名列の 0 始まりインデックス（P列なら 16）。指定時は自動検出より優先",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"出力 JSON パス（デフォルト: {DEFAULT_OUTPUT}）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"エラー: ファイルが見つかりません: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    # 英名列をインデックスで取得（P列 = View Sold Prices の左隣を自動検出 or --english-name-index）
    data_rows, english_col_index_auto = read_rows_by_index(args.csv_path)
    english_col_index = args.english_name_index
    if english_col_index is None and english_col_index_auto is not None:
        english_col_index = english_col_index_auto
        print(f"英名列を自動検出（インデックス {english_col_index} = View Sold Prices の左隣）", file=sys.stderr)

    if data_rows and english_col_index is not None:
        cn_counts = Counter()
        for row in data_rows:
            if len(row) > CARD_NUMBER_INDEX:
                cn_counts[normalize(row[CARD_NUMBER_INDEX])] += 1
        result = {}
        skipped = 0
        for row in data_rows:
            if len(row) <= max(CARD_NUMBER_INDEX, english_col_index):
                skipped += 1
                continue
            card_number = normalize(row[CARD_NUMBER_INDEX])
            card_name = normalize(row[CARD_NAME_INDEX])
            eng = normalize(row[english_col_index]) if english_col_index < len(row) else ""
            if not card_number or not eng:
                skipped += 1
                continue
            url = build_url_from_english_name(eng, card_number)
            if cn_counts[card_number] > 1:
                key = f"{card_number}|{card_name}" if card_name else card_number
            else:
                key = card_number
            result[key] = url
        out_dir = os.path.dirname(args.output)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"出力: {args.output} （{len(result)} 件、スキップ {skipped} 件）")
        return

    # 列名指定で DictReader
    with open(args.csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if not rows:
        print("エラー: CSV にデータ行がありません。", file=sys.stderr)
        sys.exit(1)

    # card_number の列名（No か card_number）
    cn_col = "card_number" if "card_number" in fieldnames else "No"
    name_col = "カード名"

    # URL 列の決定
    url_col = args.url_column
    if url_col and url_col not in fieldnames:
        print(f"警告: 列 '{url_col}' が見つかりません。", file=sys.stderr)
        url_col = None
    if not url_col:
        # 先頭行で http を含む列を探す
        first = rows[0]
        for col in fieldnames:
            if is_url(normalize(first.get(col, ""))):
                url_col = col
                break
        if not url_col:
            url_col = None

    english_col = args.english_name_column
    if english_col and english_col not in fieldnames:
        print(f"警告: 列 '{english_col}' が見つかりません。", file=sys.stderr)
        english_col = None

    if not url_col and not english_col:
        print(
            "エラー: URL を取得できません。--url-column で URL 列を指定するか、"
            "--english-name-column で英名列を指定してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    # card_number の出現回数（複合キー用）
    cn_counts = Counter(normalize(r.get(cn_col, "")) for r in rows if normalize(r.get(cn_col, "")))

    result = {}
    skipped = 0
    for row in rows:
        card_number = normalize(row.get(cn_col, ""))
        card_name = normalize(row.get(name_col, ""))
        if not card_number:
            skipped += 1
            continue

        url = None
        if url_col:
            raw = normalize(row.get(url_col, ""))
            if is_url(raw):
                url = raw.strip()
        if not url and english_col:
            eng = normalize(row.get(english_col, ""))
            if eng:
                url = build_url_from_english_name(eng, card_number)

        if not url:
            skipped += 1
            continue

        if cn_counts[card_number] > 1:
            key = f"{card_number}|{card_name}" if card_name else card_number
        else:
            key = card_number

        result[key] = url

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"出力: {args.output} （{len(result)} 件、スキップ {skipped} 件）")


if __name__ == "__main__":
    main()
