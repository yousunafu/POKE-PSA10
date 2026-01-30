# Web版（FastAPI + React/Vite）の起動方法

## 構成

- **backend/** … FastAPI。`merged_card_data.csv` はプロジェクトルートを参照。
- **frontend/** … Vite + React + Tailwind。開発時は proxy で `http://localhost:8000` に API を転送。

## 手順

### 1. バックエンド

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- `http://localhost:8000/api/cards` で JSON が返ることを確認。

### 2. フロントエンド

```bash
cd frontend
npm install
npm run dev
```

- ブラウザで `http://localhost:5173` を開く（API は proxy で 8000 に転送される）。

## 本番ビルド

- フロント: `cd frontend && npm run build` → `dist/` を静的ホストに配置。
- API の URL は環境変数 `VITE_API_URL` で指定（例: `VITE_API_URL=https://api.example.com`）。未設定時は同オリジン（proxy または同じホスト）を利用。
