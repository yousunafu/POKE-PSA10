"""
カードラッシュで販売価格と在庫状況を調査するスクリプト
"""
import csv
import re
import time
import sys
from urllib.parse import quote
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def read_otachu_csv(filename: str) -> List[Dict]:
    """
    otachu_psa10.csvを読み込む
    """
    data = []
    with open(filename, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(row)
    return data


def is_graded_card(product_name: str) -> bool:
    """
    商品名にPSA10、PSA9などの鑑定品、または「状態」表記が含まれるかチェック
    除外対象：
    - PSA10、PSA9などの鑑定品
    - 「状態A-」「状態B」などの傷あり品
    """
    # 鑑定品のパターン
    graded_patterns = [
        r'PSA\d+',
        r'ARS\d+',
        r'BGS\d+',
        r'鑑定',
        r'鑑定済',
        r'グレード'
    ]
    
    # 状態表記のパターン（傷あり品を除外）
    condition_patterns = [
        r'状態[A-Z]',  # 状態A、状態Bなど
        r'状態[A-Z]-',  # 状態A-など
        r'状態難',  # 状態難
        r'\(状態',  # (状態A-)など
        r'\{状態',  # {状態A-}など
        r'【状態',  # 【状態A-】など
        r'状態\w+',  # その他の状態表記
    ]
    
    # 鑑定品チェック
    for pattern in graded_patterns:
        if re.search(pattern, product_name, re.IGNORECASE):
            return True
    
    # 状態表記チェック
    for pattern in condition_patterns:
        if re.search(pattern, product_name):
            return True
    
    return False


def extract_price(price_text: str) -> Optional[int]:
    """
    価格テキストから数値を抽出
    例: "5,480円(税込)" -> 5480
    """
    # 数字とカンマを抽出
    price_match = re.search(r'([\d,]+)', price_text.replace(',', ''))
    if price_match:
        try:
            return int(price_match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None


def extract_stock_count(stock_text: str) -> Optional[int]:
    """
    在庫テキストから在庫数を抽出
    例: "在庫数 29枚" -> 29, "×" -> None
    """
    if '×' in stock_text or '在庫なし' in stock_text:
        return None
    
    stock_match = re.search(r'在庫数\s*(\d+)', stock_text)
    if stock_match:
        try:
            return int(stock_match.group(1))
        except ValueError:
            return None
    
    # "在庫あり"の場合は在庫数が不明なので1を返す（存在することを示す）
    if '在庫あり' in stock_text:
        return 1
    
    return None


def _fullwidth_to_halfwidth(s: str) -> str:
    """全角英数字・記号（ｅｘ、Ｖ、＆等）を半角に変換する。"""
    result = []
    for c in s:
        if '\uff01' <= c <= '\uff5e':  # 全角 ! ～ ~
            result.append(chr(ord(c) - 0xFEE0))
        else:
            result.append(c)
    return ''.join(result)


def _normalize_card_name(name: str) -> str:
    """
    カード名のゆらぎを吸収するために正規化するヘルパー
    - 全角英数字・記号を半角に統一（ｅｘ→ex、Ｖ→V、＆→&）
    - 空白・全角空白の削除
    - 括弧や装飾記号の削除
    - 大文字→小文字（Vstar/VSTAR などの表記ゆれを吸収）
    """
    if not name:
        return ""
    # 前後の空白を削除
    name = name.strip()
    # 全角英数字・記号を半角に（ラティアスｅｘ、ブースターＶ、＆ 等）
    name = _fullwidth_to_halfwidth(name)
    # 「（」「(」以降の補足情報は一旦切り落とす（例: ピカチュウGX(SA) -> ピカチュウGX）
    name = re.split(r'[（(]', name)[0]
    # 装飾用の記号を削除（☆★ はカード名の装飾で使われるためここで除去）
    name = re.sub(r'[【】\[\]（）\(\)「」『』<>＜＞:：・、，,\s☆★]', '', name)
    name = name.lower()
    return name


def _check_card_number_in_text(target_number: str, text: str) -> bool:
    """
    商品名・URL に型番が含まれるか確認（表記ゆれ対応）。
    「/」で区切ったブロック単位で一致させる（227/S-P と 227/SM-P を区別する）。
    例: target_number="227/S-P" → text 内に "227" と "S-P" がこの順で含まれるか。
    例: target_number="091/064" → "091" と "064" がこの順で含まれるか。
    """
    if not target_number or not text:
        return False
    # 「/」で区切ってブロック単位に（S-P と SM-P を区別するため、英数字以外で細かく分割しない）
    parts = [s.strip() for s in target_number.strip().split("/") if s.strip()]
    if not parts:
        return False
    if len(parts) == 1:
        return parts[0] in text
    # 各ブロックがこの順で出現するパターン（間に任意の文字を許容）
    pattern = r'.*'.join([re.escape(p) for p in parts])
    return re.search(pattern, text) is not None


def _target_tokens_all_in_product(normalized_target: str, normalized_product: str) -> bool:
    """
    ターゲットを「日本語ブロック」「英数字ブロック」に分割し、
    各ブロックが商品名に含まれるか判定する。
    「カシオペアsv6a」vs「カシオペアsar{091/064}sv6a」のように
    商品名の途中に【SAR】等が挟まるケースでマッチさせる。
    「ex」+ セットコード（sv5k, sv7 等）は境界でさらに分割し、
    タケルライコex・テラパゴスex などがマッチするようにする。
    """
    if not normalized_target or not normalized_product:
        return False
    # 日本語（ひらがな・カタカナ・漢字）と英数字の境界で分割
    tokens = re.split(
        r'(?<=[\u3040-\u9fff])(?=[a-zA-Z0-9])|(?<=[a-zA-Z0-9])(?=[\u3040-\u9fff])',
        normalized_target,
    )
    tokens = [t for t in tokens if len(t) >= 1]
    # 「ex」+ セットコード（sv5k, sv8a, sv7, s10a 等）の境界でさらに分割（商品名の【SAR】等で分断されるケース用）
    expanded = []
    for t in tokens:
        m = re.match(r'^ex(s[a-z]*\d+[a-z]?)$', t, re.IGNORECASE)
        if m:
            expanded.extend(["ex", m.group(1).lower()])
        else:
            expanded.append(t)
    tokens = expanded
    if not tokens:
        return normalized_target in normalized_product
    return all(t in normalized_product for t in tokens)


def _filter_masbo_candidates(candidates: list) -> list:
    """
    レアがマスボの場合の候補を絞る。
    「マスターボールミラー」を含む商品のみにし、状態表記のないものを優先する。
    """
    if not candidates:
        return []
    masbo_only = [p for p in candidates if "マスターボールミラー" in p.get("name", "")]
    if not masbo_only:
        return []
    no_condition = [p for p in masbo_only if "状態" not in p.get("name", "")]
    return no_condition if no_condition else masbo_only


def _prefer_without_mikaeri(candidates: list) -> list:
    """
    候補のうち「未開封」が商品名に含まれないものを優先する。
    「未開封」を含まない商品が1件でもあればそれだけに絞り、なければそのまま返す。
    """
    if not candidates:
        return []
    without_mikaeri = [p for p in candidates if "未開封" not in p.get("name", "")]
    return without_mikaeri if without_mikaeri else candidates


def search_cardrush(page, keyword: str, target_name: str = "", rarity: str = "", card_number: str = "") -> Optional[Dict]:
    """
    カードラッシュで検索して、在庫ありの最安値商品情報を取得
    タイムアウトが発生しても画像だけは取得を試みる
    rarity: レア（マスボの場合は「マスターボールミラー」の価格を取得する）。
    card_number: 型番（例: 091/064）。型番一致時のみ名前を双方向部分一致で判定し、パターン2対応。
    """
    image_url = None  # エラー時でも画像取得を試みるため、外側で定義
    
    try:
        # 検索URL（日本語キーワードをURLエンコード）
        encoded_keyword = quote(keyword)
        search_url = f"https://www.cardrush-pokemon.jp/product-list?keyword={encoded_keyword}"
        
        print(f"  検索中: {keyword} -> {search_url}")
        if target_name:
            print(f"  ターゲットカード名: {target_name} (正規化後: {_normalize_card_name(target_name)})")
        
        # domcontentloaded で待機（networkidle は Cloudflare 等でタイムアウトしやすい）
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            print(f"  タイムアウトが発生しましたが、ページの読み込みを続行します...")
            time.sleep(2)
        
        # Cloudflare チャレンジ通過を待つ: 商品リンクが表示されるまで最大20秒待機
        try:
            page.wait_for_selector("a[href*='/product/']", timeout=20000)
        except PlaywrightTimeoutError:
            pass  # 見つからなくても続行（後で product_links が 0 ならリトライ）
        
        time.sleep(2)  # 追加の描画待ち
        
        # 検索結果の商品リストを取得
        product_items = []  # 在庫ありの商品
        out_of_stock_items = []  # 在庫なしの商品（価格と画像を取得するため）
        normalized_target_name = _normalize_card_name(target_name)
        
        # 商品リンクを取得
        product_links = page.query_selector_all("a[href*='/product/']")
        _page_title = page.title()
        _is_cf = "Just a moment" in page.content() or "Verify you are human" in page.content()
        print(f"  [DEBUG] 商品リンク数: {len(product_links)}, Cloudflare検出: {_is_cf}, ページタイトル: {_page_title[:80] if _page_title else '(なし)'}")

        # Cloudflare チャレンジページの場合は待機してリトライ（2件目以降でブロックされやすい）
        _is_cloudflare = "Just a moment" in page.content() or "Verify you are human" in page.content()
        if len(product_links) == 0 and _is_cloudflare:
            print(f"  Cloudflareチャレンジ検出。15秒待機してリトライ...")
            time.sleep(15)
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
                page.wait_for_selector("a[href*='/product/']", timeout=25000)
            except PlaywrightTimeoutError:
                pass
            product_links = page.query_selector_all("a[href*='/product/']")
            print(f"  [DEBUG] リトライ後 商品リンク数: {len(product_links)}")

        # 重複を避けるためにURLを記録
        seen_urls = set()
        
        for link in product_links:
            try:
                # 商品URLを取得
                product_url = link.get_attribute('href')
                if not product_url:
                    continue
                
                if not product_url.startswith('http'):
                    product_url = f"https://www.cardrush-pokemon.jp{product_url}"
                
                # 重複チェック
                if product_url in seen_urls:
                    continue
                seen_urls.add(product_url)
                
                # リンクのテキスト全体を取得
                full_text = link.inner_text().strip()
                
                if not full_text or len(full_text) < 5:
                    continue
                
                # 鑑定品を除外
                if is_graded_card(full_text):
                    continue
                
                # 価格を抽出
                price_match = re.search(r'([\d,]+)円', full_text)
                if not price_match:
                    continue
                
                price = extract_price(price_match.group(0))
                if price is None:
                    continue
                
                # 商品名を抽出（価格と在庫情報を除く）
                product_name = full_text
                # 価格と在庫情報の部分を削除して商品名だけにする
                product_name = re.sub(r'\s*\d+[,，]\d+円.*', '', product_name)
                product_name = re.sub(r'\s*在庫数\s*\d+枚.*', '', product_name)
                product_name = product_name.strip()
                
                # 画像URLを取得（検索結果ページのリスト内の画像を取得）
                # 価格の上にあるカード画像を取得する
                image_url = None
                try:
                    # JavaScriptでリンク要素の親要素内の画像を探す
                    image_url = link.evaluate("""
                        (element) => {
                            // 親要素を取得（li, div, articleなど）
                            let parent = element.closest('li, div[class*="product"], div[class*="item"], article, a[class*="product"]');
                            if (!parent) {
                                parent = element.parentElement;
                            }
                            
                            if (!parent) return null;
                            
                            // 親要素内の画像を探す（価格の上にあるカード画像）
                            // 商品画像は通常、リンク要素の前や親要素内にある
                            let img = parent.querySelector('img[src*="product"], img[src*="card"], img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]');
                            
                            // 画像が見つからない場合、リンク要素の前の兄弟要素を探す
                            if (!img) {
                                let prev = element.previousElementSibling;
                                while (prev) {
                                    img = prev.querySelector('img');
                                    if (img) break;
                                    prev = prev.previousElementSibling;
                                }
                            }
                            
                            // まだ見つからない場合、親要素の最初の画像を探す
                            if (!img && parent) {
                                img = parent.querySelector('img');
                            }
                            
                            return img ? img.src : null;
                        }
                    """)
                    
                    # URLを正規化
                    if image_url:
                        # 相対パスの場合は絶対パスに変換
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = f"https://www.cardrush-pokemon.jp{image_url}"
                        elif not image_url.startswith('http'):
                            image_url = f"https://www.cardrush-pokemon.jp/{image_url}"
                        
                except Exception as e:
                    print(f"    画像取得エラー: {e}")
                
                # 在庫状況を確認
                stock_count = extract_stock_count(full_text)
                
                # 元データのカード名とのマッチ度を計算（パターン2対応: 型番一致時は双方向部分一致）
                normalized_product_name = _normalize_card_name(product_name)
                has_number_match = bool(card_number) and (
                    _check_card_number_in_text(card_number, product_name)
                    or _check_card_number_in_text(card_number, product_url or "")
                )
                if has_number_match:
                    # 型番が合っている商品に限り、名前は双方向部分一致 or トークン全含むでOK（【SAR】カシオペア など対応）
                    name_match = (
                        bool(normalized_target_name)
                        and (
                            normalized_target_name in normalized_product_name
                            or normalized_product_name in normalized_target_name
                            or _target_tokens_all_in_product(normalized_target_name, normalized_product_name)
                        )
                    )
                else:
                    # 型番なし/不一致のときは既存の厳しい条件（ターゲット ⊂ 商品）のみ
                    name_match = (
                        bool(normalized_target_name)
                        and normalized_target_name in normalized_product_name
                    )
                
                # デバッグ出力（最初の数件のみ）
                if len(product_items) + len(out_of_stock_items) < 3:
                    print(f"    商品名: {product_name[:50]}")
                    print(f"    正規化後: {normalized_product_name}")
                    print(f"    ターゲット名: {target_name} -> 正規化後: {normalized_target_name}")
                    print(f"    型番一致: {has_number_match} マッチ: {name_match}")

                product_data = {
                    'name': product_name[:100],  # 長すぎる場合は切り詰め
                    'price': price,
                    'stock': stock_count,
                    'url': product_url,
                    'image_url': image_url or '',
                    # 元カード名とのマッチしているかどうか（優先度付けに使用）
                    'name_match': name_match,
                    # 型番一致（card_number 指定時のみ候補を絞るために使用）
                    'number_match': has_number_match,
                }
                
                # 在庫がある場合は在庫ありリストに、ない場合は在庫なしリストに追加
                if stock_count is not None:
                    product_items.append(product_data)
                else:
                    # 在庫なしでも価格と画像を保存
                    out_of_stock_items.append(product_data)
                
            except Exception as e:
                print(f"    商品情報取得エラー: {e}")
                continue
        
        # 在庫あり・在庫なしの両方からマッチする商品を抽出（型番指定時は型番一致も必須）
        matched_items = [
            p for p in product_items
            if p.get('name_match') and (not card_number or p.get('number_match'))
        ]
        matched_out_of_stock = [
            p for p in (out_of_stock_items or [])
            if p.get('name_match') and (not card_number or p.get('number_match'))
        ]
        # レアがマスボの場合は「マスターボールミラー」の商品に絞り、状態なしを優先
        if rarity == "マスボ":
            matched_items = _filter_masbo_candidates(matched_items)
            matched_out_of_stock = _filter_masbo_candidates(matched_out_of_stock)
            if matched_items or matched_out_of_stock:
                print(f"    マスボ: マスターボールミラー対象 在庫あり{len(matched_items)}件 / 在庫なし{len(matched_out_of_stock)}件")

        # 在庫あり・在庫なしをまとめて「未開封」が付いていないものを優先し、その中で最安値を1件選ぶ
        combined = matched_items + matched_out_of_stock
        if combined:
            preferred = _prefer_without_mikaeri(combined)
            cheapest = min(preferred, key=lambda x: x['price'])
            if cheapest.get('stock') is not None:
                print(f"    在庫ありリストから該当カード名({target_name})を含む商品を選択: {cheapest['name'][:50]} ({cheapest['price']}円)")
            else:
                print(f"    在庫なしリストから該当カード名({target_name})を含む商品を選択: {cheapest['name'][:50]} ({cheapest['price']}円)")
            return {
                'price': cheapest['price'],
                'stock': cheapest.get('stock'),
                'url': cheapest['url'],
                'image_url': cheapest['image_url'],
                'product_name': cheapest['name']
            }

        # マッチする商品が1件もない場合
        if not product_items and not out_of_stock_items:
            print(f"  [DEBUG] 商品リンク0件 or 価格抽出失敗でパースできず（検索結果が空の可能性）")
        elif product_items or out_of_stock_items:
            print(f"  [DEBUG] 商品は見つかったが名前マッチせず: 在庫あり{len(product_items)}件, 在庫なし{len(out_of_stock_items)}件")
            if product_items and len(product_items) <= 3:
                for p in product_items:
                    print(f"    - 候補: {p.get('name', '')[:60]}")
            elif out_of_stock_items and len(out_of_stock_items) <= 3:
                for p in out_of_stock_items:
                    print(f"    - 候補: {p.get('name', '')[:60]}")
        if product_items:
            print(f"    在庫ありリストに該当カード名({target_name})を含む商品が見つかりませんでした (全{len(product_items)}件)")
        if out_of_stock_items:
            print(f"  在庫なしリストにも該当カード名({target_name})を含む商品が見つかりませんでした (全{len(out_of_stock_items)}件)")
        
        # マッチする商品が1件もない場合は、別カードの画像を表示しないよう画像も空で返す
        print(f"  該当する商品が見つかりませんでした。")
        return {
            'price': None,
            'stock': None,
            'url': None,
            'image_url': '',
            'product_name': ''
        }
        
    except PlaywrightTimeoutError as e:
        print(f"  タイムアウトエラー: {keyword}")
        print(f"  タイムアウトが発生しましたが、画像取得を試みます...")
        
        # タイムアウトが発生しても、ページは部分的に読み込まれている可能性がある
        # 画像だけは取得を試みる
        try:
            time.sleep(2)  # 少し待機
            first_product_link = page.query_selector("a[href*='/product/']")
            if first_product_link:
                image_url = first_product_link.evaluate("""
                    (element) => {
                        let parent = element.closest('li, div[class*="product"], div[class*="item"], article, a[class*="product"]');
                        if (!parent) parent = element.parentElement;
                        
                        if (!parent) return null;
                        
                        let img = parent.querySelector('img[src*="product"], img[src*="card"], img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]');
                        
                        if (!img) {
                            let prev = element.previousElementSibling;
                            while (prev) {
                                img = prev.querySelector('img');
                                if (img) break;
                                prev = prev.previousElementSibling;
                            }
                        }
                        
                        if (!img && parent) {
                            img = parent.querySelector('img');
                        }
                        
                        return img ? img.src : null;
                    }
                """)
                
                # URLを正規化
                if image_url:
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = f"https://www.cardrush-pokemon.jp{image_url}"
                    elif not image_url.startswith('http'):
                        image_url = f"https://www.cardrush-pokemon.jp/{image_url}"
        except Exception as img_error:
            print(f"    画像取得エラー: {img_error}")
            image_url = None
        
        # 画像があれば返す
        return {
            'price': None,
            'stock': None,
            'url': None,
            'image_url': image_url or '',
            'product_name': ''
        }
    except Exception as e:
        print(f"  検索エラー: {keyword} - {e}")
        print(f"  エラーが発生しましたが、画像取得を試みます...")
        
        # エラーが発生しても画像取得を試みる
        try:
            time.sleep(1)
            first_product_link = page.query_selector("a[href*='/product/']")
            if first_product_link:
                image_url = first_product_link.evaluate("""
                    (element) => {
                        let parent = element.closest('li, div[class*="product"], div[class*="item"], article, a[class*="product"]');
                        if (!parent) parent = element.parentElement;
                        
                        if (!parent) return null;
                        
                        let img = parent.querySelector('img[src*="product"], img[src*="card"], img[src*=".jpg"], img[src*=".png"], img[src*=".webp"]');
                        
                        if (!img) {
                            let prev = element.previousElementSibling;
                            while (prev) {
                                img = prev.querySelector('img');
                                if (img) break;
                                prev = prev.previousElementSibling;
                            }
                        }
                        
                        if (!img && parent) {
                            img = parent.querySelector('img');
                        }
                        
                        return img ? img.src : null;
                    }
                """)
                
                # URLを正規化
                if image_url:
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = f"https://www.cardrush-pokemon.jp{image_url}"
                    elif not image_url.startswith('http'):
                        image_url = f"https://www.cardrush-pokemon.jp/{image_url}"
        except Exception as img_error:
            print(f"    画像取得エラー: {img_error}")
            image_url = None
        
        # 画像があれば返す
        return {
            'price': None,
            'stock': None,
            'url': None,
            'image_url': image_url or '',
            'product_name': ''
        }


def scrape_cardrush_data(input_csv: str, output_csv: str, debug_mode: bool = False, filter_card_number: str = None, filter_card_numbers: list = None, last_n: int = None, first_n: int = None):
    """
    カードラッシュのデータをスクレイピングして統合
    
    Args:
        input_csv: 入力CSVファイル
        output_csv: 出力CSVファイル
        debug_mode: デバッグモード（先頭5件のみ）
        filter_card_number: 特定のカード番号でフィルタリング（1件、例: "058/051"）
        filter_card_numbers: 複数のカード番号でフィルタリング（例: ["236/187", "132/106"]）
        last_n: 最後N件のみ処理（例: 30）
    """
    # CSVを読み込む
    print(f"CSVファイルを読み込み中: {input_csv}")
    data = read_otachu_csv(input_csv)
    
    # 複数カード番号でフィルタリング（--cards / --cards-file）
    if filter_card_numbers is not None:
        original_count = len(data)
        allowed = {s.strip() for s in filter_card_numbers if s and str(s).strip()}
        data = [row for row in data if row.get('card_number', '').strip() in allowed]
        print(f"カード番号リストでフィルタリング: {original_count}件 -> {len(data)}件")
        if len(data) == 0:
            print("エラー: 指定したカード番号がCSVにありませんでした")
            return
    # 単一カード番号でフィルタリング（--card）
    elif filter_card_number:
        original_count = len(data)
        data = [row for row in data if row.get('card_number', '').strip() == filter_card_number]
        print(f"カード番号 '{filter_card_number}' でフィルタリング: {original_count}件 -> {len(data)}件")
        if len(data) == 0:
            print(f"エラー: カード番号 '{filter_card_number}' が見つかりませんでした")
            return
    
    # 先頭N件のみ処理
    if first_n is not None and first_n > 0:
        original_count = len(data)
        data = data[:first_n]
        print(f"先頭{first_n}件のみ処理: {original_count}件 -> {len(data)}件")
    # 最後N件のみ処理
    elif last_n is not None and last_n > 0:
        original_count = len(data)
        data = data[-last_n:]  # 最後N件を取得
        print(f"最後{last_n}件のみ処理: {original_count}件 -> {len(data)}件")
    
    if debug_mode:
        data = data[:5]
        print(f"デバッグモード: 先頭5件のみ処理します")
    
    print(f"合計 {len(data)} 件のデータを処理します")
    
    results = []
    
    with sync_playwright() as p:
        # ブラウザを起動（Chrome優先: Cloudflare検出されにくい。GitHub Actions等ではChromiumへフォールバック）
        browser = None
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            print("Chrome で起動しました")
        except Exception:
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                print("Chromium で起動しました")
            except Exception as e:
                print(f"Chromiumの起動に失敗しました: {e}")
                print("Firefoxを使用して再試行します...")
                try:
                    browser = p.firefox.launch(headless=True)
                except Exception as e2:
                    print(f"Firefoxの起動にも失敗しました: {e2}")
                    raise
        
        # リクエスト間の待機時間（秒）
        wait_between_requests = 5
        
        for idx, row in enumerate(data, 1):
            print(f"\n[{idx}/{len(data)}] 処理中...")
            
            # 検索キーワードを決定（card_numberを優先、なければカード名）
            keyword = row.get('card_number', '').strip()
            if not keyword:
                keyword = row.get('カード名', '').strip()
            
            if not keyword:
                print(f"  検索キーワードが見つかりません")
                # データをそのまま追加（情報なし）
                row['ラッシュ販売価格'] = ''
                row['ラッシュ在庫状況'] = 'キーワードなし'
                row['画像URL'] = ''
                row['期待利益'] = ''
                results.append(row)
                continue
            
            # Cloudflare対策: 毎回新しいコンテキストで初回アクセスとして扱う
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            try:
                target_name = row.get('カード名', '').strip()
                rarity = row.get('レア', '').strip()
                card_number_val = row.get('card_number', '').strip()
                rush_data = search_cardrush(page, keyword, target_name=target_name, rarity=rarity, card_number=card_number_val)
            finally:
                context.close()
            
            # リクエスト間に待機
            if idx < len(data):
                time.sleep(wait_between_requests)
            
            if rush_data:
                # データを統合
                if rush_data['price'] is not None:
                    # 価格が取得できた場合（在庫あり or 在庫なしでも価格あり）
                    row['ラッシュ販売価格'] = rush_data['price']
                    if rush_data['stock'] is not None:
                        # 在庫あり
                        row['ラッシュ在庫状況'] = f"在庫あり ({rush_data['stock']}枚)"
                    else:
                        # 在庫なしだが価格は取得できた
                        row['ラッシュ在庫状況'] = '在庫なし'
                    row['画像URL'] = rush_data['image_url'] or ''
                    
                    # 期待利益を計算（買取金額 - 販売価格）
                    buy_price = row.get('買取金額', '')
                    if buy_price and rush_data['price']:
                        try:
                            buy_price_int = int(buy_price)
                            expected_profit = buy_price_int - rush_data['price']
                            row['期待利益'] = expected_profit
                        except ValueError:
                            row['期待利益'] = ''
                    else:
                        row['期待利益'] = ''
                else:
                    # 価格が取得できなかったが画像は取得できた場合
                    row['ラッシュ販売価格'] = ''
                    row['ラッシュ在庫状況'] = '在庫なし'
                    row['画像URL'] = rush_data['image_url'] or ''
                    row['期待利益'] = ''
            else:
                # 検索に完全に失敗した場合
                row['ラッシュ販売価格'] = ''
                row['ラッシュ在庫状況'] = '在庫なし'
                row['画像URL'] = ''
                row['期待利益'] = ''
            
            results.append(row)
        
        browser.close()
    
    # (型番, カード名) で重複をまとめ、更新日が新しい行だけ残す
    if results:
        key_cols = ('card_number', 'カード名')
        def _parse_date(s):
            if not s or not str(s).strip():
                return (0, 0, 0)
            parts = str(s).strip().split('/')
            if len(parts) == 3:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return (y, m, d)
            if len(parts) == 2:
                m, d = int(parts[0]), int(parts[1])
                return (0, m, d)
            return (0, 0, 0)
        by_key = {}
        for row in results:
            key = tuple((row.get(k) or '').strip() for k in key_cols)
            if key not in by_key or _parse_date(row.get('更新日')) > _parse_date(by_key[key].get('更新日')):
                by_key[key] = row
        results = list(by_key.values())

    # CSVに保存
    print(f"\n結果をCSVに保存中: {output_csv}")
    if results:
        fieldnames = list(results[0].keys())
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"保存完了: {len(results)} 件のデータを {output_csv} に保存しました")
    else:
        print("保存するデータがありません")


def main():
    """
    メイン処理
    """
    input_csv = "otachu_psa10.csv"
    output_csv = "merged_card_data.csv"
    
    # デバッグモードの確認（コマンドライン引数で指定可能）
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    
    # 特定のカード番号でフィルタリング（--card 058/051 のように指定）
    filter_card_number = None
    filter_card_numbers = None
    if '--card' in sys.argv:
        card_index = sys.argv.index('--card')
        if card_index + 1 < len(sys.argv):
            filter_card_number = sys.argv[card_index + 1]
    # 複数カード番号でフィルタリング（--cards "236/187 132/106 ..." または --cards-file ファイル）
    if '--cards-file' in sys.argv:
        idx = sys.argv.index('--cards-file')
        if idx + 1 < len(sys.argv):
            path = sys.argv[idx + 1]
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    filter_card_numbers = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print(f"エラー: ファイルが見つかりません: {path}")
                return
    if '--cards' in sys.argv and filter_card_numbers is None:
        idx = sys.argv.index('--cards')
        if idx + 1 < len(sys.argv):
            raw = sys.argv[idx + 1]
            filter_card_numbers = [s.strip() for s in re.split(r'[\s,]+', raw) if s.strip()]
    
    # 最後N件のみ処理（--last 30 または --tail 30 のように指定）
    last_n = None
    if '--last' in sys.argv:
        last_index = sys.argv.index('--last')
        if last_index + 1 < len(sys.argv):
            try:
                last_n = int(sys.argv[last_index + 1])
            except ValueError:
                print("エラー: --last の後には数値を指定してください")
                return
    elif '--tail' in sys.argv:
        tail_index = sys.argv.index('--tail')
        if tail_index + 1 < len(sys.argv):
            try:
                last_n = int(sys.argv[tail_index + 1])
            except ValueError:
                print("エラー: --tail の後には数値を指定してください")
                return
    
    # 先頭N件のみ処理（--head 10）
    first_n = None
    if '--head' in sys.argv:
        head_index = sys.argv.index('--head')
        if head_index + 1 < len(sys.argv):
            try:
                first_n = int(sys.argv[head_index + 1])
            except ValueError:
                print("エラー: --head の後には数値を指定してください")
                return
    
    if debug_mode:
        print("=" * 50)
        print("デバッグモード: 先頭5件のみ処理します")
        print("=" * 50)
    
    if filter_card_number:
        print("=" * 50)
        print(f"フィルタモード: カード番号 '{filter_card_number}' のみ処理します")
        print("=" * 50)
    if filter_card_numbers:
        print("=" * 50)
        print(f"フィルタモード: カード番号リスト {len(filter_card_numbers)} 件のみ処理します")
        print("=" * 50)
    
    if last_n:
        print("=" * 50)
        print(f"最後{last_n}件のみ処理します")
        print("=" * 50)
    if first_n:
        print("=" * 50)
        print(f"先頭{first_n}件のみ処理します")
        print("=" * 50)
    
    scrape_cardrush_data(input_csv, output_csv, debug_mode=debug_mode, filter_card_number=filter_card_number, filter_card_numbers=filter_card_numbers, last_n=last_n, first_n=first_n)
    
    print("\n処理が完了しました")


if __name__ == "__main__":
    main()
