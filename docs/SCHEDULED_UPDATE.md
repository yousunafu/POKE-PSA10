# 1日2回（10時・18時）のデータ定期更新

`merged_card_data.csv` を 1日2回（10:00 と 18:00 JST）更新して運用する方法です。

---

## 更新の流れ（何を実行するか）

1. **買取価格を更新したい場合**  
   `scrape_otachu.py` → `otachu_psa10.csv` を更新  
   （おたちゅうの買取表が変わったとき）

2. **販売価格・在庫を更新する**  
   `scrape_rush.py` → `otachu_psa10.csv` を読んでカードラッシュを検索し、`merged_card_data.csv` を更新

**定期実行で毎回やること**  
- 買取表も一緒に更新する: `scrape_otachu.py` → `scrape_rush.py`  
- 販売・在庫だけ更新する: `scrape_rush.py` のみ  

通常は **`scrape_otachu.py` → `scrape_rush.py`** の順で 1日2回回す想定で問題ありません。

---

## 定期実行のやり方（3パターン）

### 1. ローカル（Mac）で cron / launchd

**条件**: 10時・18時に Mac が起動していること。

- **cron**  
  `crontab -e` で次を追加（例: 10:00 と 18:00 JST）:
  ```cron
  0 10 * * * cd /Users/あなた/Desktop/Poke\ trade\ PSA && /usr/bin/python3 scrape_otachu.py && /usr/bin/python3 scrape_rush.py
  0 18 * * * cd /Users/あなた/Desktop/Poke\ trade\ PSA && /usr/bin/python3 scrape_otachu.py && /usr/bin/python3 scrape_rush.py
  ```
- **launchd**（macOS 推奨）  
  plist で「10:00 と 18:00 に上記コマンドを実行」するエージェントを登録。

**本番への反映**  
- 更新後の `merged_card_data.csv` を Git で commit & push し、本番（Railway 等）をデプロイする  
- または「CSV アップロード用 API」を用意し、スクリプトの最後でその API に CSV を POST する

**メリット**: 設定が分かりやすい  
**デメリット**: PC がついている時間だけ動く

---

### 2. GitHub Actions

**条件**: リポジトリを GitHub に置いていること。本番が「Git の main をデプロイする」形（Vercel + Railway など）であること。

- 10:00 と 18:00（JST）に workflow が起動
- リポジトリ内で `scrape_otachu.py` → `scrape_rush.py` を実行
- 生成した `merged_card_data.csv` を commit & push
- main に push されると本番が自動デプロイされ、API が新しい CSV を読む

**メリット**: PC を付けっぱなしにしなくてよい。  
**デメリット**: **1回40分かかる場合**、40分×2回/日×30日 ≒ **2,400分/月** になり、**private リポジトリの無料枠（2,000分/月）を超える**。public なら枠が広い場合あり。長時間実行は AWS 等の方が向く。

実ファイル: `.github/workflows/update-data.yml` を参照。手動実行は Actions タブの「Update card data (10:00 & 18:00 JST)」→「Run workflow」で行えます。

---

### 3. 本番サーバー上で cron（Railway / Render 等）

- Railway の Cron、Render の Cron Job などで「10:00 と 18:00 にスクリプト実行」を設定
- そのスクリプトで `scrape_otachu.py` → `scrape_rush.py` を実行（Playwright 入り Docker などが必要）
- 出力した `merged_card_data.csv` を S3 や永続ボリュームに保存し、API はそこを読む

**メリット**: すべてクラウドで完結  
**デメリット**: Playwright のセットアップと CSV の永続化が必要で、構成が重め

---

## 1回40分かかる場合（scrape_rush が重いとき）

- **40分×2回/日 ≒ 月2,400分** になるため、**GitHub Actions の無料枠（private 2,000分/月）を超えやすい**です。
- この場合は **AWS（または同様のクラウド）で定期実行**する方が向いています。

### おすすめ: AWS で定期実行

