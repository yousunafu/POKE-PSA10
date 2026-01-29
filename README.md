# ポケモンカード PSA10 買取・販売価格比較アプリ

## 概要

このプロジェクトは、**ポケモンカード（PSA10鑑定品）**の**買取価格**と**販売価格**を比較し、**転売・トレードの利益**を可視化するツールです。

- **買取元**: おたちゅう秋葉原（PSA10買取価格表）
- **販売先**: カードラッシュ（素体A相当の販売価格・在庫）
- **目的**: 「おたちゅうで買い取ってもらい、カードラッシュで売る」場合の**期待利益**を一覧で確認する

---

## プロジェクト構成

| ファイル・フォルダ | 説明 |
|-------------------|------|
| **app.py** | Streamlitで動くメインアプリ。統合データの表示・フィルター・利益計算 |
| **scrape_otachu.py** | おたちゅう秋葉原のPSA10買取価格表をスクレイピングし、`otachu_psa10.csv` を生成 |
| **scrape_rush.py** | `otachu_psa10.csv` を元にカードラッシュで販売価格・在庫を検索し、`merged_card_data.csv` を生成 |
| **merged_card_data.csv** | 買取価格＋販売価格＋在庫＋期待利益を統合したデータ（アプリの入力データ） |
| **otachu_psa10.csv** | おたちゅうの買取価格のみのCSV（scrape_otachu の出力） |
| **requirements.txt** | Python依存パッケージ（playwright, streamlit, pandas） |
| **.streamlit/config.toml** | Streamlitの設定（ポート8501、UIの簡略化など） |

---

## データの流れ

```
1. scrape_otachu.py
   → おたちゅう秋葉原のPSA10買取価格表をスクレイピング
   → otachu_psa10.csv（No, レア, カード名, card_number, 買取金額, 更新日, 弾）

2. scrape_rush.py
   → otachu_psa10.csv を読み込み、各カードをカードラッシュで検索
   → 販売価格・在庫・画像URLを取得し、期待利益（買取価格 − 販売価格）を計算
   → merged_card_data.csv に統合

3. app.py
   → merged_card_data.csv を読み込み、Streamlitで表示
   → キーワード検索・在庫ありのみ・利益が出るもののみなどのフィルター
   → テーブル表示（PC向け）とカード型リスト表示（スマホ向け）の2モード
```

---

## 主な機能（app.py）

- **買取比較表示**
  - おたちゅうの買取価格（PSA10）
  - カードラッシュの販売価格（素体A相当）と在庫状況
  - **期待利益** = 買取価格 − 販売価格（プラスなら転売で利益が出る想定）
- **フィルター**
  - キーワード検索（カード名・型番・No）
  - 「在庫ありのみ表示」
  - 「利益が出る商品のみ表示」
- **表示モード**
  - **データ分析（PC向け）**: テーブル形式、ソート・統計表示
  - **現場リサーチ（スマホ向け）**: カード型リスト、ページネーション、画像付き
- **レスポンシブ**: スマホ用のコンパクトなレイアウト・サイドバーとメインのフィルター連携

---

## 技術スタック

- **Python 3**
- **Streamlit** … WebアプリUI
- **Pandas** … CSVの読み込み・フィルター・集計
- **Playwright** … おたちゅう・カードラッシュのスクレイピング（ヘッドレスブラウザ）

---

## 使い方

### 1. 環境準備

```bash
pip install -r requirements.txt
playwright install   # Chromium 等のブラウザをインストール
```

### 2. データ取得（任意・更新時）

```bash
# おたちゅうの買取価格を取得
python scrape_otachu.py

# カードラッシュの販売価格・在庫を取得して統合CSVを更新
python scrape_rush.py
```

scrape_rush.py のオプション例:

- `--debug` または `-d` … 先頭5件のみ処理（動作確認用）
- `--card 058/051` … 指定したカード番号のみ処理
- `--last 30` または `--tail 30` … 最後30件のみ処理

### 3. アプリの起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` を開く（`.streamlit/config.toml` でポート8501・アドレス0.0.0.0に設定済み）。

---

## デプロイ方法

### 推奨: Streamlit Community Cloud（無料・公式）

1. **GitHubにリポジトリを用意**
   - このプロジェクトのリポジトリ: [https://github.com/yousunafu/POKE-PSA10](https://github.com/yousunafu/POKE-PSA10)
   - `merged_card_data.csv` をリポジトリに含める（アプリがこのファイルを読み込むため）

2. **Streamlit Cloudに登録・デプロイ**
   - [share.streamlit.io](https://share.streamlit.io) にアクセス
   - GitHubでサインインし、「New app」からリポジトリを選択
   - **Branch**: `main`（または使用しているブランチ）
   - **Main file path**: `app.py`
   - **App URL**: 任意のサブドメイン（例: `poke-trade-psa`）
   - 「Deploy」でデプロイ開始。数分で公開URLが発行される

3. **注意**
   - スクレイピング（`scrape_otachu.py` / `scrape_rush.py`）は**クラウド上では実行しない**想定。データ更新はローカルで行い、更新した `merged_card_data.csv` をコミット・プッシュするとアプリが自動で再デプロイされる
   - `playwright` は**app.py の実行には不要**。デプロイ時のビルドを軽くするため、`requirements.txt` を「app 用」と「スクレイプ用」で分けてもよい（後述）

#### デプロイ専用 requirements（オプション）

Streamlit Cloud ではアプリ表示だけなら Playwright は不要です。デプロイ用に `requirements-deploy.txt` を用意し、Streamlit Cloud の「Advanced settings」でこれを指定するとビルドが速くなります。

```
streamlit>=1.28.0
pandas>=2.0.0
```

（スクレイピングはローカルでのみ実行し、そのときは `pip install -r requirements.txt` を使う）

### その他の選択肢

- **Render** … Web Service として「Start command」に `streamlit run app.py --server.port=$PORT` を指定
- **Railway** … 同様に Streamlit を起動コマンドで指定
- **自前サーバー** … `streamlit run app.py --server.port=8501` を systemd や Docker で常時起動

---

## 注意事項

- スクレイピングは対象サイトの利用規約・robots.txtに配慮し、負荷をかけない間隔（待機時間など）で実行してください。
- 買取・販売価格は変動するため、`merged_card_data.csv` は定期的に再取得する想定です。
- カードラッシュでは「PSA10」ではなく「素体A」相当の販売価格を参照しているため、実際の取引条件とは異なる場合があります。

---

## まとめ

| 項目 | 内容 |
|------|------|
| **何をするアプリか** | ポケカPSA10の「おたちゅう買取価格」と「カードラッシュ販売価格」を比較し、期待利益を一覧表示する |
| **誰向けか** | ポケカの売買・トレードをしている人（転売・リサーチ用途） |
| **入力** | おたちゅう＋カードラッシュから取得した統合CSV（merged_card_data.csv） |
| **出力** | ブラウザ上の一覧・フィルター・利益の可視化（Streamlit） |
