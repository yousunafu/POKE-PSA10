#!/usr/bin/env bash
# 定時実行用: おたちゅう → カードラッシュ → filtered_cards → eBay リンク（新規のみ Gemini）
# 環境変数は .env から読み込む（GEMINI_API_KEY など）。cron から呼ぶときはプロジェクトルートで実行すること。
#
# 例（cron）:
#   0 10 * * * cd /Users/あなた/Desktop/Poke\ trade\ PSA && ./scripts/run_scheduled_update.sh
#   0 1 * * * cd /home/ubuntu/app && PYTHON=/home/ubuntu/app/venv/bin/python ./scripts/run_scheduled_update.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# .env があれば読み込む（GEMINI_API_KEY 等）
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

PYTHON="${PYTHON:-python3}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] scrape_otachu.py"
$PYTHON scrape_otachu.py

echo "[$(date '+%Y-%m-%d %H:%M:%S')] scrape_rush.py"
$PYTHON scrape_rush.py

echo "[$(date '+%Y-%m-%d %H:%M:%S')] generate_filtered_csv.py"
$PYTHON generate_filtered_csv.py

echo "[$(date '+%Y-%m-%d %H:%M:%S')] update_ebay_links_gemini.py（新規カードがあれば ebay_links.json に追加）"
$PYTHON scripts/update_ebay_links_gemini.py || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完了"
