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


def _normalize_card_name(name: str) -> str:
    """
    カード名のゆらぎを吸収するために正規化するヘルパー
    - 空白・全角空白の削除
    - 括弧や装飾記号の削除
    """
    if not name:
        return ""
    # 前後の空白を削除
    name = name.strip()
    # 「（」「(」以降の補足情報は一旦切り落とす（例: ピカチュウGX(SA) -> ピカチュウGX）
    name = re.split(r'[（(]', name)[0]
    # 装飾用の記号を削除
    name = re.sub(r'[【】\[\]（）\(\)「」『』<>＜＞:：・、，,\s]', '', name)
    return name


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


def search_cardrush(page, keyword: str, target_name: str = "", rarity: str = "") -> Optional[Dict]:
    """
    カードラッシュで検索して、在庫ありの最安値商品情報を取得
    タイムアウトが発生しても画像だけは取得を試みる
    rarity: レア（マスボの場合は「マスターボールミラー」の価格を取得する）。
    """
    image_url = None  # エラー時でも画像取得を試みるため、外側で定義
    
    try:
        # 検索URL（日本語キーワードをURLエンコード）
        encoded_keyword = quote(keyword)
        search_url = f"https://www.cardrush-pokemon.jp/product-list?keyword={encoded_keyword}"
        
        print(f"  検索中: {keyword} -> {search_url}")
        if target_name:
            print(f"  ターゲットカード名: {target_name} (正規化後: {_normalize_card_name(target_name)})")
        
        # タイムアウトを長めに設定し、エラーが発生しても処理を続行
        try:
            page.goto(search_url, wait_until="networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            print(f"  タイムアウトが発生しましたが、ページの読み込みを続行します...")
            # タイムアウトしてもページは部分的に読み込まれている可能性がある
            time.sleep(2)  # 少し待機してから続行
        
        # ページが読み込まれるまで少し待機
        time.sleep(1)
        
        # 検索結果の商品リストを取得
        product_items = []  # 在庫ありの商品
        out_of_stock_items = []  # 在庫なしの商品（価格と画像を取得するため）
        normalized_target_name = _normalize_card_name(target_name)
        
        # 商品リンクを取得（より具体的なセレクターを使用）
        # 検索結果ページでは、商品情報が含まれるリンクを探す
        product_links = page.query_selector_all("a[href*='/product/']")
        
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
                
                # 元データのカード名とのマッチ度を計算
                normalized_product_name = _normalize_card_name(product_name)
                name_match = (
                    bool(normalized_target_name)
                    and normalized_target_name in normalized_product_name
                )
                
                # デバッグ出力（最初の数件のみ）
                if len(product_items) + len(out_of_stock_items) < 3:
                    print(f"    商品名: {product_name[:50]}")
                    print(f"    正規化後: {normalized_product_name}")
                    print(f"    ターゲット名: {target_name} -> 正規化後: {normalized_target_name}")
                    print(f"    マッチ: {name_match}")

                product_data = {
                    'name': product_name[:100],  # 長すぎる場合は切り詰め
                    'price': price,
                    'stock': stock_count,
                    'url': product_url,
                    'image_url': image_url or '',
                    # 元カード名とのマッチしているかどうか（優先度付けに使用）
                    'name_match': name_match,
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
        
        # 在庫ありの商品がある場合
        if product_items:
            # 元カード名とマッチする商品だけを抽出
            matched_items = [p for p in product_items if p.get('name_match')]
            # レアがマスボの場合は「マスターボールミラー」の商品に絞り、状態なしを優先
            if rarity == "マスボ":
                matched_items = _filter_masbo_candidates(matched_items)
                if matched_items:
                    print(f"    マスボ: マスターボールミラー対象 {len(matched_items)} 件")
            
            # マッチする商品がある場合のみ、その中から最安値を探す
            if matched_items:
                cheapest = min(matched_items, key=lambda x: x['price'])
                print(f"    在庫ありリストから該当カード名({target_name})を含む商品を選択: {cheapest['name'][:50]} ({cheapest['price']}円)")
                return {
                    'price': cheapest['price'],
                    'stock': cheapest['stock'],
                    'url': cheapest['url'],
                    'image_url': cheapest['image_url'],
                    'product_name': cheapest['name']
                }
            else:
                # マッチする商品がない場合は、「見つからなかった」として処理を続行
                # (無理やり違うカードを返さないようにする)
                print(f"    在庫ありリストに該当カード名({target_name})を含む商品が見つかりませんでした (全{len(product_items)}件)")
        
        # 在庫ありの商品がない場合、在庫なしの商品から価格と画像を取得
        if out_of_stock_items:
            # 元カード名とマッチする在庫なし商品のみを抽出
            matched_out_of_stock = [p for p in out_of_stock_items if p.get('name_match')]
            # レアがマスボの場合は「マスターボールミラー」の商品に絞り、状態なしを優先
            if rarity == "マスボ":
                matched_out_of_stock = _filter_masbo_candidates(matched_out_of_stock)
                if matched_out_of_stock:
                    print(f"    マスボ: マスターボールミラー対象(在庫なし) {len(matched_out_of_stock)} 件")
            
            if matched_out_of_stock:
                print(f"  在庫ありの商品が見つかりませんでした。在庫なしの商品から価格と画像を取得します...")
                # マッチしたものの中から最安値を取得
                cheapest_out_of_stock = min(matched_out_of_stock, key=lambda x: x['price'])
                print(f"    在庫なしリストから該当カード名({target_name})を含む商品を選択: {cheapest_out_of_stock['name'][:50]} ({cheapest_out_of_stock['price']}円)")
                return {
                    'price': cheapest_out_of_stock['price'],  # 価格を返す
                    'stock': None,  # 在庫なし
                    'url': cheapest_out_of_stock['url'],
                    'image_url': cheapest_out_of_stock['image_url'],
                    'product_name': cheapest_out_of_stock['name']
                }
            else:
                print(f"  在庫なしリストにも該当カード名({target_name})を含む商品が見つかりませんでした (全{len(out_of_stock_items)}件)")
        
        # 商品が全く見つからない場合、画像だけでも取得を試みる
        print(f"  商品が見つかりませんでした。画像のみ取得を試みます...")
        
        # 検索結果ページから最初の商品画像を取得（在庫状況に関係なく）
        image_url = None
        try:
            # 検索結果ページの最初の商品リンクから画像を取得
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
        except Exception as e:
            print(f"    画像取得エラー: {e}")
        
        # 画像があれば返す
        return {
            'price': None,
            'stock': None,
            'url': None,
            'image_url': image_url or '',
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


def scrape_cardrush_data(input_csv: str, output_csv: str, debug_mode: bool = False, filter_card_number: str = None, last_n: int = None):
    """
    カードラッシュのデータをスクレイピングして統合
    
    Args:
        input_csv: 入力CSVファイル
        output_csv: 出力CSVファイル
        debug_mode: デバッグモード（先頭5件のみ）
        filter_card_number: 特定のカード番号でフィルタリング（例: "058/051"）
        last_n: 最後N件のみ処理（例: 30）
    """
    # CSVを読み込む
    print(f"CSVファイルを読み込み中: {input_csv}")
    data = read_otachu_csv(input_csv)
    
    # 特定のカード番号でフィルタリング
    if filter_card_number:
        original_count = len(data)
        data = [row for row in data if row.get('card_number', '').strip() == filter_card_number]
        print(f"カード番号 '{filter_card_number}' でフィルタリング: {original_count}件 -> {len(data)}件")
        if len(data) == 0:
            print(f"エラー: カード番号 '{filter_card_number}' が見つかりませんでした")
            return
    
    # 最後N件のみ処理
    if last_n is not None and last_n > 0:
        original_count = len(data)
        data = data[-last_n:]  # 最後N件を取得
        print(f"最後{last_n}件のみ処理: {original_count}件 -> {len(data)}件")
    
    if debug_mode:
        data = data[:5]
        print(f"デバッグモード: 先頭5件のみ処理します")
    
    print(f"合計 {len(data)} 件のデータを処理します")
    
    results = []
    
    with sync_playwright() as p:
        # ブラウザを起動
        browser = None
        try:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
        except Exception as e:
            print(f"Chromiumの起動に失敗しました: {e}")
            print("Firefoxを使用して再試行します...")
            try:
                browser = p.firefox.launch(headless=True)
            except Exception as e2:
                print(f"Firefoxの起動にも失敗しました: {e2}")
                raise
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
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
            
            # カードラッシュで検索（元のカード名・レアも渡す。マスボの場合はマスターボールミラーを取得）
            target_name = row.get('カード名', '').strip()
            rarity = row.get('レア', '').strip()
            rush_data = search_cardrush(page, keyword, target_name=target_name, rarity=rarity)
            
            # リクエスト間に待機時間を入れる
            wait_time = 2.5  # 2.5秒待機
            time.sleep(wait_time)
            
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
    if '--card' in sys.argv:
        card_index = sys.argv.index('--card')
        if card_index + 1 < len(sys.argv):
            filter_card_number = sys.argv[card_index + 1]
    
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
    
    if debug_mode:
        print("=" * 50)
        print("デバッグモード: 先頭5件のみ処理します")
        print("=" * 50)
    
    if filter_card_number:
        print("=" * 50)
        print(f"フィルタモード: カード番号 '{filter_card_number}' のみ処理します")
        print("=" * 50)
    
    if last_n:
        print("=" * 50)
        print(f"最後{last_n}件のみ処理します")
        print("=" * 50)
    
    scrape_cardrush_data(input_csv, output_csv, debug_mode=debug_mode, filter_card_number=filter_card_number, last_n=last_n)
    
    print("\n処理が完了しました")


if __name__ == "__main__":
    main()
