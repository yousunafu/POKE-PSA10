# Lightsail 1台に全部載せる — 手順書

React（フロント）・FastAPI（API）・定期スクレイプ（cron）を **1台の AWS Lightsail** で動かす手順です。

---

## 前提

- AWS アカウントがあること
- リポジトリが GitHub などにあり、Lightsail から clone できること
- インスタンスは **Ubuntu**（20.04 LTS または 22.04 LTS）を想定（Lightsail の「OS のみ」で選択）
- **2GB プラン**（約 $12/月、2 vCPU・60 GB SSD）を推奨（Playwright + Nginx + API で十分）

---

## 1. Lightsail インスタンスを作成

1. AWS コンソール → **Lightsail**
2. **インスタンスの作成**
3. **プラットフォーム**: Linux/Unix  
   **ブループリント**: OS のみ → **Ubuntu 22.04**
4. **インスタンスプラン**: **$12**（2 GB RAM, 2 vCPU, 60 GB SSD）— 一覧から「2 GB Memory」のプランを選択
5. インスタンス名を付けて作成
6. 作成後、**静的 IP をアタッチ**しておく（再起動しても IP が変わらないようにする）
7. **SSH 用のキー**をダウンロードするか、ブラウザの「ターミナル」から入る

---

## 2. サーバーに SSH 接続

- Lightsail の画面から「ターミナル」を開く  
  または  
- ローカルから: `ssh -i /path/to/key.pem ubuntu@<静的IP>`

以降のコマンドは **ubuntu ユーザー**で実行する想定です。

---

## 3. 初期設定（Python, Node, Nginx, Playwright）

```bash
# パッケージ更新
sudo apt update && sudo apt upgrade -y

# Python 3.10+, pip, venv
sudo apt install -y python3 python3-pip python3-venv

# Node.js 20（React ビルド用）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Nginx
sudo apt install -y nginx

# Playwright 用の依存（Chromium 実行に必要）
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2
```

---

## 4. リポジトリの配置と CSV

```bash
# 作業ディレクトリ（例: /home/ubuntu/app）
export APP_DIR=/home/ubuntu/app
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Git で clone（HTTPS の場合）
git clone https://github.com/<あなたのユーザー>/<リポジトリ名>.git .
# または SSH で clone する場合はあらかじめ SSH キーを登録

# 初回のみ: merged_card_data.csv が無い場合は scrape を 1 回手動実行するか、
# ローカルで用意した CSV を scp でアップロードする
# scp merged_card_data.csv ubuntu@<IP>:$APP_DIR/
```

- **API は** `$APP_DIR/merged_card_data.csv` **を読む**（backend のコードが `../merged_card_data.csv` を参照）
- **cron のスクレイプ**がこの同じファイルを更新する

---

## 5. Python 環境と FastAPI の起動

```bash
cd $APP_DIR

# venv 作成
python3 -m venv venv
source venv/bin/activate

# API 用
pip install --upgrade pip
pip install -r backend/requirements.txt

# スクレイプ用（scrape_otachu.py / scrape_rush.py）
pip install playwright
playwright install chromium
playwright install-deps || true
```

**systemd で API を常時起動**する:

```bash
sudo tee /etc/systemd/system/poke-psa-api.service << 'EOF'
[Unit]
Description=Poke PSA FastAPI
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/app
Environment="PATH=/home/ubuntu/app/venv/bin"
ExecStart=/home/ubuntu/app/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

- `WorkingDirectory=/home/ubuntu/app` にすると、`backend/main.py` の `CSV_PATH` が `../merged_card_data.csv` ＝ `/home/ubuntu/app/merged_card_data.csv` になる

```bash
sudo systemctl daemon-reload
sudo systemctl enable poke-psa-api
sudo systemctl start poke-psa-api
sudo systemctl status poke-psa-api
```

---

## 6. React のビルドと配置

**サーバー上でビルドする場合**（推奨）:

```bash
cd $APP_DIR/frontend
npm ci
npm run build
```

- 本番では **同じオリジン**で API を叩くので、`VITE_API_URL` は指定しなくてよい（空のまま＝`/api` に相対でアクセス）

**ビルド結果**は `frontend/dist` にできます。Nginx ではこの `dist` をドキュメントルートにします。

---

## 7. Nginx の設定

- **`/`** … React の静的ファイル（`frontend/dist`）
- **`/api`** … FastAPI（`http://127.0.0.1:8000`）にリバースプロキシ

