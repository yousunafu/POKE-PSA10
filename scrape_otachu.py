"""
おたちゅう秋葉原のPSA10買取価格表をスクレイピングするスクリプト
"""
import re
import csv
from playwright.sync_api import sync_playwright
from typing import List, Dict


def extract_card_number(card_name: str) -> str:
    """
    カード名から型番を抽出する
    例: "094/080", "SV2a", "123/456" などを抽出
    """
    if not card_name:
        return ""
    
    # パターン1: 数字/数字の形式（例: 094/080, 123/456, 025/165）
    pattern1 = r'\d{2,3}/\d{2,3}'
    match1 = re.search(pattern1, card_name)
    if match1:
        return match1.group(0)
    
    # パターン2: 数字/数字/数字の形式（例: 001/030）
    pattern1b = r'\d{3}/\d{3}'
    match1b = re.search(pattern1b, card_name)
    if match1b:
        return match1b.group(0)
    
    # パターン3: 数字/SV-P などの形式（例: 001/SV-P, 260/SV-P, 062/SV-P）
    pattern2 = r'\d{2,3}/[A-Z-]+'
    match2 = re.search(pattern2, card_name)
    if match2:
        return match2.group(0)
    
    # パターン4: アルファベット+数字+アルファベットの形式（例: SV2a, M2, SV11B, SV8a）
    pattern3 = r'[A-Z]{1,3}\d{1,3}[a-zA-Z]?'
    match3 = re.search(pattern3, card_name)
    if match3:
        return match3.group(0)
    
    # パターン5: 数字/S-P などの形式（例: 001/S-P）
    pattern4 = r'\d{2,3}/S-P'
    match4 = re.search(pattern4, card_name)
    if match4:
        return match4.group(0)
    
    return ""


def clean_price(price_str: str) -> int:
    """
    買取金額から「円」やカンマを除去して数値型に変換
    """
    # 「¥」、カンマ、「円」を除去
    cleaned = price_str.replace('¥', '').replace(',', '').replace('円', '').strip()
    
    # 数値に変換
    try:
        return int(cleaned)
    except ValueError:
        return 0


def scrape_otachu_psa10(url: str) -> List[Dict]:
    """
    おたちゅう秋葉原のPSA10買取価格表をスクレイピング
    """
    results = []
    current_set_name = ""  # 現在のセット名を保持
    
    with sync_playwright() as p:
        # ブラウザを起動（Chromiumで試行、失敗した場合はFirefoxを使用）
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
        
        page = browser.new_page()
        
        # ページにアクセス
        print(f"ページにアクセス中: {url}")
        page.goto(url, wait_until="networkidle")
        
        # 少し待機してページが完全に読み込まれるのを待つ
        page.wait_for_timeout(2000)
        
        # テーブルを取得
        tables = page.query_selector_all("table")
        
        print(f"{len(tables)}個のテーブルが見つかりました")
        
        for table_idx, table in enumerate(tables):
            # テーブル内のすべての行を取得
            rows = table.query_selector_all("tr")
            
            for row_idx, row in enumerate(rows):
                cells = row.query_selector_all("td, th")
                
                # セルが少なすぎる場合はスキップ
                if len(cells) < 4:
                    continue
                
                # セルのテキストを取得
                cell_texts = [cell.inner_text().strip() for cell in cells]
                
                # ヘッダー行をスキップ（「弾」「Ｎｏ．」「レア」などのキーワードが含まれている場合）
                if any(keyword in " ".join(cell_texts) for keyword in ["弾", "Ｎｏ", "No", "レア", "カード名", "買取金額", "更新"]):
                    # ヘッダー行の場合は、次の行の準備としてスキップ
                    continue
                
                # セル数に応じてデータを抽出
                # セル構造のパターン:
                # パターン1: [弾, No, レア, カード名, 買取金額, 更新日] (6セル)
                # パターン2: [No, レア, カード名, 買取金額, 更新日] (5セル)
                # パターン3: [弾名のみ] (1セル - セット名の行)
                
                if len(cell_texts) == 1:
                    # セット名の行の可能性
                    potential_set_name = cell_texts[0]
                    if potential_set_name and not any(char in potential_set_name for char in ["¥", "円", "/"]):
                        current_set_name = potential_set_name
                    continue
                
                # データ行の処理
                if len(cell_texts) >= 5:
                    # セル数に応じてインデックスを調整
                    if len(cell_texts) == 6:
                        # [弾, No, レア, カード名, 買取金額, 更新日]
                        set_name = cell_texts[0] if cell_texts[0] else current_set_name
                        no = cell_texts[1]
                        rarity = cell_texts[2]
                        card_name = cell_texts[3]
                        price = cell_texts[4]
                        update_date = cell_texts[5] if len(cell_texts) > 5 else ""
                    elif len(cell_texts) == 5:
                        # [No, レア, カード名, 買取金額, 更新日] または [弾, No, レア, カード名, 買取金額]
                        # 最初のセルが数字/数字の形式ならNo、そうでなければ弾名
                        if re.match(r'\d+/\d+', cell_texts[0]) or cell_texts[0].isdigit():
                            set_name = current_set_name
                            no = cell_texts[0]
                            rarity = cell_texts[1]
                            card_name = cell_texts[2]
                            price = cell_texts[3]
                            update_date = cell_texts[4] if len(cell_texts) > 4 else ""
                        else:
                            set_name = cell_texts[0] if cell_texts[0] else current_set_name
                            no = cell_texts[1]
                            rarity = cell_texts[2]
                            card_name = cell_texts[3]
                            price = cell_texts[4]
                            update_date = ""
                    else:
                        # その他のパターンはスキップ
                        continue
                    
                    # 空のデータはスキップ
                    if not card_name or not price or "¥" not in price:
                        continue
                    
                    # 型番を抽出（Noカラムとカード名の両方から試行）
                    card_number = no if no else extract_card_number(card_name)
                    if not card_number:
                        card_number = extract_card_number(card_name)
                    
                    # 価格を数値に変換
                    price_int = clean_price(price)
                    
                    # 価格が0の場合はスキップ（データが不正な可能性）
                    if price_int == 0:
                        continue
                    
                    # 結果に追加
                    result = {
                        "No": no,
                        "レア": rarity,
                        "カード名": card_name,
                        "買取金額": price_int,
                        "更新日": update_date,
                        "card_number": card_number,
                        "弾": set_name
                    }
                    
                    results.append(result)
        
        browser.close()
    
    print(f"合計 {len(results)} 件のデータを取得しました")
    return results


def save_to_csv(data: List[Dict], filename: str):
    """
    データをCSVファイルに保存
    """
    if not data:
        print("保存するデータがありません")
        return
    
    # CSVのカラム順序を定義（要件に合わせて順序を調整）
    fieldnames = ["No", "レア", "カード名", "card_number", "買取金額", "更新日", "弾"]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"データを {filename} に保存しました")


def main():
    """
    メイン処理
    """
    url = "https://otachu-akiba.com/1gocard/buying_price/psa-pokemon-cards/"
    output_file = "otachu_psa10.csv"
    
    # スクレイピング実行
    data = scrape_otachu_psa10(url)
    
    # CSVに保存
    save_to_csv(data, output_file)
    
    print("処理が完了しました")


if __name__ == "__main__":
    main()
