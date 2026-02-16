#!/usr/bin/env python3
"""
filtered_cards.csv と ebay_links.json を比較し、ebay_links にないカード（新規）だけ
Gemini API で英名を取得して eBay URL を組み立て、ebay_links.json にマージする。

前提:
  - 環境変数 GEMINI_API_KEY に API キーを設定（Google AI Studio で取得）
  - pip install google-genai

使い方:
  python scripts/update_ebay_links_gemini.py

  オプション:
    --dry-run   … 新規カードを表示するだけで JSON は更新しない
    --csv path  … filtered_cards.csv のパス（省略時はプロジェクトルートの filtered_cards.csv）
    --output    … 出力 JSON パス（省略時は ebay_links.json）
"""
import json
import os
import sys
from collections import Counter
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(BASE_DIR, "filtered_cards.csv")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "ebay_links.json")
EBAY_BASE = "https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1"


def normalize(s):
    if s is None or (isinstance(s, float) and (s != s or s == 0)):
        return ""
    return str(s).strip()


def build_url_from_english_name(english_name: str, card_number: str) -> str:
    query = f"{english_name} {card_number} Japanese PSA 9"
    return EBAY_BASE.format(query=quote(query, safe=""))


def load_filtered_cards(csv_path: str):
    """filtered_cards.csv を読み、(key, card_number, card_name) のリストを返す。"""
    import pandas as pd
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    cn_col = "card_number" if "card_number" in df.columns else "No"
    name_col = "カード名"
    counts = Counter()
    for _, row in df.iterrows():
        cn = normalize(row.get(cn_col, ""))
        if cn:
            counts[cn] += 1
    rows = []
    for _, row in df.iterrows():
        cn = normalize(row.get(cn_col, ""))
        name = normalize(row.get(name_col, ""))
        if not cn:
            continue
        key = f"{cn}|{name}" if (name and counts[cn] > 1) else cn
        rows.append((key, cn, name))
    return rows


def load_ebay_links(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def translate_with_gemini(japanese_names: list, api_key: str) -> list:
    """Gemini で日本語カード名を英名に訳す。順序は維持。"""
    try:
        from google import genai
    except ImportError:
        print("エラー: google-genai がインストールされていません。pip install google-genai", file=sys.stderr)
        sys.exit(1)

    model_id = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    numbered = "\n".join(f"{i+1}. {n}" for i, n in enumerate(japanese_names))
    prompt = f"""Translate the following Japanese Pokémon TCG card names to their official English names as used on English cards.
Return ONLY the English name for each, one per line, in the exact same order (1 line per card). No other text.

Japanese names:
{numbered}"""
    client = genai.Client(api_key=api_key)
    response = None
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        print(f"  モデル: {model_id}", file=sys.stderr)
    except Exception as e:
        for fallback in ["gemini-2.0-flash", "gemini-2.5-flash-lite"]:
            if fallback == model_id:
                continue
            try:
                response = client.models.generate_content(model=fallback, contents=prompt)
                print(f"  モデル: {fallback}", file=sys.stderr)
                break
            except Exception:
                continue
        if response is None:
            raise e
    finally:
        client.close()

    text = (response.text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 行頭の "1. " "1) " などを除去
    result = []
    for ln in lines:
        s = ln
        for i, c in enumerate(s):
            if c.isdigit() or c in ".) ":
                continue
            s = s[i:].lstrip()
            break
        result.append(s or ln)
    # 数が足りない場合はそのまま返す（呼び出し側で不足分は空文字）
    while len(result) < len(japanese_names):
        result.append("")
    return result[: len(japanese_names)]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="新規カードのみ Gemini で英名取得し ebay_links にマージ")
    parser.add_argument("--dry-run", action="store_true", help="新規のみ表示し JSON は更新しない")
    parser.add_argument("--csv", default=DEFAULT_CSV, help=f"filtered_cards.csv のパス（デフォルト: {DEFAULT_CSV}）")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"出力 JSON（デフォルト: {DEFAULT_OUTPUT}）")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("エラー: 環境変数 GEMINI_API_KEY を設定してください（Google AI Studio で取得）", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.csv):
        print(f"エラー: {args.csv} が見つかりません", file=sys.stderr)
        sys.exit(1)

    all_cards = load_filtered_cards(args.csv)
    existing = load_ebay_links(args.output)
    new_cards = [(k, cn, name) for k, cn, name in all_cards if k not in existing]

    if not new_cards:
        print("新規カードはありません。")
        return

    print(f"新規カード: {len(new_cards)} 件")
    for k, cn, name in new_cards:
        print(f"  - {k}: {name}")

    if args.dry_run:
        print("（--dry-run のため JSON は更新しません）")
        return

    names_ja = [name for _, _, name in new_cards]
    print("Gemini で英名を取得中...")
    names_en = translate_with_gemini(names_ja, api_key)

    merged = dict(existing)
    for (key, card_number, _), eng in zip(new_cards, names_en):
        eng = normalize(eng)
        if not eng:
            print(f"  警告: 英名が空です key={key}", file=sys.stderr)
            continue
        url = build_url_from_english_name(eng, card_number)
        merged[key] = url
        print(f"  {key} -> {eng}")

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"完了: {args.output} に {len(merged)} 件を保存しました（新規 {len(new_cards)} 件追加）")


if __name__ == "__main__":
    main()
