# 下部ページネーション押下時の「トップへスクロール」問題のまとめ

## アプリ概要
- **技術**: Streamlit（Python）
- **内容**: ポケモンカード買取・販売価格比較。データ分析モード（テーブル＋カード一覧）と現場リサーチモード（カード一覧）の2タブ。
- **ページネーション**: 画面上部と下部の両方に「10前」「前へ」「ページ 1/36…」「次へ」「10後」がある。

## 実現したいこと
**下部のページネーション（10前・前へ・次へ・10後）を押したときに、ページ先頭へ自動でスクロールする。**

- 下部ボタンでページを変えると、今は画面下部に留まったままになる。
- 上部にスクロールして、新しいページの先頭から見られるようにしたい。

## 現在の実装

### 1. フラグの設定（`display_card_view` 内）
下部用のボタン／ページ番号入力が押されたときに、`st.session_state["scroll_to_top"] = True` を立ててから `st.rerun()` している。

- 対象: `key_prefix` が `_bottom` のボタン（prev10_bottom, prev_bottom, next_bottom, next10_bottom）と、下部のページ番号入力（page_input_bottom 変更時）。
- 場所: `app.py` の `display_card_view` 内、該当ボタン／入力の `if` 内で `st.session_state["scroll_to_top"] = True` → `st.rerun()`。

### 2. スクロール用スクリプト（`main()` の先頭）
`main()` の `load_data()` の直後に以下を実行している。

- `if st.session_state.get("scroll_to_top"):` のときだけ、
- `st.markdown(..., unsafe_allow_html=True)` で `<script>` を出力。
- スクリプト内容:
  - `document.querySelector('.main')`, `section[class*="main"]`, `[data-testid="stAppViewContainer"]`, `.block-container` および `documentElement`, `body` の `scrollTop = 0`。
  - `window.scrollTo(0, 0)`。
  - `setTimeout(goTop, 150 / 600 / 1200 / 1800)` で複数回実行。
- 毎回違う HTML にするため `<script id="scroll-top-{t}">` に `t = str(time.time()).replace(".", "")` を埋め込んでいる。
- 出力後に `del st.session_state["scroll_to_top"]` でフラグ削除。

## 現在の症状
- **リロード後の1回目**: 下部の「次へ」等を押すと、期待どおりページ先頭へスクロールする。
- **2回目以降**: 同じく下部の「次へ」等を押しても、**スクロールが発生しない**（ページ番号は変わるが、表示位置は下部のまま）。

## 試したこと（いずれも2回目以降は不発）
1. **`window.scrollTo(0,0)` のみ** → 効かず（Streamlit のスクロールが `.main` 等のコンテナ内で起きている想定）。
2. **`.main` / `section.main` 等の `scrollTop = 0` を追加** → 1回目は効くようになったが、2回目以降は効かない。
3. **スクリプトを `main()` の最後に移動** → 1回目から効かなくなったので、先頭に戻した。
4. **`streamlit.components.v1.html` で iframe から親をスクロール** → コンソールに OpaqueResponseBlocking や iframe sandbox 警告が出たためやめた。
5. **`<script id="scroll-top-{timestamp}">` で毎回ユニークな HTML に** → 1回目だけ効く状態（現状）。
6. **セッションで `scroll_to_top_run_id` をインクリメントして `<div data-scroll-run="{run_id}">` で囲む** → 1回目から効かなくなったので、タイムスタンプ版に戻した。

## 推測している原因
- Streamlit が **2回目以降の rerun で、同じ「ブロック」としてマークダウンを再利用**しており、`<script>` が再実行されていない可能性。
- または **クライアント側で同じ script 要素が再利用**され、ブラウザが再実行していない可能性。
- タイムスタンプで `id` を変えても、Streamlit のブロックキーや DOM の扱いで「同一ブロック」とみなされ、スクリプトが 1 回しか実行されない、という状況を疑っている。

## ファイル・該当箇所
- **ファイル**: `app.py`
- **フラグ設定**: `display_card_view` 内の下部ページネーション（`_bottom` のボタン／ページ番号入力）。該当行付近: 523–526, 535–539, 541–544, 551–554, 558–561。
- **スクロール出力**: `main()` 内、`df = load_data()` の直後。該当行付近: 675–702。

## 依頼したいこと
「下部のページネーションを押すたびに、毎回確実にページ先頭へスクロールする」ようにしたい。  
Streamlit の制約（`st.markdown` の `<script>` が 2 回目以降実行されない可能性）を考慮したうえで、**別の実装方法やワークアラウンド**の提案が欲しい。  
`components.html` の iframe はコンソールエラーが出るため、できれば避けたい。
