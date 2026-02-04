"""
みんなのポケカ相場のカード詳細ページURLを取得するスクリプト

merged_card_data.csv の card_number をもとに検索し、
各カードの pokeca-chart.com 詳細ページURLを抽出して pokeca_chart_links.json に保存する。

検索結果が JavaScript で遅延表示されるため Playwright を使用し、
表示待ちを入れてからリンクを抽出する。
"""
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# プロジェクトルート
ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "merged_card_data.csv"
OUTPUT_PATH = ROOT / "pokeca_chart_links.json"
BASE_URL = "https://pokeca-chart.com"
SEARCH_URL = f"{BASE_URL}/"
# カード詳細ページのURLパターン
# 1) 標準: /s6a-093-069/, /s8a-p-001-025/ など末尾が -数字-数字
CARD_LINK_PATTERN_STD = re.compile(
    rf"^{re.escape(BASE_URL)}/([a-z0-9]+(?:-[a-z0-9]+)*-\d+-\d+)/?$"
)
# 2) 特殊（001/S-P, 001/SV-P など）: /001-s-p/, /001-sv-p/ 形式（card_number の / → - 小文字化）
CARD_LINK_PATTERN_SPECIAL = re.compile(
    rf"^{re.escape(BASE_URL)}/(\d+-[a-z0-9]+(?:-[a-z0-9]+)*)/?$"
)
REQUEST_DELAY_SEC = 1.5
PAGE_LOAD_WAIT_SEC = 2.5  # 検索結果の表示待ち


def _composite_key(card_number: str, card_name: str) -> str:
    """重複用の複合キー（JSON のキー用）"""
    return f"{card_number}|{card_name}"


def get_card_entries() -> list[tuple[str, str, bool]]:
    """
    CSV から (card_number, card_name, is_duplicate) の一覧を取得
    is_duplicate: 同じ card_number で複数カード名がある場合 True
    """
    if not CSV_PATH.exists():
        print(f"エラー: {CSV_PATH} が見つかりません")
        sys.exit(1)
    # (card_number, card_name) の重複なし
    pairs: set[tuple[str, str]] = set()
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cn = row.get("card_number", "").strip()
            name = (row.get("カード名") or "").strip()
            if cn and name:
                pairs.add((cn, name))
    # card_number ごとのカード名の数
    cn_counts = Counter(cn for cn, _ in pairs)
    return [(cn, name, cn_counts[cn] > 1) for cn, name in sorted(pairs)]


# サイトが「見つからない」と明示した場合の戻り値（URL ではない）
NOT_FOUND_ON_SITE = "NOT_FOUND"


def search_and_extract_link(card_number: str, page, card_name: str | None = None) -> str | None:
    """
    pokeca-chart.com で検索し、カード詳細ページのURLを抽出
    card_name を渡すと「card_number card_name」で検索（重複型番で正しいカードを特定）
    戻り値: URL | NOT_FOUND_ON_SITE（サイトに存在しない） | None（技術的エラー）
    """
    if card_name:
        query = quote(f"{card_number} {card_name}")
    else:
        query = card_number.replace("/", "%2F")
    url = f"{SEARCH_URL}?s={query}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(int(PAGE_LOAD_WAIT_SEC * 1000))
        html = page.content()
    except Exception as e:
        print(f"  取得失敗 {card_number}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")
    expected_special_slug = card_number.replace("/", "-").lower()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = BASE_URL + href

        # 1) 標準パターン（末尾 -数字-数字）
        m = CARD_LINK_PATTERN_STD.match(href)
        if m:
            slug = m.group(1)
            parts = slug.split("-")
            num_part = parts[-2] + "/" + parts[-1]
            if num_part == card_number:
                return href.rstrip("/") + "/"
            return href.rstrip("/") + "/"

        # 2) 特殊パターン（001/S-P → 001-s-p など、letter 含む card_number）
        if "/" in card_number and any(c.isalpha() for c in card_number.split("/")[-1]):
            m = CARD_LINK_PATTERN_SPECIAL.match(href)
            if m:
                slug = m.group(1)
                if slug == expected_special_slug:
                    return href.rstrip("/") + "/"

    # リンクが見つからなかった場合、サイトが「NOT FOUND」と表示しているか確認
    if "NOT FOUND" in html.upper():
        return NOT_FOUND_ON_SITE
    return None


def load_existing_links() -> dict[str, str]:
    """既存の JSON を読み込む"""
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def main():
    entries = get_card_entries()
    if "--test" in sys.argv:
        entries = entries[:8]  # 055/050 など重複が含まれるように多め
        print("※ テストモード: 先頭8件のみ")

    print(f"カード数: {len(entries)} 件（重複型番はカード名ごとに取得）")

    existing = load_existing_links()
    results: dict[str, str] = dict(existing)

    # 今回実際に処理する件数（既存はスキップ）
    to_process = [
        (card_number, card_name, is_duplicate)
        for card_number, card_name, is_duplicate in entries
        if (_composite_key(card_number, card_name) if is_duplicate else card_number) not in results
    ]
    total_to_process = len(to_process)
    if total_to_process < len(entries):
        print(f"既存により {len(entries) - total_to_process} 件スキップ、今回 {total_to_process} 件を処理")

    fetched = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(20000)

        for n, (card_number, card_name, is_duplicate) in enumerate(to_process, 1):
            key = _composite_key(card_number, card_name) if is_duplicate else card_number
            label = f"{card_number} {card_name}" if is_duplicate else card_number
            print(f"  [{n}/{total_to_process}] {label} ... ", end="", flush=True)
            result = search_and_extract_link(card_number, page, card_name if is_duplicate else None)
            if result and result != NOT_FOUND_ON_SITE:
                results[key] = result
                print(result)
                fetched += 1
            elif result == NOT_FOUND_ON_SITE:
                print("NOT FOUND")
            else:
                print("(見つからず)")
            time.sleep(REQUEST_DELAY_SEC)

        browser.close()

    # JSON 保存（キーでソート）
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(results.items())), f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(results)} 件のリンクを保存（新規 {fetched} 件）")
    print(f"出力: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
