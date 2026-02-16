"""
みんなのポケカ相場のカード詳細ページURLを取得するスクリプト

filtered_cards.csv の card_number をもとに検索し、
各カードの pokeca-chart.com 詳細ページURLを抽出して pokeca_chart_links.json に保存する。

検索結果が JavaScript で遅延表示されるため Playwright を使用し、
表示待ちを入れてからリンクを抽出する。

オプション:
  --test  先頭8件のみ処理
  --headed  ブラウザを表示（ボット対策が厳しい場合に試す）
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
CSV_PATH = ROOT / "filtered_cards.csv"
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
PAGE_LOAD_WAIT_SEC = 5.0  # 検索結果の表示待ち（JS遅延表示のため多めに）
RESULTS_LINK_WAIT_MS = 12000  # カード詳細リンクが出現するまで待つ最大時間
SEARCH_RETRY_WAIT_MS = 4000  # 検索結果が「もう一度押すと出る」場合の追加待機（ミリ秒）

# ボット対策回避: 実ブラウザに近い User-Agent とヘッダー
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1280, "height": 720}


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


def normalize_card_name_for_search(name: str) -> str:
    """
    検索用にカード名を正規化。
    - 全角＆→半角&（広場は半角で登録されているため）
    - 末尾の (SA) / （SA） / (HR) など括弧表記を除去
    """
    if not name or not name.strip():
        return name
    s = name.strip()
    # 広場は「レシラム&リザードンGX」なので、全角＆を半角&に統一
    s = s.replace("＆", "&")
    # 末尾の半角・全角括弧で囲まれた表記（SA, HR, SR など）を繰り返し除去
    while True:
        m = re.search(r"\s*[(\（](SA|HR|SR|SAR|MUR|UR|CSR|SSR|P|PR)[)\）]\s*$", s, re.IGNORECASE)
        if not m:
            break
        s = s[: m.start()].rstrip()
    return s


def _do_search_and_parse(page, query: str, card_number: str, try_click_search_retry: bool = False) -> tuple[str | None, bool]:
    """
    検索を実行し、HTML から該当 card_number のリンクを抽出する。
    try_click_search_retry: True のとき、見つからなければ🔍検索ボタン押下で再検索を試す。
    戻り値: (URL または None, サイト側で NOT FOUND だったか)
    """
    url = f"{SEARCH_URL}?s={query}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(int(PAGE_LOAD_WAIT_SEC * 1000))
        try:
            page.wait_for_selector(
                'a[href^="/"][href*="-"], a[href*="pokeca-chart.com/"][href*="-"]',
                timeout=RESULTS_LINK_WAIT_MS,
            )
        except Exception:
            pass
        page.wait_for_timeout(500)
        html = page.content()
    except Exception:
        return None, False

    def _parse(html_text: str) -> str | None:
        sp = BeautifulSoup(html_text, "html.parser")
        exp_slug = card_number.replace("/", "-").lower()
        for a in sp.find_all("a", href=True):
            h = a["href"].strip()
            if h.startswith("//"):
                h = "https:" + h
            elif h.startswith("/"):
                h = BASE_URL + h
            m = CARD_LINK_PATTERN_STD.match(h)
            if m:
                parts = m.group(1).split("-")
                num_part = parts[-2] + "/" + parts[-1]
                if num_part == card_number:
                    return h.rstrip("/") + "/"
            if "/" in card_number and any(c.isalpha() for c in card_number.split("/")[-1]):
                m2 = CARD_LINK_PATTERN_SPECIAL.match(h)
                if m2 and m2.group(1) == exp_slug:
                    return h.rstrip("/") + "/"
        return None

    found = _parse(html)
    if found:
        return (found, False)

    # サイトが「検索ボタンをもう一度押すと出てくる」ように遅延表示している場合のリトライ
    page.wait_for_timeout(SEARCH_RETRY_WAIT_MS)
    html2 = page.content()
    found = _parse(html2)
    if found:
        return (found, False)

    # 名前のみ検索でまだ見つからなければ、文字は変えず🔍検索ボタンを押して再検索
    if try_click_search_retry:
        for sel in ['input[type="submit"]', 'button[type="submit"]', 'button:has-text("検索")', '[aria-label="検索"]']:
            try:
                page.locator(sel).first.click(timeout=2000)
                break
            except Exception:
                continue
        page.wait_for_timeout(SEARCH_RETRY_WAIT_MS)
        html3 = page.content()
        found = _parse(html3)
        if found:
            return (found, False)
        not_found = "NOT FOUND" in html.upper() or "NOT FOUND" in html2.upper() or "NOT FOUND" in html3.upper()
    else:
        not_found = "NOT FOUND" in html.upper() or "NOT FOUND" in html2.upper()
    return (None, not_found)


def search_and_extract_link(card_number: str, page, card_name: str | None = None) -> str | None:
    """
    pokeca-chart.com で検索し、カード詳細ページのURLを抽出。
    検索は「型番 名前」→「名前のみ」の順。名前のみで見つからなければ🔍検索ボタン押下で再検索する。
    戻り値: URL | NOT_FOUND_ON_SITE | None
    """
    if card_name:
        search_name = normalize_card_name_for_search(card_name)
        # 型番 名前 → 名前のみ の順。名前のみのときは見つからなければ検索ボタン押下で再検索
        queries = [
            (f"{card_number} {search_name}", False),
            (search_name, True),  # 名前だけ（見つからなければ🔍を押して再検索）
        ]
    else:
        queries = [(card_number.replace("/", "%2F"), False)]

    for q, click_retry in queries:
        # & をそのままにすると URL のパラメータ区切りと解釈され「ファイヤー」だけ送られるので必ず quote
        query = quote(q) if (" " in q or "&" in q) else q
        found, not_found = _do_search_and_parse(page, query, card_number, try_click_search_retry=click_retry)
        if found:
            return found
        if not_found:
            continue  # 次のクエリを試す
    # 最後の試行で NOT FOUND だったかは判定しない（複数クエリ試したため）
    return NOT_FOUND_ON_SITE


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
    use_headed = "--headed" in sys.argv  # ウィンドウ表示でボット対策が厳しい場合に試す
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not use_headed)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="ja-JP",
            extra_http_headers={
                "Accept-Language": "ja,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = context.new_page()
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
