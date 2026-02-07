# GAS PSA9 API デプロイ手順

## 1. コードを GAS に配置

1. [Google Apps Script](https://script.google.com/) を開く
2. 「新しいプロジェクト」を作成
3. `scripts/gas/psa9_stats_api.gs` の内容をすべてコピーして、GAS の `Code.gs` を上書き
4. 保存（Ctrl+S / Cmd+S）

## 2. ウェブアプリとしてデプロイ

1. 右上の「デプロイ」→「新しいデプロイ」
2. 種類: 「ウェブアプリ」を選択
3. 設定:
   - **説明**: 任意（例: PSA9 API v1）
   - **実行ユーザー**: 自分
   - **アクセスできるユーザー**: 全員（匿名ユーザーを含む）
4. 「デプロイ」をクリック
5. **ウェブアプリのURL**をコピー（`https://script.google.com/macros/s/xxx/exec` の形式）

## 3. 動作確認

### GET（デプロイ確認）

ブラウザでデプロイした URL を開く。

- 表示: `PSA9 API is running. Use POST with { cards: [...] }.` → 成功

### POST（1件テスト）

ターミナルで curl を実行:

```bash
curl -X POST "あなたのGAS_URL" \
  -H "Content-Type: application/json" \
  -d '{"cards":[{"id":"test1","cardName":"リーリエのピッピex","cardNum":"765/742","rarity":"SAR"}]}'
```

- JSON 形式で `{ "results": [ { "yahooAvg", "yahooMedian", "recent1", ... } ] }` が返ってくれば成功

## 4. コード更新時の再デプロイ

1. コードを編集して保存
2. 「デプロイ」→「デプロイを管理」
3. 該当デプロイの右側の鉛筆アイコン「編集」
4. 「バージョン」を「新バージョン」に変更
5. 「デプロイ」をクリック
6. **URL は変わらない**（同じデプロイIDのまま）

## 5. FastAPI での利用

デプロイした URL を環境変数に設定してバックエンドを起動:

```bash
export GAS_PSA9_API_URL=https://script.google.com/macros/s/xxx/exec
uvicorn backend.main:app --reload
```

または `.env` に記述して読み込む（プロジェクトで dotenv を使用している場合）:

```
GAS_PSA9_API_URL=https://script.google.com/macros/s/xxx/exec
```

POST のボディ形式:

```json
{
  "cards": [
    {
      "id": "optional-id",
      "cardName": "リーリエのピッピex",
      "cardNum": "765/742",
      "rarity": "SAR"
    }
  ]
}
```

- `cardName` / `card_name`、`cardNum` / `card_number` のどちらでも可
- 1回あたり最大 30 件まで
