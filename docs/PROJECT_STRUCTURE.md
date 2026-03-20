# Poke trade PSA 全体構造

上司や新規メンバー向けに、リポジトリの全体像を短時間で把握できるようにまとめたドキュメントです。

## 1. 何をするシステムか

- おたちゅう買取価格とカードラッシュ販売価格を収集
- 利益計算を行い、仕入れ候補を抽出
- フロントでカード一覧・利益・外部リンク（eBay/メルカリ/ヤフオク/スニダン/ポケ相場）を表示

## 2. ディレクトリの役割

- `backend/`
  - FastAPI API
  - `main.py`: `/api/cards` と PSA9系 API を提供
- `frontend/`
  - React + Vite UI
  - `src/App.jsx`: 画面全体・データ取得・フィルタ管理
  - `src/components/`: 一覧表示・テーブル表示・フィルタUI
  - `src/utils/profitCalc.js`: 利益計算ロジック
- `scripts/`
  - 運用補助スクリプト群
  - `run_scheduled_update.sh`: 定期更新のまとめ実行
  - `refresh_psa9_stats.py`: PSA9（ヤフオク/メルカリ）更新
  - `update_ebay_links_gemini.py`: eBayリンクの新規追加
- `docs/`
  - Lightsail運用、GAS、定期更新、CSV仕様などの手順書

## 3. 主要データファイル

- `merged_card_data.csv`
  - おたちゅう + カードラッシュを突合した元データ
- `filtered_cards.csv`
  - 利益条件で絞り込んだ候補データ
- `psa9_stats.json`
  - PSA9のヤフオク統計・直近リンク・メルカリURL
- `ebay_links.json`
  - カードごとの eBay 売却済み検索URL
- `pokeca_chart_links.json`
  - カードごとのポケ相場URL

## 4. 更新フロー（通常運用）

1. `run_scheduled_update.sh`
   - `scrape_otachu.py`
   - `scrape_rush.py`
   - `generate_filtered_csv.py`
2. `refresh_psa9_stats.py`（ヤフオク/メルカリ）
3. `update_ebay_links_gemini.py`（必要時）
4. `fetch_pokeca_chart_links.py`（必要時）

## 5. 環境変数と機密情報

- `.env` は Git 管理外（`.gitignore` 設定済み）
- 主なキー:
  - `GAS_PSA9_API_URL`
  - `GEMINI_API_KEY`
- APIキーはコードやドキュメントに直書きしない

## 6. ローカル起動

- API:
  - `cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Front:
  - `cd frontend && npm run dev`

## 7. デプロイ（Lightsail）

- `docs/LIGHTSAIL_ONE_SERVER.md` を参照
- 基本は `git pull` -> フロントビルド -> API再起動

