# PSA9 相場 定期取得（cron）

filtered_cards.csv の全件について GAS を呼び出し、PSA9 相場を取得して
`psa9_stats.json` に保存する。1日1回の実行を想定。

## 前提

- `merged_card_data.csv`（おたちゅう・カードラッシュのマージ結果）
- `filtered_cards.csv`（利益率20%以上のフィルタ済み）

が存在すること。

## 実行順（全体）

1. おたちゅう・カードラッシュをスクレイピング → `merged_card_data.csv`
2. `generate_filtered_csv.py` → `filtered_cards.csv`
3. `scripts/refresh_psa9_stats.py` → `psa9_stats.json`

## 手動実行

```bash
cd /path/to/project
export GAS_PSA9_API_URL=https://script.google.com/macros/s/あなたのID/exec
python scripts/refresh_psa9_stats.py
```

## cron 設定（毎日 3:00）

```bash
crontab -e
```

追加:

```
0 3 * * * cd /path/to/project && GAS_PSA9_API_URL=https://script.google.com/macros/s/あなたのID/exec /path/to/python scripts/refresh_psa9_stats.py >> /path/to/project/logs/psa9_refresh.log 2>&1
```

- `/path/to/project` を実際のプロジェクトルートに置き換え
- `/path/to/python` を venv の python に置き換える場合（例: `/path/to/project/venv/bin/python`）
- `logs` フォルダをあらかじめ作成しておく

## Lightsail の場合

Lightsail のサーバーで cron を設定し、上記と同じコマンドを登録する。
スクレイピング → generate_filtered_csv → refresh_psa9_stats の順で
1日1回まとめて実行する cron を組んでもよい。

例（毎日 3:00、フルパス指定）:

```
0 3 * * * cd /home/ubuntu/poke-trade-psa && GAS_PSA9_API_URL=https://script.google.com/macros/s/xxx/exec /home/ubuntu/poke-trade-psa/venv/bin/python scripts/refresh_psa9_stats.py >> /home/ubuntu/poke-trade-psa/logs/psa9.log 2>&1
```
