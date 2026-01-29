"""
ポケモンカード買取・販売価格比較アプリ
Streamlitで作成
"""
import streamlit as st
import pandas as pd
import re
from typing import Optional

# ページ設定
st.set_page_config(
    page_title="ポケカ PSA10 買取比較",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="auto"
)

# シンプルで見やすいデザイン（色使い・カード・サイドバー）
st.markdown("""
<style>
    /* === テーマカラー === */
    :root {
        --bg-main: #f8fafc;
        --bg-sidebar: #f1f5f9;
        --bg-card: #ffffff;
        --border: #e2e8f0;
        --accent: #2563eb;
        --accent-light: #dbeafe;
        --text: #1e293b;
        --text-muted: #64748b;
        --profit-up: #059669;
        --profit-down: #dc2626;
    }
    
    /* メインエリア */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 100%;
        background: var(--bg-main);
    }
    
    /* サイドバー全体 */
    [data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] .stMarkdown { color: var(--text); }
    
    /* カード風ボックス（ヘッダー・セクション用） */
    .section-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .section-card h1, .section-card h2, .section-card h3 {
        color: var(--text) !important;
        margin-top: 0 !important;
        border-bottom: 2px solid var(--accent-light);
        padding-bottom: 0.5rem;
    }
    
    /* ヘッダー用カード（タイトル＋キャプション） */
    .header-card {
        background: linear-gradient(135deg, var(--bg-card) 0%, var(--accent-light) 100%);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
    }
    .header-card h1 { color: var(--accent) !important; font-size: 1.75rem !important; }
    .header-card p { color: var(--text-muted); margin-bottom: 0 !important; }
    
    /* サイドバー内のカード */
    .sidebar-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .sidebar-card h2, .sidebar-card h3 {
        font-size: 1rem !important;
        color: var(--text) !important;
        margin-bottom: 0.75rem !important;
    }
    
    /* カード一覧の各カード（商品カード） */
    .card-container {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        background: var(--bg-card);
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .card-name {
        font-weight: bold;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
        color: var(--text);
    }
    .profit-positive {
        color: var(--profit-up);
        font-weight: bold;
        font-size: 1.4em;
    }
    .profit-negative {
        color: var(--profit-down);
        font-weight: bold;
        font-size: 1.4em;
    }
    .compact-title { font-size: 1rem; font-weight: 600; color: var(--text); }
    .compact-stats { font-size: 0.75rem; color: var(--text-muted); }
    
    /* タブ・メトリックの見た目 */
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] {
        background: var(--bg-card);
        border-radius: 8px;
        border: 1px solid var(--border);
        padding: 0.5rem 1rem;
    }
    [data-testid="stMetricValue"] { color: var(--text) !important; font-weight: 600; }
    
    /* ページネーションの「ページ 1/36...」表示 */
    .pagination-page-info {
        text-align: center;
        padding: 0.5rem 0;
        font-size: 0.9rem;
        color: var(--text-muted);
    }
    
    /* 区切り線を控えめに */
    hr { border-color: var(--border) !important; }
    
    /* データフレームをカード風に */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    
    /* ========== スマホ：全体コンパクト ========== */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 0.4rem !important;
            padding-bottom: 0.8rem !important;
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        /* ヘッダーカードをコンパクトに */
        .header-card {
            padding: 0.5rem 0.75rem !important;
            margin-bottom: 0.5rem !important;
            border-radius: 8px !important;
        }
        .header-card h1 { font-size: 1rem !important; line-height: 1.2 !important; }
        .header-card p { font-size: 0.7rem !important; }
        /* セクションカードをコンパクトに */
        .section-card {
            padding: 0.5rem 0.75rem !important;
            margin-bottom: 0.5rem !important;
            border-radius: 8px !important;
        }
        .section-card h3 { font-size: 0.9rem !important; padding-bottom: 0.25rem !important; border-bottom-width: 1px !important; }
        .section-card p { font-size: 0.75rem !important; }
        /* タブをコンパクトに */
        .stTabs [data-baseweb="tab"] {
            padding: 0.35rem 0.6rem !important;
            font-size: 0.8rem !important;
        }
        .stTabs [data-baseweb="tab-list"] { margin-bottom: 0.3rem !important; }
        /* 商品カードをコンパクトに */
        .card-container {
            padding: 0.5rem 0.6rem !important;
            margin-bottom: 0.5rem !important;
            border-radius: 8px !important;
        }
        .card-name { font-size: 0.95rem !important; margin-bottom: 0.25rem !important; }
        .profit-positive, .profit-negative { font-size: 1.1em !important; }
        /* 区切り線の余白削減 */
        hr { margin: 0.4rem 0 !important; }
        /* ページネーション周りを詰める */
        div[data-testid="column"] { padding: 0.25rem !important; }
        /* テキスト入力・チェックボックスを詰める */
        div[data-testid="stTextInput"], div[data-testid="stCheckbox"] { margin-bottom: 0.2rem !important; }
        [data-testid="stVerticalBlock"] > div { padding: 0.15rem 0 !important; }
        /* カード内のテキスト・画像を詰める */
        .main [data-testid="stVerticalBlock"] p, .main [data-testid="stVerticalBlock"] span { font-size: 0.85rem !important; line-height: 1.35 !important; }
        .main [data-testid="column"] { padding: 0.2rem !important; }
        /* ページネーション：ページ情報とボタンの間をあける（触れないように） */
        .pagination-page-info {
            padding-top: 0.6rem !important;
            padding-bottom: 0.6rem !important;
            margin-top: 0.35rem !important;
            margin-bottom: 0.35rem !important;
            font-size: 0.85rem !important;
        }
        /* ページネーション行どうしの間隔 */
        .pagination-in-page [data-testid="stHorizontalBlock"] {
            margin-top: 0.4rem !important;
            margin-bottom: 0.4rem !important;
        }
        .pagination-in-page [data-testid="stVerticalBlock"] > div { padding: 0.35rem 0 !important; }
        /* スマホでもページネーション・カラムを横並びに（縦に積まない） */
        .main [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 0.35rem !important;
        }
        .main [data-testid="stHorizontalBlock"] > div {
            flex: 1 1 0% !important;
            min-width: 0 !important;
            max-width: none !important;
        }
        button { padding: 0.35rem 0.5rem !important; font-size: 0.8rem !important; }
        /* number_input をコンパクトに */
        [data-testid="stNumberInput"] input { padding: 0.3rem !important; font-size: 0.85rem !important; }
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """
    CSVファイルを読み込む
    """
    try:
        df = pd.read_csv('merged_card_data.csv', encoding='utf-8-sig')
        return df
    except FileNotFoundError:
        st.error("merged_card_data.csv が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        st.stop()


def calculate_profit(row):
    """
    予想最大利益を計算
    在庫なし（取得失敗）の場合は0円を返す
    マイナスの場合もそのまま返す
    """
    # 在庫状況を確認
    stock_status = str(row.get('ラッシュ在庫状況', ''))
    if '取得失敗' in stock_status or stock_status == '' or pd.isna(stock_status) or '在庫なし' in stock_status:
        # 在庫なしの場合は0円
        # ただし、販売価格が取得できている場合は計算する
        sell_price = row.get('ラッシュ販売価格', 0)
        if pd.notna(sell_price) and sell_price != '' and sell_price != 0:
            try:
                buy_price = row.get('買取金額', 0)
                buy_price = float(buy_price) if pd.notna(buy_price) and buy_price != '' else 0
                sell_price = float(sell_price)
                if buy_price > 0 and sell_price > 0:
                    return buy_price - sell_price  # マイナスも含めて返す
            except:
                pass
        return 0  # 在庫なしで販売価格も取得できていない場合は0円
    
    # CSVに期待利益がある場合はそれを使用
    if pd.notna(row.get('期待利益')) and row.get('期待利益') != '':
        try:
            profit = float(row['期待利益'])
            return profit  # マイナスも含めて返す
        except:
            pass
    
    # 計算する
    buy_price = row.get('買取金額', 0)
    sell_price = row.get('ラッシュ販売価格', 0)
    
    try:
        buy_price = float(buy_price) if pd.notna(buy_price) and buy_price != '' else 0
        sell_price = float(sell_price) if pd.notna(sell_price) and sell_price != '' else 0
        
        # 販売価格が取得できていない場合は0円
        if sell_price == 0:
            return 0
        
        profit = buy_price - sell_price
        return profit  # マイナスも含めて返す
    except:
        return 0


def format_profit(profit):
    """
    利益をフォーマット（色付き）
    """
    if profit > 0:
        return f'<span class="profit-positive">+{profit:,.0f}円</span>'
    elif profit < 0:
        return f'<span class="profit-negative">{profit:,.0f}円</span>'
    else:
        return f'<span>{profit:,.0f}円</span>'


def filter_data(df, search_keyword, profit_only, in_stock_only):
    """
    データをフィルター
    """
    filtered_df = df.copy()
    
    # 検索キーワードでフィルター
    if search_keyword:
        mask = (
            filtered_df['カード名'].astype(str).str.contains(search_keyword, case=False, na=False) |
            filtered_df['card_number'].astype(str).str.contains(search_keyword, case=False, na=False) |
            filtered_df['No'].astype(str).str.contains(search_keyword, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    # 在庫ありのみ表示
    if in_stock_only:
        # 在庫状況を正規化して確認
        filtered_df['在庫状況（チェック用）'] = filtered_df['ラッシュ在庫状況'].apply(normalize_stock_status)
        filtered_df = filtered_df[filtered_df['在庫状況（チェック用）'].str.contains('在庫あり', na=False)]
        filtered_df = filtered_df.drop(columns=['在庫状況（チェック用）'])
    
    # 利益が出るものだけ表示
    if profit_only:
        filtered_df['利益'] = filtered_df.apply(calculate_profit, axis=1)
        filtered_df = filtered_df[filtered_df['利益'] > 0]
    
    return filtered_df


def normalize_stock_status(stock_status):
    """
    在庫状況を正規化（取得失敗→在庫なし）
    """
    if pd.isna(stock_status) or stock_status == '' or '取得失敗' in str(stock_status):
        return '在庫なし'
    return str(stock_status)


def display_card_view(df, key_prefix="card_view"):
    """
    カード型リスト表示（スマホ向け）
    ページネーション対応
    """
    if df.empty:
        st.info("表示するデータがありません。")
        return
    
    # 在庫状況を正規化
    df['在庫状況（正規化）'] = df['ラッシュ在庫状況'].apply(normalize_stock_status)
    
    # 利益を計算してソート
    df['予想最大利益'] = df.apply(calculate_profit, axis=1)
    df = df.sort_values('予想最大利益', ascending=False)
    
    # 1ページあたりの表示件数を初期化（key_prefixごとに管理）
    items_per_page_key = f'{key_prefix}_items_per_page'
    current_page_key = f'{key_prefix}_current_page'
    
    if items_per_page_key not in st.session_state:
        st.session_state[items_per_page_key] = 10
    
    # ページネーションの設定
    total_items = len(df)
    items_per_page = st.session_state[items_per_page_key]
    total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1  # 切り上げ
    
    # 現在のページ番号を初期化
    if current_page_key not in st.session_state:
        st.session_state[current_page_key] = 1
    
    # ページ番号が範囲外の場合は調整
    if st.session_state[current_page_key] < 1:
        st.session_state[current_page_key] = 1
    elif st.session_state[current_page_key] > total_pages and total_pages > 0:
        st.session_state[current_page_key] = total_pages
    
    # 現在のページのデータを取得
    start_idx = (st.session_state[current_page_key] - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_page_df = df.iloc[start_idx:end_idx]
    
    # ページネーションコントロール（上側：統一版）
    if total_pages > 1:
        st.markdown('<div class="pagination-in-page">', unsafe_allow_html=True)
        # ページ番号直接入力（1行目：コンパクト、中央配置）
        col_input1, col_input2, col_input3 = st.columns([2, 1, 2])
        
        with col_input1:
            st.empty()
        
        with col_input2:
            col_label, col_field = st.columns([2, 1], vertical_alignment="center")
            with col_label:
                st.markdown('<div style="text-align: right; font-size: 0.9rem; line-height: 2.5; white-space: nowrap;">ページ番号を指定:</div>', unsafe_allow_html=True)
            with col_field:
                page_input = st.number_input(
                    "",
                    min_value=1,
                    max_value=total_pages,
                    value=st.session_state[current_page_key],
                    key=f"{key_prefix}_page_input_top",
                    label_visibility="collapsed"
                )
                if page_input != st.session_state[current_page_key]:
                    st.session_state[current_page_key] = int(page_input)
                    st.rerun()
        
        with col_input3:
            st.empty()
        
        # 1行にまとめたページネーション（2行目）
        col1, col2, col3, col4, col5 = st.columns([1, 1, 3, 1, 1])
        
        with col1:
            prev_10_disabled = (st.session_state[current_page_key] <= 10)
            if st.button("◀◀ 10前", disabled=prev_10_disabled, use_container_width=True, key=f"{key_prefix}_prev10_top"):
                st.session_state[current_page_key] = max(1, st.session_state[current_page_key] - 10)
                st.rerun()
        
        with col2:
            if st.button("◀ 前へ", disabled=(st.session_state[current_page_key] <= 1), use_container_width=True, key=f"{key_prefix}_prev_top"):
                st.session_state[current_page_key] -= 1
                st.rerun()
        
        with col3:
            st.markdown(f'<div class="pagination-page-info">ページ {st.session_state[current_page_key]} / {total_pages} ({total_items}件中 {start_idx+1}-{min(end_idx, total_items)}件を表示)</div>', unsafe_allow_html=True)
        
        with col4:
            if st.button("次へ ▶", disabled=(st.session_state[current_page_key] >= total_pages), use_container_width=True, key=f"{key_prefix}_next_top"):
                st.session_state[current_page_key] += 1
                st.rerun()
        
        with col5:
            next_10_disabled = (st.session_state[current_page_key] >= total_pages - 9)
            if st.button("10後 ▶▶", disabled=next_10_disabled, use_container_width=True, key=f"{key_prefix}_next10_top"):
                st.session_state[current_page_key] = min(total_pages, st.session_state[current_page_key] + 10)
                st.rerun()
        
        st.divider()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 現在のページのデータを表示
    for idx, row in current_page_df.iterrows():
        with st.container():
            # カード情報を取得
            card_name = row.get('カード名', '不明')
            card_number = row.get('card_number', '')
            buy_price = row.get('買取金額', 0)
            sell_price = row.get('ラッシュ販売価格', 0)
            stock = row.get('在庫状況（正規化）', '在庫なし')
            image_url = row.get('画像URL', '')
            profit = row['予想最大利益']
            
            # 買取価格がない場合はスキップ
            if pd.isna(buy_price) or buy_price == '':
                continue
            
            # カードコンテナ
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # 画像表示
                if pd.notna(image_url) and image_url != '' and image_url != '取得失敗':
                    try:
                        st.image(image_url, use_container_width=True)
                    except:
                        st.write("📷 画像読み込みエラー")
                else:
                    st.write("📷 画像なし")
            
            with col2:
                # カード名と型番
                st.markdown(f'<div class="card-name">{card_name}</div>', unsafe_allow_html=True)
                if card_number:
                    st.caption(f"型番: {card_number}")
                
                # 予想最大利益（大きく表示）
                st.markdown(f"**予想最大利益**: {format_profit(profit)}", unsafe_allow_html=True)
                
                # 価格情報
                st.write(f"**買取価格（おたちゅう PSA10）**: {buy_price:,.0f}円")
                
                sell_price_str = f"{sell_price:,.0f}円" if pd.notna(sell_price) and sell_price != '' else "取得失敗"
                st.write(f"**販売価格（ラッシュ 素体A）**: {sell_price_str}")
                
                # 在庫数
                st.write(f"**在庫**: {stock}")
            
            st.divider()
    
    # ページネーションコントロール（下側：上部と同じ構成）
    if total_pages > 1:
        st.markdown('<div class="pagination-in-page">', unsafe_allow_html=True)
        # ページ番号直接入力（1行目：コンパクト、中央配置）
        col_input1_bottom, col_input2_bottom, col_input3_bottom = st.columns([2, 1, 2])
        
        with col_input1_bottom:
            st.empty()
        
        with col_input2_bottom:
            col_label_bottom, col_field_bottom = st.columns([2, 1], vertical_alignment="center")
            with col_label_bottom:
                st.markdown('<div style="text-align: right; font-size: 0.9rem; line-height: 2.5; white-space: nowrap;">ページ番号を指定:</div>', unsafe_allow_html=True)
            with col_field_bottom:
                page_input_bottom = st.number_input(
                    "",
                    min_value=1,
                    max_value=total_pages,
                    value=st.session_state[current_page_key],
                    key=f"{key_prefix}_page_input_bottom",
                    label_visibility="collapsed"
                )
                if page_input_bottom != st.session_state[current_page_key]:
                    st.session_state[current_page_key] = int(page_input_bottom)
                    st.rerun()
        
        with col_input3_bottom:
            st.empty()
        
        # 1行にまとめたページネーション（2行目）
        col1_bottom, col2_bottom, col3_bottom, col4_bottom, col5_bottom = st.columns([1, 1, 3, 1, 1])
        
        with col1_bottom:
            prev_10_disabled_bottom = (st.session_state[current_page_key] <= 10)
            if st.button("◀◀ 10前", disabled=prev_10_disabled_bottom, use_container_width=True, key=f"{key_prefix}_prev10_bottom"):
                st.session_state[current_page_key] = max(1, st.session_state[current_page_key] - 10)
                st.rerun()
        
        with col2_bottom:
            if st.button("◀ 前へ", disabled=(st.session_state[current_page_key] <= 1), use_container_width=True, key=f"{key_prefix}_prev_bottom"):
                st.session_state[current_page_key] -= 1
                st.rerun()
        
        with col3_bottom:
            st.markdown(f'<div class="pagination-page-info">ページ {st.session_state[current_page_key]} / {total_pages} ({total_items}件中 {start_idx+1}-{min(end_idx, total_items)}件を表示)</div>', unsafe_allow_html=True)
        
        with col4_bottom:
            if st.button("次へ ▶", disabled=(st.session_state[current_page_key] >= total_pages), use_container_width=True, key=f"{key_prefix}_next_bottom"):
                st.session_state[current_page_key] += 1
                st.rerun()
        
        with col5_bottom:
            next_10_disabled_bottom = (st.session_state[current_page_key] >= total_pages - 9)
            if st.button("10後 ▶▶", disabled=next_10_disabled_bottom, use_container_width=True, key=f"{key_prefix}_next10_bottom"):
                st.session_state[current_page_key] = min(total_pages, st.session_state[current_page_key] + 10)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    


def display_table_view(df):
    """
    テーブル表示（PC向け）
    """
    if df.empty:
        st.info("表示するデータがありません。")
        return
    
    # 在庫状況を正規化
    df['在庫状況（正規化）'] = df['ラッシュ在庫状況'].apply(normalize_stock_status)
    
    # 予想最大利益を計算
    df['予想最大利益'] = df.apply(calculate_profit, axis=1)
    df = df.sort_values('予想最大利益', ascending=False)
    
    # 表示用のデータフレームを作成
    display_df = df.copy()
    
    # カラム設定
    column_config = {
        'カード名': st.column_config.TextColumn(
            'カード名',
            width='medium'
        ),
        'card_number': st.column_config.TextColumn(
            '型番',
            width='small'
        ),
        '買取金額': st.column_config.NumberColumn(
            '買取価格（おたちゅう）',
            format='%d円',
            width='small'
        ),
        'ラッシュ販売価格': st.column_config.NumberColumn(
            '販売価格（ラッシュ）',
            format='%d円',
            width='small'
        ),
        'ラッシュ在庫状況': st.column_config.TextColumn(
            '在庫状況',
            width='small'
        ),
        '画像URL': st.column_config.ImageColumn(
            '画像',
            width='small'
        )
    }
    
    # 画像URLを処理（空の場合はNoneに）
    display_df['画像URL'] = display_df['画像URL'].apply(
        lambda x: x if pd.notna(x) and x != '' and x != '取得失敗' else None
    )
    
    # 利益カラムを文字列に変換（色付き表示用）
    def format_profit_for_table(val):
        if pd.isna(val):
            return "0円"
        try:
            val_float = float(val)
            if val_float > 0:
                return f"🟢 +{val_float:,.0f}円"
            elif val_float < 0:
                return f"🔴 {val_float:,.0f}円"
            else:
                return f"{val_float:,.0f}円"
        except:
            return "0円"
    
    display_df['予想最大利益（表示用）'] = display_df['予想最大利益'].apply(format_profit_for_table)
    
    # テーブル表示
    st.dataframe(
        display_df[['カード名', 'card_number', '買取金額', 'ラッシュ販売価格', '予想最大利益（表示用）', '在庫状況（正規化）', '画像URL']],
        column_config={
            **column_config,
            '予想最大利益（表示用）': st.column_config.TextColumn(
                '予想最大利益',
                width='small',
                help='🟢: プラス、🔴: マイナス'
            ),
            '在庫状況（正規化）': st.column_config.TextColumn(
                '在庫状況',
                width='small'
            )
        },
        use_container_width=True,
        hide_index=True
    )
    
    # 利益の詳細を表示（カード風）
    if len(display_df) > 0:
        mean_p = display_df['予想最大利益'].mean()
        max_p = display_df['予想最大利益'].max()
        min_p = display_df['予想最大利益'].min()
        st.markdown(
            f'<div class="section-card" style="padding: 0.75rem 1rem; font-size: 0.9rem;">'
            f'💡 予想最大利益の平均: {mean_p:,.0f}円 | 最大: {max_p:,.0f}円 | 最小: {min_p:,.0f}円'
            f'</div>',
            unsafe_allow_html=True,
        )


def main():
    """
    メイン処理
    """
    # データ読み込み
    df = load_data()
    
    # ヘッダー（カードで囲む）
    st.markdown(
        '<div class="header-card">'
        '<h1>🃏 ポケモンカード PSA10 買取比較</h1>'
        '<p>おたちゅう（買取）vs カードラッシュ（販売）の価格比較</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    
    # フィルターの状態を初期化（session_stateを使用）
    if 'search_keyword' not in st.session_state:
        st.session_state.search_keyword = ''
    if 'in_stock_only' not in st.session_state:
        st.session_state.in_stock_only = False
    if 'profit_only' not in st.session_state:
        st.session_state.profit_only = False
    
    # デスクトップ版：サイドバーにフィルターを配置（見出しをカード風に）
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-card"><strong>🔍 フィルター</strong></div>',
            unsafe_allow_html=True,
        )
        search_keyword = st.text_input(
            "キーワード検索",
            placeholder="カード名・型番で検索",
            help="カード名、型番、Noで検索できます",
            value=st.session_state.search_keyword,
            key="sidebar_search"
        )
        st.session_state.search_keyword = search_keyword
        in_stock_only = st.checkbox(
            "在庫ありのみ表示",
            value=st.session_state.in_stock_only,
            help="在庫がある商品のみ表示します",
            key="sidebar_in_stock"
        )
        st.session_state.in_stock_only = in_stock_only
        profit_only = st.checkbox(
            "利益が出る商品のみ表示",
            value=st.session_state.profit_only,
            help="粗利がプラスの商品のみ表示します",
            key="sidebar_profit"
        )
        st.session_state.profit_only = profit_only
        
        st.markdown(
            '<div class="sidebar-card"><strong>📊 統計</strong></div>',
            unsafe_allow_html=True,
        )
        total_count = len(df)
        filtered_df_temp = filter_data(df, search_keyword, profit_only, in_stock_only)
        filtered_count = len(filtered_df_temp)
        st.metric("全データ数", total_count)
        st.metric("表示中", filtered_count)
        if filtered_count > 0:
            filtered_df_temp['予想最大利益'] = filtered_df_temp.apply(calculate_profit, axis=1)
            profitable_count = len(filtered_df_temp[filtered_df_temp['予想最大利益'] > 0])
            st.metric("利益が出る商品", profitable_count)
            if not in_stock_only:
                filtered_df_temp['在庫状況（チェック用）'] = filtered_df_temp['ラッシュ在庫状況'].apply(normalize_stock_status)
                in_stock_count = len(filtered_df_temp[filtered_df_temp['在庫状況（チェック用）'].str.contains('在庫あり', na=False)])
                filtered_df_temp = filtered_df_temp.drop(columns=['在庫状況（チェック用）'])
                st.metric("在庫ありの商品", in_stock_count)
    
    # データフィルター
    filtered_df = filter_data(df, st.session_state.search_keyword, st.session_state.profit_only, st.session_state.in_stock_only)
    
    # フィルターが変更された場合はページをリセット（各表示用に）
    if 'last_filter_state' not in st.session_state:
        st.session_state.last_filter_state = (st.session_state.search_keyword, st.session_state.profit_only, st.session_state.in_stock_only)
    
    current_filter_state = (st.session_state.search_keyword, st.session_state.profit_only, st.session_state.in_stock_only)
    if current_filter_state != st.session_state.last_filter_state:
        if 'card_view_current_page' in st.session_state:
            st.session_state.card_view_current_page = 1
        st.session_state.last_filter_state = current_filter_state
    
    # スマホ版：メイン画面にフィルターを配置（デスクトップでは非表示）
    st.markdown("""
    <style>
    /* スマホ版のフィルター（デスクトップでは非表示） */
    .mobile-filter {
        display: none;
    }
    
    @media (max-width: 768px) {
        .mobile-filter { display: block; }
        .mobile-filter .section-card { padding: 0.4rem 0.6rem !important; margin-bottom: 0.35rem !important; }
        .mobile-filter .section-card strong { font-size: 0.85rem !important; }
        h1 { font-size: 0.95rem !important; margin-bottom: 0 !important; }
        .stCaption { font-size: 0.65rem !important; margin-bottom: 0.15rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # スマホ版のフィルター（メイン画面に表示、デスクトップでは非表示）
    st.markdown('<div class="mobile-filter">', unsafe_allow_html=True)
    st.markdown('<div class="section-card"><strong>🔍 フィルター</strong></div>', unsafe_allow_html=True)
    
    # スマホ版のフィルター（メイン画面、サイドバーと同期）
    # 検索ボックス
    mobile_search_keyword = st.text_input(
        "キーワード検索",
        placeholder="カード名・型番で検索",
        help="カード名、型番、Noで検索できます",
        value=st.session_state.search_keyword,
        key="mobile_search"
    )
    st.session_state.search_keyword = mobile_search_keyword
    
    # チェックボックス
    mobile_filter_col1, mobile_filter_col2 = st.columns(2)
    
    with mobile_filter_col1:
        mobile_in_stock_only = st.checkbox(
            "在庫ありのみ表示",
            value=st.session_state.in_stock_only,
            help="在庫がある商品のみ表示します",
            key="mobile_in_stock"
        )
        st.session_state.in_stock_only = mobile_in_stock_only
    
    with mobile_filter_col2:
        mobile_profit_only = st.checkbox(
            "利益が出る商品のみ表示",
            value=st.session_state.profit_only,
            help="粗利がプラスの商品のみ表示します",
            key="mobile_profit"
        )
        st.session_state.profit_only = mobile_profit_only
    
    # フィルターが変更された場合はデータを再フィルター
    filtered_df = filter_data(df, st.session_state.search_keyword, st.session_state.profit_only, st.session_state.in_stock_only)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # タブ：データ分析 / 現場リサーチ（現場リサーチは1回だけ表示）
    tab1, tab2 = st.tabs(["📊 データ分析（PC向け）", "📱 現場リサーチ（スマホ向け）"])
    
    with tab1:
        st.markdown(
            '<div class="section-card">'
            '<h3>📊 データ分析モード</h3>'
            '<p style="color: var(--text-muted); margin: 0; font-size: 0.9rem;">PCで見やすいテーブル形式で表示します。各カラムでソート可能です。</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        display_table_view(filtered_df)
    
    with tab2:
        st.markdown(
            '<div class="section-card">'
            '<h3>📱 現場リサーチモード</h3>'
            '<p style="color: var(--text-muted); margin: 0; font-size: 0.9rem;">スマホで見やすいカード型リスト表示です。</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        display_card_view(filtered_df, key_prefix="card_view")


if __name__ == "__main__":
    main()