| 方式 | 内容 | コスト感 |
|------|------|----------|
| **Lightsail 2GB（推奨）** | 2GB プラン（約 $10/月）のインスタンスを 1 台立て、cron で 10:00・18:00 JST に `scrape_otachu.py` → `scrape_rush.py` を実行。CSV は Git push や S3 で本番に渡す。 | **固定で約 $10/月**。Fargate より設定が簡単で、料金も読みやすい。 |
| **ECS Fargate のスケジュールタスク** | EventBridge で 10:00・18:00 JST にタスクを起動。Docker 内でスクレイプ実行し、CSV を S3 に保存 or リポジトリに push。 | 実行時間分の課金。1回40分×2回/日で月数百円〜千円程度の想定。 |
| **小さい EC2 + cron** | 常時起動の t4g.micro などに cron を仕込み、10時・18時に同じスクリプトを実行。CSV は Git push や S3 アップロードで本番に反映。 | インスタンス稼働分の課金。月数百円〜。 |

**Lambda は向かない**: 1回の実行が最大15分のため、40分かかる処理はそのままでは動かせません（複数に分割する設計なら可能だが複雑）。

#### Lightsail 2GB パターン（おすすめ）

- **2GB RAM** あれば Playwright + Chromium のスクレイプで十分。
- **月額固定**なので「今月は何分使ったか」を気にしなくてよい。
- **Fargate よりシンプル**: Docker / ECR / ECS / EventBridge を触らず、普通の Linux サーバーに SSH して cron を入れるだけ。
- **手順のイメージ**: (1) Lightsail で 2GB インスタンス（Ubuntu など）を作成、(2) Python + Playwright + Chromium をインストール、(3) リポジトリを clone するかスクリプトを置く、(4) cron で `0 1 * * *` と `0 9 * * *`（UTC＝10:00・18:00 JST）に `scrape_otachu.py` → `scrape_rush.py` を実行、(5) 生成した `merged_card_data.csv` を Git に push するか S3 にアップロードして本番から参照する。

**手順のイメージ（Fargate）**  
1. スクレイプ用の Docker イメージ（Python + Playwright Chromium）を ECR に push。  
2. ECS で Fargate タスク定義を作成（そのイメージを実行し、`scrape_otachu.py` → `scrape_rush.py` の順で実行）。  
3. EventBridge で 10:00 と 18:00 JST にそのタスクを起動するルールを定義。  
4. タスク内で `merged_card_data.csv` を S3 にアップロードするか、Git に commit & push する処理を入れて、本番（Vercel + Railway 等）がそのデータを読むようにする。

#### Lightsail vs Fargate メリット・デメリット

| 観点 | Lightsail 2GB | ECS Fargate |
|------|----------------|-------------|
| **メリット** | ・月額固定（約 $10）で予算が読みやすい<br>・設定が簡単（Linux + cron だけ、Docker 不要）<br>・SSH で入ってログや手動実行がしやすい<br>・使うサービスが少ない（Lightsail だけ） | ・使った時間だけ課金（1日2回×40分なら月数百円〜千円程度で済む場合あり）<br>・サーバーを常時起動しておかなくてよい<br>・スケールや複数タスクに拡張しやすい |
| **デメリット** | ・**24時間起動**なので「動いていない時間」も $10 かかる<br>・OS のパッチや再起動は自分で管理<br>・インスタンスが落ちたら cron も止まる（監視が必要） | ・**設定が重い**（Dockerfile / ECR / ECS タスク定義 / EventBridge）<br>・デバッグはログやタスクの再実行で見る形になり、SSH で入って直す、ができない<br>・実行時間が長いと Fargate の課金が $10 を超えることもある |

**まとめ**: まずは **Lightsail** で「動かす・運用する」を簡単にしたい向き。**Fargate** は「サーバーを立てたくない」「使った分だけ払いたい」ときに選ぶ、というイメージでよいです。

必要なら「AWS Fargate でスクレイプ定期実行」の具体的な手順（Dockerfile 例・タスク定義・EventBridge の cron）を別ドキュメントにまとめます。

---

## おすすめの選び方

- **scrape が数分で終わる場合**  
  → **GitHub Actions** で 10:00 と 18:00 に実行し、`merged_card_data.csv` を commit & push する形で十分です。
- **scrape_rush が 1回40分など長時間かかる場合**  
  → **AWS Lightsail 2GB + cron**（月額固定で設定が簡単）か、**Fargate のスケジュールタスク / 小さい EC2 + cron** で定期実行し、CSV を S3 や Git で本番に渡す形がおすすめです。