```bash
sudo tee /etc/nginx/sites-available/poke-psa << 'EOF'
server {
    listen 80;
    server_name _;   # ドメインを付ける場合はここに例: example.com

    root /home/ubuntu/app/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

```bash
sudo ln -sf /etc/nginx/sites-available/poke-psa /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

- ドメインを使う場合は `server_name` をそのドメインに変更する
- HTTPS にする場合は後述の「任意: SSL」を参照

---

## 8. 定期スクレイプ（cron）の設定

10:00 と 18:00 **JST** に `scrape_otachu.py` → `scrape_rush.py` を実行します。サーバーが UTC なら **01:00** と **09:00 UTC** にします。

```bash
crontab -e
```

次の 2 行を追加（1行目が 10:00 JST、2行目が 18:00 JST）:

```cron
0 1 * * * cd /home/ubuntu/app && /home/ubuntu/app/venv/bin/python scrape_otachu.py && /home/ubuntu/app/venv/bin/python scrape_rush.py
0 9 * * * cd /home/ubuntu/app && /home/ubuntu/app/venv/bin/python scrape_otachu.py && /home/ubuntu/app/venv/bin/python scrape_rush.py
```

- 実行後、`merged_card_data.csv` が同じディレクトリで更新され、API が次回リクエストからその内容を返します
- ログを残したい場合の例:
  ```cron
  0 1 * * * cd /home/ubuntu/app && /home/ubuntu/app/venv/bin/python scrape_otachu.py && /home/ubuntu/app/venv/bin/python scrape_rush.py >> /home/ubuntu/app/scrape.log 2>&1
  ```

---

## 9. 動作確認

1. ブラウザで `http://<静的IP>/` を開く → React の画面が出る
2. 画面からカード一覧が表示される → API（`/api/cards`）が動いている
3. `http://<静的IP>/api/cards` を直接開く → JSON が返る

手動でスクレイプを試す場合:

```bash
cd /home/ubuntu/app
source venv/bin/activate
python scrape_otachu.py
python scrape_rush.py
# merged_card_data.csv が更新されていることを確認
```

---

## 10. 任意: ドメインと SSL（HTTPS）

- Lightsail で **ドメイン**を割り当て可能
- HTTPS には **Let's Encrypt**（certbot）が使える

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

- Nginx の `server_name` を `example.com` にしておき、certbot 実行後に自動で HTTPS 設定が入ります

---

## 11. 運用メモ

| やりたいこと | コマンド例 |
|--------------|------------|
| API の再起動 | `sudo systemctl restart poke-psa-api` |
| API のログ確認 | `journalctl -u poke-psa-api -f` |
| フロントの更新 | `cd $APP_DIR/frontend && git pull && npm ci && npm run build`（Nginx は再起動不要） |
| バックエンドの更新 | `cd $APP_DIR && git pull && sudo systemctl restart poke-psa-api` |
| スクレイプの手動実行 | `cd $APP_DIR && source venv/bin/activate && python scrape_otachu.py && python scrape_rush.py` |
| cron のログ | 上記のように `>> scrape.log` を入れていれば `tail -f /home/ubuntu/app/scrape.log` |

---

## トラブルシュート

- **502 Bad Gateway**  
  - FastAPI が止まっている: `sudo systemctl status poke-psa-api` で確認し、`sudo systemctl start poke-psa-api`
  - `merged_card_data.csv` が無いと API が 500 を返すので、初回は CSV を置くかスクレイプを 1 回実行する

- **カード一覧が表示されない**  
  - ブラウザの開発者ツールで `/api/cards` のレスポンスを確認。404 なら Nginx の `location /api/` と proxy_pass を確認

- **スクレイプが cron で動かない**  
  - `crontab -l` でパスとユーザーを確認。フルパスで `python` とスクリプトを指定しているか。ログを `>> scrape.log` で確認

- **Playwright がヘッドレスで動かない**  
  - `playwright install-deps` を実行。それでも失敗する場合は `DISPLAY= playwright install chromium` や、上記の依存パッケージが入っているか確認

---

以上で、Lightsail 1台に React・Python・定期スクレイプを載せた構成になります。
